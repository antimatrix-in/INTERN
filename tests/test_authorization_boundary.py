"""Security test suite validating employee authorization boundaries and session realm isolation."""
import unittest
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import User, Student, College, Department
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class AuthorizationBoundaryTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            seed_initial_data()

            # Create dual-identity / edge case user (similar to AM0193: User has role='admin' but logs in with employee_id)
            col = College.query.first()
            dept = Department.query.filter_by(college_id=col.id).first()
            dual_user = User(
                email="dual@antimatrix.ai",
                employee_id="AM0193",
                role="admin",
                full_name="Dual Identity Admin-Employee"
            )
            dual_user.set_password("DualPassword123!")
            db.session.add(dual_user)
            db.session.flush()

            dual_student = Student(
                user_id=dual_user.id,
                student_uid="AM0193",
                college_id=col.id,
                department_id=dept.id,
                roll_number="21CS193",
                degree="B.Tech",
                current_year="4th Year",
                graduation_year="2026",
                is_verified=True
            )
            db.session.add(dual_student)
            db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # 1. Normal employee login lands on student dashboard
    def test_01_employee_form_login_redirects_to_student_dashboard(self):
        """Employee form login at /login must redirect to /dashboard."""
        resp = self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/dashboard', resp.headers.get('Location', ''))
        self.assertNotIn('/admin', resp.headers.get('Location', ''))

    def test_02_employee_api_login_returns_student_dashboard_url(self):
        """Employee JSON login at /api/auth/employee-login must return /dashboard redirect."""
        resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['redirect_url'], '/dashboard')

    # 2. Next param manipulation is neutralized
    def test_03_employee_login_with_admin_next_url_redirects_to_student_dashboard(self):
        """Employee login with ?next=/admin/dashboard must not redirect to admin area."""
        resp = self.client.post('/login?next=/admin/dashboard', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers.get('Location', ''), '/dashboard')

    def test_04_employee_login_with_admin_employees_next_url_redirects_to_student_dashboard(self):
        """Employee login with ?next=/admin/employees must redirect to /dashboard."""
        resp = self.client.post('/login?next=/admin/employees', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers.get('Location', ''), '/dashboard')

    # 3. Authenticated employee requesting admin routes returns 403 Forbidden
    def _login_as_employee(self):
        self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=True)

    def test_05_employee_access_admin_dashboard_returns_403(self):
        """Authenticated employee accessing /admin/dashboard gets 403 Forbidden."""
        self._login_as_employee()
        resp = self.client.get('/admin/dashboard')
        self.assertEqual(resp.status_code, 403)

    def test_06_employee_access_admin_employees_returns_403(self):
        """Authenticated employee accessing /admin/employees gets 403 Forbidden."""
        self._login_as_employee()
        resp = self.client.get('/admin/employees')
        self.assertEqual(resp.status_code, 403)

    def test_07_employee_access_admin_projects_returns_403(self):
        """Authenticated employee accessing /admin/projects gets 403 Forbidden."""
        self._login_as_employee()
        resp = self.client.get('/admin/projects')
        self.assertEqual(resp.status_code, 403)

    def test_08_employee_access_admin_upload_tasks_returns_403(self):
        """Authenticated employee accessing /admin/upload-tasks gets 403 Forbidden."""
        self._login_as_employee()
        resp = self.client.get('/admin/upload-tasks')
        self.assertEqual(resp.status_code, 403)

    def test_09_employee_access_admin_evaluations_returns_403(self):
        """Authenticated employee accessing /admin/evaluations gets 403 Forbidden."""
        self._login_as_employee()
        resp = self.client.get('/admin/evaluations')
        self.assertEqual(resp.status_code, 403)

    def test_10_employee_access_admin_meetings_returns_403(self):
        """Authenticated employee accessing /admin/meetings gets 403 Forbidden."""
        self._login_as_employee()
        resp = self.client.get('/admin/meetings')
        self.assertEqual(resp.status_code, 403)

    # 4. Root route redirection
    def test_11_root_route_redirects_employee_to_student_dashboard(self):
        """Root route / redirects authenticated employee to /dashboard."""
        self._login_as_employee()
        resp = self.client.get('/', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers.get('Location', ''), '/dashboard')

    # 5. Dual-identity / AM0193 account security (role='admin' in DB, logs in via employee portal)
    def test_12_dual_role_user_logging_in_via_employee_portal_cannot_access_admin(self):
        """Account with role='admin' logging in via /login gets employee realm and 403 on admin routes."""
        resp = self.client.post('/login', data={
            'employee_id': 'AM0193',
            'password': 'DualPassword123!'
        }, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers.get('Location', ''), '/dashboard')

        # Attempt to access admin dashboard
        resp_admin = self.client.get('/admin/dashboard')
        self.assertEqual(resp_admin.status_code, 403)

    # 6. Admin login at /admin/login works and admin has access
    def test_13_legitimate_admin_login_accesses_admin_dashboard(self):
        """Admin logging in via /admin/login lands on and accesses /admin/dashboard."""
        resp = self.client.post('/admin/login', data={
            'email_or_id': 'admin@antimatrix.com',
            'password': 'Admin@2026Password!'
        }, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers.get('Location', ''), '/admin/dashboard')

        # Access admin dashboard
        resp_dash = self.client.get('/admin/dashboard')
        self.assertEqual(resp_dash.status_code, 200)

    # 7. Session isolation and cross-session identity bleeding
    def test_14_admin_logout_clears_session_and_subsequent_employee_is_isolated(self):
        """Logging out from admin session clears realm; employee logging in cannot access admin."""
        # 1. Admin login
        self.client.post('/admin/login', data={
            'email_or_id': 'admin@antimatrix.com',
            'password': 'Admin@2026Password!'
        }, follow_redirects=True)

        # 2. Admin logout
        resp_logout = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(resp_logout.status_code, 200)

        # 3. Employee login
        self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=True)

        # 4. Ensure admin routes are 403
        resp_forbidden = self.client.get('/admin/dashboard')
        self.assertEqual(resp_forbidden.status_code, 403)

    # 8. Employee logout clears session completely
    def test_15_employee_logout_clears_session(self):
        """Employee logout clears session and subsequent protected route access redirects to login."""
        self._login_as_employee()
        resp_logout = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(resp_logout.status_code, 200)

        # Accessing /dashboard should now redirect to login
        resp_dash = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(resp_dash.status_code, 302)
        self.assertIn('/login', resp_dash.headers.get('Location', ''))


if __name__ == '__main__':
    unittest.main()
