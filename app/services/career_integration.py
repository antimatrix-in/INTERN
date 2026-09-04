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
    College, Department, AuditLog
)

logger = logging.getLogger(__name__)


class CareerIntegrationService:
    """Service layer for querying and converting Anti Matrix Career Portal applications."""

    @staticmethod
    def get_application_by_id(application_no):
        """
        Query an application by its unique Application ID (e.g. AM-APP-2026-1024).
        Normalizes and searches case-insensitively.
        """
        if not application_no:
            return None
        app_id_clean = application_no.strip().upper()
        return Application.query.filter(
            db.func.upper(Application.application_no) == app_id_clean
        ).first()

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
            if user and user.student_profile:
                return user.student_profile, user

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
        Returns authenticated User object or None.
        """
        if not employee_id or not password:
            return None

        user = CareerIntegrationService.get_employee_by_employee_id(employee_id)
        if not user:
            return None

        if not user.is_active:
            return None

        if user.check_password(password):
            return user

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
        app_status_upper = (app.status or '').upper()
        if app_status_upper in ['REJECTED', 'CANCELLED']:
            return False, 'Application has been rejected or cancelled.', 400

        # 2. Check Payment Status
        # Check if there is a successful Payment record or application status indicates PAID / APPROVED / SUCCESS
        has_successful_payment = False
        if app.payments.filter(Payment.status.in_(['SUCCESS', 'SUCCESSFUL', 'PAID', 'COMPLETED'])).first():
            has_successful_payment = True
        elif app_status_upper in ['APPROVED', 'PAID', 'SUCCESS', 'VERIFIED']:
            has_successful_payment = True

        if not has_successful_payment:
            return False, 'Payment has not been completed for this application.', 400

        # 3. Check if already converted to employee
        if app.is_converted_to_employee:
            return False, 'Employee already exists.', 200

        return True, None, 200

    @staticmethod
    def create_or_link_employee_from_application(app, duration_plan=None, admin_user=None, raw_ip=None):
        """
        Create and link an active employee from a validated Career Portal application.
        Preserves the source-of-truth Employee ID from the Career Portal whenever present.
        """
        # Determine duration plan
        if not duration_plan:
            # Check applied role or application plan
            if app.plan:
                plan = app.plan
            else:
                # Default to 1 Month or 3 Month based on applied_role or default
                role_str = (app.applied_role or '').lower()
                plan_code = '3_MONTH_PROFESSIONAL' if ('3 month' in role_str or 'professional' in role_str) else '1_MONTH_PROJECT'
                plan = InternshipPlan.query.filter_by(plan_code=plan_code).first()
                if not plan:
                    plan = InternshipPlan.query.first()
        else:
            plan = InternshipPlan.query.filter_by(plan_code=duration_plan).first()
            if not plan:
                plan = InternshipPlan.query.first()

        # College and Department resolution
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

        # Preserve Career Portal Employee ID (Source of Truth)
        # If Career Portal has already assigned an Employee ID (e.g., AM4827 or converted_employee_id), USE THAT!
        source_employee_id = None
        if app.converted_employee_id and app.converted_employee_id.strip():
            source_employee_id = app.converted_employee_id.strip()
        
        # Check if user already exists with candidate email or employee id
        existing_user = None
        if source_employee_id:
            existing_user = User.query.filter_by(employee_id=source_employee_id).first()
        if not existing_user and app.candidate_email:
            existing_user = User.query.filter_by(email=app.candidate_email.strip().lower()).first()

        # Generate a temporary password if new user is created
        from app.admin.routes import generate_temp_password, generate_next_employee_id
        temp_password = generate_temp_password()

        if not existing_user:
            # If no Employee ID was set by Career Portal, assign the sequential ID
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

        # Create or update Student record
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
            # Sync college / department
            if college: student.college_id = college.id
            if department: student.department_id = department.id

        # Create Internship record
        start_dt = date.today()
        if plan and plan.duration_months == 3:
            end_dt = start_dt + relativedelta(months=3)
        else:
            end_dt = start_dt + relativedelta(months=1)

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
                current_stage='Week 1 Requirement & Architecture',
                mentor_id=mentor.id if mentor else None
            )
            db.session.add(internship)
            db.session.flush()

        # Update application conversion status
        app.student_id = student.id
        app.is_converted_to_employee = True
        app.converted_employee_id = assigned_emp_id
        if plan:
            app.plan_id = plan.id

        # Audit log
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
                    'plan': plan.title if plan else 'Standard'
                }),
                ip_address=raw_ip
            )
            db.session.add(audit)

        db.session.commit()
        return student, user, assigned_emp_id, temp_password
