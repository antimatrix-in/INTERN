import os
import re
import time
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import (
    User, Student, Application, Internship, InternshipPlan, ProjectAssignment, WeeklyMilestone,
    WeeklyTask, WeeklySubmission, Meeting, Notification
)

student_bp = Blueprint('student', __name__)

GITHUB_URL_PATTERN = re.compile(r'^https?:\/\/(www\.)?github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(\/.*)?$', re.IGNORECASE)


def allowed_video_file(filename):
    """Check if uploaded file has a permitted video extension."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    allowed = current_app.config.get('ALLOWED_VIDEO_EXTENSIONS', {'mp4', 'mov', 'webm'})
    return ext in allowed


def is_valid_github_url(url):
    """Validate that the provided string is a valid GitHub repository URL."""
    if not url:
        return False
    return bool(GITHUB_URL_PATTERN.match(url.strip()))


def get_current_student():
    """Retrieve and validate student profile for current authenticated user."""
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('No active employee/student profile linked to your account. Please contact Anti Matrix support.', 'danger')
        abort(403)
    return student


@student_bp.before_request
@login_required
def check_student_role():
    if current_user.role != 'student' and not current_user.is_admin_or_staff:
        flash('Access restricted to enrolled internship employees.', 'danger')
        return redirect(url_for('auth.login'))


# ─── Dashboard ────────────────────────────────────────────────────────────────

@student_bp.route('/dashboard')
@login_required
def dashboard():
    student = get_current_student()
    internship = student.active_internship

    # Ensure student has an active internship record
    if not internship:
        from app.services.career_integration import CareerIntegrationService
        app_record = student.applications.order_by(Application.id.desc()).first()
        duration_months = CareerIntegrationService.get_application_duration_months(app_record) if app_record else 1
        plan_code = '3_MONTH_PROFESSIONAL' if duration_months == 3 else '1_MONTH_PROJECT'
        plan = InternshipPlan.query.filter_by(plan_code=plan_code).first() or InternshipPlan.query.first()
        start_dt = datetime.utcnow().strftime('%d %b %Y')
        from dateutil.relativedelta import relativedelta
        from datetime import date
        end_dt = (date.today() + relativedelta(months=duration_months)).strftime('%d %b %Y')
        mentor = User.query.filter_by(role='mentor').first() or User.query.filter_by(role='super_admin').first()
        internship = Internship(
            internship_no=student.student_uid or current_user.employee_id or f"AM-INT-{student.id}",
            student_id=student.id,
            application_id=app_record.id if app_record else None,
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

    # Ensure student has an active project assignment (auto-allocate if none exists)
    assignment = internship.active_assignment if internship else None
    if internship and not assignment:
        from app.services.problem_allocation_service import ProblemAllocationService
        duration_months = internship.plan.duration_months if (internship.plan and internship.plan.duration_months) else 1
        app_record = student.applications.first()
        domain = app_record.applied_role if app_record and app_record.applied_role else None
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
                assignment = internship.active_assignment
        except Exception:
            db.session.rollback()

    milestones = []
    current_milestone = None
    project = None

    if assignment:
        project = assignment.project
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
        project=project,
        milestones=milestones,
        current_milestone=current_milestone,
        upcoming_meeting=upcoming_meeting,
        notifications=notifications,
        progress_percent=progress_percent
    )


# ─── Project Detail ───────────────────────────────────────────────────────────

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


# ─── Weekly Progress ──────────────────────────────────────────────────────────

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


# ─── Week Detail & Tasks ──────────────────────────────────────────────────────

@student_bp.route('/week/<int:milestone_id>')
@login_required
def week_detail(milestone_id):
    student = get_current_student()
    milestone = WeeklyMilestone.query.get_or_404(milestone_id)

    # Strict IDOR ownership check
    if milestone.assignment.internship.student_id != student.id:
        abort(403)

    tasks = milestone.tasks.all()
    submissions = milestone.submissions.order_by(WeeklySubmission.id.desc()).all()
    latest_submission = milestone.latest_submission
    meeting = Meeting.query.filter_by(milestone_id=milestone.id).first()

    return render_template(
        'student/week_detail.html',
        student=student,
        internship=milestone.assignment.internship,
        assignment=milestone.assignment,
        project=milestone.assignment.project,
        milestone=milestone,
        tasks=tasks,
        submissions=submissions,
        latest_submission=latest_submission,
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

    if request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'task_id': task.id,
            'is_completed': task.is_completed,
            'all_completed': milestone.all_tasks_completed,
            'completed_count': milestone.completed_tasks_count,
            'total_count': milestone.total_tasks_count
        })
    return redirect(url_for('student.week_detail', milestone_id=milestone.id))


# ─── Milestone Submission ────────────────────────────────────────────────────

@student_bp.route('/submissions/submit/<int:milestone_id>', methods=['POST'])
@login_required
def submit_milestone(milestone_id):
    student = get_current_student()
    milestone = WeeklyMilestone.query.get_or_404(milestone_id)

    # Strict IDOR check
    if milestone.assignment.internship.student_id != student.id:
        abort(403)

    # Verify milestone is active / unlocked
    if milestone.status in ['LOCKED', 'COMPLETED', 'APPROVED']:
        flash('This week is not in a submittable state.', 'danger')
        return redirect(url_for('student.week_detail', milestone_id=milestone.id))

    # Duplicate submission protection
    if milestone.status in ['UNDER_REVIEW', 'SUBMITTED']:
        flash('A submission is already currently under review for this week. Please await evaluation.', 'warning')
        return redirect(url_for('student.week_detail', milestone_id=milestone.id))

    # 1. Require all tasks to be completed
    if not milestone.all_tasks_completed:
        flash('Complete all required tasks before submitting your work.', 'danger')
        return redirect(url_for('student.week_detail', milestone_id=milestone.id))

    # 2. Validate GitHub URL
    github_url = request.form.get('github_url', '').strip() or request.form.get('repo_url', '').strip()
    if not github_url or not is_valid_github_url(github_url):
        flash('Please provide a valid GitHub repository URL (e.g. https://github.com/username/project).', 'danger')
        return redirect(url_for('student.week_detail', milestone_id=milestone.id))

    # 3. Validate Demo Video Upload
    video_file = request.files.get('demo_video') or request.files.get('video')
    if not video_file or not video_file.filename:
        flash('Please upload your Demo Video (.mp4, .mov, or .webm).', 'danger')
        return redirect(url_for('student.week_detail', milestone_id=milestone.id))

    if not allowed_video_file(video_file.filename):
        flash('Invalid video format. Supported formats: MP4, MOV, WEBM.', 'danger')
        return redirect(url_for('student.week_detail', milestone_id=milestone.id))

    # Secure file save
    orig_filename = secure_filename(video_file.filename)
    timestamp = int(time.time())
    unique_filename = f"demo_m{milestone.id}_s{student.id}_{timestamp}_{orig_filename}"
    upload_folder = current_app.config.get('VIDEO_UPLOAD_FOLDER')
    os.makedirs(upload_folder, exist_ok=True)
    full_save_path = os.path.join(upload_folder, unique_filename)

    try:
        video_file.save(full_save_path)
    except Exception as e:
        flash(f'Failed to save video upload: {str(e)}', 'danger')
        return redirect(url_for('student.week_detail', milestone_id=milestone.id))

    submission_notes = request.form.get('submission_notes', '').strip()

    try:
        # Create submission record (preserving full history)
        sub = WeeklySubmission(
            milestone_id=milestone.id,
            student_id=student.id,
            github_url=github_url,
            repo_url=github_url,
            demo_video_path=unique_filename,
            demo_video_url=unique_filename,
            file_path=unique_filename,
            submission_notes=submission_notes,
            status='UNDER_REVIEW',
            submitted_at=datetime.utcnow()
        )
        db.session.add(sub)

        # Update milestone status
        milestone.status = 'UNDER_REVIEW'
        milestone.assignment.internship.update_progress()

        # Notification for student
        notif = Notification(
            user_id=current_user.id,
            title=f"Week {milestone.week_number} Submitted for Verification",
            message=f"Your deliverables for Week {milestone.week_number} ({milestone.title}) were submitted successfully and are under evaluation.",
            type='SUCCESS',
            link=url_for('student.week_detail', milestone_id=milestone.id)
        )
        db.session.add(notif)
        db.session.commit()

        flash(f'Week {milestone.week_number} submitted for verification successfully! Your submission is now UNDER REVIEW.', 'success')
    except Exception as e:
        db.session.rollback()
        # Clean up uploaded video file if database commit fails
        if os.path.exists(full_save_path):
            os.remove(full_save_path)
        flash(f'An error occurred while processing your submission: {str(e)}', 'danger')

    return redirect(url_for('student.week_detail', milestone_id=milestone.id))


# ─── Protected Video Stream ───────────────────────────────────────────────────

@student_bp.route('/employee/submission/<int:sub_id>/video')
@login_required
def stream_submission_video(sub_id):
    """Securely stream demo video for the owning employee only."""
    student = get_current_student()
    sub = WeeklySubmission.query.get_or_404(sub_id)

    # Strict ownership check (IDOR protection)
    if sub.student_id != student.id:
        abort(403)

    filename = sub.demo_video_path or sub.demo_video_url or sub.file_path
    if not filename:
        abort(404)

    upload_folder = current_app.config.get('VIDEO_UPLOAD_FOLDER')
    full_path = os.path.join(upload_folder, filename)

    if not os.path.exists(full_path):
        abort(404)

    # Determine mimetype
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    mimetype = 'video/mp4'
    if ext == 'webm':
        mimetype = 'video/webm'
    elif ext == 'mov':
        mimetype = 'video/quicktime'

    return send_file(full_path, mimetype=mimetype, conditional=True)


# ─── Other Student Views ──────────────────────────────────────────────────────

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
