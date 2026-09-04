import os
import json
import random
import string
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, current_app, send_file
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    User, Student, Internship, Project, ProjectAssignment, ProjectWeek, ProjectTask,
    WeeklyMilestone, WeeklyTask, WeeklySubmission, Meeting, Notification,
    AuditLog, Application, Payment, College, Department, InternshipPlan, Evaluation
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
    """Server-side AJAX endpoint: look up a career application by its Application ID."""
    from app.services.career_integration import CareerIntegrationService
    app = CareerIntegrationService.get_application_by_id(app_id)
    if not app:
        return jsonify({'success': False, 'error': 'Application ID not found.'}), 404

    # Validate application status
    app_status = (app.status or '').upper()
    if app_status in ['REJECTED', 'CANCELLED']:
        return jsonify({'success': False, 'error': 'Application has been rejected or cancelled.'}), 400

    # Validate payment status
    has_payment = False
    if app.payments.filter(Payment.status.in_(['SUCCESS', 'SUCCESSFUL', 'PAID', 'COMPLETED'])).first():
        has_payment = True
    elif app_status in ['APPROVED', 'PAID', 'SUCCESS', 'VERIFIED']:
        has_payment = True

    if not has_payment:
        return jsonify({'success': False, 'error': 'Payment has not been completed for this application.'}), 400

    # Determine duration display
    duration_months = 1
    if app.plan:
        duration_months = app.plan.duration_months
    elif app.applied_role:
        role_lower = app.applied_role.lower()
        if '3 month' in role_lower or 'professional' in role_lower:
            duration_months = 3

    duration_str = f"{duration_months} Month{'s' if duration_months > 1 else ''}"
    plan_code = '3_MONTH_PROFESSIONAL' if duration_months == 3 else '1_MONTH_PROJECT'

    # Check if already converted / employee exists
    student, user = CareerIntegrationService.get_employee_by_application_id(app.application_no)
    if app.is_converted_to_employee or student:
        emp_id = app.converted_employee_id or (user.employee_id if user else (student.student_uid if student else ''))
        return jsonify({
            'success': True,
            'already_exists': True,
            'message': 'Employee already exists.',
            'application_no': app.application_no,
            'candidate_name': app.candidate_name or (user.full_name if user else ''),
            'candidate_email': app.candidate_email or (user.email if user else ''),
            'candidate_phone': app.candidate_phone or '',
            'college_name': app.college_name or (student.college.name if student and student.college else ''),
            'department_name': app.department_name or (student.department.name if student and student.department else ''),
            'applied_role': app.applied_role or 'Intern',
            'duration': duration_str,
            'duration_plan': plan_code,
            'payment_status': 'SUCCESS',
            'status': 'APPROVED',
            'employee_id': emp_id,
            'student_id': student.id if student else None
        }), 200

    return jsonify({
        'success': True,
        'already_exists': False,
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
        'applied_role': app.applied_role or 'Intern',
        'duration': duration_str,
        'duration_plan': plan_code,
        'payment_status': 'SUCCESS',
        'status': 'APPROVED',
        'employee_id': app.converted_employee_id or 'Generated on Creation',
        'city': app.city or '',
        'state': app.state or '',
        'aadhaar_masked': app.aadhaar_masked or '',
    })


# ─── Employee Directory ───────────────────────────────────────────────────────

@admin_bp.route('/employees')
@login_required
def employees_list():
    query = request.args.get('q', '').strip()
    duration = request.args.get('duration', '').strip()

    # Query active employees with an active internship
    students_query = Student.query.join(User, Student.user_id == User.id)\
        .join(Internship, Internship.student_id == Student.id)\
        .join(InternshipPlan, Internship.plan_id == InternshipPlan.id)\
        .filter(User.is_active == True, Internship.status == 'ACTIVE')

    if duration in ['1', '3']:
        students_query = students_query.filter(InternshipPlan.duration_months == int(duration))

    if query:
        search = f'%{query}%'
        students_query = students_query.join(College, Student.college_id == College.id, isouter=True)\
            .join(Application, Application.student_id == Student.id, isouter=True)\
            .filter(
                db.or_(
                    User.full_name.ilike(search),
                    User.email.ilike(search),
                    Student.student_uid.ilike(search),
                    Student.roll_number.ilike(search),
                    College.name.ilike(search),
                    Application.application_no.ilike(search)
                )
            )

    students = students_query.order_by(Student.id.desc()).all()

    # Badge count metrics for active employees
    count_1m = Student.query.join(User, Student.user_id == User.id)\
        .join(Internship, Internship.student_id == Student.id)\
        .join(InternshipPlan, Internship.plan_id == InternshipPlan.id)\
        .filter(User.is_active == True, Internship.status == 'ACTIVE', InternshipPlan.duration_months == 1).count()

    count_3m = Student.query.join(User, Student.user_id == User.id)\
        .join(Internship, Internship.student_id == Student.id)\
        .join(InternshipPlan, Internship.plan_id == InternshipPlan.id)\
        .filter(User.is_active == True, Internship.status == 'ACTIVE', InternshipPlan.duration_months == 3).count()

    count_all = count_1m + count_3m

    return render_template(
        'admin/employees.html',
        students=students,
        search_query=query,
        current_duration=duration,
        count_1m=count_1m,
        count_3m=count_3m,
        count_all=count_all
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
    from app.services.career_integration import CareerIntegrationService
    plans = InternshipPlan.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        application_no = request.form.get('application_no', '').strip().upper()
        duration_plan = request.form.get('duration_plan', '1_MONTH_PROJECT').strip()

        # Validate application ID on server side
        app = CareerIntegrationService.get_application_by_id(application_no)
        if not app:
            flash(f'Application ID "{application_no}" not found in the system.', 'danger')
            return render_template('admin/create_employee.html', plans=plans)

        is_valid, err_msg, err_code = CareerIntegrationService.validate_application_for_onboarding(app)
        if not is_valid:
            if err_msg == 'Employee already exists.':
                flash(f'An employee account already exists for application {application_no}. Employee ID: {app.converted_employee_id}', 'warning')
            else:
                flash(err_msg, 'danger')
            return render_template('admin/create_employee.html', plans=plans)

        try:
            student, new_user, emp_id, temp_password = CareerIntegrationService.create_or_link_employee_from_application(
                app=app,
                duration_plan=duration_plan,
                admin_user=current_user,
                raw_ip=request.remote_addr
            )

            flash(f'Employee {new_user.full_name} ({emp_id}) created successfully from Application {app.application_no}!', 'success')
            return render_template(
                'admin/create_employee.html',
                plans=plans,
                created=True,
                created_employee_id=emp_id,
                created_temp_password=temp_password,
                created_name=new_user.full_name,
                created_email=new_user.email,
                created_student_id=student.id
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


# ─── Projects Directory / Project Database ────────────────────────────────────

@admin_bp.route('/projects')
@login_required
def projects_list():
    query = request.args.get('q', '').strip()
    duration = request.args.get('duration', '').strip()

    projects_query = Project.query

    if duration in ['1', '3']:
        projects_query = projects_query.filter(Project.duration_months == int(duration))

    if query:
        search = f'%{query}%'
        projects_query = projects_query.filter(
            db.or_(
                Project.project_code.ilike(search),
                Project.title.ilike(search),
                Project.domain.ilike(search)
            )
        )

    projects = projects_query.order_by(Project.id.desc()).all()

    count_1m = Project.query.filter_by(duration_months=1).count()
    count_3m = Project.query.filter_by(duration_months=3).count()
    count_all = count_1m + count_3m

    return render_template(
        'admin/projects.html',
        projects=projects,
        search_query=query,
        current_duration=duration,
        count_1m=count_1m,
        count_3m=count_3m,
        count_all=count_all
    )


# ─── Create Project ───────────────────────────────────────────────────────────

@admin_bp.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create_project():
    if request.method == 'POST':
        project_code = request.form.get('project_code', '').strip().upper()
        title = request.form.get('title', '').strip()
        domain = request.form.get('domain', '').strip()
        description = request.form.get('description', '').strip()
        problem_statement = request.form.get('problem_statement', '').strip()
        expected_outcome = request.form.get('expected_outcome', '').strip()
        duration_months = int(request.form.get('duration_months', 1))
        difficulty = request.form.get('difficulty', 'Intermediate').strip()
        status_val = request.form.get('status', 'ACTIVE').strip().upper()
        is_active = (status_val == 'ACTIVE')
        tech_stack_raw = request.form.get('tech_stack', '').strip()
        objectives_raw = request.form.get('objectives', '').strip()

        if not title or not domain or not description:
            flash('Project Title, Domain / Category, and Description are required.', 'danger')
            return render_template('admin/create_project.html')

        duration_weeks = 4 if duration_months == 1 else 12

        # Generate or validate project code
        if not project_code:
            prefix = f'AM-{duration_months}M'
            count = Project.query.filter(Project.project_code.like(f'{prefix}-%')).count()
            project_code = f'{prefix}-{count + 1:03d}'
            while Project.query.filter_by(project_code=project_code).first():
                count += 1
                project_code = f'{prefix}-{count + 1:03d}'
        else:
            existing = Project.query.filter_by(project_code=project_code).first()
            if existing:
                flash(f'Project ID "{project_code}" already exists. Please choose a unique Project ID.', 'danger')
                return render_template('admin/create_project.html')

        tech_list = [t.strip() for t in tech_stack_raw.split(',') if t.strip()]
        obj_list = [o.strip() for o in objectives_raw.split('\n') if o.strip()]

        try:
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
                difficulty=difficulty,
                is_active=is_active
            )
            db.session.add(project)
            db.session.flush()

            # Create ProjectWeek entries for each week (4 or 12 weeks)
            for w_num in range(1, duration_weeks + 1):
                week_title_raw = request.form.get(f'week_{w_num}_title', '').strip()
                week_title = week_title_raw or f'Week {w_num} Milestone'
                week_desc = request.form.get(f'week_{w_num}_description', '').strip()
                week_obj = request.form.get(f'week_{w_num}_objective', '').strip()
                week_instr = request.form.get(f'week_{w_num}_instructions', '').strip()

                pw = ProjectWeek(
                    project_id=project.id,
                    week_number=w_num,
                    title=week_title,
                    description=week_desc,
                    objective=week_obj,
                    instructions=week_instr,
                    deliverables_json=json.dumps([])
                )
                db.session.add(pw)
                db.session.flush()

                # Process tasks for this week
                tasks_raw = request.form.get(f'week_{w_num}_tasks', '[]')
                try:
                    tasks_data = json.loads(tasks_raw) if tasks_raw else []
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
            flash(f'Project "{title}" ({project_code}) created successfully with {duration_weeks} weeks!', 'success')
            return redirect(url_for('admin.edit_project', project_id=project.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Failed to create project: {str(e)}', 'danger')
            return render_template('admin/create_project.html')

    # Default suggested codes for GET
    p1_count = Project.query.filter(Project.project_code.like('AM-1M-%')).count()
    suggested_1m_code = f'AM-1M-{p1_count + 1:03d}'
    p3_count = Project.query.filter(Project.project_code.like('AM-3M-%')).count()
    suggested_3m_code = f'AM-3M-{p3_count + 1:03d}'

    return render_template(
        'admin/create_project.html',
        suggested_1m_code=suggested_1m_code,
        suggested_3m_code=suggested_3m_code
    )


# ─── Edit Project ─────────────────────────────────────────────────────────────

@admin_bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST':
        # Project ID is immutable and cannot be changed!
        project.title = request.form.get('title', project.title).strip()
        project.domain = request.form.get('domain', project.domain).strip()
        project.description = request.form.get('description', project.description).strip()
        project.problem_statement = request.form.get('problem_statement', project.problem_statement or '').strip()
        project.expected_outcome = request.form.get('expected_outcome', project.expected_outcome or '').strip()
        project.difficulty = request.form.get('difficulty', project.difficulty).strip()
        
        status_val = request.form.get('status', 'ACTIVE').strip().upper()
        project.is_active = (status_val == 'ACTIVE')

        tech_stack_raw = request.form.get('tech_stack', '').strip()
        if tech_stack_raw:
            project.tech_stack_json = json.dumps([t.strip() for t in tech_stack_raw.split(',') if t.strip()])

        objectives_raw = request.form.get('objectives', '').strip()
        if objectives_raw:
            project.objectives_json = json.dumps([o.strip() for o in objectives_raw.split('\n') if o.strip()])

        db.session.commit()
        flash(f'Project "{project.title}" updated successfully.', 'success')
        return redirect(url_for('admin.edit_project', project_id=project.id))

    weeks = project.project_weeks.all()
    return render_template('admin/edit_project.html', project=project, weeks=weeks)


@admin_bp.route('/projects/<int:project_id>/toggle-status', methods=['POST'])
@login_required
def toggle_project_status(project_id):
    project = Project.query.get_or_404(project_id)
    project.is_active = not project.is_active
    db.session.commit()
    new_status = 'ACTIVE' if project.is_active else 'INACTIVE'
    flash(f'Project "{project.project_code}" is now {new_status}.', 'info')
    return redirect(request.referrer or url_for('admin.projects_list'))


# ─── Week & Task Management ───────────────────────────────────────────────────

@admin_bp.route('/weeks/<int:week_id>/edit', methods=['POST'])
@login_required
def edit_week(week_id):
    week = ProjectWeek.query.get_or_404(week_id)
    week.title = request.form.get('title', week.title).strip()
    week.description = request.form.get('description', week.description or '').strip()
    week.objective = request.form.get('objective', week.objective or '').strip()
    week.instructions = request.form.get('instructions', week.instructions or '').strip()
    db.session.commit()
    flash(f'Week {week.week_number} details updated.', 'success')
    return redirect(url_for('admin.edit_project', project_id=week.project_id))


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


# ─── API: Get tasks for a project week ───────────────────────────────────────

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


# ─── Assign Project Page ──────────────────────────────────────────────────────

@admin_bp.route('/assign-project')
@admin_bp.route('/assign-tasks')
@login_required
def assign_tasks():
    query = request.args.get('q', '').strip()
    duration = request.args.get('duration', '').strip()

    students_query = Student.query.join(User, Student.user_id == User.id)\
        .join(Internship, Internship.student_id == Student.id)\
        .join(InternshipPlan, Internship.plan_id == InternshipPlan.id)\
        .filter(User.is_active == True, Internship.status == 'ACTIVE')

    if duration in ['1', '3']:
        students_query = students_query.filter(InternshipPlan.duration_months == int(duration))

    if query:
        search = f'%{query}%'
        students_query = students_query.join(College, Student.college_id == College.id, isouter=True)\
            .filter(
                db.or_(
                    User.full_name.ilike(search),
                    Student.student_uid.ilike(search),
                    College.name.ilike(search)
                )
            )

    students = students_query.order_by(Student.id.desc()).all()
    return render_template('admin/assign_tasks.html', students=students, search_query=query, current_duration=duration)


@admin_bp.route('/assign-project/<int:student_id>', methods=['GET', 'POST'])
@admin_bp.route('/assign-tasks/<int:student_id>', methods=['GET', 'POST'])
@admin_bp.route('/employees/<int:student_id>/assign-project', methods=['GET', 'POST'])
@login_required
def assign_project_to_student(student_id):
    student = Student.query.get_or_404(student_id)
    internship = student.active_internship

    if not internship:
        flash(f'{student.user.full_name} does not have an active internship.', 'danger')
        return redirect(url_for('admin.assign_tasks'))

    student_duration_months = internship.plan.duration_months if internship.plan else 1

    # Fetch active projects matching duration
    projects = Project.query.filter_by(
        duration_months=student_duration_months,
        is_active=True
    ).order_by(Project.id.desc()).all()

    existing_assignment = internship.active_assignment

    # Calculate availability for each project for this student's college
    for p in projects:
        conflict_assignment = db.session.query(ProjectAssignment)\
            .join(Internship, ProjectAssignment.internship_id == Internship.id)\
            .join(Student, Internship.student_id == Student.id)\
            .filter(
                ProjectAssignment.project_id == p.id,
                ProjectAssignment.status.in_(['ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'REVISION_REQUIRED', 'UNDER_EVALUATION', 'ACTIVE']),
                Internship.status == 'ACTIVE',
                Student.college_id == student.college_id,
                Student.id != student.id
            ).first()

        if conflict_assignment:
            p.is_available_for_student = False
            p.unavailable_reason = f"Already assigned to another active student from {student.college.name}"
        else:
            p.is_available_for_student = True
            p.unavailable_reason = None

    if request.method == 'POST':
        project_id = request.form.get('project_id', type=int)
        deadline = request.form.get('deadline', '').strip()

        if not project_id:
            flash('Please select a project to assign.', 'danger')
            return render_template(
                'admin/assign_project_detail.html',
                student=student,
                internship=internship,
                projects=projects,
                existing_assignment=existing_assignment
            )

        project = Project.query.get_or_404(project_id)

        # 1. Check if project is active
        if not project.is_active:
            flash(f'Project "{project.title}" is currently inactive and cannot be assigned.', 'danger')
            return redirect(url_for('admin.assign_project_to_student', student_id=student.id))

        # 2. Check duration compatibility
        if project.duration_months != student_duration_months:
            flash(f'Project duration ({project.duration_months} Month) does not match student internship duration ({student_duration_months} Month).', 'danger')
            return redirect(url_for('admin.assign_project_to_student', student_id=student.id))

        # 3. CRITICAL VALIDATION: Project Uniqueness by College for Active Assignments
        conflict = db.session.query(ProjectAssignment)\
            .join(Internship, ProjectAssignment.internship_id == Internship.id)\
            .join(Student, Internship.student_id == Student.id)\
            .filter(
                ProjectAssignment.project_id == project.id,
                ProjectAssignment.status.in_(['ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'REVISION_REQUIRED', 'UNDER_EVALUATION', 'ACTIVE']),
                Internship.status == 'ACTIVE',
                Student.college_id == student.college_id,
                Student.id != student.id
            ).first()

        if conflict:
            flash(f'Project {project.project_code} has already been assigned to another active student from {student.college.name}. Please select a different project.', 'danger')
            return redirect(url_for('admin.assign_project_to_student', student_id=student.id))

        try:
            if existing_assignment:
                existing_assignment.status = 'COMPLETED'

            # Create new ProjectAssignment
            assignment = ProjectAssignment(
                internship_id=internship.id,
                project_id=project.id,
                assigned_by=current_user.id,
                deadline=deadline or internship.end_date,
                status='IN_PROGRESS',
                description=f'Project assigned by {current_user.full_name} on {datetime.utcnow().strftime("%d %b %Y")}'
            )
            db.session.add(assignment)
            db.session.flush()

            # Clone ProjectWeeks and ProjectTasks to WeeklyMilestones and WeeklyTasks
            weeks = project.project_weeks.all()
            now = datetime.utcnow()
            for pw in weeks:
                m_status = 'AVAILABLE' if pw.week_number == 1 else 'LOCKED'
                milestone = WeeklyMilestone(
                    assignment_id=assignment.id,
                    week_number=pw.week_number,
                    title=f'Week {pw.week_number}: {pw.title}',
                    objective=pw.objective or pw.title,
                    instructions=pw.instructions or '',
                    deliverables_json=pw.deliverables_json or '[]',
                    status=m_status,
                    started_at=now if m_status == 'AVAILABLE' else None,
                    due_at=(now + timedelta(days=7)) if m_status == 'AVAILABLE' else None,
                    unlocked_at=now if m_status == 'AVAILABLE' else None
                )
                db.session.add(milestone)
                db.session.flush()

                for pt in pw.tasks.all():
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
                message=f'You have been assigned the project "{project.title}" ({project.project_code}) by {current_user.full_name}. Week 1 is now available.',
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
                details_json=json.dumps({
                    'project_id': project.id,
                    'project_code': project.project_code,
                    'student_id': student.id,
                    'college_id': student.college_id,
                    'college_name': student.college.name
                }),
                ip_address=request.remote_addr
            )
            db.session.add(audit)

            # Update internship stage
            internship.current_stage = 'Week 1 Requirement & Architecture'
            internship.progress_percent = 0

            db.session.commit()
            flash(f'Project "{project.title}" ({project.project_code}) successfully assigned to {student.user.full_name}. Week 1 is AVAILABLE.', 'success')
            return redirect(url_for('admin.employee_detail', student_id=student.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Failed to assign project: {str(e)}', 'danger')
            return redirect(url_for('admin.assign_project_to_student', student_id=student.id))

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


# ─── Manage Employee Tasks Dashboard ──────────────────────────────────────────

@admin_bp.route('/employee-tasks')
@login_required
def employee_tasks():
    # Filter params
    duration_filter = request.args.get('duration', 'all').lower()
    status_filter = request.args.get('status', 'all').lower()
    search_query = request.args.get('q', '').strip()

    # Metrics
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    pending_count = WeeklySubmission.query.filter(WeeklySubmission.status.in_(['SUBMITTED', 'UNDER_REVIEW'])).count()
    redo_count = WeeklySubmission.query.filter(WeeklySubmission.status.in_(['REDO_REQUIRED', 'REVISION_REQUIRED'])).count()
    approved_this_week_count = WeeklySubmission.query.filter(
        WeeklySubmission.status.in_(['APPROVED', 'COMPLETED']),
        WeeklySubmission.reviewed_at >= seven_days_ago
    ).count()
    completed_weeks_count = WeeklyMilestone.query.filter(WeeklyMilestone.status.in_(['COMPLETED', 'APPROVED'])).count()

    # Query for submissions
    query = WeeklySubmission.query.join(
        WeeklyMilestone, WeeklySubmission.milestone_id == WeeklyMilestone.id
    ).join(
        ProjectAssignment, WeeklyMilestone.assignment_id == ProjectAssignment.id
    ).join(
        Project, ProjectAssignment.project_id == Project.id
    ).join(
        Student, WeeklySubmission.student_id == Student.id
    ).join(
        User, Student.user_id == User.id
    ).join(
        College, Student.college_id == College.id
    )

    # Duration filter
    if duration_filter == '1m':
        query = query.filter((Project.duration_months == 1) | (Project.duration_weeks == 4))
    elif duration_filter == '3m':
        query = query.filter((Project.duration_months == 3) | (Project.duration_weeks == 12))

    # Status filter
    if status_filter in ['submitted', 'under_review']:
        query = query.filter(WeeklySubmission.status.in_(['SUBMITTED', 'UNDER_REVIEW']))
    elif status_filter in ['redo_required', 'redo']:
        query = query.filter(WeeklySubmission.status.in_(['REDO_REQUIRED', 'REVISION_REQUIRED']))
    elif status_filter == 'approved':
        query = query.filter(WeeklySubmission.status == 'APPROVED')
    elif status_filter == 'completed':
        query = query.filter(WeeklySubmission.status == 'COMPLETED')

    # Search filter
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.outerjoin(Application, Application.student_id == Student.id).filter(
            (User.full_name.ilike(search_pattern)) |
            (User.employee_id.ilike(search_pattern)) |
            (Student.student_uid.ilike(search_pattern)) |
            (College.name.ilike(search_pattern)) |
            (Project.project_code.ilike(search_pattern)) |
            (Project.title.ilike(search_pattern)) |
            (Application.application_no.ilike(search_pattern))
        )

    submissions_list = query.order_by(WeeklySubmission.id.desc()).all()

    return render_template(
        'admin/employee_tasks.html',
        submissions=submissions_list,
        pending_count=pending_count,
        redo_count=redo_count,
        approved_this_week_count=approved_this_week_count,
        completed_weeks_count=completed_weeks_count,
        duration_filter=duration_filter,
        status_filter=status_filter,
        search_query=search_query
    )


# ─── Submission Review Page ───────────────────────────────────────────────────

@admin_bp.route('/submissions/<int:submission_id>/review')
@login_required
def review_submission(submission_id):
    submission = WeeklySubmission.query.get_or_404(submission_id)
    milestone = submission.milestone
    assignment = milestone.assignment
    student = submission.student
    project = assignment.project

    tasks = milestone.tasks.all()
    submission_history = WeeklySubmission.query.filter_by(
        milestone_id=milestone.id
    ).order_by(WeeklySubmission.id.desc()).all()

    evaluations_list = Evaluation.query.filter_by(
        milestone_id=milestone.id
    ).order_by(Evaluation.id.desc()).all()

    return render_template(
        'admin/submission_review.html',
        submission=submission,
        milestone=milestone,
        assignment=assignment,
        student=student,
        project=project,
        tasks=tasks,
        submission_history=submission_history,
        evaluations=evaluations_list
    )


# ─── Admin Review Action: REDO ────────────────────────────────────────────────

@admin_bp.route('/submissions/<int:submission_id>/redo', methods=['POST'])
@login_required
def submission_action_redo(submission_id):
    submission = WeeklySubmission.query.get_or_404(submission_id)
    milestone = submission.milestone
    student = submission.student

    remarks = request.form.get('admin_remarks', '').strip() or request.form.get('remarks', '').strip()
    if not remarks:
        flash('Admin Remarks are required when requesting a REDO from the student.', 'danger')
        return redirect(url_for('admin.review_submission', submission_id=submission.id))

    try:
        now = datetime.utcnow()
        submission.status = 'REDO_REQUIRED'
        submission.review_feedback = remarks
        submission.reviewed_by = current_user.id
        submission.reviewed_at = now

        milestone.status = 'REDO_REQUIRED'
        milestone.admin_notes = remarks

        eval_log = Evaluation(
            submission_id=submission.id,
            milestone_id=milestone.id,
            assignment_id=milestone.assignment_id,
            employee_id=student.id,
            admin_id=current_user.id,
            evaluator_id=current_user.id,
            action='REDO',
            remarks=remarks,
            feedback=remarks,
            result='REDO_REQUIRED',
            evaluated_at=now
        )
        db.session.add(eval_log)

        notif = Notification(
            user_id=student.user.id,
            title=f'Redo Required: Week {milestone.week_number}',
            message=f'Your submission for Week {milestone.week_number} ({milestone.title}) requires changes. Mentor Remarks: "{remarks}"',
            type='WARNING',
            link=url_for('student.week_detail', milestone_id=milestone.id)
        )
        db.session.add(notif)

        audit = AuditLog(
            actor_id=current_user.id,
            actor_role=current_user.role,
            action='SUBMISSION_REDO',
            target_entity='weekly_submissions',
            target_id=str(submission.id),
            details_json=json.dumps({
                'milestone_id': milestone.id,
                'student_id': student.id,
                'remarks': remarks
            }),
            ip_address=request.remote_addr
        )
        db.session.add(audit)

        milestone.assignment.internship.update_progress()
        db.session.commit()

        flash(f'Submission marked REDO REQUIRED. Feedback transmitted to {student.user.full_name}.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to process REDO action: {str(e)}', 'danger')

    return redirect(url_for('admin.review_submission', submission_id=submission.id))


# ─── Admin Review Action: VERIFY ──────────────────────────────────────────────

@admin_bp.route('/submissions/<int:submission_id>/verify', methods=['POST'])
@login_required
def submission_action_verify(submission_id):
    submission = WeeklySubmission.query.get_or_404(submission_id)
    milestone = submission.milestone
    student = submission.student

    remarks = request.form.get('admin_remarks', '').strip() or request.form.get('remarks', '').strip() or 'Work verified and approved by evaluator.'

    try:
        now = datetime.utcnow()
        submission.status = 'APPROVED'
        submission.review_feedback = remarks
        submission.reviewed_by = current_user.id
        submission.reviewed_at = now

        milestone.status = 'APPROVED'
        milestone.admin_notes = remarks
        milestone.approved_by = current_user.id
        milestone.approved_at = now

        eval_log = Evaluation(
            submission_id=submission.id,
            milestone_id=milestone.id,
            assignment_id=milestone.assignment_id,
            employee_id=student.id,
            admin_id=current_user.id,
            evaluator_id=current_user.id,
            action='VERIFY',
            remarks=remarks,
            feedback=remarks,
            result='VERIFIED',
            evaluated_at=now
        )
        db.session.add(eval_log)

        notif = Notification(
            user_id=student.user.id,
            title=f'Week {milestone.week_number} Verified',
            message=f'Your deliverables for Week {milestone.week_number} have passed verification. Evaluation notes: "{remarks}"',
            type='SUCCESS',
            link=url_for('student.week_detail', milestone_id=milestone.id)
        )
        db.session.add(notif)

        audit = AuditLog(
            actor_id=current_user.id,
            actor_role=current_user.role,
            action='SUBMISSION_VERIFY',
            target_entity='weekly_submissions',
            target_id=str(submission.id),
            details_json=json.dumps({
                'milestone_id': milestone.id,
                'student_id': student.id,
                'remarks': remarks
            }),
            ip_address=request.remote_addr
        )
        db.session.add(audit)

        milestone.assignment.internship.update_progress()
        db.session.commit()

        flash(f'Submission for Week {milestone.week_number} verified successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to verify submission: {str(e)}', 'danger')

    return redirect(url_for('admin.review_submission', submission_id=submission.id))


# ─── Admin Review Action: PROCEED TO NEXT ─────────────────────────────────────

@admin_bp.route('/submissions/<int:submission_id>/proceed-next', methods=['POST'])
@login_required
def submission_action_proceed_next(submission_id):
    submission = WeeklySubmission.query.get_or_404(submission_id)
    milestone = submission.milestone
    assignment = milestone.assignment
    student = submission.student

    # Double-click / Duplicate progression protection
    if milestone.status == 'COMPLETED':
        flash(f'Week {milestone.week_number} has already been completed and progressed.', 'info')
        return redirect(url_for('admin.employee_tasks'))

    remarks = request.form.get('admin_remarks', '').strip() or request.form.get('remarks', '').strip() or 'Milestone approved and progressed to next week.'

    try:
        now = datetime.utcnow()

        # 1. Complete current week
        milestone.status = 'COMPLETED'
        milestone.completed_at = now
        milestone.approved_by = current_user.id
        milestone.approved_at = now
        milestone.admin_notes = remarks

        # 2. Complete submission
        submission.status = 'COMPLETED'
        submission.review_feedback = remarks
        submission.reviewed_by = current_user.id
        submission.reviewed_at = now

        # 3. Progression check for next week
        next_milestone = WeeklyMilestone.query.filter_by(
            assignment_id=assignment.id,
            week_number=milestone.week_number + 1
        ).first()

        if next_milestone:
            # Unlock next week immediately with 7-day schedule
            next_milestone.status = 'AVAILABLE'
            next_milestone.unlocked_at = now
            next_milestone.started_at = now
            next_milestone.due_at = now + timedelta(days=7)

            notif = Notification(
                user_id=student.user.id,
                title=f'Week {milestone.week_number} Approved — Week {next_milestone.week_number} Unlocked!',
                message=f'Your submission for Week {milestone.week_number} ({milestone.title}) was approved by {current_user.full_name}. Week {next_milestone.week_number} ({next_milestone.title}) is now AVAILABLE.',
                type='SUCCESS',
                link=url_for('student.week_detail', milestone_id=next_milestone.id)
            )
            db.session.add(notif)
            flash_msg = f'Week {milestone.week_number} marked COMPLETED. Week {next_milestone.week_number} UNLOCKED and AVAILABLE for {student.user.full_name}.'
        else:
            # Final week completed -> 100% completion
            assignment.status = 'COMPLETED'
            assignment.internship.status = 'COMPLETED'
            assignment.internship.progress_percent = 100

            notif = Notification(
                user_id=student.user.id,
                title='All Internship Milestones Completed!',
                message=f'Congratulations! You have completed all weekly project milestones for "{assignment.project.title}". Your internship progress is 100%.',
                type='SUCCESS',
                link=url_for('student.project_detail')
            )
            db.session.add(notif)
            flash_msg = f'Final Week {milestone.week_number} COMPLETED! {student.user.full_name} has successfully completed all project milestones (100%).'

        # 4. Update overall internship progress
        assignment.internship.update_progress()

        # 5. Audit & Evaluation log
        eval_log = Evaluation(
            submission_id=submission.id,
            milestone_id=milestone.id,
            assignment_id=assignment.id,
            employee_id=student.id,
            admin_id=current_user.id,
            evaluator_id=current_user.id,
            action='PROCEED_TO_NEXT',
            remarks=remarks,
            feedback=remarks,
            result='PASSED',
            evaluated_at=now
        )
        db.session.add(eval_log)

        audit = AuditLog(
            actor_id=current_user.id,
            actor_role=current_user.role,
            action='SUBMISSION_PROCEED_TO_NEXT',
            target_entity='weekly_submissions',
            target_id=str(submission.id),
            details_json=json.dumps({
                'milestone_id': milestone.id,
                'week_number': milestone.week_number,
                'student_id': student.id,
                'remarks': remarks
            }),
            ip_address=request.remote_addr
        )
        db.session.add(audit)

        db.session.commit()
        flash(flash_msg, 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to progress milestone: {str(e)}', 'danger')

    return redirect(url_for('admin.employee_tasks'))


# ─── Protected Admin Video Stream ─────────────────────────────────────────────

@admin_bp.route('/submission/<int:sub_id>/video')
@login_required
def stream_admin_submission_video(sub_id):
    """Securely stream demo video for authenticated administrators."""
    sub = WeeklySubmission.query.get_or_404(sub_id)

    filename = sub.demo_video_path or sub.demo_video_url or sub.file_path
    if not filename:
        abort(404)

    upload_folder = current_app.config.get('VIDEO_UPLOAD_FOLDER')
    full_path = os.path.join(upload_folder, filename)

    if not os.path.exists(full_path):
        abort(404)

    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    mimetype = 'video/mp4'
    if ext == 'webm':
        mimetype = 'video/webm'
    elif ext == 'mov':
        mimetype = 'video/quicktime'

    return send_file(full_path, mimetype=mimetype, conditional=True)


# ─── Legacy Evaluations & Meetings Views ──────────────────────────────────────

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


