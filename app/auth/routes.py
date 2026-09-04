from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, Student, AuditLog
from app.auth.forms import LoginForm, AdminLoginForm

auth_bp = Blueprint('auth', __name__)


def find_user_by_identifier(identifier):
    """Find user by Student UID, Employee ID, or Email."""
    identifier_clean = identifier.strip()
    
    # 1. Match User.employee_id
    user = User.query.filter(db.func.lower(User.employee_id) == identifier_clean.lower()).first()
    if user:
        return user
    
    # 2. Match Student.student_uid
    student = Student.query.filter(db.func.lower(Student.student_uid) == identifier_clean.lower()).first()
    if student and student.user:
        return student.user
    
    # 3. Match User.email
    user = User.query.filter(db.func.lower(User.email) == identifier_clean.lower()).first()
    if user:
        return user
        
    return None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin_or_staff:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = find_user_by_identifier(form.employee_id.data)
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact Anti Matrix support.', 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)

            # Log audit
            try:
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
            except Exception:
                db.session.rollback()

            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            
            if user.is_admin_or_staff:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('student.dashboard'))
        else:
            flash('Invalid Employee ID or password. Please try again.', 'danger')

    return render_template('auth/login.html', form=form)


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
            flash(f'Administrator session active. Welcome, {user.full_name}.', 'success')
            
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid administrator credentials.', 'danger')

    return render_template('auth/admin_login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been securely signed out of the portal.', 'info')
    return redirect(url_for('auth.login'))
