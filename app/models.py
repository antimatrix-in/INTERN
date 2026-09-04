import json
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=True, index=True) # AM-ADM-..., AM-MTR-...
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student') # super_admin, admin, hr, mentor, evaluator, student
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student_profile = db.relationship('Student', backref='user', uselist=False, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan', order_by='Notification.id.desc()')
    audit_logs = db.relationship('AuditLog', backref='actor', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin_or_staff(self):
        return self.role in ['super_admin', 'admin', 'hr', 'mentor', 'evaluator']

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'


class College(db.Model):
    __tablename__ = 'colleges'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    departments = db.relationship('Department', backref='college', cascade='all, delete-orphan')
    students = db.relationship('Student', backref='college', lazy='dynamic')

    def __repr__(self):
        return f'<College {self.code} - {self.name}>'


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('colleges.id', ondelete='CASCADE'), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship('Student', backref='department', lazy='dynamic')

    def __repr__(self):
        return f'<Department {self.name}>'


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    student_uid = db.Column(db.String(30), unique=True, nullable=False, index=True) # AM-INT-2026-001 / AM-STU-...
    dob = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    college_id = db.Column(db.Integer, db.ForeignKey('colleges.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    roll_number = db.Column(db.String(50), nullable=False)
    degree = db.Column(db.String(100), nullable=False)
    current_year = db.Column(db.String(20), nullable=False)
    graduation_year = db.Column(db.String(10), nullable=False)
    aadhaar_masked = db.Column(db.String(20), nullable=True) # XXXX XXXX 4821
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    applications = db.relationship('Application', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    internships = db.relationship('Internship', backref='student', lazy='dynamic')
    documents = db.relationship('Document', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='student', lazy='dynamic')
    submissions = db.relationship('WeeklySubmission', back_populates='student', lazy='dynamic', cascade='all, delete-orphan')
    meetings = db.relationship('Meeting', back_populates='student', lazy='dynamic')

    @property
    def active_internship(self):
        return self.internships.order_by(Internship.id.desc()).first()

    def __repr__(self):
        return f'<Student {self.student_uid} - {self.user.full_name if self.user else ""}>'


class InternshipPlan(db.Model):
    __tablename__ = 'internship_plans'

    id = db.Column(db.Integer, primary_key=True)
    plan_code = db.Column(db.String(50), unique=True, nullable=False) # 1_MONTH_PROJECT, 3_MONTH_PROFESSIONAL
    title = db.Column(db.String(100), nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)
    fee = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    description = db.Column(db.Text, nullable=False)
    features_json = db.Column(db.Text, nullable=False)
    badge = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    applications = db.relationship('Application', backref='plan', lazy='dynamic')
    internships = db.relationship('Internship', backref='plan', lazy='dynamic')

    @property
    def features(self):
        try:
            return json.loads(self.features_json)
        except:
            return []

    def __repr__(self):
        return f'<InternshipPlan {self.title}>'


class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    application_no = db.Column(db.String(30), unique=True, nullable=False, index=True) # AM-APP-2026-0001
    # student_id is nullable: career applications exist BEFORE employee conversion
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('internship_plans.id'), nullable=True)
    status = db.Column(db.String(30), default='APPROVED') # DRAFT, SUBMITTED, PAYMENT_PENDING, PAID, DOCUMENT_PENDING, UNDER_REVIEW, VERIFIED, REJECTED, APPROVED
    consent_agreed = db.Column(db.Boolean, default=True)
    consent_version = db.Column(db.String(20), default='v1.0-2026')
    consent_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Career application candidate fields (populated before student/employee onboarding)
    candidate_name = db.Column(db.String(150), nullable=True)
    candidate_email = db.Column(db.String(150), nullable=True)
    candidate_phone = db.Column(db.String(30), nullable=True)
    candidate_dob = db.Column(db.String(20), nullable=True)
    candidate_gender = db.Column(db.String(20), nullable=True)
    college_name = db.Column(db.String(200), nullable=True)
    department_name = db.Column(db.String(150), nullable=True)
    course = db.Column(db.String(100), nullable=True)
    year_of_study = db.Column(db.String(20), nullable=True)
    roll_number = db.Column(db.String(50), nullable=True)
    applied_role = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    aadhaar_masked = db.Column(db.String(20), nullable=True)
    # Employee conversion tracking
    is_converted_to_employee = db.Column(db.Boolean, default=False)
    converted_employee_id = db.Column(db.String(50), nullable=True)  # AM-INT-XXXX

    # Relationships
    payments = db.relationship('Payment', backref='application', lazy='dynamic')
    internship = db.relationship('Internship', backref='application', uselist=False)

    def __repr__(self):
        return f'<Application {self.application_no} - {self.status}>'


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    transaction_id = db.Column(db.String(50), unique=True, nullable=False, index=True) # AM-TXN-2026-XXXXX
    order_id = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    status = db.Column(db.String(20), default='SUCCESSFUL') # PENDING, SUCCESSFUL, FAILED, REFUNDED
    payment_method = db.Column(db.String(50), default='ONLINE')
    gateway_response_json = db.Column(db.Text, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Payment {self.transaction_id} - {self.status}>'


class Internship(db.Model):
    __tablename__ = 'internships'

    id = db.Column(db.Integer, primary_key=True)
    internship_no = db.Column(db.String(30), unique=True, nullable=False, index=True) # AM-INT-2026-0001
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('internship_plans.id'), nullable=False)
    status = db.Column(db.String(20), default='ACTIVE') # NOT_STARTED, ACTIVE, ON_HOLD, COMPLETED, TERMINATED
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20), nullable=False)
    progress_percent = db.Column(db.Integer, default=0)
    current_stage = db.Column(db.String(50), default='Week 1 Understanding')
    mentor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    mentor = db.relationship('User', foreign_keys=[mentor_id])
    assignments = db.relationship('ProjectAssignment', backref='internship', lazy='dynamic', cascade='all, delete-orphan')
    issued_documents = db.relationship('IssuedDocument', backref='internship', lazy='dynamic')
    verification = db.relationship('CertificateVerification', backref='internship', uselist=False)
    meetings = db.relationship('Meeting', back_populates='internship', lazy='dynamic')

    @property
    def active_assignment(self):
        return self.assignments.order_by(ProjectAssignment.id.desc()).first()

    def update_progress(self):
        assignment = self.active_assignment
        if assignment:
            milestones = assignment.weekly_milestones.all()
            if milestones:
                completed = sum(1 for m in milestones if m.status in ['COMPLETED', 'APPROVED'])
                self.progress_percent = int((completed / len(milestones)) * 100)
                active_m = next((m for m in milestones if m.status in ['AVAILABLE', 'IN_PROGRESS', 'SUBMITTED', 'UNDER_REVIEW', 'REVISION_REQUIRED']), None)
                if active_m:
                    self.current_stage = f"Week {active_m.week_number} ({active_m.status.replace('_', ' ').title()})"
                elif completed == len(milestones):
                    self.current_stage = "All Milestones Completed"
                db.session.commit()

    def __repr__(self):
        return f'<Internship {self.internship_no} - {self.status}>'


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=True)
    doc_type = db.Column(db.String(30), nullable=False) # AADHAAR, COLLEGE_ID, RESUME, PHOTO
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(30), default='UPLOADED') # NOT_UPLOADED, UPLOADED, UNDER_REVIEW, APPROVED, REJECTED, RE_UPLOAD_REQUIRED
    rejection_reason = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    verifier = db.relationship('User', foreign_keys=[verified_by])

    def __repr__(self):
        return f'<Document {self.doc_type} - {self.status}>'


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    project_code = db.Column(db.String(30), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    domain = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    problem_statement = db.Column(db.Text, nullable=True)
    expected_outcome = db.Column(db.Text, nullable=True)
    objectives_json = db.Column(db.Text, nullable=False)
    tech_stack_json = db.Column(db.Text, nullable=False)
    requirements_json = db.Column(db.Text, nullable=False)
    instructions_md = db.Column(db.Text, nullable=False)
    reference_links_json = db.Column(db.Text, nullable=False)
    duration_weeks = db.Column(db.Integer, default=4) # 4 or 12
    duration_months = db.Column(db.Integer, default=1) # 1 or 3
    difficulty = db.Column(db.String(20), default='Intermediate') # Beginner, Intermediate, Advanced
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship('ProjectAssignment', backref='project', lazy='dynamic')
    project_weeks = db.relationship('ProjectWeek', backref='project', lazy='dynamic', cascade='all, delete-orphan', order_by='ProjectWeek.week_number.asc()')

    @property
    def objectives(self):
        try: return json.loads(self.objectives_json)
        except: return []

    @property
    def tech_stack(self):
        try: return json.loads(self.tech_stack_json)
        except: return []

    @property
    def requirements(self):
        try: return json.loads(self.requirements_json)
        except: return []

    @property
    def reference_links(self):
        try: return json.loads(self.reference_links_json)
        except: return []


class ProjectWeek(db.Model):
    """Reusable project template week structure."""
    __tablename__ = 'project_weeks'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)  # 1..4 or 1..12
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    objective = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    deliverables_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('ProjectTask', backref='week', lazy='dynamic', cascade='all, delete-orphan', order_by='ProjectTask.id.asc()')

    @property
    def deliverables(self):
        try:
            return json.loads(self.deliverables_json) if self.deliverables_json else []
        except:
            return []

    def __repr__(self):
        return f'<ProjectWeek Week {self.week_number}: {self.title}>'


class ProjectTask(db.Model):
    """Reusable task template belonging to a ProjectWeek."""
    __tablename__ = 'project_tasks'

    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey('project_weeks.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    expected_output = db.Column(db.Text, nullable=True)
    priority = db.Column(db.String(20), default='Medium')  # High, Medium, Low
    estimated_hours = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ProjectTask {self.title} ({self.priority})>'


class ProjectAssignment(db.Model):
    __tablename__ = 'project_assignments'

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), default='IN_PROGRESS') # ASSIGNED, IN_PROGRESS, SUBMITTED, REVISION_REQUIRED, UNDER_EVALUATION, PASSED, FAILED, COMPLETED
    repo_url = db.Column(db.String(255), nullable=True)
    live_demo_url = db.Column(db.String(255), nullable=True)
    zip_path = db.Column(db.String(255), nullable=True)
    docs_path = db.Column(db.String(255), nullable=True)
    demo_video_url = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    tech_used = db.Column(db.String(255), nullable=True)
    challenges = db.Column(db.Text, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)

    assigner = db.relationship('User', foreign_keys=[assigned_by])
    evaluation = db.relationship('Evaluation', backref='assignment', uselist=False)
    weekly_milestones = db.relationship('WeeklyMilestone', backref='assignment', lazy='dynamic', cascade='all, delete-orphan', order_by='WeeklyMilestone.week_number.asc()')

    @property
    def progress_percent(self):
        milestones = self.weekly_milestones.all()
        if not milestones:
            return 0
        completed = sum(1 for m in milestones if m.status in ['COMPLETED', 'APPROVED'])
        return int((completed / len(milestones)) * 100)

    @property
    def current_milestone(self):
        milestones = self.weekly_milestones.all()
        for m in milestones:
            if m.status in ['AVAILABLE', 'IN_PROGRESS', 'SUBMITTED', 'UNDER_REVIEW', 'REVISION_REQUIRED']:
                return m
        return milestones[-1] if milestones else None


class WeeklyMilestone(db.Model):
    __tablename__ = 'weekly_milestones'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('project_assignments.id', ondelete='CASCADE'), nullable=False)
    week_number = db.Column(db.Integer, nullable=False) # 1, 2, 3, 4, ...
    title = db.Column(db.String(200), nullable=False)
    objective = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    deliverables_json = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default='LOCKED') # LOCKED, AVAILABLE, IN_PROGRESS, SUBMITTED, UNDER_REVIEW, APPROVED, REVISION_REQUIRED, COMPLETED
    unlocked_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tasks = db.relationship('WeeklyTask', backref='milestone', lazy='dynamic', cascade='all, delete-orphan', order_by='WeeklyTask.order_num.asc()')
    submissions = db.relationship('WeeklySubmission', backref='milestone', lazy='dynamic', cascade='all, delete-orphan', order_by='WeeklySubmission.id.desc()')
    meetings = db.relationship('Meeting', backref='milestone', lazy='dynamic')
    approver = db.relationship('User', foreign_keys=[approved_by])

    @property
    def deliverables(self):
        try:
            return json.loads(self.deliverables_json) if self.deliverables_json else []
        except:
            return []

    @property
    def latest_submission(self):
        return self.submissions.first()

    @property
    def is_locked(self):
        return self.status == 'LOCKED'

    @property
    def is_available(self):
        return self.status in ['AVAILABLE', 'IN_PROGRESS', 'REVISION_REQUIRED', 'SUBMITTED', 'UNDER_REVIEW']

    @property
    def is_completed(self):
        return self.status in ['COMPLETED', 'APPROVED']

    def __repr__(self):
        return f'<WeeklyMilestone Week {self.week_number}: {self.title} ({self.status})>'


class WeeklyTask(db.Model):
    __tablename__ = 'weekly_tasks'

    id = db.Column(db.Integer, primary_key=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey('weekly_milestones.id', ondelete='CASCADE'), nullable=False)
    task_text = db.Column(db.String(255), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    order_num = db.Column(db.Integer, default=1)

    def __repr__(self):
        return f'<WeeklyTask {self.task_text}>'


class WeeklySubmission(db.Model):
    __tablename__ = 'weekly_submissions'

    id = db.Column(db.Integer, primary_key=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey('weekly_milestones.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    repo_url = db.Column(db.String(255), nullable=True)
    live_demo_url = db.Column(db.String(255), nullable=True)
    demo_video_url = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(255), nullable=True)
    submission_notes = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(30), default='SUBMITTED') # SUBMITTED, UNDER_REVIEW, APPROVED, REVISION_REQUIRED
    review_feedback = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship('Student', foreign_keys=[student_id], back_populates='submissions')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<WeeklySubmission Milestone={self.milestone_id} Status={self.status}>'


class Meeting(db.Model):
    __tablename__ = 'meetings'

    id = db.Column(db.Integer, primary_key=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey('weekly_milestones.id'), nullable=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    meeting_date = db.Column(db.String(30), nullable=False)
    meeting_time = db.Column(db.String(30), nullable=False)
    meeting_link = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), default='SCHEDULED') # SCHEDULED, COMPLETED, RESCHEDULED, CANCELLED
    meeting_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', foreign_keys=[student_id], back_populates='meetings')
    internship = db.relationship('Internship', foreign_keys=[internship_id], back_populates='meetings')
    host = db.relationship('User', foreign_keys=[host_id])

    def __repr__(self):
        return f'<Meeting {self.title} ({self.status})>'


class Evaluation(db.Model):
    __tablename__ = 'evaluations'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('project_assignments.id'), nullable=False)
    evaluator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    technical_score = db.Column(db.Integer, default=0) # max 20
    functionality_score = db.Column(db.Integer, default=0) # max 20
    ui_ux_score = db.Column(db.Integer, default=0) # max 15
    documentation_score = db.Column(db.Integer, default=0) # max 15
    demo_score = db.Column(db.Integer, default=0) # max 15
    originality_score = db.Column(db.Integer, default=0) # max 10
    presentation_score = db.Column(db.Integer, default=0) # max 5
    total_score = db.Column(db.Integer, default=0) # max 100
    result = db.Column(db.String(30), nullable=False) # PASSED, NEEDS_IMPROVEMENT, FAILED
    feedback = db.Column(db.Text, nullable=False)
    revision_notes = db.Column(db.Text, nullable=True)
    evaluated_at = db.Column(db.DateTime, default=datetime.utcnow)

    evaluator = db.relationship('User', foreign_keys=[evaluator_id])


class IssuedDocument(db.Model):
    __tablename__ = 'issued_documents'

    id = db.Column(db.Integer, primary_key=True)
    document_no = db.Column(db.String(50), unique=True, nullable=False, index=True) # AM-OFFER-..., AM-CERT-...
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    doc_type = db.Column(db.String(30), nullable=False) # OFFER_LETTER, JOINING_LETTER, CERTIFICATE, EXPERIENCE_LETTER
    template_version = db.Column(db.String(20), default='v1.0')
    file_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='DRAFT') # DRAFT, GENERATED, ISSUED, REVOKED
    issued_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    revocation_reason = db.Column(db.Text, nullable=True)

    issuer = db.relationship('User', foreign_keys=[issued_by])
    student = db.relationship('Student', foreign_keys=[student_id])


class CertificateVerification(db.Model):
    __tablename__ = 'certificate_verifications'

    id = db.Column(db.Integer, primary_key=True)
    certificate_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id'), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    program_title = db.Column(db.String(150), nullable=False)
    duration = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20), nullable=False)
    issue_date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(50), default='Successfully Completed') # Successfully Completed, Revoked
    qr_code_data = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(30), default='INFO') # INFO, SUCCESS, WARNING, ACTION_REQUIRED
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    actor_role = db.Column(db.String(30), default='SYSTEM')
    action = db.Column(db.String(100), nullable=False)
    target_entity = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.String(50), nullable=True)
    details_json = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
