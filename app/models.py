import json
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event
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
    name = db.Column(db.String(100), nullable=True) # Portfolio compatibility
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=False)
    password_changed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, **kwargs):
        if 'full_name' in kwargs and 'name' not in kwargs:
            kwargs['name'] = kwargs['full_name']
        elif 'name' in kwargs and 'full_name' not in kwargs:
            kwargs['full_name'] = kwargs['name']
        super().__init__(**kwargs)

    # Relationships
    student_profile = db.relationship('Student', backref='user', uselist=False, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan', order_by='Notification.id.desc()')
    audit_logs = db.relationship('AuditLog', backref='actor', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash or not password:
            return False

        # 1. Standard Werkzeug hash check (scrypt, pbkdf2:sha256, sha256, etc.)
        try:
            if check_password_hash(self.password_hash, password):
                return True
        except Exception:
            pass

        # 2. Check for bcrypt hash ($2b$, $2a$, $2y$, etc.)
        if isinstance(self.password_hash, str) and self.password_hash.startswith(('$2b$', '$2a$', '$2y$', '$2x$')):
            try:
                import bcrypt
                if bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8')):
                    return True
            except Exception:
                pass

        # 3. Check for raw SHA256 hex digest
        try:
            import hashlib
            if hashlib.sha256(password.encode('utf-8')).hexdigest() == self.password_hash:
                return True
        except Exception:
            pass

        # 4. Fallback if stored as plaintext during temporary credential migration
        if self.password_hash == password:
            return True

        return False

    @property
    def is_admin_or_staff(self):
        return self.role in ['super_admin', 'admin', 'hr', 'mentor', 'evaluator']

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'


@event.listens_for(User, 'before_insert')
@event.listens_for(User, 'before_update')
def sync_user_names(mapper, connection, target):
    """Ensure both name and full_name are populated for cross-system Supabase compatibility."""
    if target.full_name and not target.name:
        target.name = target.full_name
    elif target.name and not target.full_name:
        target.full_name = target.name


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
    student_uid = db.Column(db.String(50), unique=True, nullable=False, index=True) # AM-INT-2026-001 / AM-STU-...
    dob = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(30), nullable=True)
    college_id = db.Column(db.Integer, db.ForeignKey('colleges.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    roll_number = db.Column(db.String(50), nullable=False)
    degree = db.Column(db.String(150), nullable=False)
    current_year = db.Column(db.String(50), nullable=False)
    graduation_year = db.Column(db.String(10), nullable=False)
    aadhaar_masked = db.Column(db.String(30), nullable=True) # XXXX XXXX 4821
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
    candidate_gender = db.Column(db.String(30), nullable=True)
    college_name = db.Column(db.String(200), nullable=True)
    department_name = db.Column(db.String(150), nullable=True)
    course = db.Column(db.String(150), nullable=True)
    year_of_study = db.Column(db.String(50), nullable=True)
    roll_number = db.Column(db.String(50), nullable=True)
    applied_role = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    aadhaar_masked = db.Column(db.String(30), nullable=True)
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
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    transaction_id = db.Column(db.String(50), unique=True, nullable=False, index=True) # AM-TXN-2026-XXXXX
    order_id = db.Column(db.String(100), nullable=False)
    cashfree_order_id = db.Column(db.String(100), nullable=True) # Cashfree gateway / Supabase compatibility
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    status = db.Column(db.String(20), default='SUCCESSFUL') # PENDING, SUCCESSFUL, FAILED, REFUNDED
    payment_method = db.Column(db.String(50), default='ONLINE')
    gateway_response_json = db.Column(db.Text, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        if 'order_id' in kwargs and 'cashfree_order_id' not in kwargs:
            kwargs['cashfree_order_id'] = kwargs['order_id']
        elif 'cashfree_order_id' in kwargs and 'order_id' not in kwargs:
            kwargs['order_id'] = kwargs['cashfree_order_id']
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<Payment {self.transaction_id} - {self.status}>'


@event.listens_for(Payment, 'before_insert')
@event.listens_for(Payment, 'before_update')
def sync_payment_order_ids(mapper, connection, target):
    """Ensure both order_id and cashfree_order_id are populated for cross-system Supabase compatibility."""
    if target.order_id and not target.cashfree_order_id:
        target.cashfree_order_id = target.order_id
    elif target.cashfree_order_id and not target.order_id:
        target.order_id = target.cashfree_order_id


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
                active_m = next((m for m in milestones if m.status in ['AVAILABLE', 'IN_PROGRESS', 'SUBMITTED', 'UNDER_REVIEW', 'REDO_REQUIRED', 'REVISION_REQUIRED']), None)
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
    description = db.Column(db.Text, nullable=True, default='')
    problem_statement = db.Column(db.Text, nullable=True)
    expected_outcome = db.Column(db.Text, nullable=True)
    objectives_json = db.Column(db.Text, nullable=True, default='[]')
    tech_stack_json = db.Column(db.Text, nullable=True, default='[]')
    requirements_json = db.Column(db.Text, nullable=True, default='[]')
    instructions_md = db.Column(db.Text, nullable=True, default='')
    reference_links_json = db.Column(db.Text, nullable=True, default='[]')
    project_type = db.Column(db.String(100), nullable=True) # Real-Time AI/ML Web Application, etc.
    deployment = db.Column(db.String(100), nullable=True) # Localhost, Cloud, etc.
    cloud_required = db.Column(db.Boolean, default=False)
    paid_api_required = db.Column(db.Boolean, default=False)
    github_required = db.Column(db.Boolean, default=True)
    modules_json = db.Column(db.Text, nullable=True)
    restrictions_json = db.Column(db.Text, nullable=True)
    final_deliverable_json = db.Column(db.Text, nullable=True)
    evaluation_json = db.Column(db.Text, nullable=True)
    source_json = db.Column(db.Text, nullable=True)
    source_json_name = db.Column(db.String(255), nullable=True)
    duration_weeks = db.Column(db.Integer, default=4) # 4 or 12
    duration_months = db.Column(db.Integer, default=1) # 1 or 3
    difficulty = db.Column(db.String(50), default='Intermediate') # Beginner, Intermediate, Advanced, Easy to Medium, etc.
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignments = db.relationship('ProjectAssignment', backref='project', lazy='dynamic')
    project_weeks = db.relationship('ProjectWeek', backref='project', lazy='dynamic', cascade='all, delete-orphan', order_by='ProjectWeek.week_number.asc()')

    @property
    def problem_id(self):
        """Alias for project_code ensuring seamless Problem ID compatibility."""
        return self.project_code

    @problem_id.setter
    def problem_id(self, val):
        self.project_code = val

    @property
    def project_title(self):
        return self.title

    @project_title.setter
    def project_title(self, val):
        self.title = val

    @property
    def level(self):
        return self.difficulty

    @level.setter
    def level(self, val):
        self.difficulty = val

    @property
    def duration_display(self):
        return f"{self.duration_months} Month{'s' if self.duration_months > 1 else ''}"

    @property
    def status(self):
        return 'ACTIVE' if self.is_active else 'INACTIVE'

    @status.setter
    def status(self, val):
        if isinstance(val, bool):
            self.is_active = val
        else:
            self.is_active = (str(val).upper() == 'ACTIVE')

    @property
    def total_weeks(self):
        return self.duration_weeks or (4 if self.duration_months == 1 else 12)

    @property
    def total_tasks_count(self):
        try:
            return sum(w.tasks.count() for w in self.project_weeks.all())
        except Exception:
            return 0

    @property
    def active_colleges_count(self):
        """Count of distinct colleges with active assignments for this project."""
        try:
            from app.models import Student, Internship, ProjectAssignment
            count = db.session.query(Student.college_id).join(
                Internship, Internship.student_id == Student.id
            ).join(
                ProjectAssignment, ProjectAssignment.internship_id == Internship.id
            ).filter(
                ProjectAssignment.project_id == self.id,
                ProjectAssignment.status.in_(['ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'REVISION_REQUIRED', 'UNDER_EVALUATION', 'ACTIVE']),
                Internship.status == 'ACTIVE'
            ).distinct().count()
            return count
        except Exception:
            return 0

    @property
    def total_colleges_count(self):
        """Count of distinct colleges with any assignments for this project."""
        try:
            from app.models import Student, Internship, ProjectAssignment
            count = db.session.query(Student.college_id).join(
                Internship, Internship.student_id == Student.id
            ).join(
                ProjectAssignment, ProjectAssignment.internship_id == Internship.id
            ).filter(
                ProjectAssignment.project_id == self.id
            ).distinct().count()
            return count
        except Exception:
            return 0

    @property
    def objectives(self):
        try: return json.loads(self.objectives_json) if self.objectives_json else []
        except: return []

    @property
    def tech_stack(self):
        try: return json.loads(self.tech_stack_json) if self.tech_stack_json else []
        except: return []

    @property
    def requirements(self):
        try: return json.loads(self.requirements_json) if self.requirements_json else []
        except: return []

    @property
    def reference_links(self):
        try: return json.loads(self.reference_links_json) if self.reference_links_json else []
        except: return []

    @property
    def modules(self):
        try: return json.loads(self.modules_json) if self.modules_json else []
        except: return []

    @property
    def restrictions(self):
        try: return json.loads(self.restrictions_json) if self.restrictions_json else []
        except: return []

    @property
    def final_deliverable(self):
        try: return json.loads(self.final_deliverable_json) if self.final_deliverable_json else {}
        except: return {}

    @property
    def evaluation(self):
        try: return json.loads(self.evaluation_json) if self.evaluation_json else {}
        except: return {}


class ProjectWeek(db.Model):
    """Reusable project template week structure."""
    __tablename__ = 'project_weeks'
    __table_args__ = (db.UniqueConstraint('project_id', 'week_number', name='uq_project_week'),)

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)  # 1..4 or 1..12
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    objective = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    deliverables_json = db.Column(db.Text, nullable=True)

    # Extended metadata from task plan JSON
    phase_number = db.Column(db.Integer, nullable=True) # 1..4 for 3-Month projects
    phase_title = db.Column(db.String(200), nullable=True)
    weeks_label = db.Column(db.String(50), nullable=True) # "1-3", "4-6", etc.
    completion_percentage = db.Column(db.String(20), nullable=True) # "25%", "50%", etc.
    goal = db.Column(db.Text, nullable=True)
    expected_features_json = db.Column(db.Text, nullable=True)
    demo_output_json = db.Column(db.Text, nullable=True)
    github_requirement = db.Column(db.Text, nullable=True)
    completion_condition = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('ProjectTask', backref='week', lazy='dynamic', cascade='all, delete-orphan', order_by='ProjectTask.order_num.asc(), ProjectTask.id.asc()')

    @property
    def deliverables(self):
        try:
            return json.loads(self.deliverables_json) if self.deliverables_json else []
        except:
            return []

    @property
    def expected_features(self):
        try:
            return json.loads(self.expected_features_json) if self.expected_features_json else []
        except:
            return []

    @property
    def demo_output(self):
        try:
            return json.loads(self.demo_output_json) if self.demo_output_json else {}
        except:
            return {}

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
    order_num = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ProjectTask {self.title} ({self.priority})>'


class TaskImportHistory(db.Model):
    """Audit log of all uploaded JSON task plans."""
    __tablename__ = 'task_import_history'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    project_code = db.Column(db.String(50), nullable=True) # Problem ID
    project_title = db.Column(db.String(200), nullable=False)
    domain = db.Column(db.String(100), nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)
    total_weeks = db.Column(db.Integer, default=4)
    total_tasks = db.Column(db.Integer, default=0)
    imported_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String(30), default='IMPORTED') # IMPORTED, UPDATED, FAILED
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    importer = db.relationship('User', foreign_keys=[imported_by])
    project = db.relationship('Project', foreign_keys=[project_id])

    @property
    def duration_display(self):
        return f"{self.duration_months} Month{'s' if self.duration_months > 1 else ''}"

    def __repr__(self):
        return f'<TaskImportHistory {self.filename} -> {self.project_code} ({self.status})>'


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
    status = db.Column(db.String(30), default='LOCKED') # LOCKED, AVAILABLE, IN_PROGRESS, SUBMITTED, UNDER_REVIEW, APPROVED, REDO_REQUIRED, REVISION_REQUIRED, COMPLETED
    started_at = db.Column(db.DateTime, nullable=True)
    due_at = db.Column(db.DateTime, nullable=True)
    unlocked_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tasks = db.relationship('WeeklyTask', backref='milestone', lazy='dynamic', cascade='all, delete-orphan', order_by='WeeklyTask.order_num.asc()')
    submissions = db.relationship('WeeklySubmission', backref='milestone', lazy='dynamic', cascade='all, delete-orphan', order_by='WeeklySubmission.id.desc()')
    evaluations = db.relationship('Evaluation', backref='milestone', lazy='dynamic')
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
    def is_overdue(self):
        if self.due_at and self.status not in ['COMPLETED', 'APPROVED', 'SUBMITTED', 'UNDER_REVIEW']:
            return datetime.utcnow() > self.due_at
        return False

    @property
    def display_status(self):
        norm = (self.status or '').upper()
        if norm in ['COMPLETED', 'APPROVED']:
            return 'COMPLETED'
        if norm in ['SUBMITTED', 'UNDER_REVIEW']:
            return 'UNDER_REVIEW'
        if norm in ['REDO_REQUIRED', 'REVISION_REQUIRED']:
            return 'REDO_REQUIRED'
        if norm == 'LOCKED':
            return 'LOCKED'
        if norm in ['AVAILABLE', 'IN_PROGRESS']:
            if self.is_overdue:
                return 'OVERDUE'
            return norm
        return norm

    @property
    def all_tasks_completed(self):
        task_list = self.tasks.all()
        if not task_list:
            return True
        return all(t.is_completed for t in task_list)

    @property
    def completed_tasks_count(self):
        return sum(1 for t in self.tasks.all() if t.is_completed)

    @property
    def total_tasks_count(self):
        return self.tasks.count()

    @property
    def is_available(self):
        return self.status in ['AVAILABLE', 'IN_PROGRESS', 'REVISION_REQUIRED', 'REDO_REQUIRED', 'SUBMITTED', 'UNDER_REVIEW']

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
    github_url = db.Column(db.String(255), nullable=True)
    live_demo_url = db.Column(db.String(255), nullable=True)
    demo_video_url = db.Column(db.String(255), nullable=True)
    demo_video_path = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(255), nullable=True)
    submission_notes = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(30), default='SUBMITTED') # SUBMITTED, UNDER_REVIEW, APPROVED, REDO_REQUIRED, REVISION_REQUIRED, COMPLETED
    review_feedback = db.Column(db.Text, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship('Student', foreign_keys=[student_id], back_populates='submissions')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    evaluations = db.relationship('Evaluation', backref='submission', lazy='dynamic', cascade='all, delete-orphan', order_by='Evaluation.id.desc()')

    @property
    def effective_repo_url(self):
        return self.github_url or self.repo_url or ''

    @property
    def effective_video_path(self):
        return self.demo_video_path or self.file_path or self.demo_video_url or ''

    @property
    def admin_remarks(self):
        return self.review_feedback or (self.milestone.admin_notes if self.milestone else '')

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
    assignment_id = db.Column(db.Integer, db.ForeignKey('project_assignments.id', ondelete='CASCADE'), nullable=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('weekly_submissions.id', ondelete='CASCADE'), nullable=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey('weekly_milestones.id', ondelete='CASCADE'), nullable=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    evaluator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=True) # REDO, VERIFY, PROCEED_TO_NEXT
    remarks = db.Column(db.Text, nullable=True)
    technical_score = db.Column(db.Integer, default=0) # max 20
    functionality_score = db.Column(db.Integer, default=0) # max 20
    ui_ux_score = db.Column(db.Integer, default=0) # max 15
    documentation_score = db.Column(db.Integer, default=0) # max 15
    demo_score = db.Column(db.Integer, default=0) # max 15
    originality_score = db.Column(db.Integer, default=0) # max 10
    presentation_score = db.Column(db.Integer, default=0) # max 5
    total_score = db.Column(db.Integer, default=0) # max 100
    result = db.Column(db.String(30), nullable=True) # PASSED, NEEDS_IMPROVEMENT, FAILED
    feedback = db.Column(db.Text, nullable=True)
    revision_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    evaluated_at = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship('User', foreign_keys=[admin_id])
    evaluator = db.relationship('User', foreign_keys=[evaluator_id])
    employee = db.relationship('Student', foreign_keys=[employee_id])


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
