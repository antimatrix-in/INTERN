import unittest
from app import create_app
from app.extensions import db
from app.models import (
    User, Student, Internship, Project, ProjectAssignment,
    ProjectWeek, ProjectTask, WeeklyMilestone, WeeklyTask,
    Application
)
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class AdminTestCase(unittest.TestCase):
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

    # ── Helper: login as admin ────────────────────────────────────────────────

    def login_admin(self):
        return self.client.post('/admin/login', data={
            'email_or_id': 'admin',
            'password': 'Admin@12345'
        }, follow_redirects=True)

    def login_student(self):
        return self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=True)

    # ── Test 1: Admin login with admin / Admin@12345 ──────────────────────────

    def test_admin_login_success(self):
        """Admin should log in with ID=admin, password=Admin@12345."""
        response = self.login_admin()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)

    # ── Test 2: Admin login fails with wrong password ─────────────────────────

    def test_admin_login_wrong_password(self):
        """Admin login should fail with wrong password."""
        response = self.client.post('/admin/login', data={
            'email_or_id': 'admin',
            'password': 'WrongPassword!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid administrator credentials', response.data)

    # ── Test 3: Student role is blocked from admin routes ────────────────────

    def test_student_blocked_from_admin(self):
        """Student role must not access /admin/* routes — expect 403."""
        self.login_student()
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 403)

    # ── Test 4: Admin can access dashboard ───────────────────────────────────

    def test_admin_dashboard_accessible(self):
        """Admin should see dashboard with metric content."""
        self.login_admin()
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)

    # ── Test 5: Application ID lookup returns candidate data ─────────────────

    def test_application_lookup_found(self):
        """Lookup of AM-APP-2026-001 returns Rahul Kumar's details."""
        self.login_admin()
        response = self.client.get('/admin/api/application/AM-APP-2026-001')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['candidate_name'], 'Rahul Kumar')
        self.assertEqual(data['application_no'], 'AM-APP-2026-001')

    # ── Test 6: Non-existent Application ID returns error ────────────────────

    def test_application_lookup_not_found(self):
        """Non-existent Application ID should return 404 with error message."""
        self.login_admin()
        response = self.client.get('/admin/api/application/AM-APP-9999-999')
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertIn('not found', data['error'].lower())

    # ── Test 7: Create employee from valid application ID ─────────────────────

    def test_create_employee_from_application(self):
        """Posting valid application ID creates a new User, Student, and Internship."""
        self.login_admin()
        response = self.client.post('/admin/employees/create', data={
            'application_no': 'AM-APP-2026-001',
            'duration_plan': '1_MONTH_PROJECT'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Verify DB state
        with self.app.app_context():
            app = Application.query.filter_by(application_no='AM-APP-2026-001').first()
            self.assertTrue(app.is_converted_to_employee)
            self.assertIsNotNone(app.converted_employee_id)
            emp_user = User.query.filter_by(employee_id=app.converted_employee_id).first()
            self.assertIsNotNone(emp_user)
            self.assertEqual(emp_user.role, 'student')
            self.assertIsNotNone(emp_user.student_profile)

    # ── Test 8: Duplicate application ID is rejected ─────────────────────────

    def test_duplicate_application_rejected(self):
        """Creating an employee from an already-converted application ID is rejected."""
        self.login_admin()
        # First creation
        self.client.post('/admin/employees/create', data={
            'application_no': 'AM-APP-2026-001',
            'duration_plan': '1_MONTH_PROJECT'
        }, follow_redirects=True)
        # Second creation — should be rejected
        response = self.client.post('/admin/employees/create', data={
            'application_no': 'AM-APP-2026-001',
            'duration_plan': '1_MONTH_PROJECT'
        }, follow_redirects=True)
        # Should return already_exists flag from API to display existing record
        api_resp = self.client.get('/admin/api/application/AM-APP-2026-001')
        self.assertEqual(api_resp.status_code, 200)
        data = api_resp.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['already_exists'])
        self.assertIn('already exists', data['message'].lower())

    # ── Test 9: ProjectWeek and ProjectTask models seeded correctly ───────────

    def test_project_weeks_and_tasks_seeded(self):
        """AM-PRJ-001 should have 4 ProjectWeek rows and multiple ProjectTasks."""
        with self.app.app_context():
            project = Project.query.filter_by(project_code='AM-PRJ-001').first()
            self.assertIsNotNone(project)
            weeks = project.project_weeks.all()
            self.assertEqual(len(weeks), 4)
            total_tasks = sum(w.tasks.count() for w in weeks)
            self.assertGreater(total_tasks, 0)

    # ── Test 10: 3-Month project has 12 weeks ─────────────────────────────────

    def test_project_12_weeks_seeded(self):
        """AM-PRJ-002 should have 12 ProjectWeek rows (3-month track)."""
        with self.app.app_context():
            project = Project.query.filter_by(project_code='AM-PRJ-002').first()
            self.assertIsNotNone(project)
            weeks = project.project_weeks.all()
            self.assertEqual(len(weeks), 12)

    # ── Test 11: Admin can list employees ─────────────────────────────────────

    def test_admin_employees_list(self):
        """Admin employees list should show seeded students."""
        self.login_admin()
        response = self.client.get('/admin/employees')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Aarav Kumar', response.data)

    # ── Test 12: Admin can list projects ──────────────────────────────────────

    def test_admin_projects_list(self):
        """Admin projects list should show seeded projects."""
        self.login_admin()
        response = self.client.get('/admin/projects')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AM-PRJ-001', response.data)

    # ── Test 13: Career applications seeded ───────────────────────────────────

    def test_career_applications_seeded(self):
        """AM-APP-2026-001/002/003 should exist and not be converted."""
        with self.app.app_context():
            app1 = Application.query.filter_by(application_no='AM-APP-2026-001').first()
            app2 = Application.query.filter_by(application_no='AM-APP-2026-002').first()
            app3 = Application.query.filter_by(application_no='AM-APP-2026-003').first()
            self.assertIsNotNone(app1)
            self.assertIsNotNone(app2)
            self.assertIsNotNone(app3)
            self.assertFalse(app1.is_converted_to_employee)
            self.assertEqual(app2.candidate_name, 'Priya Sharma')
            self.assertEqual(app3.applied_role, 'Cloud & DevOps Intern')

    # ── Test 14: Generated employee ID format ─────────────────────────────────

    def test_generated_employee_id_format(self):
        """Created employee should have ID in format AM-INT-XXXX."""
        self.login_admin()
        self.client.post('/admin/employees/create', data={
            'application_no': 'AM-APP-2026-001',
            'duration_plan': '1_MONTH_PROJECT'
        }, follow_redirects=True)
        with self.app.app_context():
            app = Application.query.filter_by(application_no='AM-APP-2026-001').first()
            emp_id = app.converted_employee_id
            self.assertTrue(emp_id.startswith('AM-INT-'))
            parts = emp_id.split('-')
            self.assertEqual(len(parts), 3)
            self.assertTrue(parts[-1].isdigit())

    # ── Test 15: Existing Phase 1 student tests still pass ────────────────────

    def test_phase1_student_login_still_works(self):
        """Existing student login must still work after admin additions."""
        response = self.login_student()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Aarav Kumar', response.data)


if __name__ == '__main__':
    unittest.main()
