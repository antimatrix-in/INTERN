from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    User, Student, Internship, Project, ProjectAssignment,
    WeeklyMilestone, WeeklySubmission, Meeting, Notification, AuditLog
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.before_request
@login_required
def require_admin():
    if not current_user.is_admin_or_staff:
        flash('Access restricted to ANTI MATRIX Administrators and Staff.', 'danger')
        abort(403)


@admin_bp.route('/dashboard')
@login_required
def dashboard():
    total_students = Student.query.count()
    active_internships = Internship.query.filter_by(status='ACTIVE').count()
    pending_submissions = WeeklySubmission.query.filter_by(status='SUBMITTED').count()
    scheduled_meetings = Meeting.query.filter_by(status='SCHEDULED').count()
    
    recent_students = Student.query.order_by(Student.id.desc()).limit(8).all()
    pending_sub_list = WeeklySubmission.query.filter_by(status='SUBMITTED').order_by(WeeklySubmission.id.desc()).limit(6).all()
    
    return render_template(
        'admin/dashboard.html',
        total_students=total_students,
        active_internships=active_internships,
        pending_submissions=pending_submissions,
        scheduled_meetings=scheduled_meetings,
        recent_students=recent_students,
        pending_sub_list=pending_sub_list
    )


@admin_bp.route('/students')
@login_required
def students_list():
    query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    
    students_query = Student.query.join(User)
    
    if query:
        search = f"%{query}%"
        students_query = students_query.filter(
            db.or_(
                User.full_name.ilike(search),
                User.email.ilike(search),
                Student.student_uid.ilike(search),
                Student.roll_number.ilike(search)
            )
        )
        
    students = students_query.order_by(Student.id.desc()).all()
    
    return render_template(
        'admin/students.html',
        students=students,
        search_query=query,
        status_filter=status_filter
    )


@admin_bp.route('/students/<int:student_id>')
@login_required
def student_detail(student_id):
    student = Student.query.get_or_404(student_id)
    internship = student.active_internship
    assignment = internship.active_assignment if internship else None
    milestones = assignment.weekly_milestones.all() if assignment else []
    meetings = Meeting.query.filter_by(student_id=student.id).order_by(Meeting.id.desc()).all()
    submissions = WeeklySubmission.query.filter_by(student_id=student.id).order_by(WeeklySubmission.id.desc()).all()
    staff_members = User.query.filter(User.role.in_(['super_admin', 'admin', 'mentor', 'evaluator'])).all()
    
    return render_template(
        'admin/student_detail.html',
        student=student,
        internship=internship,
        assignment=assignment,
        milestones=milestones,
        meetings=meetings,
        submissions=submissions,
        staff_members=staff_members
    )


@admin_bp.route('/milestone/<int:milestone_id>/review', methods=['POST'])
@login_required
def review_milestone(milestone_id):
    milestone = WeeklyMilestone.query.get_or_404(milestone_id)
    action = request.form.get('action', 'approve') # approve, revision, unlock
    feedback = request.form.get('feedback', '').strip()
    student = milestone.assignment.internship.student
    
    if action == 'approve':
        milestone.status = 'COMPLETED'
        milestone.completed_at = db.func.now()
        milestone.approved_by = current_user.id
        milestone.approved_at = db.func.now()
        milestone.admin_notes = feedback or 'Milestone reviewed and approved.'
        
        # Mark latest submission approved
        latest_sub = milestone.latest_submission
        if latest_sub:
            latest_sub.status = 'APPROVED'
            latest_sub.review_feedback = feedback
            latest_sub.reviewed_by = current_user.id
            latest_sub.reviewed_at = db.func.now()
            
        # Unlock next week milestone
        next_milestone = WeeklyMilestone.query.filter_by(
            assignment_id=milestone.assignment_id,
            week_number=milestone.week_number + 1
        ).first()
        
        if next_milestone:
            next_milestone.status = 'AVAILABLE'
            next_milestone.unlocked_at = db.func.now()
            
            notif = Notification(
                user_id=student.user.id,
                title=f"Week {milestone.week_number} Approved — Week {next_milestone.week_number} Unlocked!",
                message=f"Your submission for Week {milestone.week_number} was approved by {current_user.full_name}. Week {next_milestone.week_number} is now available.",
                type='SUCCESS',
                link=url_for('student.week_detail', milestone_id=next_milestone.id)
            )
            db.session.add(notif)
            flash(f"Week {milestone.week_number} marked as COMPLETED. Week {next_milestone.week_number} has been UNLOCKED successfully for {student.user.full_name}.", 'success')
        else:
            # Final milestone completed
            milestone.assignment.status = 'COMPLETED'
            milestone.assignment.internship.status = 'COMPLETED'
            notif = Notification(
                user_id=student.user.id,
                title="All Internship Milestones Completed!",
                message=f"Congratulations! You have completed all weekly project milestones for your {milestone.assignment.project.title}.",
                type='SUCCESS',
                link=url_for('student.project_detail')
            )
            db.session.add(notif)
            flash(f"Final Week {milestone.week_number} approved! Student has successfully completed all project milestones.", 'success')

    elif action == 'revision':
        milestone.status = 'REVISION_REQUIRED'
        milestone.admin_notes = feedback
        
        latest_sub = milestone.latest_submission
        if latest_sub:
            latest_sub.status = 'REVISION_REQUIRED'
            latest_sub.review_feedback = feedback
            latest_sub.reviewed_by = current_user.id
            latest_sub.reviewed_at = db.func.now()
            
        notif = Notification(
            user_id=student.user.id,
            title=f"Revision Requested: Week {milestone.week_number}",
            message=f"Your mentor reviewed Week {milestone.week_number} and requested revisions: {feedback}",
            type='WARNING',
            link=url_for('student.week_detail', milestone_id=milestone.id)
        )
        db.session.add(notif)
        flash(f"Revision request submitted for Week {milestone.week_number}.", 'warning')

    elif action == 'unlock':
        milestone.status = 'AVAILABLE'
        milestone.unlocked_at = db.func.now()
        
        notif = Notification(
            user_id=student.user.id,
            title=f"Week {milestone.week_number} Manually Unlocked",
            message=f"Administrator unlocked Week {milestone.week_number} ({milestone.title}) for your project.",
            type='INFO',
            link=url_for('student.week_detail', milestone_id=milestone.id)
        )
        db.session.add(notif)
        flash(f"Week {milestone.week_number} manually unlocked.", 'info')

    # Update overall internship progress percent
    milestone.assignment.internship.update_progress()
    db.session.commit()
    
    return redirect(url_for('admin.student_detail', student_id=student.id))


@admin_bp.route('/meeting/schedule', methods=['POST'])
@login_required
def schedule_meeting():
    student_id = request.form.get('student_id', type=int)
    student = Student.query.get_or_404(student_id)
    internship = student.active_internship
    
    title = request.form.get('title', '').strip()
    meeting_date = request.form.get('meeting_date', '').strip()
    meeting_time = request.form.get('meeting_time', '').strip()
    meeting_link = request.form.get('meeting_link', '').strip()
    host_id = request.form.get('host_id', type=int) or current_user.id
    milestone_id = request.form.get('milestone_id', type=int) or None
    meeting_notes = request.form.get('meeting_notes', '').strip()
    
    meeting = Meeting(
        milestone_id=milestone_id,
        internship_id=internship.id if internship else 1,
        student_id=student.id,
        host_id=host_id,
        title=title,
        meeting_date=meeting_date,
        meeting_time=meeting_time,
        meeting_link=meeting_link,
        status='SCHEDULED',
        meeting_notes=meeting_notes
    )
    db.session.add(meeting)
    
    notif = Notification(
        user_id=student.user.id,
        title=f"Evaluation Meeting Scheduled: {title}",
        message=f"Your mentor scheduled an evaluation session on {meeting_date} at {meeting_time}. Meeting link: {meeting_link}",
        type='INFO',
        link=url_for('student.meetings')
    )
    db.session.add(notif)
    db.session.commit()
    
    flash(f"Meeting '{title}' scheduled successfully for {student.user.full_name}.", 'success')
    return redirect(url_for('admin.student_detail', student_id=student.id))


@admin_bp.route('/evaluations')
@login_required
def evaluations():
    pending_submissions = WeeklySubmission.query.order_by(WeeklySubmission.id.desc()).all()
    return render_template('admin/evaluations.html', submissions=pending_submissions)


@admin_bp.route('/meetings')
@login_required
def meetings():
    all_meetings = Meeting.query.order_by(Meeting.id.desc()).all()
    return render_template('admin/meetings.html', meetings=all_meetings)
