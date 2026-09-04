import json
import random
import string
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    User, Student, Internship, Project, ProjectAssignment, ProjectWeek, ProjectTask,
    WeeklyMilestone, WeeklyTask, WeeklySubmission, Meeting, Notification,
    AuditLog, Application, College, Department, InternshipPlan
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ─── Helpers ──────────────────────────────────────────────────────────────────

def generate_next_employee_id():
    """Generate the next sequential AM-INT-XXXX employee ID."""
    users = User.query.filter(User.employee_id.like('AM-INT-%')).all()
    max_num = 0
    for u in users:
        try:
            num = int(u.employee_id.split('-')[-1])
            if num > max_num:
                max_num = num
        except (ValueError, IndexError):
            pass
    return f'AM-INT-{max_num + 1:04d}'


def generate_temp_password():
    """Generate a secure temporary password in format AM@XXXXXX."""
    chars = string.ascii_letters + string.digits
    suffix = ''.join(random.choices(chars, k=6))
    return f'AM@{suffix}'


def require_admin_role():
    """Check that the current user is admin/staff. Returns 403 response if not."""
    if not current_user.is_authenticated or not current_user.is_admin_or_staff:
        flash('Access restricted to ANTI MATRIX Administrators and Staff.', 'danger')
        abort(403)


# ─── Auth Guard ───────────────────────────────────────────────────────────────

@admin_bp.before_request
@login_required
def require_admin():
    if not current_user.is_admin_or_staff:
        flash('Access restricted to ANTI MATRIX Administrators and Staff.', 'danger')
        abort(403)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    total_employees = Student.query.count()
    active_interns = Internship.query.filter_by(status='ACTIVE').count()
    total_projects = Project.query.count()
    assigned_projects = ProjectAssignment.query.count()
    pending_submissions = WeeklySubmission.query.filter_by(status='SUBMITTED').count()
    scheduled_meetings = Meeting.query.filter_by(status='SCHEDULED').count()

    recent_students = Student.query.order_by(Student.id.desc()).limit(8).all()
    pending_sub_list = WeeklySubmission.query.filter_by(status='SUBMITTED').order_by(WeeklySubmission.id.desc()).limit(6).all()

    return render_template(
        'admin/dashboard.html',
        total_employees=total_employees,
        active_interns=active_interns,
        total_projects=total_projects,
        assigned_projects=assigned_projects,
        pending_submissions=pending_submissions,
        scheduled_meetings=scheduled_meetings,
        recent_students=recent_students,
        pending_sub_list=pending_sub_list
    )


# ─── Application ID Lookup API ────────────────────────────────────────────────

@admin_bp.route('/api/application/<app_id>')
@login_required
def api_application_lookup(app_id):
    """Server-side AJAX endpoint: look up a career application by its number."""
    app = Application.query.filter_by(application_no=app_id.strip().upper()).first()
    if not app:
        return jsonify({'success': False, 'error': 'Application ID not found. Verify the Application ID and try again.'}), 404

    if app.is_converted_to_employee:
        return jsonify({
            'success': False,
            'error': f'Employee already created for this application. Employee ID: {app.converted_employee_id}'
        }), 409

    return jsonify({
        'success': True,
        'application_no': app.application_no,
        'candidate_name': app.candidate_name or '',
        'candidate_email': app.candidate_email or '',
        'candidate_phone': app.candidate_phone or '',
        'candidate_dob': app.candidate_dob or '',
        'candidate_gender': app.candidate_gender or '',
        'college_name': app.college_name or '',
        'department_name': app.department_name or '',
        'course': app.course or '',
        'year_of_study': app.year_of_study or '',
        'roll_number': app.roll_number or '',
        'applied_role': app.applied_role or '',
        'city': app.city or '',
        'state': app.state or '',
        'aadhaar_masked': app.aadhaar_masked or '',
    })


# ─── Employee Directory ───────────────────────────────────────────────────────

@admin_bp.route('/employees')
@login_required
def employees_list():
    query = request.args.get('q', '').strip()
    students_query = Student.query.join(User)

    if query:
        search = f'%{query}%'
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
        'admin/employees.html',
        students=students,
        search_query=query
    )


@admin_bp.route('/employees/<int:student_id>')
@login_required
def employee_detail(student_id):
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


# ─── Create Employee ──────────────────────────────────────────────────────────

@admin_bp.route('/employees/create', methods=['GET', 'POST'])
@login_required
def create_employee():
    plans = InternshipPlan.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        application_no = request.form.get('application_no', '').strip().upper()
        duration_plan = request.form.get('duration_plan', '1_MONTH_PROJECT').strip()

        # Validate application ID on the server side
        app = Application.query.filter_by(application_no=application_no).first()
        if not app:
            flash(f'Application ID "{application_no}" not found in the system.', 'danger')
            return render_template('admin/create_employee.html', plans=plans)

        if app.is_converted_to_employee:
            flash(f'An employee account already exists for application {application_no}. Employee ID: {app.converted_employee_id}', 'warning')
            return render_template('admin/create_employee.html', plans=plans)

        # Fetch plan
        plan = InternshipPlan.query.filter_by(plan_code=duration_plan).first()
        if not plan:
            flash('Invalid internship plan selected.', 'danger')
            return render_template('admin/create_employee.html', plans=plans)

        # Look up or create college
        college = College.query.filter(College.name.ilike(f'%{app.college_name or "Other"}%')).first()
        if not college:
            college = College.query.filter_by(code='OTHER-COLLEGE').first()
        if not college:
            college = College.query.first()

        dept = Department.query.filter_by(college_id=college.id).first()

        # Generate Employee ID and temporary password
        employee_id = generate_next_employee_id()
        temp_password = generate_temp_password()

        # Start date / end date
        from datetime import date
        today = date.today()
        if plan.duration_months == 1:
            from dateutil.relativedelta import relativedelta
            end = today + relativedelta(months=1)
        else:
            from dateutil.relativedelta import relativedelta
            end = today + relativedelta(months=3)

        start_str = today.strftime('%d %b %Y')
        end_str = end.strftime('%d %b %Y')

        try:
            # Create User
            new_user = User(
                email=app.candidate_email or f'{employee_id.lower()}@antimatrix.com',
                employee_id=employee_id,
                role='student',
                full_name=app.candidate_name or 'Intern',
                phone=app.candidate_phone,
                is_active=True
            )
            new_user.set_password(temp_password)
            db.session.add(new_user)
            db.session.flush()

            # Create Student
            new_student = Student(
                user_id=new_user.id,
                student_uid=employee_id,
                dob=app.candidate_dob or '',
                gender=app.candidate_gender or '',
                college_id=college.id,
                department_id=dept.id if dept else 1,
                roll_number=app.roll_number or 'N/A',
                degree=app.course or 'B.Tech',
                current_year=app.year_of_study or '1st Year',
                graduation_year=str(today.year + 1),
                aadhaar_masked=app.aadhaar_masked or 'XXXX XXXX 0000',
                is_verified=True
            )
            db.session.add(new_student)
            db.session.flush()

            # Create Internship
            internship_no = f'AM-INT-{today.year}-{new_student.id:04d}'
            new_internship = Internship(
                internship_no=internship_no,
                student_id=new_student.id,
                plan_id=plan.id,
                status='ACTIVE',
                start_date=start_str,
                end_date=end_str,
                progress_percent=0,
                current_stage='Week 1 Orientation'
            )
            db.session.add(new_internship)
            db.session.flush()

            # Link application to new employee
            app.is_converted_to_employee = True
            app.converted_employee_id = employee_id
            app.student_id = new_student.id

            # Audit log
            audit = AuditLog(
                actor_id=current_user.id,
                actor_role=current_user.role,
                action='CREATE_EMPLOYEE',
                target_entity='users',
                target_id=str(new_user.id),
                details_json=json.dumps({'employee_id': employee_id, 'application_no': application_no}),
                ip_address=request.remote_addr
            )
            db.session.add(audit)

            # Welcome notification
            notif = Notification(
                user_id=new_user.id,
                title='Welcome to ANTI MATRIX Internship Portal!',
                message=f'Your employee account has been created. Employee ID: {employee_id}. Please change your password on first login.',
                type='SUCCESS',
                link='/dashboard'
            )
            db.session.add(notif)

            db.session.commit()

            # Redirect to success page with temporary password shown once
            return render_template(
                'admin/create_employee.html',
                plans=plans,
                created=True,
                created_employee_id=employee_id,
                created_temp_password=temp_password,
                created_name=app.candidate_name or 'Intern',
                created_email=new_user.email
            )

        except Exception as e:
            db.session.rollback()
            flash(f'Failed to create employee: {str(e)}', 'danger')

    return render_template('admin/create_employee.html', plans=plans)


# ─── Students (legacy alias) ──────────────────────────────────────────────────

@admin_bp.route('/students')
@login_required
def students_list():
    return redirect(url_for('admin.employees_list'))


@admin_bp.route('/students/<int:student_id>')
@login_required
def student_detail(student_id):
    return redirect(url_for('admin.employee_detail', student_id=student_id))


# ─── Projects Directory ───────────────────────────────────────────────────────

@admin_bp.route('/projects')
@login_required
def projects_list():
    projects = Project.query.order_by(Project.id.desc()).all()
    return render_template('admin/projects.html', projects=projects)


# ─── Create Project ───────────────────────────────────────────────────────────

@admin_bp.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create_project():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        domain = request.form.get('domain', '').strip()
        description = request.form.get('description', '').strip()
        problem_statement = request.form.get('problem_statement', '').strip()
        expected_outcome = request.form.get('expected_outcome', '').strip()
        duration_months = int(request.form.get('duration_months', 1))
        difficulty = request.form.get('difficulty', 'Intermediate').strip()
        tech_stack_raw = request.form.get('tech_stack', '').strip()
        objectives_raw = request.form.get('objectives', '').strip()

        if not title or not domain or not description:
            flash('Title, domain and description are required.', 'danger')
            return render_template('admin/create_project.html')

        duration_weeks = 4 if duration_months == 1 else 12

        # Generate project code
        count = Project.query.count()
        project_code = f'AM-PRJ-{count + 1:03d}'
        while Project.query.filter_by(project_code=project_code).first():
            count += 1
            project_code = f'AM-PRJ-{count + 1:03d}'

        tech_list = [t.strip() for t in tech_stack_raw.split(',') if t.strip()]
        obj_list = [o.strip() for o in objectives_raw.split('\n') if o.strip()]

        project = Project(
            project_code=project_code,
            title=title,
            domain=domain,
            description=description,
            problem_statement=problem_statement,
            expected_outcome=expected_outcome,
            objectives_json=json.dumps(obj_list),
            tech_stack_json=json.dumps(tech_list),
            requirements_json=json.dumps([]),
            instructions_md=f'Follow the {duration_weeks}-week structured milestone roadmap.',
            reference_links_json=json.dumps([]),
            duration_weeks=duration_weeks,
            duration_months=duration_months,
            difficulty=difficulty
        )
        db.session.add(project)
        db.session.flush()

        # Create ProjectWeek stubs for each week
        for w_num in range(1, duration_weeks + 1):
            week_title_raw = request.form.get(f'week_{w_num}_title', f'Week {w_num} Milestone').strip()
            week_desc = request.form.get(f'week_{w_num}_description', '').strip()
            week_obj = request.form.get(f'week_{w_num}_objective', '').strip()
            week_instr = request.form.get(f'week_{w_num}_instructions', '').strip()

            pw = ProjectWeek(
                project_id=project.id,
                week_number=w_num,
                title=week_title_raw or f'Week {w_num}: Milestone',
                description=week_desc,
                objective=week_obj,
                instructions=week_instr,
                deliverables_json=json.dumps([])
            )
            db.session.add(pw)
            db.session.flush()

            # Process tasks for this week (submitted as JSON array from JS)
            tasks_json_key = f'week_{w_num}_tasks'
            tasks_raw = request.form.get(tasks_json_key, '[]')
            try:
                tasks_data = json.loads(tasks_raw)
            except (json.JSONDecodeError, ValueError):
                tasks_data = []

            for t_data in tasks_data:
                if not t_data.get('title'):
                    continue
                pt = ProjectTask(
                    week_id=pw.id,
                    title=t_data.get('title', '').strip(),
                    description=t_data.get('description', '').strip(),
                    instructions=t_data.get('instructions', '').strip(),
                    expected_output=t_data.get('expected_output', '').strip(),
                    priority=t_data.get('priority', 'Medium'),
                    estimated_hours=float(t_data.get('estimated_hours') or 0) or None
                )
                db.session.add(pt)

        db.session.commit()
        flash(f'Project "{title}" created successfully with {duration_weeks} weeks! Project Code: {project_code}', 'success')
        return redirect(url_for('admin.edit_project', project_id=project.id))

    return render_template('admin/create_project.html')


# ─── Edit Project ─────────────────────────────────────────────────────────────

@admin_bp.route('/projects/<int:project_id>/edit')
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    weeks = project.project_weeks.all()
    return render_template('admin/edit_project.html', project=project, weeks=weeks)


@admin_bp.route('/projects/<int:project_id>/weeks/<int:week_id>/tasks/add', methods=['POST'])
@login_required
def add_task(project_id, week_id):
    week = ProjectWeek.query.get_or_404(week_id)
    if week.project_id != project_id:
        abort(403)

    title = request.form.get('title', '').strip()
    if not title:
        flash('Task title is required.', 'danger')
        return redirect(url_for('admin.edit_project', project_id=project_id))

    task = ProjectTask(
        week_id=week_id,
        title=title,
        description=request.form.get('description', '').strip(),
        instructions=request.form.get('instructions', '').strip(),
        expected_output=request.form.get('expected_output', '').strip(),
        priority=request.form.get('priority', 'Medium'),
        estimated_hours=float(request.form.get('estimated_hours') or 0) or None
    )
    db.session.add(task)
    db.session.commit()
    flash(f'Task "{title}" added to Week {week.week_number}.', 'success')
    return redirect(url_for('admin.edit_project', project_id=project_id))


@admin_bp.route('/tasks/<int:task_id>/edit', methods=['POST'])
@login_required
def edit_task(task_id):
    task = ProjectTask.query.get_or_404(task_id)
    project_id = task.week.project_id

    task.title = request.form.get('title', task.title).strip()
    task.description = request.form.get('description', task.description or '').strip()
    task.instructions = request.form.get('instructions', task.instructions or '').strip()
    task.expected_output = request.form.get('expected_output', task.expected_output or '').strip()
    task.priority = request.form.get('priority', task.priority)
    eh = request.form.get('estimated_hours', '')
    task.estimated_hours = float(eh) if eh else None

    db.session.commit()
    flash(f'Task "{task.title}" updated.', 'success')
    return redirect(url_for('admin.edit_project', project_id=project_id))


@admin_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = ProjectTask.query.get_or_404(task_id)
    project_id = task.week.project_id
    title = task.title
    db.session.delete(task)
    db.session.commit()
    flash(f'Task "{title}" deleted.', 'success')
    return redirect(url_for('admin.edit_project', project_id=project_id))


# ─── API: Get tasks for a project week (used in assign flow) ─────────────────

@admin_bp.route('/api/project/<int:project_id>/weeks')
@login_required
def api_project_weeks(project_id):
    project = Project.query.get_or_404(project_id)
    weeks_data = []
    for week in project.project_weeks.all():
        tasks = []
        for task in week.tasks.all():
            tasks.append({
                'id': task.id,
                'title': task.title,
                'description': task.description or '',
                'priority': task.priority,
                'estimated_hours': task.estimated_hours,
            })
        weeks_data.append({
            'id': week.id,
            'week_number': week.week_number,
            'title': week.title,
            'objective': week.objective or '',
            'instructions': week.instructions or '',
            'tasks': tasks
        })
    return jsonify({'success': True, 'weeks': weeks_data})


# ─── Assign Tasks Page ────────────────────────────────────────────────────────

@admin_bp.route('/assign-tasks')
@login_required
def assign_tasks():
    query = request.args.get('q', '').strip()
    students_query = Student.query.join(User)
    if query:
        search = f'%{query}%'
        students_query = students_query.filter(
            db.or_(
                User.full_name.ilike(search),
                Student.student_uid.ilike(search)
            )
        )
    students = students_query.order_by(Student.id.desc()).all()
    return render_template('admin/assign_tasks.html', students=students, search_query=query)


@admin_bp.route('/assign-tasks/<int:student_id>', methods=['GET', 'POST'])
@login_required
def assign_project_to_student(student_id):
    student = Student.query.get_or_404(student_id)
    internship = student.active_internship
    projects = Project.query.order_by(Project.id.desc()).all()

    if not internship:
        flash(f'{student.user.full_name} does not have an active internship. Create employee first.', 'danger')
        return redirect(url_for('admin.assign_tasks'))

    existing_assignment = internship.active_assignment

    if request.method == 'POST':
        project_id = request.form.get('project_id', type=int)
        deadline = request.form.get('deadline', '').strip()

        # Collect selected task IDs from form (checkboxes named task_ids)
        selected_task_ids = request.form.getlist('task_ids')
        selected_task_ids = [int(tid) for tid in selected_task_ids if tid.isdigit()]

        if not project_id:
            flash('Please select a project.', 'danger')
            return render_template('admin/assign_project_detail.html',
                                   student=student, internship=internship,
                                   projects=projects, existing_assignment=existing_assignment)

        project = Project.query.get_or_404(project_id)

        if existing_assignment:
            # Mark old assignment inactive
            existing_assignment.status = 'COMPLETED'

        # Create new ProjectAssignment
        assignment = ProjectAssignment(
            internship_id=internship.id,
            project_id=project_id,
            assigned_by=current_user.id,
            deadline=deadline or internship.end_date,
            status='IN_PROGRESS',
            description=f'Project assigned by {current_user.full_name} on {datetime.utcnow().strftime("%d %b %Y")}'
        )
        db.session.add(assignment)
        db.session.flush()

        # Create WeeklyMilestone + WeeklyTask from the selected ProjectWeek/ProjectTask rows
        weeks = project.project_weeks.all()
        task_id_set = set(selected_task_ids)

        for pw in weeks:
            # Determine status: Week 1 = AVAILABLE, rest = LOCKED
            m_status = 'AVAILABLE' if pw.week_number == 1 else 'LOCKED'
            milestone = WeeklyMilestone(
                assignment_id=assignment.id,
                week_number=pw.week_number,
                title=f'Week {pw.week_number}: {pw.title}',
                objective=pw.objective or pw.title,
                instructions=pw.instructions or '',
                deliverables_json=pw.deliverables_json or '[]',
                status=m_status,
                unlocked_at=datetime.utcnow() if m_status == 'AVAILABLE' else None
            )
            db.session.add(milestone)
            db.session.flush()

            # Get all tasks for this week (filter by selected if any were chosen)
            week_tasks = pw.tasks.all()
            for pt in week_tasks:
                # If admin selected specific tasks, only include those; else include all
                if not task_id_set or pt.id in task_id_set:
                    wt = WeeklyTask(
                        milestone_id=milestone.id,
                        task_text=pt.title,
                        is_completed=False,
                        order_num=pt.id
                    )
                    db.session.add(wt)

        # Notification
        notif = Notification(
            user_id=student.user.id,
            title=f'Project Assigned: {project.title}',
            message=f'You have been assigned the project "{project.title}" by {current_user.full_name}. Week 1 is now available.',
            type='SUCCESS',
            link='/project'
        )
        db.session.add(notif)

        # Audit
        audit = AuditLog(
            actor_id=current_user.id,
            actor_role=current_user.role,
            action='ASSIGN_PROJECT',
            target_entity='project_assignments',
            target_id=str(assignment.id),
            details_json=json.dumps({'project_id': project_id, 'student_id': student_id}),
            ip_address=request.remote_addr
        )
        db.session.add(audit)

        # Update internship progress
        internship.current_stage = 'Week 1 Orientation'
        internship.progress_percent = 0

        db.session.commit()
        flash(f'Project "{project.title}" successfully assigned to {student.user.full_name}. Week 1 is AVAILABLE.', 'success')
        return redirect(url_for('admin.employee_detail', student_id=student_id))

    return render_template(
        'admin/assign_project_detail.html',
        student=student,
        internship=internship,
        projects=projects,
        existing_assignment=existing_assignment
    )


# ─── Milestone Review ─────────────────────────────────────────────────────────

@admin_bp.route('/milestone/<int:milestone_id>/review', methods=['POST'])
@login_required
def review_milestone(milestone_id):
    milestone = WeeklyMilestone.query.get_or_404(milestone_id)
    action = request.form.get('action', 'approve')
    feedback = request.form.get('feedback', '').strip()
    student = milestone.assignment.internship.student

    if action == 'approve':
        milestone.status = 'COMPLETED'
        milestone.completed_at = db.func.now()
        milestone.approved_by = current_user.id
        milestone.approved_at = db.func.now()
        milestone.admin_notes = feedback or 'Milestone reviewed and approved.'

        latest_sub = milestone.latest_submission
        if latest_sub:
            latest_sub.status = 'APPROVED'
            latest_sub.review_feedback = feedback
            latest_sub.reviewed_by = current_user.id
            latest_sub.reviewed_at = db.func.now()

        next_milestone = WeeklyMilestone.query.filter_by(
            assignment_id=milestone.assignment_id,
            week_number=milestone.week_number + 1
        ).first()

        if next_milestone:
            next_milestone.status = 'AVAILABLE'
            next_milestone.unlocked_at = db.func.now()
            notif = Notification(
                user_id=student.user.id,
                title=f'Week {milestone.week_number} Approved — Week {next_milestone.week_number} Unlocked!',
                message=f'Your submission for Week {milestone.week_number} was approved by {current_user.full_name}. Week {next_milestone.week_number} is now available.',
                type='SUCCESS',
                link=url_for('student.week_detail', milestone_id=next_milestone.id)
            )
            db.session.add(notif)
            flash(f'Week {milestone.week_number} marked COMPLETED. Week {next_milestone.week_number} UNLOCKED for {student.user.full_name}.', 'success')
        else:
            milestone.assignment.status = 'COMPLETED'
            milestone.assignment.internship.status = 'COMPLETED'
            notif = Notification(
                user_id=student.user.id,
                title='All Internship Milestones Completed!',
                message=f'Congratulations! You have completed all weekly project milestones for {milestone.assignment.project.title}.',
                type='SUCCESS',
                link=url_for('student.project_detail')
            )
            db.session.add(notif)
            flash(f'Final Week {milestone.week_number} approved! Student has completed all milestones.', 'success')

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
            title=f'Revision Requested: Week {milestone.week_number}',
            message=f'Your mentor reviewed Week {milestone.week_number} and requested revisions: {feedback}',
            type='WARNING',
            link=url_for('student.week_detail', milestone_id=milestone.id)
        )
        db.session.add(notif)
        flash(f'Revision request submitted for Week {milestone.week_number}.', 'warning')

    elif action == 'unlock':
        milestone.status = 'AVAILABLE'
        milestone.unlocked_at = db.func.now()
        notif = Notification(
            user_id=student.user.id,
            title=f'Week {milestone.week_number} Manually Unlocked',
            message=f'Administrator unlocked Week {milestone.week_number} ({milestone.title}) for your project.',
            type='INFO',
            link=url_for('student.week_detail', milestone_id=milestone.id)
        )
        db.session.add(notif)
        flash(f'Week {milestone.week_number} manually unlocked.', 'info')

    milestone.assignment.internship.update_progress()
    db.session.commit()
    return redirect(url_for('admin.employee_detail', student_id=student.id))


# ─── Schedule Meeting ─────────────────────────────────────────────────────────

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
        title=f'Evaluation Meeting Scheduled: {title}',
        message=f'Your mentor scheduled an evaluation session on {meeting_date} at {meeting_time}. Meeting link: {meeting_link}',
        type='INFO',
        link=url_for('student.meetings')
    )
    db.session.add(notif)
    db.session.commit()

    flash(f"Meeting '{title}' scheduled successfully for {student.user.full_name}.", 'success')
    return redirect(url_for('admin.employee_detail', student_id=student.id))


# ─── Evaluations & Meetings ───────────────────────────────────────────────────

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
