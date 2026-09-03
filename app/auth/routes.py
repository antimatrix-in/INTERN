import random
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, Student, College, Department, InternshipPlan, Application, Notification, AuditLog
from app.auth.forms import LoginForm, RegistrationForm, ForgotPasswordForm

auth_bp = Blueprint('auth', __name__)

def generate_student_uid():
    num = random.randint(10000, 99999)
    return f'AM-STU-2026-{num}'

def generate_application_no():
    num = random.randint(10000, 99999)
    return f'AM-APP-2026-{num}'

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact Anti Matrix support.', 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)

            # Log audit
            audit = AuditLog(
                actor_id=user.id,
                actor_role=user.role,
                action='USER_LOGIN',
                target_entity='users',
                target_id=str(user.id),
                ip_address=request.remote_addr
            )
            db.session.add(audit)
            db.session.commit()

            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            
            if user.role == 'student':
                return redirect(url_for('student.dashboard'))
            return redirect(url_for('main.index'))
        else:
            flash('Invalid email address or password. Please try again.', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))

    form = RegistrationForm()

    # Populate dynamic college choices
    colleges = College.query.filter_by(is_active=True).order_by(College.name.asc()).all()
    form.college_id.choices = [(c.id, f"{c.name} ({c.city}, {c.state})") for c in colleges]

    # Pre-select first college departments or default
    first_college_id = colleges[0].id if colleges else 1
    selected_college_id = form.college_id.data or first_college_id
    departments = Department.query.filter_by(college_id=selected_college_id, is_active=True).all()
    form.department_id.choices = [(d.id, d.name) for d in departments]

    # Check query param for pre-selected plan (e.g. ?plan=1_MONTH_PROJECT)
    preselected_plan = request.args.get('plan')
    if preselected_plan in ['1_MONTH_PROJECT', '3_MONTH_PROFESSIONAL'] and request.method == 'GET':
        form.plan_code.data = preselected_plan

    if form.validate_on_submit():
        try:
            # 1. Create User
            user = User(
                email=form.email.data.lower(),
                role='student',
                full_name=form.full_name.data.strip(),
                phone=form.phone.data.strip()
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush() # Populate user.id

            # 2. Create Student Profile
            student_uid = generate_student_uid()
            student = Student(
                user_id=user.id,
                student_uid=student_uid,
                college_id=form.college_id.data,
                department_id=form.department_id.data,
                roll_number=form.roll_number.data.strip(),
                degree=form.degree.data,
                current_year=form.current_year.data,
                graduation_year=form.graduation_year.data,
                is_verified=False
            )
            db.session.add(student)
            db.session.flush() # Populate student.id

            # 3. Create Application
            plan = InternshipPlan.query.filter_by(plan_code=form.plan_code.data).first()
            if not plan:
                plan = InternshipPlan.query.first()

            application_no = generate_application_no()
            application = Application(
                application_no=application_no,
                student_id=student.id,
                plan_id=plan.id,
                status='PAYMENT_PENDING',
                consent_agreed=True,
                consent_version='v1.0-2026',
                ip_address=request.remote_addr,
                notes=f'Applied via web registration portal for {plan.title}'
            )
            db.session.add(application)

            # 4. Create Welcome Notification
            notification = Notification(
                user_id=user.id,
                title='Welcome to Anti Matrix!',
                message=f'Your student account ({student_uid}) has been provisioned. Application ({application_no}) is created for {plan.title}.',
                type='SUCCESS',
                link='/student/dashboard'
            )
            db.session.add(notification)

            # 5. Audit Log
            audit = AuditLog(
                actor_id=user.id,
                actor_role='student',
                action='STUDENT_REGISTER',
                target_entity='students',
                target_id=str(student.id),
                details_json=f'{{"student_uid": "{student_uid}", "email": "{user.email}", "plan": "{plan.plan_code}"}}',
                ip_address=request.remote_addr
            )
            db.session.add(audit)
            db.session.commit()

            # Auto login the new student
            login_user(user)
            flash('Registration successful! Welcome to the Anti Matrix Internship Portal.', 'success')
            return redirect(url_for('student.dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration. Please try again: {str(e)}', 'danger')

    return render_template('auth/register.html', form=form, colleges=colleges)


@auth_bp.route('/logout')
@login_required
def logout():
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

    logout_user()
    flash('You have been signed out of your Anti Matrix session.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            # Audit log request
            audit = AuditLog(
                actor_id=user.id,
                actor_role=user.role,
                action='FORGOT_PASSWORD_REQUEST',
                target_entity='users',
                target_id=str(user.id),
                ip_address=request.remote_addr
            )
            db.session.add(audit)
            db.session.commit()

        flash('If an account exists with that email address, password reset instructions have been dispatched.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form)


@auth_bp.route('/api/departments/<int:college_id>')
def get_departments(college_id):
    departments = Department.query.filter_by(college_id=college_id, is_active=True).order_by(Department.name.asc()).all()
    return jsonify([{'id': d.id, 'name': d.name} for d in departments])
