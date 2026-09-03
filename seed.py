import json
from app import create_app
from app.extensions import db
from app.models import (
    User, College, Department, Student, InternshipPlan,
    Application, Payment, Internship, Project, ProjectAssignment,
    CertificateVerification, Notification
)

app = create_app()

def seed_database():
    with app.app_context():
        # Create all tables
        db.create_all()

        # 1. Seed Internship Plans
        if not InternshipPlan.query.first():
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
                    'Source Code & Live Deployment Submission',
                    'Demo Video Submission & Evaluation',
                    'Mentor Review & Project Scoring',
                    'Official Anti Matrix Completion Certificate',
                    'Public QR Verification Link'
                ]),
                badge='Fast-Track Project Plan'
            )

            plan_3m = InternshipPlan(
                plan_code='3_MONTH_PROFESSIONAL',
                title='3 Month Professional Internship',
                duration_months=3,
                fee=3999.00,
                currency='INR',
                description='Comprehensive industrial internship with official onboarding letters, document verification, monthly milestone tracking, and experience credentials.',
                features_json=json.dumps([
                    'Complete Academic & Identity Verification',
                    'Official Anti Matrix Offer Letter',
                    'Official Joining Letter with Internship ID',
                    'Enterprise-Grade Industry Project Assignment',
                    'Monthly Milestone Progress Tracking (Month 1/2/3)',
                    'Dedicated Technical Mentor & Review Process',
                    'Final Codebase & Technical Documentation Submission',
                    '5-10 Min Demo Video Defense',
                    '7-Criteria Final Evaluation Report',
                    'Official Anti Matrix Completion Certificate',
                    'Official Experience / Internship Letter (Subject to completion)',
                    'Tamper-Proof QR Certificate Verification'
                ]),
                badge='Enterprise Professional Track'
            )

            db.session.add(plan_1m)
            db.session.add(plan_3m)
            db.session.commit()
            print('[OK] Seeded Internship Plans')

        # 2. Seed Master Colleges & Departments
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
            print('[OK] Seeded Master Colleges & Departments')

        # 3. Seed Default Staff & Demo Student
        if not User.query.filter_by(email='admin@antimatrix.com').first():
            # Super Admin
            admin = User(email='admin@antimatrix.com', role='super_admin', full_name='Anti Matrix Super Admin', phone='+91 98765 43210')
            admin.set_password('Admin@2026Password!')
            db.session.add(admin)

            # HR
            hr = User(email='hr@antimatrix.com', role='hr', full_name='Divya Raman (HR Lead)', phone='+91 98765 43211')
            hr.set_password('Hr@2026Password!')
            db.session.add(hr)

            # Mentor
            mentor = User(email='mentor@antimatrix.com', role='mentor', full_name='Dr. Rajesh Sharma (Lead Architect)', phone='+91 98765 43212')
            mentor.set_password('Mentor@2026Password!')
            db.session.add(mentor)

            # Evaluator
            evaluator = User(email='evaluator@antimatrix.com', role='evaluator', full_name='Pooja Nair (Senior Evaluator)', phone='+91 98765 43213')
            evaluator.set_password('Evaluator@2026Password!')
            db.session.add(evaluator)

            # Demo Student
            student_user = User(email='aarav.kumar@example.com', role='student', full_name='Aarav Kumar', phone='+91 98765 00184')
            student_user.set_password('Student@2026Password!')
            db.session.add(student_user)
            db.session.flush()

            col = College.query.first()
            dept = Department.query.filter_by(college_id=col.id).first()

            student = Student(
                user_id=student_user.id,
                student_uid='AM-STU-2026-00184',
                dob='2003-08-15',
                gender='Male',
                college_id=col.id,
                department_id=dept.id,
                roll_number='21CS048',
                degree='B.Tech / B.E',
                current_year='3rd Year',
                graduation_year='2026',
                aadhaar_masked='XXXX XXXX 4821',
                is_verified=True
            )
            db.session.add(student)
            db.session.flush()

            plan_3m = InternshipPlan.query.filter_by(plan_code='3_MONTH_PROFESSIONAL').first()

            app_rec = Application(
                application_no='AM-APP-2026-00184',
                student_id=student.id,
                plan_id=plan_3m.id,
                status='APPROVED',
                consent_agreed=True,
                consent_version='v1.0-2026'
            )
            db.session.add(app_rec)
            db.session.flush()

            payment = Payment(
                application_id=app_rec.id,
                student_id=student.id,
                transaction_id='AM-TXN-2026-94821',
                order_id='ORDER-AM-94821',
                amount=3999.00,
                status='SUCCESSFUL',
                payment_method='ONLINE_UPI'
            )
            db.session.add(payment)

            internship = Internship(
                internship_no='AM-INT-2026-00184',
                student_id=student.id,
                application_id=app_rec.id,
                plan_id=plan_3m.id,
                status='ACTIVE',
                start_date='01 Sep 2026',
                end_date='30 Nov 2026',
                progress_percent=72,
                current_stage='Month 2 Development',
                mentor_id=mentor.id
            )
            db.session.add(internship)
            db.session.flush()

            # Seed project
            project = Project(
                project_code='AM-PRJ-01',
                title='Autonomous Cloud Microservices Security Gateway',
                domain='Cyber Security & Cloud',
                description='Design and deploy a Zero-Trust API gateway featuring rate limiting, JWT token introspection, anomaly detection, and automated threat mitigations.',
                objectives_json=json.dumps(['Implement token verification', 'Add circuit breakers', 'Build real-time metric dashboard', 'Automate IP blocklisting']),
                tech_stack_json=json.dumps(['Python', 'Flask', 'Redis', 'Docker', 'HTML5', 'CSS3']),
                requirements_json=json.dumps(['Full authentication pipeline', 'Sub-50ms latency overhead', 'Unit test coverage > 85%', 'Detailed API documentation']),
                instructions_md='Follow the Anti Matrix microservice security guidelines. Configure Redis token stores, implement HMAC request signing, and deploy the live demo.',
                reference_links_json=json.dumps([{'title': 'Zero Trust Architecture Guide', 'url': 'https://csrc.nist.gov'}]),
                duration_weeks=12,
                difficulty='Advanced'
            )
            db.session.add(project)
            db.session.flush()

            assignment = ProjectAssignment(
                internship_id=internship.id,
                project_id=project.id,
                assigned_by=admin.id,
                deadline='20 Nov 2026',
                status='IN_PROGRESS',
                repo_url='https://github.com/aarav-antimatrix/cloud-sec-gateway',
                live_demo_url='https://gateway-demo.antimatrix.tech',
                demo_video_url='https://youtube.com/watch?v=demo_anti_matrix',
                description='Built high performance Zero-Trust API Gateway with active rate limiting and live health monitoring.',
                tech_used='Python, Flask, SQLite, HTML5, CSS3, Docker'
            )
            db.session.add(assignment)

            # Seed certificate verification
            cert = CertificateVerification(
                certificate_no='AM-CERT-2026-00184',
                internship_id=internship.id,
                student_name='Aarav Kumar',
                program_title='3 Month Professional Internship (Cyber Security & Cloud)',
                duration='3 Months',
                start_date='01 Sep 2026',
                end_date='30 Nov 2026',
                issue_date='30 Nov 2026',
                status='Successfully Completed',
                qr_code_data='http://localhost:5000/verify/AM-CERT-2026-00184'
            )
            db.session.add(cert)

            # Welcome notification
            notif = Notification(
                user_id=student_user.id,
                title='Welcome to Anti Matrix Internship Portal',
                message='Your 3-Month Professional Internship profile is active. Check your assigned project and milestone roadmap.',
                type='SUCCESS',
                link='/student/dashboard'
            )
            db.session.add(notif)

            db.session.commit()
            print('[OK] Seeded Users, Student, Project & Demo Verification Credentials')

if __name__ == '__main__':
    seed_database()
