import io
import json
import unittest
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    User, Student, Internship, Project, ProjectAssignment,
    ProjectWeek, ProjectTask, WeeklyMilestone, WeeklyTask,
    WeeklySubmission, Application, Payment, College, Evaluation
)
from app.seed import seed_initial_data
from app.services.career_integration import CareerIntegrationService
from tests.test_config import TestConfig


class CareerIntegrationTestCase(unittest.TestCase):
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

    # ── Helpers ───────────────────────────────────────────────────────────────

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

    # ── 1. Valid Application ID fetches correct details ───────────────────────

    def test_01_valid_application_lookup_fetches_career_data(self):
        """Admin entering AM-APP-2026-1024 fetches Rahul Kumar's details."""
        self.login_admin()
        resp = self.client.get('/admin/api/application/AM-APP-2026-1024')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertFalse(data['already_exists'])
        self.assertEqual(data['application_no'], 'AM-APP-2026-1024')
        self.assertEqual(data['candidate_name'], 'Rahul Kumar')
        self.assertEqual(data['candidate_email'], 'rahul@example.com')
        self.assertEqual(data['college_name'], 'Velammal Institute of Technology')
        self.assertEqual(data['department_name'], 'Computer Science and Engineering')
        self.assertEqual(data['applied_role'], 'AI Engineer Intern')
        self.assertEqual(data['duration'], '3 Months')
        self.assertEqual(data['payment_status'], 'SUCCESS')
        self.assertEqual(data['status'], 'APPROVED')
        self.assertEqual(data['employee_id'], 'AM4827')

    # ── 2. Invalid Application ID returns proper error ────────────────────────

    def test_02_invalid_application_lookup_returns_404(self):
        """Entering non-existent Application ID returns 404 'Application ID not found.'"""
        self.login_admin()
        resp = self.client.get('/admin/api/application/NON-EXISTENT-999')
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn('not found', data['error'].lower())

    # ── 3. Payment incomplete application is rejected ─────────────────────────

    def test_03_unpaid_application_lookup_rejected(self):
        """Application with incomplete payment cannot be onboarded."""
        self.login_admin()
        resp = self.client.get('/admin/api/application/AM-APP-2026-004')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn('payment has not been completed', data['error'].lower())

    # ── 4. Rejected/cancelled application is rejected ─────────────────────────

    def test_04_rejected_application_lookup_rejected(self):
        """Application with REJECTED status is blocked from onboarding."""
        self.login_admin()
        resp = self.client.get('/admin/api/application/AM-APP-2026-005')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn('rejected or cancelled', data['error'].lower())

    # ── 5. Existing Employee ID from Career Portal is reused (AM4827) ──────────

    def test_05_career_portal_employee_id_is_reused(self):
        """Creating employee from AM-APP-2026-1024 MUST use AM4827 as Employee ID."""
        self.login_admin()
        resp = self.client.post('/admin/employees/create', data={
            'application_no': 'AM-APP-2026-1024',
            'duration_plan': '3_MONTH_PROFESSIONAL'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            app = Application.query.filter_by(application_no='AM-APP-2026-1024').first()
            self.assertTrue(app.is_converted_to_employee)
            self.assertEqual(app.converted_employee_id, 'AM4827')

            user = User.query.filter_by(employee_id='AM4827').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.full_name, 'Rahul Kumar')
            self.assertEqual(user.email, 'rahul@example.com')
            self.assertEqual(user.role, 'student')

            student = user.student_profile
            self.assertIsNotNone(student)
            self.assertEqual(student.student_uid, 'AM4827')
            self.assertEqual(student.college.name, 'Velammal Institute of Technology')

    # ── 6. Duplicate employee cannot be created & shows existing record ────────

    def test_06_duplicate_employee_lookup_shows_already_exists(self):
        """After creation, subsequent lookups report already_exists=True with Employee ID."""
        self.login_admin()
        # Create first
        self.client.post('/admin/employees/create', data={
            'application_no': 'AM-APP-2026-1024',
            'duration_plan': '3_MONTH_PROFESSIONAL'
        }, follow_redirects=True)

        # Lookup again
        resp = self.client.get('/admin/api/application/AM-APP-2026-1024')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['already_exists'])
        self.assertEqual(data['employee_id'], 'AM4827')
        self.assertIn('already exists', data['message'].lower())

    # ── 7. Employee login with valid credentials ──────────────────────────────

    def test_07_employee_login_with_valid_credentials(self):
        """Employee can sign in at /login using Employee ID."""
        resp = self.login_employee('AM-INT-2026-001', 'Student@2026Password!')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Hi,', resp.data)
        self.assertIn(b'Aarav Kumar', resp.data)

    # ── 8. Invalid password is rejected ───────────────────────────────────────

    def test_08_employee_login_with_invalid_password_rejected(self):
        """Invalid password yields error message and blocks access."""
        resp = self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'WrongPassword123!'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Invalid Employee ID or password', resp.data)

    # ── 9. Employee dashboard data rendering ──────────────────────────────────

    def test_09_employee_dashboard_displays_employee_specs(self):
        """Employee dashboard renders Employee ID, College, Project, Week, and Progress."""
        resp = self.login_employee('AM-INT-2026-001', 'Student@2026Password!')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Hi,', resp.data)
        self.assertIn(b'Aarav Kumar', resp.data)
        self.assertIn(b'AM-INT-2026-001', resp.data)
        self.assertIn(b'AI-Based Student Performance Analysis', resp.data)
        self.assertIn(b'Week 1', resp.data)
        self.assertIn(b'0%', resp.data)

    # ── 10. Employee data isolation & IDOR protection ─────────────────────────

    def test_10_employee_isolation_and_idor_protection(self):
        """Employee A cannot view Employee B's milestone or stream video."""
        # Log in as Student 1 (Aarav Kumar)
        self.login_employee('AM-INT-2026-001', 'Student@2026Password!')

        # Student 2's milestone
        with self.app.app_context():
            student2 = Student.query.filter_by(student_uid='AM-INT-2026-002').first()
            s2_milestone = student2.active_internship.active_assignment.weekly_milestones.first()
            s2_m_id = s2_milestone.id

        # Attempt to access student 2's milestone
        resp = self.client.get(f'/week/{s2_m_id}')
        self.assertEqual(resp.status_code, 403)

    # ── 11. Admin project creation (1M = 4 weeks, 3M = 12 weeks) ───────────────

    def test_11_admin_project_creation_duration_weeks(self):
        """Creating a 1-Month project creates 4 weeks; 3-Month creates 12 weeks."""
        self.login_admin()
        # 1-Month Project
        resp1 = self.client.post('/admin/projects/create', data={
            'project_code': 'AM-TEST-1M-001',
            'title': 'Test 1 Month Project',
            'domain': 'AI & ML',
            'duration_months': '1',
            'description': '1-Month track description',
            'problem_statement': 'Problem statement',
            'expected_outcome': 'Expected outcome',
            'difficulty': 'Intermediate',
            'tech_stack': 'Python, Flask',
            'objectives': 'Objective 1, Objective 2',
            'requirements': 'Req 1, Req 2',
            'reference_links': 'https://example.com'
        }, follow_redirects=True)
        self.assertEqual(resp1.status_code, 200)

        with self.app.app_context():
            p1 = Project.query.filter_by(project_code='AM-TEST-1M-001').first()
            self.assertIsNotNone(p1)
            self.assertEqual(p1.project_weeks.count(), 4)

        # 3-Month Project
        resp2 = self.client.post('/admin/projects/create', data={
            'project_code': 'AM-TEST-3M-001',
            'title': 'Test 3 Month Project',
            'domain': 'Cyber Security',
            'duration_months': '3',
            'description': '3-Month track description',
            'problem_statement': 'Problem statement',
            'expected_outcome': 'Expected outcome',
            'difficulty': 'Advanced',
            'tech_stack': 'Python, Docker, Redis',
            'objectives': 'Objective 1, Objective 2',
            'requirements': 'Req 1, Req 2',
            'reference_links': 'https://example.com'
        }, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)

        with self.app.app_context():
            p2 = Project.query.filter_by(project_code='AM-TEST-3M-001').first()
            self.assertIsNotNone(p2)
            self.assertEqual(p2.project_weeks.count(), 12)

    # ── 12. Same college project uniqueness rule ──────────────────────────────

    def test_12_same_college_project_uniqueness_enforced(self):
        """Two active students from the same college cannot receive the same project."""
        self.login_admin()
        with self.app.app_context():
            col = College.query.first()
            p1 = Project.query.filter_by(project_code='AM-PRJ-001').first()

            # Create Student A from College
            u_a = User(email='student.a@example.com', employee_id='AM-STU-A', role='student', full_name='Student A')
            u_a.set_password('Pass@123')
            db.session.add(u_a); db.session.flush()
            s_a = Student(user_id=u_a.id, student_uid='AM-STU-A', college_id=col.id, department_id=1, roll_number='A1', degree='BE', current_year='3', graduation_year='2026')
            db.session.add(s_a); db.session.flush()
            i_a = Internship(internship_no='AM-STU-A', student_id=s_a.id, plan_id=1, status='ACTIVE', start_date='01 Sep', end_date='30 Sep')
            db.session.add(i_a); db.session.flush()

            # Assign Project 1 to Student A
            assign_a = ProjectAssignment(internship_id=i_a.id, project_id=p1.id, assigned_by=1, deadline='30 Sep', status='IN_PROGRESS')
            db.session.add(assign_a); db.session.flush()

            # Create Student B from SAME College
            u_b = User(email='student.b@example.com', employee_id='AM-STU-B', role='student', full_name='Student B')
            u_b.set_password('Pass@123')
            db.session.add(u_b); db.session.flush()
            s_b = Student(user_id=u_b.id, student_uid='AM-STU-B', college_id=col.id, department_id=1, roll_number='B1', degree='BE', current_year='3', graduation_year='2026')
            db.session.add(s_b); db.session.flush()
            i_b = Internship(internship_no='AM-STU-B', student_id=s_b.id, plan_id=1, status='ACTIVE', start_date='01 Sep', end_date='30 Sep')
            db.session.add(i_b); db.session.commit()
            s_b_id = s_b.id
            p1_id = p1.id

        # Attempt to assign SAME Project 1 to Student B from SAME college
        resp = self.client.post(f'/admin/employees/{s_b_id}/assign-project', data={
            'project_id': p1_id,
            'deadline': '30 Oct 2026'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'already been assigned to another active student', resp.data)

    # ── 13. Week 1 available, subsequent weeks locked ─────────────────────────

    def test_13_week_1_available_and_later_weeks_locked(self):
        """Initial state: Week 1 is AVAILABLE, Week 2/3/4 are LOCKED."""
        with self.app.app_context():
            student = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student.active_internship.active_assignment
            w1 = assignment.weekly_milestones.filter_by(week_number=1).first()
            w2 = assignment.weekly_milestones.filter_by(week_number=2).first()

            self.assertEqual(w1.status, 'AVAILABLE')
            self.assertEqual(w2.status, 'LOCKED')

    # ── 14. 7-Day overdue calculation does NOT unlock next week ───────────────

    def test_14_seven_days_overdue_does_not_unlock_next_week(self):
        """Elapsed 7 days marks milestone as OVERDUE, but does NOT unlock Week 2."""
        with self.app.app_context():
            student = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student.active_internship.active_assignment
            w1 = assignment.weekly_milestones.filter_by(week_number=1).first()
            w2 = assignment.weekly_milestones.filter_by(week_number=2).first()

            # Set started_at to 10 days ago, due_at to 3 days ago
            w1.started_at = datetime.utcnow() - timedelta(days=10)
            w1.due_at = datetime.utcnow() - timedelta(days=3)
            db.session.commit()

            self.assertTrue(w1.is_overdue)
            self.assertEqual(w1.display_status, 'OVERDUE')
            # Week 2 remains strictly LOCKED
            self.assertEqual(w2.status, 'LOCKED')

    # ── 15. Employee submission workflow & Admin PROCEED TO NEXT ──────────────

    def test_15_submission_and_admin_proceed_unlocks_week_2(self):
        """Employee completes tasks, submits demo video + GitHub URL; Admin PROCEED unlocks Week 2."""
        with self.app.app_context():
            student = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student.active_internship.active_assignment
            w1 = assignment.weekly_milestones.filter_by(week_number=1).first()
            w1_id = w1.id
            for t in w1.tasks:
                t.is_completed = True
            db.session.commit()

        # Submit as Employee
        self.login_employee('AM-INT-2026-001', 'Student@2026Password!')
        video = (io.BytesIO(b'demo video binary'), 'demo.mp4')
        resp = self.client.post(f'/submissions/submit/{w1_id}', data={
            'github_url': 'https://github.com/aarav/ai-project',
            'demo_video': video,
            'submission_notes': 'Completed all Week 1 deliverables.'
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            w1_ref = db.session.get(WeeklyMilestone, w1_id)
            self.assertEqual(w1_ref.status, 'UNDER_REVIEW')
            sub_id = w1_ref.latest_submission.id

        # Admin reviews and clicks PROCEED TO NEXT
        self.login_admin()
        proc_resp = self.client.post(f'/admin/submissions/{sub_id}/proceed-next', data={
            'remarks': 'Outstanding architecture and data modeling. Proceeding to Week 2.'
        }, follow_redirects=True)
        self.assertEqual(proc_resp.status_code, 200)

        with self.app.app_context():
            student = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student.active_internship.active_assignment
            w1_after = assignment.weekly_milestones.filter_by(week_number=1).first()
            w2_after = assignment.weekly_milestones.filter_by(week_number=2).first()

            self.assertEqual(w1_after.status, 'COMPLETED')
            self.assertEqual(w2_after.status, 'AVAILABLE')
            self.assertIsNotNone(w2_after.started_at)
            self.assertIsNotNone(w2_after.due_at)


if __name__ == '__main__':
    unittest.main()
