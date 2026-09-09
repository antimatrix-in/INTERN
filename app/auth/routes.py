from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, csrf
from app.models import (
    User, Student, Application, Internship, InternshipPlan, AuditLog,
    Employee, EmployeeOnboardingCredential, JobApplication, College, Department
)
from app.auth.forms import LoginForm, AdminLoginForm, ChangePasswordForm

auth_bp = Blueprint('auth', __name__)


def find_user_by_identifier(identifier):
    """
    Find user by Employee ID, Student UID, or Registered Email
    across the shared Anti-Matrix database.
    """
    if not identifier:
        return None
    identifier_clean = str(identifier).strip()
    if not identifier_clean:
        return None

    # 1. Match User.employee_id (case-insensitive)
    user = User.query.filter(db.func.lower(User.employee_id) == identifier_clean.lower()).first()
    if user:
        return user

    # 2. Match Student.student_uid (case-insensitive)
    student = Student.query.filter(db.func.lower(Student.student_uid) == identifier_clean.lower()).first()
    if student and student.user:
        return student.user

    # 3. Match User.email (case-insensitive)
    user = User.query.filter(db.func.lower(User.email) == identifier_clean.lower()).first()
    if user:
        return user

    # 4. Match Application converted_employee_id or application_no
    app_record = Application.query.filter(
        (db.func.lower(Application.converted_employee_id) == identifier_clean.lower()) |
        (db.func.lower(Application.application_no) == identifier_clean.lower())
    ).first()
    if app_record and app_record.student and app_record.student.user:
        return app_record.student.user

    return None


def authenticate_employee_or_user(identifier, password):
    """
    Authenticate employee against the shared Anti-Matrix Supabase database.
    1. First, checks the dedicated `employee_onboarding_credentials` table by employee_id.
    2. Checks the authoritative `employees` table by employee_id.
    3. Verifies account_status == 'active'.
    4. If active temporary onboarding credential exists, verifies password against temporary_password_hash.
       If match, authenticates employee and sets must_change_password=True.
    5. If permanent password, verifies password against employee.password_hash.
       If match, authenticates employee (must_change_password=False unless credential still active).
    6. If onboarding credential status is 'RESET', old temporary password will fail verification.
    7. On successful verification, provisions or synchronizes the local User and Student
       session records without modifying production corporate data.
    8. Falls back to find_user_by_identifier() for administrative/staff accounts.
    Returns: (user: User or None, error_message: str or None, status_code: int)
    """
    if not identifier or not str(identifier).strip():
        return None, "Please provide your Employee ID.", 400
    if not password:
        return None, "Please provide your password.", 400

    clean_id = str(identifier).strip()

    # 1. Search dedicated `employee_onboarding_credentials` table in shared Supabase database
    onboarding_cred = EmployeeOnboardingCredential.query.filter(
        db.func.upper(EmployeeOnboardingCredential.employee_id) == clean_id.upper()
    ).first()

    # 2. Search authoritative Anti-Matrix Corporate `employees` table
    employee = Employee.query.filter(
        db.func.upper(Employee.employee_id) == clean_id.upper()
    ).first()

    if not employee and onboarding_cred and hasattr(onboarding_cred, 'employee') and onboarding_cred.employee:
        employee = onboarding_cred.employee

    if employee and not onboarding_cred and hasattr(employee, 'onboarding_credential') and employee.onboarding_credential:
        onboarding_cred = employee.onboarding_credential

    if employee or onboarding_cred:
        # Check employee account status
        if employee and employee.account_status != 'active':
            return None, "Your account has been deactivated. Please contact Anti Matrix support.", 403

        is_authenticated = False
        must_change_pw = False

        # Mode A: Active temporary onboarding credential verification
        # Strictly only allows temporary password while status is 'ACTIVE'
        if onboarding_cred and onboarding_cred.status == 'ACTIVE':
            if onboarding_cred.verify_password(password):
                is_authenticated = True
                must_change_pw = True

        # Mode B: Permanent password verification against employee record
        if not is_authenticated and employee:
            if employee.check_password(password):
                is_authenticated = True
                if onboarding_cred and onboarding_cred.status == 'ACTIVE':
                    must_change_pw = True
                elif employee.temporary_password_active and (not onboarding_cred or onboarding_cred.status != 'RESET'):
                    must_change_pw = True
                else:
                    must_change_pw = False

        if is_authenticated:
            emp_id = (employee.employee_id if employee else onboarding_cred.employee_id).strip()

            # Resolve / link the User session object for Flask-Login
            job_app = None
            if employee and employee.application_id:
                job_app = JobApplication.query.get(employee.application_id)

            user = User.query.filter(
                (db.func.upper(User.employee_id) == emp_id.upper()) |
                (db.func.lower(User.email) == (job_app.email.lower() if job_app and job_app.email else ''))
            ).first()

            candidate_name = job_app.full_name if job_app and job_app.full_name else emp_id
            candidate_email = job_app.email if job_app and job_app.email else f"{emp_id.lower()}@antimatrix.tech"

            active_hash = (
                employee.password_hash if (employee and employee.password_hash)
                else (onboarding_cred.temporary_password_hash if onboarding_cred else None)
            )

            if not user:
                # Provision local User record linked to this Anti-Matrix Employee
                user = User(
                    employee_id=emp_id,
                    email=candidate_email,
                    full_name=candidate_name,
                    role='student',
                    phone=job_app.phone if job_app else None,
                    is_active=True
                )
                user.password_hash = active_hash or ''
                user.must_change_password = must_change_pw
                db.session.add(user)
                db.session.flush()

                # Ensure Student profile exists
                college_name = job_app.college if job_app and job_app.college else None
                college = College.query.filter(College.name.ilike(f"%{college_name.strip()}%")).first() if college_name else None
                if not college:
                    college = College.query.filter_by(code='OTHER-COLLEGE').first() or College.query.first()

                dept_name = job_app.department if job_app and job_app.department else None
                department = Department.query.filter_by(college_id=college.id).first() if college else Department.query.first()

                student = Student(
                    user_id=user.id,
                    student_uid=emp_id,
                    roll_number=emp_id,
                    college_id=college.id if college else 1,
                    department_id=department.id if department else 1,
                    degree=job_app.degree if job_app and job_app.degree else 'B.Tech',
                    current_year='3rd Year',
                    graduation_year=job_app.graduation_year if job_app and job_app.graduation_year else '2026',
                    is_verified=True
                )
                db.session.add(student)
                db.session.flush()

                # Create Application record in Internship Portal matching duration
                dur_str = (job_app.duration or '').lower() if job_app else ''
                duration_months = 3 if ('3' in dur_str or 'professional' in dur_str) else 1
                plan_code = '3_MONTH_PROFESSIONAL' if duration_months == 3 else '1_MONTH_PROJECT'
                plan = InternshipPlan.query.filter_by(plan_code=plan_code).first() or InternshipPlan.query.first()

                app_record = Application(
                    application_no=job_app.application_code if (job_app and job_app.application_code) else f"AM-APP-{emp_id}",
                    student_id=student.id,
                    plan_id=plan.id if plan else None,
                    status='APPROVED',
                    candidate_name=candidate_name,
                    candidate_email=candidate_email,
                    converted_employee_id=emp_id,
                    is_converted_to_employee=True
                )
                db.session.add(app_record)
                db.session.flush()
                db.session.commit()

                _ensure_student_project_allocation(user)
            else:
                # Sync password hash and must_change_password flag
                if active_hash:
                    user.password_hash = active_hash
                user.must_change_password = must_change_pw
                if not user.employee_id:
                    user.employee_id = emp_id
                user.is_active = True
                db.session.commit()
                if not user.student_profile or not user.student_profile.active_internship:
                    _ensure_student_project_allocation(user)

            return user, None, 200

        # If employee/onboarding_cred exists but password was wrong, do not return distinct error
        # Fall through to generic error or fallback accounts

    # 2. Fallback to existing Internship Portal user accounts (e.g. Admin, Mentors, Evaluators)
    user = find_user_by_identifier(clean_id)
    if user:
        if not user.check_password(password):
            return None, "Invalid Employee ID or password.", 401
        if not user.is_active:
            return None, "Your account has been deactivated. Please contact Anti Matrix support.", 403
        return user, None, 200

    return None, "Invalid Employee ID or password.", 401


@auth_bp.before_app_request
def enforce_password_change_guard():
    """
    Redirect users with must_change_password=True to the Change Password screen
    before allowing access to protected dashboard pages.
    """
    if current_user.is_authenticated and getattr(current_user, 'must_change_password', False):
        allowed_endpoints = [
            'auth.login', 'auth.employee_login_api', 'auth.admin_login',
            'auth.change_password', 'auth.api_change_password', 'auth.logout', 'static'
        ]
        if request.endpoint and request.endpoint in allowed_endpoints:
            return
        if (
            request.path.startswith('/static') or
            request.path.startswith('/logout') or
            request.path.startswith('/login') or
            request.path.startswith('/api/auth/employee-login') or
            request.path.startswith('/change-password') or
            request.path.startswith('/api/auth/change-password')
        ):
            return

        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'must_change_password': True,
                'error': 'First login temporary password change required.',
                'redirect_url': url_for('auth.change_password')
            }), 403

        flash('First login detected. Please change your temporary password to access the portal.', 'info')
        return redirect(url_for('auth.change_password'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if getattr(current_user, 'must_change_password', False):
            return redirect(url_for('auth.change_password'))
        if current_user.is_admin_or_staff:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    # Support JSON requests to /login as well
    if request.is_json:
        data = request.get_json() or {}
        emp_id = data.get('employee_id') or data.get('email_or_id') or data.get('email')
        password = data.get('password')
        remember = bool(data.get('remember_me', False))

        user, err_msg, status_code = authenticate_employee_or_user(emp_id, password)
        if not user:
            return jsonify({'success': False, 'error': err_msg}), status_code

        login_user(user, remember=remember)
        _log_login_audit(user, request.remote_addr)

        if getattr(user, 'must_change_password', False):
            return jsonify({
                'success': True,
                'must_change_password': True,
                'message': 'Temporary password change required before accessing the portal.',
                'redirect_url': url_for('auth.change_password'),
                'user': _safe_user_dict(user)
            }), 200

        redirect_url = url_for('admin.dashboard') if user.is_admin_or_staff else url_for('student.dashboard')
        return jsonify({
            'success': True,
            'must_change_password': False,
            'message': f'Welcome back, {user.full_name}!',
            'redirect_url': redirect_url,
            'user': _safe_user_dict(user)
        }), 200

    form = LoginForm()
    if form.validate_on_submit():
        user, err_msg, status_code = authenticate_employee_or_user(form.employee_id.data, form.password.data)
        if not user:
            flash(err_msg, 'danger')
            return render_template('auth/login.html', form=form)

        login_user(user, remember=form.remember_me.data)
        _log_login_audit(user, request.remote_addr)

        if getattr(user, 'must_change_password', False):
            flash('First login detected. Please change your temporary password to proceed.', 'info')
            return redirect(url_for('auth.change_password'))

        flash(f'Welcome back, {user.full_name}!', 'success')
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)

        if user.is_admin_or_staff:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    return render_template('auth/login.html', form=form)


@auth_bp.route('/api/auth/employee-login', methods=['POST'])
@csrf.exempt
def employee_login_api():
    """
    Dedicated secure Employee Login Gateway API for Anti-Matrix shared Supabase credentials.
    Accepts Employee ID + Password, verifies against shared database password hash,
    detects first login, and establishes a secure session.
    """
    data = request.get_json(silent=True) or {}
    employee_id = data.get('employee_id') or data.get('email_or_id') or data.get('email')
    password = data.get('password')
    remember_me = bool(data.get('remember_me', False))

    user, err_msg, status_code = authenticate_employee_or_user(employee_id, password)
    if not user:
        return jsonify({'success': False, 'error': err_msg}), status_code

    login_user(user, remember=remember_me)
    _log_login_audit(user, request.remote_addr)

    if getattr(user, 'must_change_password', False):
        return jsonify({
            'success': True,
            'must_change_password': True,
            'message': 'First login detected. Temporary password change required before accessing portal.',
            'redirect_url': url_for('auth.change_password'),
            'user': _safe_user_dict(user)
        }), 200

    redirect_url = url_for('admin.dashboard') if user.is_admin_or_staff else url_for('student.dashboard')
    return jsonify({
        'success': True,
        'must_change_password': False,
        'message': 'Employee authentication successful.',
        'redirect_url': redirect_url,
        'user': _safe_user_dict(user)
    }), 200


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    First login / temporary password change handler.
    Verifies current temporary password, sets new secure password, clears first-login flag,
    ensures project allocation, and redirects to dashboard.
    """
    # Handle JSON request to /change-password
    if request.is_json:
        return _process_password_change(request.get_json() or {})

    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_pw = form.current_password.data
        new_pw = form.new_password.data
        confirm_pw = form.confirm_password.data

        if not current_user.check_password(current_pw):
            flash('Current temporary password is incorrect. Please verify and try again.', 'danger')
            return render_template('auth/change_password.html', form=form)

        if new_pw == current_pw:
            flash('New password cannot be the same as your current temporary password.', 'danger')
            return render_template('auth/change_password.html', form=form)

        if new_pw != confirm_pw:
            flash('New password and confirmation do not match.', 'danger')
            return render_template('auth/change_password.html', form=form)

        if len(new_pw) < 6:
            flash('New password must be at least 6 characters long.', 'danger')
            return render_template('auth/change_password.html', form=form)

        # Update password securely
        current_user.set_password(new_pw)
        current_user.must_change_password = False
        current_user.password_changed_at = datetime.utcnow()

        # Update authoritative Employee and EmployeeOnboardingCredential in shared Supabase table if linked
        if current_user.employee_id:
            emp = Employee.query.filter(
                db.func.upper(Employee.employee_id) == current_user.employee_id.strip().upper()
            ).first()
            if emp:
                emp.reset_password(new_pw)

            cred = EmployeeOnboardingCredential.query.filter(
                db.func.upper(EmployeeOnboardingCredential.employee_id) == current_user.employee_id.strip().upper()
            ).first()
            if cred:
                cred.mark_reset()

        db.session.commit()

        # Ensure project allocation
        _ensure_student_project_allocation(current_user)

        flash('Your password has been successfully updated! Welcome to your dashboard.', 'success')
        if current_user.is_admin_or_staff:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    return render_template('auth/change_password.html', form=form)


@auth_bp.route('/api/auth/change-password', methods=['POST'])
@csrf.exempt
@login_required
def api_change_password():
    """Dedicated API endpoint for first-login temporary password change."""
    data = request.get_json(silent=True) or {}
    return _process_password_change(data)


def _process_password_change(data):
    current_pw = data.get('current_password')
    new_pw = data.get('new_password')
    confirm_pw = data.get('confirm_password')

    if not current_pw:
        return jsonify({'success': False, 'error': 'Current temporary password is required.'}), 400

    if not new_pw:
        return jsonify({'success': False, 'error': 'New password is required.'}), 400

    if not confirm_pw:
        return jsonify({'success': False, 'error': 'Confirmation password is required.'}), 400

    if not current_user.check_password(current_pw):
        return jsonify({'success': False, 'error': 'Current temporary password is incorrect.'}), 400

    if len(new_pw) < 6:
        return jsonify({'success': False, 'error': 'New password must be at least 6 characters long.'}), 400

    if new_pw != confirm_pw:
        return jsonify({'success': False, 'error': 'New password and confirmation do not match.'}), 400

    if new_pw == current_pw:
        return jsonify({'success': False, 'error': 'New password cannot be the same as your current temporary password.'}), 400

    # Update password securely
    current_user.set_password(new_pw)
    current_user.must_change_password = False
    current_user.password_changed_at = datetime.utcnow()

    # Update authoritative Employee and EmployeeOnboardingCredential in shared Supabase table if linked
    if current_user.employee_id:
        emp = Employee.query.filter(
            db.func.upper(Employee.employee_id) == current_user.employee_id.strip().upper()
        ).first()
        if emp:
            emp.reset_password(new_pw)

        cred = EmployeeOnboardingCredential.query.filter(
            db.func.upper(EmployeeOnboardingCredential.employee_id) == current_user.employee_id.strip().upper()
        ).first()
        if cred:
            cred.mark_reset()

    db.session.commit()

    # Ensure project allocation
    _ensure_student_project_allocation(current_user)

    redirect_url = url_for('admin.dashboard') if current_user.is_admin_or_staff else url_for('student.dashboard')
    return jsonify({
        'success': True,
        'message': 'Password changed successfully. Your account is now fully active.',
        'redirect_url': redirect_url,
        'user': _safe_user_dict(current_user)
    }), 200


def _ensure_student_project_allocation(user):
    """
    Ensure student has an active problem assigned respecting domain, duration pool,
    and same-college uniqueness.
    """
    if not user.student_profile:
        return
    student = user.student_profile
    internship = student.active_internship

    if not internship:
        from app.services.career_integration import CareerIntegrationService
        app = student.applications.order_by(Application.id.desc()).first()
        duration_months = CareerIntegrationService.get_application_duration_months(app) if app else 1
        plan_code = '3_MONTH_PROFESSIONAL' if duration_months == 3 else '1_MONTH_PROJECT'
        plan = InternshipPlan.query.filter_by(plan_code=plan_code).first() or InternshipPlan.query.first()
        start_dt = datetime.utcnow().strftime('%d %b %Y')
        from dateutil.relativedelta import relativedelta
        from datetime import date
        end_dt = (date.today() + relativedelta(months=duration_months)).strftime('%d %b %Y')
        mentor = User.query.filter_by(role='mentor').first() or User.query.filter_by(role='super_admin').first()
        internship = Internship(
            internship_no=student.student_uid or user.employee_id or f"AM-INT-{student.id}",
            student_id=student.id,
            application_id=app.id if app else None,
            plan_id=plan.id if plan else 1,
            status='ACTIVE',
            start_date=start_dt,
            end_date=end_dt,
            progress_percent=0,
            current_stage='Week 1 Understanding & Setup',
            mentor_id=mentor.id if mentor else None
        )
        db.session.add(internship)
        db.session.commit()

    if not internship.active_assignment:
        from app.services.problem_allocation_service import ProblemAllocationService
        duration_months = internship.plan.duration_months if internship.plan else 1
        app = student.applications.first()
        domain = app.applied_role if app and app.applied_role else None
        try:
            allocated_problem, err = ProblemAllocationService.allocate_random_problem(
                college_id=student.college_id,
                duration_months=duration_months,
                domain=domain,
                exclude_student_id=student.id
            )
            if allocated_problem:
                ProblemAllocationService.assign_problem_to_internship(
                    internship=internship,
                    project=allocated_problem
                )
                db.session.commit()
        except Exception:
            db.session.rollback()


@auth_bp.route('/api/auth/me', methods=['GET'])
def get_current_auth_user():
    """Returns safe profile info for the currently authenticated employee session."""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': _safe_user_dict(current_user)
        }), 200
    return jsonify({
        'authenticated': False,
        'error': 'No active authenticated session.'
    }), 401


@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        if current_user.is_admin_or_staff:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    form = AdminLoginForm()
    if form.validate_on_submit():
        user = find_user_by_identifier(form.email_or_id.data)
        if user and user.check_password(form.password.data):
            if not user.is_admin_or_staff:
                flash('Access denied. Administrator credentials required.', 'danger')
                return render_template('auth/admin_login.html', form=form)

            if not user.is_active:
                flash('Your administrator account is inactive.', 'danger')
                return render_template('auth/admin_login.html', form=form)

            login_user(user, remember=form.remember_me.data)
            _log_login_audit(user, request.remote_addr)
            flash(f'Administrator session active. Welcome, {user.full_name}.', 'success')

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid administrator credentials.', 'danger')

    return render_template('auth/admin_login.html', form=form)


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    if current_user.is_authenticated:
        try:
            audit = AuditLog(
                actor_id=current_user.id,
                actor_role=current_user.role,
                action='USER_LOGOUT',
                target_entity='users',
                target_id=str(current_user.id),
                ip_address=request.remote_addr
            )
            db.session.add(audit)
            db.session.commit()
        except Exception:
            db.session.rollback()

        logout_user()

    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({'success': True, 'message': 'You have been securely signed out of the portal.'}), 200

    flash('You have been securely signed out of the portal.', 'info')
    return redirect(url_for('auth.login'))


def _safe_user_dict(user):
    """Serialize safe public user fields without exposing passwords, hashes, or secrets."""
    emp_id = user.employee_id
    if not emp_id and user.student_profile:
        emp_id = user.student_profile.student_uid

    return {
        'id': user.id,
        'employee_id': emp_id,
        'full_name': user.full_name or user.name,
        'email': user.email,
        'role': user.role,
        'is_active': user.is_active,
        'must_change_password': bool(getattr(user, 'must_change_password', False)),
        'has_student_profile': bool(user.student_profile)
    }


def _log_login_audit(user, ip_addr):
    """Safely log successful login event."""
    try:
        audit = AuditLog(
            actor_id=user.id,
            actor_role=user.role,
            action='USER_LOGIN',
            target_entity='users',
            target_id=str(user.id),
            ip_address=ip_addr
        )
        db.session.add(audit)
        db.session.commit()
    except Exception:
        db.session.rollback()
