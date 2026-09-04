from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    Student, Internship, ProjectAssignment, WeeklyMilestone,
    WeeklyTask, WeeklySubmission, Meeting, Notification
)

student_bp = Blueprint('student', __name__)


def get_current_student():
    """Retrieve and validate student profile for current authenticated user."""
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('No active student profile linked to your account. Please contact Anti Matrix support.', 'danger')
        abort(403)
    return student


@student_bp.before_request
@login_required
def check_student_role():
    if current_user.role != 'student' and not current_user.is_admin_or_staff:
        flash('Access restricted to enrolled internship students.', 'danger')
        return redirect(url_for('auth.login'))


@student_bp.route('/dashboard')
@login_required
def dashboard():
    student = get_current_student()
    internship = student.active_internship
    
    assignment = None
    milestones = []
    current_milestone = None
    
    if internship:
        assignment = internship.active_assignment
        if assignment:
            milestones = assignment.weekly_milestones.all()
            current_milestone = assignment.current_milestone
    
    upcoming_meeting = Meeting.query.filter_by(
        student_id=student.id,
        status='SCHEDULED'
    ).order_by(Meeting.id.asc()).first()
    
    notifications = current_user.notifications.limit(5).all()
    
    progress_percent = assignment.progress_percent if assignment else 0

    return render_template(
        'student/dashboard.html',
        student=student,
        internship=internship,
        assignment=assignment,
        milestones=milestones,
        current_milestone=current_milestone,
        upcoming_meeting=upcoming_meeting,
        notifications=notifications,
        progress_percent=progress_percent
    )


@student_bp.route('/project')
@student_bp.route('/project/<int:assignment_id>')
@login_required
def project_detail(assignment_id=None):
    student = get_current_student()
    internship = student.active_internship
    
    if not internship or not internship.active_assignment:
        flash('No active project has been assigned to your profile yet.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    assignment = internship.active_assignment
    
    # IDOR check if explicit assignment_id is passed in URL
    if assignment_id is not None and assignment_id != assignment.id:
        requested = ProjectAssignment.query.get_or_404(assignment_id)
        if requested.internship.student_id != student.id:
            abort(403)
        assignment = requested

    milestones = assignment.weekly_milestones.all()
    
    return render_template(
        'student/project_detail.html',
        student=student,
        internship=internship,
        assignment=assignment,
        project=assignment.project,
        milestones=milestones
    )


@student_bp.route('/weekly-progress')
@login_required
def weekly_progress():
    student = get_current_student()
    internship = student.active_internship
    
    if not internship or not internship.active_assignment:
        flash('No active project roadmap found.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    assignment = internship.active_assignment
    milestones = assignment.weekly_milestones.all()
    
    return render_template(
        'student/weekly_progress.html',
        student=student,
        internship=internship,
        assignment=assignment,
        milestones=milestones
    )


@student_bp.route('/week/<int:milestone_id>')
@login_required
def week_detail(milestone_id):
    student = get_current_student()
    milestone = WeeklyMilestone.query.get_or_404(milestone_id)
    
    # Strict IDOR ownership check
    if milestone.assignment.internship.student_id != student.id:
        abort(403)
        
    tasks = milestone.tasks.all()
    submissions = milestone.submissions.all()
    meeting = Meeting.query.filter_by(milestone_id=milestone.id).first()
    
    return render_template(
        'student/week_detail.html',
        student=student,
        internship=milestone.assignment.internship,
        assignment=milestone.assignment,
        milestone=milestone,
        tasks=tasks,
        submissions=submissions,
        meeting=meeting
    )


@student_bp.route('/week/<int:milestone_id>/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(milestone_id, task_id):
    student = get_current_student()
    milestone = WeeklyMilestone.query.get_or_404(milestone_id)
    
    if milestone.assignment.internship.student_id != student.id:
        abort(403)
        
    task = WeeklyTask.query.filter_by(id=task_id, milestone_id=milestone.id).first_or_404()
    task.is_completed = not task.is_completed
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'is_completed': task.is_completed})
    return redirect(url_for('student.week_detail', milestone_id=milestone.id))


@student_bp.route('/submissions/submit/<int:milestone_id>', methods=['POST'])
@login_required
def submit_milestone(milestone_id):
    student = get_current_student()
    milestone = WeeklyMilestone.query.get_or_404(milestone_id)
    
    # Strict IDOR check
    if milestone.assignment.internship.student_id != student.id:
        abort(403)
        
    if milestone.status not in ['AVAILABLE', 'IN_PROGRESS', 'REVISION_REQUIRED', 'SUBMITTED', 'UNDER_REVIEW']:
        flash('This milestone is currently locked and cannot accept submissions.', 'danger')
        return redirect(url_for('student.week_detail', milestone_id=milestone.id))
        
    repo_url = request.form.get('repo_url', '').strip()
    live_demo_url = request.form.get('live_demo_url', '').strip()
    demo_video_url = request.form.get('demo_video_url', '').strip()
    submission_notes = request.form.get('submission_notes', '').strip()
    
    if not repo_url and not live_demo_url and not submission_notes:
        flash('Please provide at least a repository URL, live demo link, or summary notes.', 'warning')
        return redirect(url_for('student.week_detail', milestone_id=milestone.id))
        
    sub = WeeklySubmission(
        milestone_id=milestone.id,
        student_id=student.id,
        repo_url=repo_url,
        live_demo_url=live_demo_url,
        demo_video_url=demo_video_url,
        submission_notes=submission_notes,
        status='SUBMITTED'
    )
    db.session.add(sub)
    
    milestone.status = 'SUBMITTED'
    milestone.assignment.internship.update_progress()
    
    # Notification for student
    notif = Notification(
        user_id=current_user.id,
        title=f"Week {milestone.week_number} Work Submitted",
        message=f"Your deliverables for Week {milestone.week_number} ({milestone.title}) were submitted successfully and are queued for mentor review.",
        type='SUCCESS',
        link=url_for('student.week_detail', milestone_id=milestone.id)
    )
    db.session.add(notif)
    db.session.commit()
    
    flash(f'Week {milestone.week_number} submission sent successfully! Your mentor will evaluate your work in the scheduled review.', 'success')
    return redirect(url_for('student.week_detail', milestone_id=milestone.id))


@student_bp.route('/submissions')
@login_required
def submissions():
    student = get_current_student()
    submissions_list = WeeklySubmission.query.filter_by(
        student_id=student.id
    ).order_by(WeeklySubmission.id.desc()).all()
    
    return render_template(
        'student/submissions.html',
        student=student,
        submissions=submissions_list
    )


@student_bp.route('/meetings')
@login_required
def meetings():
    student = get_current_student()
    meetings_list = Meeting.query.filter_by(
        student_id=student.id
    ).order_by(Meeting.id.desc()).all()
    
    return render_template(
        'student/meetings.html',
        student=student,
        meetings=meetings_list
    )


@student_bp.route('/notifications')
@login_required
def notifications():
    student = get_current_student()
    all_notifs = current_user.notifications.all()
    return render_template('student/notifications.html', student=student, notifications=all_notifs)


@student_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    current_user.notifications.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'info')
    return redirect(url_for('student.notifications'))


@student_bp.route('/documents')
@login_required
def documents():
    student = get_current_student()
    internship = student.active_internship
    return render_template('student/documents.html', student=student, internship=internship)


@student_bp.route('/profile')
@login_required
def profile():
    student = get_current_student()
    internship = student.active_internship
    assignment = internship.active_assignment if internship else None
    
    return render_template(
        'student/profile.html',
        student=student,
        internship=internship,
        assignment=assignment
    )
