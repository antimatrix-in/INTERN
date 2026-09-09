"""ANTI MATRIX Career Portal Database Integration Service

Encapsulates all queries and operations interfacing with the shared Supabase
PostgreSQL database application records originating from the Anti Matrix Careers portal.
"""

import json
import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.models import (
    User, Student, Application, Payment, Internship, InternshipPlan,
    College, Department, AuditLog, Employee, EmployeeOnboardingCredential
)

logger = logging.getLogger(__name__)


class CareerIntegrationService:
    """Service layer for querying and converting Anti Matrix Career Portal applications."""

    @staticmethod
    def get_application_by_id(application_no):
        """
        Query an application by its unique Application ID (e.g. AM-APP-2026-001, AM-APP-000123, APP-1001, or numeric ID).
        Normalizes and searches case-insensitively across application_no, ID, and formatting variations.
        """
        if not application_no:
            return None
        app_id_clean = str(application_no).strip().upper()
        
        # 1. Exact match on application_no (case-insensitive)
        app = Application.query.filter(
            db.func.upper(Application.application_no) == app_id_clean
        ).first()
        if app:
            return app

        # 2. Check if numeric or prefix variations (e.g. AM-APP-000123, APP-1001, AM-APP-2026-001)
        if app_id_clean.startswith('AM-APP-'):
            rem = app_id_clean[len('AM-APP-'):]
            if '-' in rem:
                # E.g. 2026-001 -> also try matching suffix
                parts = rem.split('-')
                if len(parts) == 2 and parts[1].isdigit():
                    num = int(parts[1])
                    app = Application.query.filter(Application.id == num).first()
                    if app:
                        return app
            elif rem.isdigit():
                num = int(rem)
                app = Application.query.filter(Application.id == num).first()
                if app:
                    return app
        elif app_id_clean.startswith('APP-'):
            num_part = app_id_clean[len('APP-'):]
            if num_part.isdigit():
                num = int(num_part)
                app = Application.query.filter(Application.id == num).first()
                if app:
                    return app
        elif app_id_clean.isdigit():
            app = Application.query.get(int(app_id_clean))
            if app:
                return app

        # 3. Partial substring search for code suffix
        app = Application.query.filter(
            Application.application_no.ilike(f"%{app_id_clean}%")
        ).first()
        return app

    @staticmethod
    def get_employee_by_application_id(application_no):
        """
        Retrieve existing Student / User record associated with an application.
        Returns (student, user) tuple or (None, None).
        """
        app = CareerIntegrationService.get_application_by_id(application_no)
        if not app:
            return None, None
        
        # 1. Check direct student foreign key on application
        if app.student_id:
            student = Student.query.get(app.student_id)
            if student:
                return student, student.user

        # 2. Check converted_employee_id on application
        if app.converted_employee_id:
            user = User.query.filter(
                db.func.lower(User.employee_id) == app.converted_employee_id.strip().lower()
            ).first()
            if user:
                return user.student_profile, user
            
            student = Student.query.filter(
                db.func.lower(Student.student_uid) == app.converted_employee_id.strip().lower()
            ).first()
            if student:
                return student, student.user

        # 3. Check candidate email match
        if app.candidate_email:
            user = User.query.filter(
                db.func.lower(User.email) == app.candidate_email.strip().lower()
            ).first()
            if user and user.student_profile:
                return user.student_profile, user

        return None, None


    @staticmethod
    def get_employee_by_employee_id(employee_id):
        """
        Retrieve User and Student records by Employee ID, Student UID, or registered email.
        """
        if not employee_id:
            return None
        emp_clean = employee_id.strip()

        # 1. Match User.employee_id
        user = User.query.filter(
            db.func.lower(User.employee_id) == emp_clean.lower()
        ).first()
        if user:
            return user

        # 2. Match Student.student_uid
        student = Student.query.filter(
            db.func.lower(Student.student_uid) == emp_clean.lower()
        ).first()
        if student and student.user:
            return student.user

        # 3. Match User.email
        user = User.query.filter(
            db.func.lower(User.email) == emp_clean.lower()
        ).first()
        if user:
            return user

        return None

    @staticmethod
    def verify_employee_credentials(employee_id, password):
        """
        Securely verify employee login credentials against stored password hashes.
        Never returns or logs raw hashes.
        Checks User account, EmployeeOnboardingCredential, and Employee records.
        Returns authenticated User object or None.
        """
        if not employee_id or not password:
            return None

        # 1. Check local User
        user = CareerIntegrationService.get_employee_by_employee_id(employee_id)
        if user and user.is_active and user.check_password(password):
            return user

        # 2. Check EmployeeOnboardingCredential in Supabase
        clean_id = str(employee_id).strip()
        cred = EmployeeOnboardingCredential.query.filter(
            db.func.upper(EmployeeOnboardingCredential.employee_id) == clean_id.upper()
        ).first()
        if cred and cred.status == 'ACTIVE' and cred.verify_password(password):
            if user:
                return user
            from app.auth.routes import authenticate_employee_or_user
            auth_user, _, _ = authenticate_employee_or_user(employee_id, password)
            return auth_user

        # 3. Check Employee permanent password in Supabase
        emp = Employee.query.filter(
            db.func.upper(Employee.employee_id) == clean_id.upper()
        ).first()
        if emp and emp.account_status == 'active' and emp.check_password(password):
            if user:
                return user
            from app.auth.routes import authenticate_employee_or_user
            auth_user, _, _ = authenticate_employee_or_user(employee_id, password)
            return auth_user

        return None

    @staticmethod
    def validate_application_for_onboarding(app):
        """
        Validates whether a Career Portal application is eligible for employee onboarding.
        Returns (is_valid: bool, error_message: str or None, error_code: int).
        """
        if not app:
            return False, 'Application ID not found.', 404

        # 1. Check Application Status
        app_status_upper = (getattr(app, 'status', None) or '').upper()
        if app_status_upper in ['REJECTED', 'CANCELLED']:
            return False, 'Application has been rejected or cancelled.', 400

        # 2. Check Payment Status
        # Canonical Anti-Matrix check: payment_status in ('paid', 'success', 'successful')
        has_successful_payment = False
        app_id_val = getattr(app, 'id', None)
        if app_id_val is not None:
            pay_rec = Payment.query.filter(
                (Payment.application_id == app_id_val) &
                (
                    (Payment.payment_status.in_(['paid', 'SUCCESS', 'SUCCESSFUL', 'COMPLETED'])) |
                    (Payment.status.in_(['paid', 'SUCCESS', 'SUCCESSFUL', 'PAID', 'COMPLETED']))
                )
            ).first()
            if pay_rec:
                has_successful_payment = True

        if not has_successful_payment and hasattr(app, 'payments'):
            if app.payments.filter(
                (Payment.payment_status.in_(['paid', 'SUCCESS', 'SUCCESSFUL', 'COMPLETED'])) |
                (Payment.status.in_(['paid', 'SUCCESS', 'SUCCESSFUL', 'PAID', 'COMPLETED']))
            ).first():
                has_successful_payment = True

        if not has_successful_payment and app_status_upper in ['APPROVED', 'PAID', 'SUCCESS', 'VERIFIED']:
            has_successful_payment = True

        if not has_successful_payment:
            return False, 'Payment has not been completed for this application.', 400

        # 3. Check if already converted to employee
        if getattr(app, 'is_converted_to_employee', False):
            return False, 'Employee already exists.', 200

        return True, None, 200

    @staticmethod
    def get_application_duration_months(app, duration_plan=None):
        """Extract authoritative internship duration (1 or 3) from the career application."""
        if duration_plan:
            if '3' in str(duration_plan) or '3_month' in str(duration_plan).lower():
                return 3
            if '1' in str(duration_plan) or '1_month' in str(duration_plan).lower():
                return 1

        if app.plan and app.plan.duration_months in [1, 3]:
            return app.plan.duration_months

        role_str = (app.applied_role or '').lower()
        if '3 month' in role_str or '3month' in role_str or 'professional' in role_str:
            return 3
        return 1

    @staticmethod
    def create_or_link_employee_from_application(app, duration_plan=None, admin_user=None, raw_ip=None):
        """
        Create and link an active employee from a validated Career Portal application,
        automatically allocating an eligible random Problem ID respecting college uniqueness.
        """
        from app.services.problem_allocation_service import ProblemAllocationService

        # 1. Determine authoritative duration (1 Month or 3 Months)
        duration_months = CareerIntegrationService.get_application_duration_months(app, duration_plan)
        plan_code = '3_MONTH_PROFESSIONAL' if duration_months == 3 else '1_MONTH_PROJECT'
        plan = InternshipPlan.query.filter_by(plan_code=plan_code).first()
        if not plan:
            plan = InternshipPlan.query.filter_by(duration_months=duration_months).first() or InternshipPlan.query.first()

        # 2. College and Department resolution
        college = None
        if app.college_name:
            college = College.query.filter(College.name.ilike(f"%{app.college_name.strip()}%")).first()
        if not college:
            college = College.query.filter_by(code='OTHER-COLLEGE').first() or College.query.first()

        department = None
        if app.department_name and college:
            department = Department.query.filter(
                Department.college_id == college.id,
                Department.name.ilike(f"%{app.department_name.strip()}%")
            ).first()
        if not department and college:
            department = Department.query.filter_by(college_id=college.id).first()

        # 3. Check for existing User / Student
        source_employee_id = None
        if app.converted_employee_id and app.converted_employee_id.strip():
            source_employee_id = app.converted_employee_id.strip()

        existing_user = None
        if source_employee_id:
            existing_user = User.query.filter_by(employee_id=source_employee_id).first()
        if not existing_user and app.candidate_email:
            existing_user = User.query.filter_by(email=app.candidate_email.strip().lower()).first()

        from app.admin.routes import generate_temp_password, generate_next_employee_id
        temp_password = generate_temp_password()

        if not existing_user:
            assigned_emp_id = source_employee_id if source_employee_id else generate_next_employee_id()
            user = User(
                email=app.candidate_email.strip().lower() if app.candidate_email else f"{assigned_emp_id.lower()}@antimatrix.tech",
                employee_id=assigned_emp_id,
                role='student',
                full_name=app.candidate_name or 'Anti Matrix Intern',
                phone=app.candidate_phone,
                is_active=True
            )
            user.set_password(temp_password)
            db.session.add(user)
            db.session.flush()
        else:
            user = existing_user
            assigned_emp_id = user.employee_id or source_employee_id or generate_next_employee_id()
            if not user.employee_id:
                user.employee_id = assigned_emp_id

        # 4. Create or update Student profile
        student = user.student_profile
        if not student:
            student = Student(
                user_id=user.id,
                student_uid=assigned_emp_id,
                dob=app.candidate_dob,
                gender=app.candidate_gender,
                college_id=college.id if college else 1,
                department_id=department.id if department else 1,
                roll_number=app.roll_number or assigned_emp_id,
                degree=app.course or 'Engineering',
                current_year=app.year_of_study or '3rd Year',
                graduation_year='2026',
                aadhaar_masked=app.aadhaar_masked,
                is_verified=True
            )
            db.session.add(student)
            db.session.flush()
        else:
            if college: student.college_id = college.id
            if department: student.department_id = department.id

        # 5. Create or retrieve active Internship
        start_dt = date.today()
        end_dt = start_dt + relativedelta(months=duration_months)

        internship = Internship.query.filter_by(student_id=student.id, status='ACTIVE').first()
        if not internship:
            mentor = User.query.filter_by(role='mentor').first() or User.query.filter_by(role='super_admin').first()
            internship = Internship(
                internship_no=assigned_emp_id,
                student_id=student.id,
                application_id=app.id,
                plan_id=plan.id if plan else 1,
                status='ACTIVE',
                start_date=start_dt.strftime('%d %b %Y'),
                end_date=end_dt.strftime('%d %b %Y'),
                progress_percent=0,
                current_stage='Week 1 Understanding & Setup',
                mentor_id=mentor.id if mentor else None
            )
            db.session.add(internship)
            db.session.flush()

        # 6. Automatic Problem Allocation (Same-College Unique, Random Choice from Duration Pool)
        allocated_problem = None
        existing_assignment = internship.active_assignment
        if not existing_assignment:
            domain_name = app.applied_role or None
            allocated_problem, alloc_err = ProblemAllocationService.allocate_random_problem(
                college_id=student.college_id,
                duration_months=duration_months,
                domain=domain_name,
                exclude_student_id=student.id
            )
            if not allocated_problem:
                db.session.rollback()
                raise ValueError(alloc_err or f"No available {duration_months} Month problem for this college.")

            # Assign problem and build weekly milestones
            ProblemAllocationService.assign_problem_to_internship(
                internship=internship,
                project=allocated_problem,
                assigned_by_user=admin_user
            )
        else:
            allocated_problem = existing_assignment.project

        # 7. Update Application status
        app.student_id = student.id
        app.is_converted_to_employee = True
        app.converted_employee_id = assigned_emp_id
        if plan:
            app.plan_id = plan.id

        # 8. Audit Log
        if admin_user:
            audit = AuditLog(
                actor_id=admin_user.id,
                actor_role=admin_user.role,
                action='CREATE_EMPLOYEE_FROM_APPLICATION',
                target_entity='users',
                target_id=str(user.id),
                details_json=json.dumps({
                    'application_no': app.application_no,
                    'employee_id': assigned_emp_id,
                    'student_id': student.id,
                    'plan': plan.title if plan else 'Standard',
                    'duration_months': duration_months,
                    'allocated_problem_id': allocated_problem.project_code if allocated_problem else None,
                    'allocated_problem_title': allocated_problem.title if allocated_problem else None
                }),
                ip_address=raw_ip
            )
            db.session.add(audit)

        db.session.commit()
        return student, user, assigned_emp_id, temp_password, allocated_problem
