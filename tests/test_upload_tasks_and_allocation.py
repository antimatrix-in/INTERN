import io
import json
import unittest
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    User, Student, Internship, Project, ProjectAssignment,
    ProjectWeek, ProjectTask, WeeklyMilestone, WeeklyTask,
    WeeklySubmission, Application, Payment, College, TaskImportHistory
)
from app.seed import seed_initial_data
from app.services.task_import_service import TaskImportService
from app.services.problem_allocation_service import ProblemAllocationService
from app.services.career_integration import CareerIntegrationService
from tests.test_config import TestConfig


class UploadTasksAndAllocationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            seed_initial_data()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def login_admin(self):
        self.client.get('/logout')
        return self.client.post('/admin/login', data={
            'email_or_id': 'admin',
            'password': 'Admin@12345'
        }, follow_redirects=True)

    def login_employee(self, emp_id='AM-INT-2026-001', password='Student@2026Password!'):
        self.client.get('/logout')
        return self.client.post('/login', data={
            'employee_id': emp_id,
            'password': password
        }, follow_redirects=True)

    # ── 1. 1-Month JSON Upload Creates 4 Normalized Weeks & Tasks ─────────────

    def test_01_upload_1m_json_creates_project_and_4_weeks(self):
        with self.app.app_context():
            json_data = {
                "internship": {
                    "problem_id": "P1M-001",
                    "domain": "AI & ML",
                    "duration": "1 Month",
                    "level": "Easy to Medium",
                    "project_title": "AI Resume Analyzer & Job Recommendation System",
                    "project_type": "Real-Time AI/ML Web Application",
                    "deployment": "Localhost",
                    "technologies": ["Python", "Flask", "Pandas", "Scikit-learn"],
                    "milestones": [
                        {
                            "week": 1,
                            "completion": "25%",
                            "title": "Resume Upload and Text Extraction",
                            "goal": "Extract raw text from PDF/DOCX resumes",
                            "tasks": [
                                "Create project structure",
                                "Initialize Git repository",
                                "Build resume upload UI"
                            ]
                        },
                        {
                            "week": 2,
                            "completion": "50%",
                            "title": "AI Resume Analysis",
                            "goal": "NLP entity extraction",
                            "tasks": [
                                "Build skill matcher",
                                "Score extracted keywords"
                            ]
                        },
                        {
                            "week": 3,
                            "completion": "75%",
                            "title": "Job Matching Engine",
                            "goal": "Cosine similarity matching",
                            "tasks": [
                                "Load job dataset",
                                "Compute similarity matrix"
                            ]
                        },
                        {
                            "week": 4,
                            "completion": "100%",
                            "title": "Complete Platform Deployment",
                            "goal": "End-to-end integration and testing",
                            "tasks": [
                                "Run final integration tests",
                                "Prepare demo video and documentation"
                            ]
                        }
                    ]
                }
            }

            self.login_admin()
            file_bytes = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp = self.client.post('/admin/upload-tasks/import', data={
                'file': (file_bytes, 'TaskPlan_1M.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data')

            self.assertEqual(resp.status_code, 200)
            res_json = resp.get_json()
            self.assertTrue(res_json['success'])
            self.assertEqual(res_json['project_code'], 'P1M-001')

            # Verify in DB
            proj = Project.query.filter_by(project_code='P1M-001').first()
            self.assertIsNotNone(proj)
            self.assertEqual(proj.title, "AI Resume Analyzer & Job Recommendation System")
            self.assertEqual(proj.duration_months, 1)
            self.assertEqual(proj.duration_weeks, 4)

            weeks = proj.project_weeks.order_by(ProjectWeek.week_number.asc()).all()
            self.assertEqual(len(weeks), 4)
            self.assertEqual(weeks[0].title, "Resume Upload and Text Extraction")
            self.assertEqual(weeks[0].tasks.count(), 3)
            # Verify exact task order preservation
            t1 = weeks[0].tasks.first()
            self.assertEqual(t1.title, "Create project structure")
            self.assertEqual(t1.order_num, 1)

            # Check history log
            history = TaskImportHistory.query.filter_by(project_code='P1M-001').first()
            self.assertIsNotNone(history)
            self.assertEqual(history.status, 'IMPORTED')

    # ── 2. 3-Month JSON Upload Expands 4 Phases into 12 Weekly Records ────────

    def test_02_upload_3m_json_converts_4_phases_to_12_weeks(self):
        with self.app.app_context():
            json_data = {
                "internship": {
                    "problem_id": "P3M-001",
                    "domain": "AI & ML",
                    "duration": "3 Months",
                    "level": "Medium to Advanced",
                    "project_title": "AI Student Performance Prediction Platform",
                    "project_type": "Enterprise AI Web Application",
                    "milestones": [
                        {
                            "phase": 1,
                            "weeks": "1-3",
                            "completion": "25%",
                            "title": "Data Pipeline and Feature Engineering",
                            "goal": "Build robust ingestion pipeline",
                            "tasks": [
                                "Dataset acquisition",
                                "Data cleaning and outlier removal",
                                "Exploratory data analysis"
                            ]
                        },
                        {
                            "phase": 2,
                            "weeks": "4-6",
                            "completion": "50%",
                            "title": "Model Training and Evaluation",
                            "goal": "Train regression models",
                            "tasks": [
                                "Train Random Forest regressor",
                                "Hyperparameter tuning"
                            ]
                        },
                        {
                            "phase": 3,
                            "weeks": "7-9",
                            "completion": "75%",
                            "title": "Recommendation Engine and API",
                            "goal": "Build prediction endpoints",
                            "tasks": [
                                "Flask REST API",
                                "JWT authentication integration"
                            ]
                        },
                        {
                            "phase": 4,
                            "weeks": "10-12",
                            "completion": "100%",
                            "title": "UI Dashboard and Enterprise Packaging",
                            "goal": "Complete end-to-end platform",
                            "tasks": [
                                "Responsive student analytics UI",
                                "End-to-end documentation"
                            ]
                        }
                    ]
                }
            }

            self.login_admin()
            file_bytes = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp = self.client.post('/admin/upload-tasks/import', data={
                'file': (file_bytes, 'TaskPlan_3M.json'),
                'duration': '3 Months'
            }, content_type='multipart/form-data')

            self.assertEqual(resp.status_code, 200)
            proj = Project.query.filter_by(project_code='P3M-001').first()
            self.assertIsNotNone(proj)
            self.assertEqual(proj.duration_months, 3)
            self.assertEqual(proj.total_weeks, 12)

            weeks = proj.project_weeks.order_by(ProjectWeek.week_number.asc()).all()
            self.assertEqual(len(weeks), 12)

            # Phase 1 info preserved on Week 1, 2, 3
            self.assertEqual(weeks[0].phase_number, 1)
            self.assertEqual(weeks[1].phase_number, 1)
            self.assertEqual(weeks[2].phase_number, 1)
            self.assertEqual(weeks[0].weeks_label, "1-3")

            # Phase 4 info preserved on Week 10, 11, 12
            self.assertEqual(weeks[11].phase_number, 4)
            self.assertEqual(weeks[11].weeks_label, "10-12")

    # ── 3. Duration Mismatch Rejection ────────────────────────────────────────

    def test_03_duration_mismatch_rejected(self):
        with self.app.app_context():
            json_3m = {
                "internship": {
                    "project_title": "Test 3M",
                    "domain": "AI",
                    "duration": "3 Months",
                    "milestones": [{"phase": 1, "tasks": []}, {"phase": 2, "tasks": []}, {"phase": 3, "tasks": []}, {"phase": 4, "tasks": []}]
                }
            }
            self.login_admin()
            file_bytes = io.BytesIO(json.dumps(json_3m).encode('utf-8'))
            # Admin selects 1 Month but uploads 3 Months JSON
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'TaskPlan.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data')

            self.assertEqual(resp.status_code, 400)
            res_json = resp.get_json()
            self.assertFalse(res_json['success'])
            self.assertIn("does not match", res_json['error'])

    # ── 4. Duplicate Problem ID Detection & Safe Update ───────────────────────

    def test_04_duplicate_problem_id_detected_and_update(self):
        with self.app.app_context():
            json_data = {
                "internship": {
                    "problem_id": "P1M-DUP",
                    "domain": "Web Development",
                    "duration": "1 Month",
                    "project_title": "Duplicate Project Test",
                    "milestones": [
                        {"week": 1, "title": "W1", "tasks": ["Task 1"]},
                        {"week": 2, "title": "W2", "tasks": ["Task 2"]},
                        {"week": 3, "title": "W3", "tasks": ["Task 3"]},
                        {"week": 4, "title": "W4", "tasks": ["Task 4"]}
                    ]
                }
            }
            self.login_admin()
            # 1. First upload
            file_bytes1 = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp1 = self.client.post('/admin/upload-tasks/import', data={
                'file': (file_bytes1, 'TaskPlan.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data')
            self.assertEqual(resp1.status_code, 200)

            # 2. Second upload without overwrite flag triggers duplicate warning
            file_bytes2 = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp2 = self.client.post('/admin/upload-tasks/import', data={
                'file': (file_bytes2, 'TaskPlan.json'),
                'duration': '1 Month',
                'overwrite': 'false'
            }, content_type='multipart/form-data')
            self.assertEqual(resp2.status_code, 400)
            res2 = resp2.get_json()
            self.assertTrue(res2.get('is_duplicate'))

            # 3. Third upload WITH overwrite flag updates successfully
            json_data["internship"]["project_title"] = "Updated Duplicate Project Test"
            file_bytes3 = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp3 = self.client.post('/admin/upload-tasks/import', data={
                'file': (file_bytes3, 'TaskPlan.json'),
                'duration': '1 Month',
                'overwrite': 'true'
            }, content_type='multipart/form-data')
            self.assertEqual(resp3.status_code, 200)
            res3 = resp3.get_json()
            self.assertEqual(res3['action'], 'UPDATED')

            proj = Project.query.filter_by(project_code='P1M-DUP').first()
            self.assertEqual(proj.title, "Updated Duplicate Project Test")

    # ── 5. Automatic Problem Allocation During Employee Creation ──────────────

    def test_05_employee_creation_auto_allocates_problem(self):
        with self.app.app_context():
            # Create a 1M project in DB
            p1 = Project(
                project_code="P1M-TEST-001",
                title="AI Vision Classifier",
                domain="AI & ML",
                description="Vision model",
                duration_weeks=4,
                duration_months=1,
                is_active=True
            )
            db.session.add(p1)
            db.session.commit()

            # Career application for candidate from College 1 (IITM)
            app_rec = Application(
                application_no="AM-APP-2026-ALLOC1",
                candidate_name="Pooja Sharma",
                candidate_email="pooja.alloc@example.com",
                college_name="Indian Institute of Technology Madras",
                applied_role="AI & ML",
                status="APPROVED"
            )
            db.session.add(app_rec)
            db.session.commit()

            admin = User.query.filter_by(role='super_admin').first()
            student, user, emp_id, pwd, alloc_prob = CareerIntegrationService.create_or_link_employee_from_application(
                app=app_rec,
                admin_user=admin
            )

            self.assertIsNotNone(student)
            self.assertIsNotNone(alloc_prob)
            self.assertEqual(alloc_prob.duration_months, 1)

            # Check internship assignment
            internship = student.active_internship
            self.assertIsNotNone(internship)
            assignment = internship.active_assignment
            self.assertIsNotNone(assignment)
            self.assertEqual(assignment.project_id, alloc_prob.id)

            # Check weekly milestones initialized
            milestones = assignment.weekly_milestones.order_by(WeeklyMilestone.week_number.asc()).all()
            self.assertEqual(len(milestones), 4)
            self.assertEqual(milestones[0].status, 'AVAILABLE')
            self.assertEqual(milestones[1].status, 'LOCKED')
            self.assertEqual(milestones[2].status, 'LOCKED')
            self.assertEqual(milestones[3].status, 'LOCKED')

    # ── 6. Same-College Uniqueness Rule ───────────────────────────────────────

    def test_06_same_college_uniqueness_respected(self):
        with self.app.app_context():
            col = College.query.filter_by(code='IITM').first()
            
            # Ensure two distinct 1-Month projects exist
            p1 = Project.query.filter_by(project_code="P1M-POOL-A").first()
            if not p1:
                p1 = Project(project_code="P1M-POOL-A", title="Project A", domain="AI & ML", duration_weeks=4, duration_months=1, is_active=True)
                db.session.add(p1)
            p2 = Project.query.filter_by(project_code="P1M-POOL-B").first()
            if not p2:
                p2 = Project(project_code="P1M-POOL-B", title="Project B", domain="AI & ML", duration_weeks=4, duration_months=1, is_active=True)
                db.session.add(p2)
            db.session.commit()

            admin = User.query.filter_by(role='super_admin').first()

            # Student 1 from IITM
            app1 = Application(
                application_no="AM-APP-2026-SAMECOL1",
                candidate_name="Student One",
                candidate_email="s1@iitm.ac.in",
                college_name="Indian Institute of Technology Madras",
                applied_role="AI & ML",
                status="APPROVED"
            )
            db.session.add(app1)
            db.session.commit()

            s1, u1, e1, p1_pass, prob1 = CareerIntegrationService.create_or_link_employee_from_application(app=app1, admin_user=admin)

            # Student 2 from same college (IITM)
            app2 = Application(
                application_no="AM-APP-2026-SAMECOL2",
                candidate_name="Student Two",
                candidate_email="s2@iitm.ac.in",
                college_name="Indian Institute of Technology Madras",
                applied_role="AI & ML",
                status="APPROVED"
            )
            db.session.add(app2)
            db.session.commit()

            s2, u2, e2, p2_pass, prob2 = CareerIntegrationService.create_or_link_employee_from_application(app=app2, admin_user=admin)

            # Verify s1 and s2 received DIFFERENT active problems
            self.assertNotEqual(prob1.id, prob2.id)
            self.assertNotEqual(prob1.project_code, prob2.project_code)

    # ── 7. Different Colleges CAN Receive the Same Problem ────────────────────

    def test_07_different_colleges_can_receive_same_problem(self):
        with self.app.app_context():
            col1 = College.query.filter_by(code='IITM').first()
            col2 = College.query.filter_by(code='NITK').first()

            # Single active project in pool
            p_shared = Project.query.filter_by(project_code="P1M-SHARED-01").first()
            if not p_shared:
                p_shared = Project(project_code="P1M-SHARED-01", title="Shared Project", domain="AI & ML", duration_weeks=4, duration_months=1, is_active=True)
                db.session.add(p_shared)
                db.session.commit()

            # Eligible for IITM
            prob_iitm, err1 = ProblemAllocationService.allocate_random_problem(college_id=col1.id, duration_months=1, domain="AI & ML")
            self.assertIsNotNone(prob_iitm)

            # Assign to an IITM student
            # Eligible for NITK (different college) should STILL include p_shared!
            prob_nitk, err2 = ProblemAllocationService.allocate_random_problem(college_id=col2.id, duration_months=1, domain="AI & ML")
            self.assertIsNotNone(prob_nitk)

    # ── 8. No Available Problem Produces Clear Error ──────────────────────────

    def test_08_no_available_problem_raises_error(self):
        with self.app.app_context():
            col = College.query.filter_by(code='IITM').first()

            # Deactivate all 3-Month projects
            for p in Project.query.filter_by(duration_months=3).all():
                p.is_active = False
            db.session.commit()

            app_rec = Application(
                application_no="AM-APP-2026-NOPOOL",
                candidate_name="No Pool Candidate",
                candidate_email="nopool@example.com",
                college_name="Indian Institute of Technology Madras",
                applied_role="3 Month Professional Data Scientist",
                status="APPROVED"
            )
            db.session.add(app_rec)
            db.session.commit()

            admin = User.query.filter_by(role='super_admin').first()
            with self.assertRaises(ValueError) as ctx:
                CareerIntegrationService.create_or_link_employee_from_application(
                    app=app_rec,
                    admin_user=admin
                )

            self.assertIn("No available", str(ctx.exception))
            # Verify no partial employee was committed
            user_check = User.query.filter_by(email="nopool@example.com").first()
            self.assertIsNone(user_check)

    # ── 9. Employee Dashboard Renders Problem ID & Roadmaps ───────────────────

    def test_09_employee_dashboard_renders_problem_id(self):
        with self.app.app_context():
            self.login_employee('AM-INT-2026-001', 'Student@2026Password!')
            resp = self.client.get('/dashboard')
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode('utf-8')

            # Verify Problem ID / Code and Title are in HTML
            self.assertIn('AM-PRJ-001', html)
            self.assertIn('AI-Based Student Performance Analysis System', html)
            self.assertIn('WEEKLY PROJECT ROADMAP', html)


if __name__ == '__main__':
    unittest.main()
