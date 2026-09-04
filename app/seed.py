import json
import logging
from datetime import datetime, timedelta
from app.extensions import db
from app.models import (
    User, College, Department, Student, InternshipPlan,
    Application, Payment, Internship, Project, ProjectAssignment,
    ProjectWeek, ProjectTask,
    WeeklyMilestone, WeeklyTask, WeeklySubmission, Meeting,
    CertificateVerification, Notification
)

logger = logging.getLogger(__name__)


def seed_internship_plans():
    """Seed default 1-Month and 3-Month internship plans if not already present."""
    plan_1m = InternshipPlan.query.filter_by(plan_code='1_MONTH_PROJECT').first()
    if not plan_1m:
        plan_1m = InternshipPlan(
            plan_code='1_MONTH_PROJECT',
            title='1 Month Project Internship',
            duration_months=1,
            fee=1499.00,
            currency='INR',
            description='Fast-paced, project-intensive program designed for students seeking practical portfolio building.',
            features_json=json.dumps([
                'Curated Industry Project Assignment',
                'Anti Matrix Student Portal Access',
                'Structured Project Instructions & Resources',
                'Weekly Milestone Progression & Mentorship',
                'Source Code & Live Deployment Submission',
                'Demo Video Submission & Evaluation',
                'Official Anti Matrix Completion Certificate',
                'Public QR Verification Link'
            ]),
            badge='Fast-Track Project Track',
            is_active=True
        )
        db.session.add(plan_1m)

    plan_3m = InternshipPlan.query.filter_by(plan_code='3_MONTH_PROFESSIONAL').first()
    if not plan_3m:
        plan_3m = InternshipPlan(
            plan_code='3_MONTH_PROFESSIONAL',
            title='3 Month Professional Internship',
            duration_months=3,
            fee=3999.00,
            currency='INR',
            description='Comprehensive industrial internship with official onboarding, document verification, monthly milestone tracking, and experience credentials.',
            features_json=json.dumps([
                'Complete Academic & Identity Verification',
                'Official Anti Matrix Offer Letter',
                'Official Joining Letter with Internship ID',
                'Enterprise-Grade Industry Project Assignment',
                '12-Week Structured Milestone Roadmap',
                'Dedicated Technical Mentor & Review Process',
                'Weekly Code Reviews & 1-on-1 Milestone Evaluations',
                'Final Codebase & Technical Documentation Submission',
                'Official Anti Matrix Completion Certificate',
                'Official Experience / Internship Letter',
                'Tamper-Proof QR Certificate Verification'
            ]),
            badge='Enterprise Professional Track',
            is_active=True
        )
        db.session.add(plan_3m)

    db.session.commit()


def seed_colleges_and_departments():
    """Seed master colleges and departments if not present."""
    if not College.query.first():
        college_data = [
            {
                'code': 'IITM',
                'name': 'Indian Institute of Technology Madras',
                'state': 'Tamil Nadu',
                'city': 'Chennai',
                'depts': ['Computer Science and Engineering', 'Information Technology', 'Electronics and Communication', 'Data Science & AI', 'Mechanical Engineering']
            },
            {
                'code': 'NITK',
                'name': 'National Institute of Technology Karnataka',
                'state': 'Karnataka',
                'city': 'Surathkal',
                'depts': ['Computer Science and Engineering', 'Information Technology', 'Electronics and Communication', 'Artificial Intelligence', 'Electrical Engineering']
            },
            {
                'code': 'ANNA-CEG',
                'name': 'College of Engineering, Guindy (Anna University)',
                'state': 'Tamil Nadu',
                'city': 'Chennai',
                'depts': ['Computer Science and Engineering', 'Information Technology', 'Electronics and Communication', 'Electrical and Electronics', 'Mechanical Engineering']
            },
            {
                'code': 'PSG-TECH',
                'name': 'PSG College of Technology',
                'state': 'Tamil Nadu',
                'city': 'Coimbatore',
                'depts': ['Computer Science and Engineering', 'Information Technology', 'Software Engineering', 'Robotics & Automation']
            },
            {
                'code': 'VIT-VELLORE',
                'name': 'Vellore Institute of Technology',
                'state': 'Tamil Nadu',
                'city': 'Vellore',
                'depts': ['Computer Science and Engineering', 'Information Technology', 'Cyber Security', 'AI & Machine Learning']
            },
            {
                'code': 'SRM-KTR',
                'name': 'SRM Institute of Science and Technology',
                'state': 'Tamil Nadu',
                'city': 'Kattankulathur',
                'depts': ['Computer Science and Engineering', 'Information Technology', 'Cloud Computing', 'Data Analytics']
            },
            {
                'code': 'VELAMMAL',
                'name': 'Velammal Institute of Technology',
                'state': 'Tamil Nadu',
                'city': 'Chennai',
                'depts': ['Computer Science and Engineering', 'Information Technology', 'Electronics and Communication', 'Artificial Intelligence']
            },
            {
                'code': 'JAYA',
                'name': 'Jaya College of Engineering & Technology',
                'state': 'Tamil Nadu',
                'city': 'Chennai',
                'depts': ['Computer Science and Engineering', 'Information Technology', 'Mechanical Engineering']
            },
            {
                'code': 'OTHER-COLLEGE',
                'name': 'Other Autonomous / University College',
                'state': 'India',
                'city': 'All Cities',
                'depts': ['Computer Science and Engineering', 'Information Technology', 'Electronics and Communication', 'Mechanical Engineering', 'Other']
            }
        ]

        for c in college_data:
            col = College(code=c['code'], name=c['name'], state=c['state'], city=c['city'])
            db.session.add(col)
            db.session.flush()

            for d in c['depts']:
                dept = Department(college_id=col.id, code=d[:4].upper(), name=d)
                db.session.add(dept)

        db.session.commit()


def seed_projects_and_students():
    """Seed master projects, staff accounts, and demo enrolled students with weekly roadmaps."""
    col = College.query.first()
    dept = Department.query.filter_by(college_id=col.id).first() if col else None

    # 1. Staff Users
    admin = User.query.filter_by(email='admin@antimatrix.com').first()
    if not admin:
        admin = User(
            email='admin@antimatrix.com',
            employee_id='AM-ADM-001',
            role='super_admin',
            full_name='Anti Matrix Super Admin',
            phone='+91 98765 43210'
        )
        admin.set_password('Admin@2026Password!')
        db.session.add(admin)
        db.session.flush()

    mentor = User.query.filter_by(email='mentor@antimatrix.com').first()
    if not mentor:
        mentor = User(
            email='mentor@antimatrix.com',
            employee_id='AM-MTR-001',
            role='mentor',
            full_name='Dr. Rajesh Sharma (Lead Architect)',
            phone='+91 98765 43212'
        )
        mentor.set_password('Mentor@2026Password!')
        db.session.add(mentor)
        db.session.flush()

    # 2. Master Projects
    proj_1 = Project.query.filter_by(project_code='AM-PRJ-001').first()
    if not proj_1:
        proj_1 = Project(
            project_code='AM-PRJ-001',
            title='AI-Based Student Performance Analysis System',
            domain='Artificial Intelligence & Data Science',
            description='Design and implement an intelligent predictive system that analyzes student academic histories, behavioral patterns, and attendance records to forecast examination performance and identify at-risk students.',
            problem_statement='Educational institutions often lack early warning mechanisms to detect declining student engagement before examinations. This project solves that by building machine learning models that generate actionable intervention insights for educators.',
            expected_outcome='A fully functional full-stack web application featuring predictive risk scoring, feature importance visualization, responsive student scorecards, and an automated report generation pipeline.',
            objectives_json=json.dumps([
                'Perform exploratory data analysis and feature engineering on multi-dimensional academic datasets.',
                'Train and benchmark supervised learning models (Random Forest, XGBoost, Logistic Regression).',
                'Develop a secure RESTful API backend using Python Flask.',
                'Create an intuitive, responsive analytics dashboard with chart visualizers.'
            ]),
            tech_stack_json=json.dumps(['Python', 'Flask', 'Scikit-Learn', 'Pandas', 'NumPy', 'HTML5/CSS3', 'Chart.js', 'SQLite/PostgreSQL']),
            requirements_json=json.dumps([
                'Prediction accuracy > 85% with documented evaluation metrics (RMSE, Precision, Recall).',
                'Sub-100ms API inference response latency.',
                'Clean modular code structure adhering to PEP 8 standards.',
                'Comprehensive README with installation, API schema, and execution instructions.'
            ]),
            instructions_md='Follow the 4-week structured milestone roadmap. Each week requires you to complete the specified tasks, document your progress, and submit deliverables before the weekly mentor evaluation.',
            reference_links_json=json.dumps([
                {'title': 'Scikit-Learn Machine Learning Guide', 'url': 'https://scikit-learn.org/stable/'},
                {'title': 'Flask Web Development Documentation', 'url': 'https://flask.palletsprojects.com/'}
            ]),
            duration_weeks=4,
            difficulty='Intermediate'
        )
        db.session.add(proj_1)
        db.session.flush()

    proj_2 = Project.query.filter_by(project_code='AM-PRJ-002').first()
    if not proj_2:
        proj_2 = Project(
            project_code='AM-PRJ-002',
            title='Autonomous Cloud Microservices Security Gateway',
            domain='Cyber Security & Cloud Computing',
            description='Design and deploy a high-performance Zero-Trust API gateway featuring rate limiting, JWT token introspection, anomaly detection, and automated threat mitigations.',
            problem_statement='Microservice architectures expose numerous internal endpoints that are susceptible to credential stuffing, unauthorized data scraping, and DDoS attacks without centralized edge security.',
            expected_outcome='An enterprise-ready cloud API gateway that validates cryptographic tokens, applies dynamic rate limits, logs audit events, and blocks suspicious traffic in real time.',
            objectives_json=json.dumps([
                'Implement HMAC request signing and OAuth2/JWT token verification.',
                'Deploy Redis-backed token bucket rate limiting algorithms.',
                'Build real-time health and threat monitoring analytics dashboards.',
                'Automate IP blacklisting based on anomaly score thresholds.'
            ]),
            tech_stack_json=json.dumps(['Python', 'Flask', 'Redis', 'Docker', 'PostgreSQL', 'HTML5', 'CSS3']),
            requirements_json=json.dumps([
                'Sub-50ms latency overhead on proxied HTTP requests.',
                'Unit test coverage > 85% across authentication and rate-limiting modules.',
                'Detailed OpenAPI / Swagger documentation.'
            ]),
            instructions_md='Execute the 12-week comprehensive roadmap. Complete monthly milestone reviews with your assigned mentor to unlock subsequent phases.',
            reference_links_json=json.dumps([
                {'title': 'NIST Zero Trust Architecture Guidelines', 'url': 'https://csrc.nist.gov'}
            ]),
            duration_weeks=12,
            difficulty='Advanced'
        )
        db.session.add(proj_2)
        db.session.flush()

    # 3. Demo Student 1: Aarav Kumar (1-Month Track, Project 1)
    student1_user = User.query.filter_by(email='aarav.kumar@example.com').first()
    if not student1_user:
        student1_user = User(
            email='aarav.kumar@example.com',
            employee_id='AM-INT-2026-001',
            role='student',
            full_name='Aarav Kumar',
            phone='+91 98765 00184'
        )
        student1_user.set_password('Student@2026Password!')
        db.session.add(student1_user)
        db.session.flush()

        student1 = Student(
            user_id=student1_user.id,
            student_uid='AM-INT-2026-001',
            dob='2003-08-15',
            gender='Male',
            college_id=col.id if col else 1,
            department_id=dept.id if dept else 1,
            roll_number='21CS048',
            degree='B.Tech / B.E (Computer Science)',
            current_year='3rd Year',
            graduation_year='2026',
            aadhaar_masked='XXXX XXXX 4821',
            is_verified=True
        )
        db.session.add(student1)
        db.session.flush()

        plan_1m = InternshipPlan.query.filter_by(plan_code='1_MONTH_PROJECT').first()

        internship1 = Internship(
            internship_no='AM-INT-2026-001',
            student_id=student1.id,
            plan_id=plan_1m.id if plan_1m else 1,
            status='ACTIVE',
            start_date='01 Sep 2026',
            end_date='30 Sep 2026',
            progress_percent=0,
            current_stage='Week 1 Understanding & Planning',
            mentor_id=mentor.id
        )
        db.session.add(internship1)
        db.session.flush()

        assign1 = ProjectAssignment(
            internship_id=internship1.id,
            project_id=proj_1.id,
            assigned_by=admin.id,
            deadline='30 Sep 2026',
            status='IN_PROGRESS',
            description='Developing AI-Based Student Performance Analysis System for academic risk mitigation.'
        )
        db.session.add(assign1)
        db.session.flush()

        # Seed 4 Weekly Milestones for Student 1
        milestone_definitions_1 = [
            {
                'week': 1,
                'title': 'Project Understanding, Architecture & Data Modeling',
                'objective': 'Analyze academic dataset schemas, understand predictive evaluation metrics, and formulate multi-tier system architecture and data models.',
                'instructions': 'Review the problem statement and dataset schema. Perform preliminary exploratory data analysis in Python. Draft the Technical Design Document (TDD) including database ER diagrams and component architecture. Complete all tasks below and submit deliverables for mentor evaluation.',
                'deliverables': ['System Architecture & Technical Design Document (PDF)', 'Dataset Exploratory Data Analysis Notebook (.ipynb)', 'Sprint Milestone Execution Plan'],
                'status': 'AVAILABLE',
                'tasks': [
                    'Understand project requirements & domain problem statement',
                    'Study required technologies (Python, Flask, Scikit-learn, Pandas)',
                    'Perform Exploratory Data Analysis (EDA) on student performance dataset',
                    'Prepare system architecture & Entity-Relationship (ER) diagram',
                    'Create sprint execution plan & setup Git version control'
                ]
            },
            {
                'week': 2,
                'title': 'Data Preprocessing & Machine Learning Model Pipeline',
                'objective': 'Implement data cleaning pipelines, feature engineering techniques, and train predictive machine learning models for risk classification.',
                'instructions': 'Develop automated data normalization routines. Train multiple classification and regression algorithms (Random Forest, XGBoost, Logistic Regression). Document accuracy, precision, recall, and F1-score benchmarks.',
                'deliverables': ['Trained Model Artifacts (.pkl)', 'Model Evaluation & Benchmark Comparison Report', 'Data Preprocessing Pipeline Module'],
                'status': 'LOCKED',
                'tasks': [
                    'Implement data imputation and categorical encoding pipeline',
                    'Develop feature extraction and correlation analysis scripts',
                    'Train baseline and advanced supervised learning models',
                    'Conduct hyperparameter tuning with cross-validation',
                    'Serialize final optimized model pipeline'
                ]
            },
            {
                'week': 3,
                'title': 'RESTful API Backend & Interactive Analytics UI',
                'objective': 'Build Flask REST endpoints for model inference and develop a modern, responsive web dashboard with scorecards and visualization charts.',
                'instructions': 'Implement secure API routes accepting input parameters and returning prediction risk scores with confidence intervals. Build Jinja2/HTML5 views with Chart.js charts showing performance trends.',
                'deliverables': ['Flask Backend API Modules', 'Interactive Frontend UI Templates & Styles', 'API Testing Collection & Documentation'],
                'status': 'LOCKED',
                'tasks': [
                    'Create Flask API endpoints for real-time model inference',
                    'Design responsive dashboard UI cards and metric badges',
                    'Integrate Chart.js visualizations for grade distribution',
                    'Add input validation, security sanitization, and error handling'
                ]
            },
            {
                'week': 4,
                'title': 'Testing, Deployment, Demonstration & Defense',
                'objective': 'Perform test verification, deploy live web demo, record technical video walkthrough, and prepare final project defense.',
                'instructions': 'Execute comprehensive unit test suites. Deploy the live web application to cloud hosting. Record a 5-minute video walkthrough demonstrating architecture and live prediction results.',
                'deliverables': ['Public GitHub Repository URL', 'Live Deployed Web Demo URL', '5-Minute Demonstration Video Link', 'Final Comprehensive Technical Report'],
                'status': 'LOCKED',
                'tasks': [
                    'Write automated unit and integration test suites',
                    'Deploy application to cloud hosting environment',
                    'Record 5-minute video walkthrough explaining architecture & demo',
                    'Submit final GitHub repository with comprehensive README'
                ]
            }
        ]

        now = datetime.utcnow()
        for m_data in milestone_definitions_1:
            is_avail = (m_data['status'] == 'AVAILABLE')
            m = WeeklyMilestone(
                assignment_id=assign1.id,
                week_number=m_data['week'],
                title=f"Week {m_data['week']}: {m_data['title']}",
                objective=m_data['objective'],
                instructions=m_data['instructions'],
                deliverables_json=json.dumps(m_data['deliverables']),
                status=m_data['status'],
                started_at=now if is_avail else None,
                due_at=(now + timedelta(days=7)) if is_avail else None,
                unlocked_at=now if is_avail else None
            )
            db.session.add(m)
            db.session.flush()

            for idx, task_text in enumerate(m_data['tasks'], start=1):
                t = WeeklyTask(
                    milestone_id=m.id,
                    task_text=task_text,
                    is_completed=False,
                    order_num=idx
                )
                db.session.add(t)

        # Scheduled evaluation meeting for Week 1
        w1_m = WeeklyMilestone.query.filter_by(assignment_id=assign1.id, week_number=1).first()
        meeting1 = Meeting(
            milestone_id=w1_m.id if w1_m else None,
            internship_id=internship1.id,
            student_id=student1.id,
            host_id=mentor.id,
            title='Week 1 Milestone Evaluation & Architecture Review',
            meeting_date='10 Sep 2026',
            meeting_time='03:00 PM IST',
            meeting_link='https://meet.google.com/ant-matx-rev',
            status='SCHEDULED',
            meeting_notes='Please have your architecture diagram and exploratory data analysis notebook ready for review.'
        )
        db.session.add(meeting1)

        # Notifications
        notif1 = Notification(
            user_id=student1_user.id,
            title='Welcome to Anti Matrix Internship Portal',
            message='Your 1-Month Project Track is active. Your assigned project is: AI-Based Student Performance Analysis System.',
            type='SUCCESS',
            link='/project'
        )
        notif2 = Notification(
            user_id=student1_user.id,
            title='Week 1 Milestone is Available',
            message='Week 1 (Project Understanding, Architecture & Data Modeling) is unlocked. Review tasks and prepare your submission.',
            type='INFO',
            link='/week/' + str(w1_m.id if w1_m else 1)
        )
        db.session.add(notif1)
        db.session.add(notif2)

    # 4. Demo Student 2: Sneha Patel (3-Month Track, Project 2)
    student2_user = User.query.filter_by(email='sneha.patel@example.com').first()
    if not student2_user:
        student2_user = User(
            email='sneha.patel@example.com',
            employee_id='AM-INT-2026-002',
            role='student',
            full_name='Sneha Patel',
            phone='+91 98765 00185'
        )
        student2_user.set_password('Student@2026Password!')
        db.session.add(student2_user)
        db.session.flush()

        student2 = Student(
            user_id=student2_user.id,
            student_uid='AM-INT-2026-002',
            dob='2002-11-20',
            gender='Female',
            college_id=col.id if col else 1,
            department_id=dept.id if dept else 1,
            roll_number='21IT092',
            degree='B.Tech / B.E (Information Technology)',
            current_year='4th Year / Final Year',
            graduation_year='2026',
            aadhaar_masked='XXXX XXXX 9124',
            is_verified=True
        )
        db.session.add(student2)
        db.session.flush()

        plan_3m = InternshipPlan.query.filter_by(plan_code='3_MONTH_PROFESSIONAL').first()

        internship2 = Internship(
            internship_no='AM-INT-2026-002',
            student_id=student2.id,
            plan_id=plan_3m.id if plan_3m else 2,
            status='ACTIVE',
            start_date='01 Sep 2026',
            end_date='30 Nov 2026',
            progress_percent=0,
            current_stage='Week 1 Architecture Analysis',
            mentor_id=mentor.id
        )
        db.session.add(internship2)
        db.session.flush()

        assign2 = ProjectAssignment(
            internship_id=internship2.id,
            project_id=proj_2.id,
            assigned_by=admin.id,
            deadline='30 Nov 2026',
            status='IN_PROGRESS',
            description='Developing Autonomous Cloud Microservices Security Gateway.'
        )
        db.session.add(assign2)
        db.session.flush()

        # Seed 12 Weekly Milestones for Student 2
        titles_3m = [
            'Enterprise Architecture & Security Threat Modeling',
            'Token Validation Engine & JWT HMAC Verification',
            'Redis Token Bucket Rate-Limiting Implementation',
            'Month 1 Milestone Review & Security Benchmark Defense',
            'Dynamic Circuit Breaker & Resiliency Handlers',
            'Centralized Audit Logging & SIEM Event Pipeline',
            'Intrusion Anomaly Detection Algorithm Integration',
            'Month 2 Milestone Review & Resiliency Testing',
            'Admin Security Dashboard & Live Telemetry UI',
            'Docker Containerization & Kubernetes Orchestration Setup',
            'End-to-End Penetration Testing & Vulnerability Hardening',
            'Final Demonstration Defense & Technical Documentation'
        ]

        for w_num, w_title in enumerate(titles_3m, start=1):
            is_avail = (w_num == 1)
            m = WeeklyMilestone(
                assignment_id=assign2.id,
                week_number=w_num,
                title=f"Week {w_num}: {w_title}",
                objective=f"Execute Phase {w_num} objectives for Autonomous Cloud Security Gateway.",
                instructions=f"Complete Week {w_num} deliverables and verify with unit tests.",
                deliverables_json=json.dumps([f"Week {w_num} Technical Artifacts", "Implementation Source Code"]),
                status='AVAILABLE' if is_avail else 'LOCKED',
                started_at=now if is_avail else None,
                due_at=(now + timedelta(days=7)) if is_avail else None,
                unlocked_at=now if is_avail else None
            )
            db.session.add(m)
            db.session.flush()

            t = WeeklyTask(
                milestone_id=m.id,
                task_text=f"Implement core specifications for Week {w_num}: {w_title}",
                is_completed=False,
                order_num=1
            )
            db.session.add(t)

        notif_s2 = Notification(
            user_id=student2_user.id,
            title='Welcome to 3-Month Professional Internship Track',
            message='Your 12-week roadmap for Autonomous Cloud Microservices Security Gateway is initialized.',
            type='SUCCESS',
            link='/project'
        )
        db.session.add(notif_s2)

    db.session.commit()


def seed_initial_data():
    """Safely and idempotently seed all required initial data."""
    try:
        seed_internship_plans()
        seed_colleges_and_departments()
        seed_admin_user()
        seed_projects_and_students()
        seed_project_weeks_and_tasks()
        seed_career_applications()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during database seed: {e}")
        raise e


def seed_admin_user():
    """Seed the primary admin user with Admin@12345 password (idempotent)."""
    # Support login by 'admin' as employee_id
    admin = User.query.filter_by(employee_id='admin').first()
    if not admin:
        admin = User(
            email='admin@antimatrix.tech',
            employee_id='admin',
            role='super_admin',
            full_name='Anti Matrix Administrator',
            phone='+91 00000 00001',
            is_active=True
        )
        admin.set_password('Admin@12345')
        db.session.add(admin)
        db.session.commit()
        logger.info('Default admin user seeded with ID=admin password=Admin@12345')


def seed_career_applications():
    """Seed standalone career application records for admin lookup testing."""
    plan_1m = InternshipPlan.query.filter_by(plan_code='1_MONTH_PROJECT').first()
    plan_3m = InternshipPlan.query.filter_by(plan_code='3_MONTH_PROFESSIONAL').first()

    apps_data = [
        {
            'application_no': 'AM-APP-2026-1024',
            'candidate_name': 'Rahul Kumar',
            'candidate_email': 'rahul@example.com',
            'candidate_phone': '+91 98412 01024',
            'candidate_dob': '2002-05-14',
            'candidate_gender': 'Male',
            'college_name': 'Velammal Institute of Technology',
            'department_name': 'Computer Science and Engineering',
            'course': 'B.Tech Computer Science',
            'year_of_study': '3rd Year',
            'roll_number': '21CS1024',
            'applied_role': 'AI Engineer Intern',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'aadhaar_masked': 'XXXX XXXX 4827',
            'status': 'APPROVED',
            'plan_id': plan_3m.id if plan_3m else None,
            'converted_employee_id': 'AM4827',
            'is_converted_to_employee': False,
            'has_payment': True
        },
        {
            'application_no': 'AM-APP-2026-001',
            'candidate_name': 'Rahul Kumar',
            'candidate_email': 'rahul.kumar2026@gmail.com',
            'candidate_phone': '+91 98412 00001',
            'candidate_dob': '2002-03-15',
            'candidate_gender': 'Male',
            'college_name': 'Indian Institute of Technology Madras',
            'department_name': 'Computer Science and Engineering',
            'course': 'B.Tech Computer Science',
            'year_of_study': '3rd Year',
            'roll_number': '20CS101',
            'applied_role': 'Python Flask Developer Intern',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'aadhaar_masked': 'XXXX XXXX 1234',
            'status': 'APPROVED',
            'plan_id': plan_1m.id if plan_1m else None,
            'converted_employee_id': None,
            'is_converted_to_employee': False,
            'has_payment': True
        },
        {
            'application_no': 'AM-APP-2026-002',
            'candidate_name': 'Priya Sharma',
            'candidate_email': 'priya.sharma2026@gmail.com',
            'candidate_phone': '+91 98412 00002',
            'candidate_dob': '2001-11-22',
            'candidate_gender': 'Female',
            'college_name': 'Vellore Institute of Technology',
            'department_name': 'Artificial Intelligence & Machine Learning',
            'course': 'B.Tech AI & ML',
            'year_of_study': '4th Year / Final Year',
            'roll_number': '19AI055',
            'applied_role': 'AI & Data Science Intern',
            'city': 'Vellore',
            'state': 'Tamil Nadu',
            'aadhaar_masked': 'XXXX XXXX 5678',
            'status': 'APPROVED',
            'plan_id': plan_3m.id if plan_3m else None,
            'converted_employee_id': None,
            'is_converted_to_employee': False,
            'has_payment': True
        },
        {
            'application_no': 'AM-APP-2026-003',
            'candidate_name': 'Vikram Reddy',
            'candidate_email': 'vikram.reddy2026@gmail.com',
            'candidate_phone': '+91 98412 00003',
            'candidate_dob': '2003-07-08',
            'candidate_gender': 'Male',
            'college_name': 'National Institute of Technology Karnataka',
            'department_name': 'Computer Science and Engineering',
            'course': 'B.Tech Computer Science',
            'year_of_study': '2nd Year',
            'roll_number': '22CS039',
            'applied_role': 'Cloud & DevOps Intern',
            'city': 'Surathkal',
            'state': 'Karnataka',
            'aadhaar_masked': 'XXXX XXXX 9012',
            'status': 'APPROVED',
            'plan_id': plan_1m.id if plan_1m else None,
            'converted_employee_id': None,
            'is_converted_to_employee': False,
            'has_payment': True
        },
        {
            'application_no': 'AM-APP-2026-004',
            'candidate_name': 'Ananya Sen',
            'candidate_email': 'ananya.sen@example.com',
            'candidate_phone': '+91 98412 00004',
            'candidate_dob': '2003-01-10',
            'candidate_gender': 'Female',
            'college_name': 'PSG College of Technology',
            'department_name': 'Information Technology',
            'course': 'B.Tech IT',
            'year_of_study': '2nd Year',
            'roll_number': '22IT012',
            'applied_role': 'Full Stack Intern',
            'city': 'Coimbatore',
            'state': 'Tamil Nadu',
            'aadhaar_masked': 'XXXX XXXX 3456',
            'status': 'PAYMENT_PENDING',
            'plan_id': plan_1m.id if plan_1m else None,
            'converted_employee_id': None,
            'is_converted_to_employee': False,
            'has_payment': False
        },
        {
            'application_no': 'AM-APP-2026-005',
            'candidate_name': 'Karthik Raja',
            'candidate_email': 'karthik.raja@example.com',
            'candidate_phone': '+91 98412 00005',
            'candidate_dob': '2002-09-19',
            'candidate_gender': 'Male',
            'college_name': 'SRM Institute of Science and Technology',
            'department_name': 'Computer Science and Engineering',
            'course': 'B.Tech CSE',
            'year_of_study': '3rd Year',
            'roll_number': '21CS099',
            'applied_role': 'Cybersecurity Intern',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'aadhaar_masked': 'XXXX XXXX 7890',
            'status': 'REJECTED',
            'plan_id': plan_1m.id if plan_1m else None,
            'converted_employee_id': None,
            'is_converted_to_employee': False,
            'has_payment': False
        }
    ]

    for app_data in apps_data:
        existing = Application.query.filter_by(application_no=app_data['application_no']).first()
        if not existing:
            app = Application(
                application_no=app_data['application_no'],
                status=app_data['status'],
                candidate_name=app_data['candidate_name'],
                candidate_email=app_data['candidate_email'],
                candidate_phone=app_data['candidate_phone'],
                candidate_dob=app_data['candidate_dob'],
                candidate_gender=app_data['candidate_gender'],
                college_name=app_data['college_name'],
                department_name=app_data['department_name'],
                course=app_data['course'],
                year_of_study=app_data['year_of_study'],
                roll_number=app_data['roll_number'],
                applied_role=app_data['applied_role'],
                city=app_data['city'],
                state=app_data['state'],
                aadhaar_masked=app_data['aadhaar_masked'],
                plan_id=app_data.get('plan_id'),
                converted_employee_id=app_data.get('converted_employee_id'),
                is_converted_to_employee=app_data.get('is_converted_to_employee', False)
            )
            db.session.add(app)
            db.session.flush()

            if app_data.get('has_payment'):
                payment = Payment(
                    application_id=app.id,
                    student_id=1,  # initial placeholder student reference
                    transaction_id=f"AM-TXN-{app.application_no}",
                    order_id=f"AM-ORD-{app.application_no}",
                    amount=1499.00 if app_data.get('plan_id') == 1 else 3999.00,
                    currency='INR',
                    status='SUCCESSFUL',
                    payment_method='ONLINE_GATEWAY'
                )
                db.session.add(payment)

    db.session.commit()


def seed_project_weeks_and_tasks():
    """Seed ProjectWeek and ProjectTask rows for master projects (idempotent)."""
    # Project 1: AM-PRJ-001 (4-week 1-month track)
    proj_1 = Project.query.filter_by(project_code='AM-PRJ-001').first()
    if proj_1 and proj_1.project_weeks.count() == 0:
        # Update duration_months if needed
        proj_1.duration_months = 1
        weeks_1 = [
            {
                'week_number': 1,
                'title': 'Project Understanding, Architecture & Data Modeling',
                'description': 'Week 1 focuses on understanding project requirements and creating system architecture.',
                'objective': 'Analyze academic dataset schemas, understand predictive evaluation metrics, and formulate multi-tier system architecture.',
                'instructions': 'Review the problem statement and dataset schema. Perform preliminary EDA in Python. Draft the Technical Design Document including ER diagrams and component architecture.',
                'deliverables': ['System Architecture & Technical Design Document (PDF)', 'Dataset EDA Notebook (.ipynb)', 'Sprint Milestone Execution Plan'],
                'tasks': [
                    {'title': 'Understand project requirements & domain problem statement', 'priority': 'High', 'estimated_hours': 4, 'description': 'Thoroughly read all project documentation and understand the business objectives.', 'instructions': 'Read problem statement, identify key entities, list all functional requirements.', 'expected_output': 'Comprehensive requirements summary document.'},
                    {'title': 'Study required technologies (Python, Flask, Scikit-learn, Pandas)', 'priority': 'High', 'estimated_hours': 6, 'description': 'Build foundational knowledge of required tech stack.', 'instructions': 'Complete beginner tutorials on Flask and Scikit-learn. Practice basic Pandas operations.', 'expected_output': 'Working local environment with demo notebook.'},
                    {'title': 'Perform Exploratory Data Analysis (EDA) on student performance dataset', 'priority': 'High', 'estimated_hours': 8, 'description': 'Analyze dataset statistics, distributions, and correlations.', 'instructions': 'Use Pandas and Matplotlib/Seaborn to visualize distributions, check for null values, and compute correlation matrices.', 'expected_output': 'Jupyter notebook with complete EDA visualizations.'},
                    {'title': 'Prepare system architecture & Entity-Relationship (ER) diagram', 'priority': 'Medium', 'estimated_hours': 4, 'description': 'Design the complete system architecture and data models.', 'instructions': 'Create component diagram and ER diagram using draw.io or Lucidchart.', 'expected_output': 'Architecture diagram PDF file.'},
                    {'title': 'Create sprint execution plan & setup Git version control', 'priority': 'Medium', 'estimated_hours': 2, 'description': 'Initialize repository and plan weekly sprints.', 'instructions': 'Create GitHub repo with README, .gitignore, and initial commit. Document weekly sprint plan.', 'expected_output': 'GitHub repository link and sprint plan document.'}
                ]
            },
            {
                'week_number': 2,
                'title': 'Data Preprocessing & Machine Learning Model Pipeline',
                'description': 'Week 2 covers data pipeline implementation and model training.',
                'objective': 'Implement data cleaning pipelines, feature engineering, and train predictive ML models.',
                'instructions': 'Develop automated data normalization routines. Train multiple classification and regression algorithms. Document benchmark metrics.',
                'deliverables': ['Trained Model Artifacts (.pkl)', 'Model Evaluation & Benchmark Comparison Report', 'Data Preprocessing Pipeline Module'],
                'tasks': [
                    {'title': 'Implement data imputation and categorical encoding pipeline', 'priority': 'High', 'estimated_hours': 6, 'description': 'Handle missing values and encode categorical features.', 'instructions': 'Use SimpleImputer for nulls, LabelEncoder/OneHotEncoder for categories.', 'expected_output': 'Clean preprocessing module with unit tests.'},
                    {'title': 'Develop feature extraction and correlation analysis scripts', 'priority': 'High', 'estimated_hours': 5, 'description': 'Select most important features using statistical methods.', 'instructions': 'Compute Pearson correlation, use SelectKBest or feature importance from Random Forest.', 'expected_output': 'Feature importance chart and selected feature list.'},
                    {'title': 'Train baseline and advanced supervised learning models', 'priority': 'High', 'estimated_hours': 8, 'description': 'Train Logistic Regression, Random Forest, and XGBoost models.', 'instructions': 'Train each model with the preprocessed dataset, evaluate using accuracy, precision, recall, F1-score.', 'expected_output': 'Model comparison table with all benchmark metrics.'},
                    {'title': 'Conduct hyperparameter tuning with cross-validation', 'priority': 'Medium', 'estimated_hours': 4, 'description': 'Optimize model parameters for best performance.', 'instructions': 'Use GridSearchCV or RandomizedSearchCV with 5-fold CV.', 'expected_output': 'Best parameter set and corresponding benchmark scores.'},
                    {'title': 'Serialize final optimized model pipeline', 'priority': 'Medium', 'estimated_hours': 2, 'description': 'Save the best model as a .pkl artifact for API use.', 'instructions': 'Use pickle or joblib to serialize the complete pipeline.', 'expected_output': 'model_pipeline.pkl artifact file.'}
                ]
            },
            {
                'week_number': 3,
                'title': 'RESTful API Backend & Interactive Analytics UI',
                'description': 'Week 3 builds the Flask API and frontend dashboard.',
                'objective': 'Build Flask REST endpoints for model inference and develop a modern, responsive web dashboard.',
                'instructions': 'Implement secure API routes and build responsive Jinja2/HTML5 views with Chart.js visualizations.',
                'deliverables': ['Flask Backend API Modules', 'Interactive Frontend UI Templates & Styles', 'API Testing Collection & Documentation'],
                'tasks': [
                    {'title': 'Create Flask API endpoints for real-time model inference', 'priority': 'High', 'estimated_hours': 6, 'description': 'Build POST /predict endpoint accepting student data and returning risk scores.', 'instructions': 'Load serialized model, validate inputs, run inference, return JSON response with confidence.', 'expected_output': 'Working /predict API with Postman collection.'},
                    {'title': 'Design responsive dashboard UI cards and metric badges', 'priority': 'High', 'estimated_hours': 5, 'description': 'Build responsive HTML/CSS UI for the analytics dashboard.', 'instructions': 'Create scorecards, status badges, and metric widgets using CSS Grid/Flexbox.', 'expected_output': 'Fully responsive dashboard layout.'},
                    {'title': 'Integrate Chart.js visualizations for grade distribution', 'priority': 'Medium', 'estimated_hours': 4, 'description': 'Add interactive charts for performance visualization.', 'instructions': 'Implement bar charts, pie charts, and line graphs using Chart.js.', 'expected_output': 'At least 3 interactive charts integrated with live data.'},
                    {'title': 'Add input validation, security sanitization, and error handling', 'priority': 'High', 'estimated_hours': 4, 'description': 'Ensure API is secure and handles all edge cases.', 'instructions': 'Validate all inputs, sanitize strings, return structured error responses.', 'expected_output': 'All edge case error tests passing.'}
                ]
            },
            {
                'week_number': 4,
                'title': 'Testing, Deployment, Demonstration & Defense',
                'description': 'Week 4 finalizes the project with testing, deployment, and documentation.',
                'objective': 'Perform test verification, deploy live web demo, record technical video walkthrough, and prepare final defense.',
                'instructions': 'Execute comprehensive unit test suites. Deploy the live web application. Record a 5-minute video walkthrough.',
                'deliverables': ['Public GitHub Repository URL', 'Live Deployed Web Demo URL', '5-Minute Demonstration Video Link', 'Final Technical Report'],
                'tasks': [
                    {'title': 'Write automated unit and integration test suites', 'priority': 'High', 'estimated_hours': 6, 'description': 'Achieve >80% code coverage with automated tests.', 'instructions': 'Use pytest to write unit tests for all API endpoints and ML pipeline functions.', 'expected_output': 'Test suite with coverage report.'},
                    {'title': 'Deploy application to cloud hosting environment', 'priority': 'High', 'estimated_hours': 4, 'description': 'Deploy the complete application to Render or Railway.', 'instructions': 'Set up production environment, configure environment variables, and verify live demo.', 'expected_output': 'Live public URL accessible online.'},
                    {'title': 'Record 5-minute video walkthrough explaining architecture & demo', 'priority': 'Medium', 'estimated_hours': 3, 'description': 'Create a professional video demonstration of the project.', 'instructions': 'Record screen capture using OBS or Loom covering architecture, code walkthrough, and live prediction demo.', 'expected_output': 'YouTube/Drive video link.'},
                    {'title': 'Submit final GitHub repository with comprehensive README', 'priority': 'High', 'estimated_hours': 3, 'description': 'Prepare complete project documentation and submission.', 'instructions': 'Write README with setup instructions, API docs, screenshots, and deployment guide.', 'expected_output': 'Final GitHub repository link and complete README.md.'}
                ]
            }
        ]
        for w_data in weeks_1:
            pw = ProjectWeek(
                project_id=proj_1.id,
                week_number=w_data['week_number'],
                title=w_data['title'],
                description=w_data['description'],
                objective=w_data['objective'],
                instructions=w_data['instructions'],
                deliverables_json=json.dumps(w_data['deliverables'])
            )
            db.session.add(pw)
            db.session.flush()
            for t_data in w_data['tasks']:
                pt = ProjectTask(
                    week_id=pw.id,
                    title=t_data['title'],
                    description=t_data.get('description', ''),
                    instructions=t_data.get('instructions', ''),
                    expected_output=t_data.get('expected_output', ''),
                    priority=t_data.get('priority', 'Medium'),
                    estimated_hours=t_data.get('estimated_hours')
                )
                db.session.add(pt)

    # Project 2: AM-PRJ-002 (12-week 3-month track)
    proj_2 = Project.query.filter_by(project_code='AM-PRJ-002').first()
    if proj_2 and proj_2.project_weeks.count() == 0:
        proj_2.duration_months = 3
        week_titles_2 = [
            'Enterprise Architecture & Security Threat Modeling',
            'Token Validation Engine & JWT HMAC Verification',
            'Redis Token Bucket Rate-Limiting Implementation',
            'Month 1 Milestone Review & Security Benchmark Defense',
            'Dynamic Circuit Breaker & Resiliency Handlers',
            'Centralized Audit Logging & SIEM Event Pipeline',
            'Intrusion Anomaly Detection Algorithm Integration',
            'Month 2 Milestone Review & Resiliency Testing',
            'Admin Security Dashboard & Live Telemetry UI',
            'Docker Containerization & Kubernetes Orchestration Setup',
            'End-to-End Penetration Testing & Vulnerability Hardening',
            'Final Demonstration Defense & Technical Documentation'
        ]
        for w_num, w_title in enumerate(week_titles_2, start=1):
            pw = ProjectWeek(
                project_id=proj_2.id,
                week_number=w_num,
                title=w_title,
                description=f'Week {w_num} of the Autonomous Cloud Microservices Security Gateway project.',
                objective=f'Execute Phase {w_num} objectives for the Autonomous Cloud Security Gateway.',
                instructions=f'Complete all Week {w_num} deliverables and verify with unit tests before milestone submission.',
                deliverables_json=json.dumps([f'Week {w_num} Technical Artifacts', 'Implementation Source Code', 'Unit Test Report'])
            )
            db.session.add(pw)
            db.session.flush()
            pt = ProjectTask(
                week_id=pw.id,
                title=f'Implement core specifications for Week {w_num}: {w_title}',
                description=f'Complete all core implementation tasks for {w_title}.',
                instructions=f'Follow the Week {w_num} instructions in the project specification document.',
                expected_output=f'Week {w_num} deliverables submitted and passing all tests.',
                priority='High',
                estimated_hours=20.0
            )
            db.session.add(pt)

    db.session.commit()
