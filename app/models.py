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
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
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
    student_uid = db.Column(db.String(30), unique=True, nullable=False, index=True) # AM-STU-2026-0001
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
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('internship_plans.id'), nullable=False)
    status = db.Column(db.String(30), default='PAYMENT_PENDING') # DRAFT, SUBMITTED, PAYMENT_PENDING, PAID, DOCUMENT_PENDING, UNDER_REVIEW, VERIFIED, REJECTED, APPROVED
    consent_agreed = db.Column(db.Boolean, default=True)
    consent_version = db.Column(db.String(20), default='v1.0-2026')
    consent_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    status = db.Column(db.String(20), default='PENDING') # PENDING, SUCCESSFUL, FAILED, REFUNDED
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
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('internship_plans.id'), nullable=False)
    status = db.Column(db.String(20), default='ACTIVE') # NOT_STARTED, ACTIVE, ON_HOLD, COMPLETED, TERMINATED
    start_date = db.Column(db.String(20), nullable=False)
    end_date = db.Column(db.String(20), nullable=False)
    progress_percent = db.Column(db.Integer, default=0)
    current_stage = db.Column(db.String(50), default='Onboarding')
    mentor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    mentor = db.relationship('User', foreign_keys=[mentor_id])
    assignments = db.relationship('ProjectAssignment', backref='internship', lazy='dynamic')
    issued_documents = db.relationship('IssuedDocument', backref='internship', lazy='dynamic')
    verification = db.relationship('CertificateVerification', backref='internship', uselist=False)

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
    objectives_json = db.Column(db.Text, nullable=False)
    tech_stack_json = db.Column(db.Text, nullable=False)
    requirements_json = db.Column(db.Text, nullable=False)
    instructions_md = db.Column(db.Text, nullable=False)
    reference_links_json = db.Column(db.Text, nullable=False)
    duration_weeks = db.Column(db.Integer, default=4)
    difficulty = db.Column(db.String(20), default='Intermediate') # Beginner, Intermediate, Advanced
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship('ProjectAssignment', backref='project', lazy='dynamic')

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


class ProjectAssignment(db.Model):
    __tablename__ = 'project_assignments'

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), default='ASSIGNED') # NOT_ASSIGNED, ASSIGNED, IN_PROGRESS, SUBMITTED, REVISION_REQUIRED, UNDER_EVALUATION, PASSED, FAILED
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
    status = db.Column(db.String(20), default='ISSUED') # DRAFT, GENERATED, ISSUED, REVOKED
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
