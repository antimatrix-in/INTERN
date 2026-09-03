from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Student, Internship, Application, ProjectAssignment, Document, Notification, IssuedDocument

student_bp = Blueprint('student', __name__)

@student_bp.before_request
@login_required
def check_student_role():
    if current_user.role != 'student' and not current_user.is_admin_or_staff:
        flash('Access restricted to student accounts.', 'danger')
        return redirect(url_for('main.index'))

@student_bp.route('/dashboard')
@login_required
def dashboard():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Please complete your student profile setup.', 'warning')
        return redirect(url_for('main.index'))

    # Active or latest internship
    internship = Internship.query.filter_by(student_id=student.id).order_by(Internship.id.desc()).first()

    # Active applications
    applications = Application.query.filter_by(student_id=student.id).order_by(Application.id.desc()).all()

    # Assigned project if any
    project_assignment = None
    if internship:
        project_assignment = ProjectAssignment.query.filter_by(internship_id=internship.id).first()

    # Documents summary
    documents = Document.query.filter_by(student_id=student.id).all()

    # Notifications
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).limit(5).all()

    # Issued documents
    issued_docs = []
    if internship:
        issued_docs = IssuedDocument.query.filter_by(internship_id=internship.id).all()

    return render_template(
        'student/dashboard.html',
        student=student,
        internship=internship,
        applications=applications,
        project_assignment=project_assignment,
        documents=documents,
        notifications=notifications,
        issued_docs=issued_docs
    )

@student_bp.route('/profile')
@login_required
def profile():
    student = Student.query.filter_by(user_id=current_user.id).first()
    return render_template('student/profile.html', student=student)
