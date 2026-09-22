"""Test suite verifying scenarios A through J for Authentication Bug Fix."""
import unittest
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import User, Student, College, Department, Internship, InternshipPlan, Application
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class AuthenticationScenariosTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestConfig)

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            seed_initial_data()

            col = College.query.first()
            dept = Department.query.filter_by(college_id=col.id).first()
            plan = InternshipPlan.query.first()

            # Employee A
            user_a = User(
                email="emp_a@antimatrix.co.in",
                employee_id="AM-EMP-001",
                role="student",
                full_name="Employee Alice"
            )
            user_a.set_password("Alice@2026Pass!")
            db.session.add(user_a)
            db.session.flush()

            student_a = Student(
                user_id=user_a.id,
                student_uid="AM-EMP-001",
                college_id=col.id,
                department_id=dept.id,
                roll_number="ALICE01",
                degree="B.Tech",
                current_year="Final Year",
                graduation_year="2026",
                is_verified=True
            )
            db.session.add(student_a)
            db.session.flush()

            app_a = Application(
                application_no="AM-APP-001",
                student_id=student_a.id,
                plan_id=plan.id,
                status='APPROVED',
                candidate_name=user_a.full_name,
                candidate_email=user_a.email,
                converted_employee_id="AM-EMP-001",
                is_converted_to_employee=True
            )
            db.session.add(app_a)
            db.session.flush()

            internship_a = Internship(
                internship_no="AM-EMP-001",
                student_id=student_a.id,
                application_id=app_a.id,
                plan_id=plan.id,
                status='ACTIVE',
                start_date='01 Jan 2026',
                end_date='01 Apr 2026',
                progress_percent=25,
                current_stage='Phase 1'
            )
            db.session.add(internship_a)

            # Employee B
            user_b = User(
                email="emp_b@antimatrix.co.in",
                employee_id="AM-EMP-002",
                role="student",
                full_name="Employee Bob"
            )
            user_b.set_password("Bob@2026Pass!")
            db.session.add(user_b)
            db.session.flush()

            student_b = Student(
                user_id=user_b.id,
                student_uid="AM-EMP-002",
                college_id=col.id,
                department_id=dept.id,
                roll_number="BOB02",
                degree="B.Tech",
                current_year="Final Year",
                graduation_year="2026",
                is_verified=True
            )
            db.session.add(student_b)
            db.session.flush()

            app_b = Application(
                application_no="AM-APP-002",
                student_id=student_b.id,
                plan_id=plan.id,
                status='APPROVED',
                candidate_name=user_b.full_name,
                candidate_email=user_b.email,
                converted_employee_id="AM-EMP-002",
                is_converted_to_employee=True
            )
            db.session.add(app_b)
            db.session.flush()

            internship_b = Internship(
                internship_no="AM-EMP-002",
                student_id=student_b.id,
                application_id=app_b.id,
                plan_id=plan.id,
                status='ACTIVE',
                start_date='01 Jan 2026',
                end_date='01 Apr 2026',
                progress_percent=10,
                current_stage='Phase 1'
            )
            db.session.add(internship_b)

            # Admin User
            admin_user = User.query.filter_by(role='admin').first()
            if not admin_user:
                admin_user = User(
                    email="admin_test_supervisor@antimatrix.ai",
                    employee_id="AM-ADM-001",
                    role="admin",
                    full_name="Admin Supervisor"
                )
                db.session.add(admin_user)
            admin_user.set_password("Admin@Super2026!")
            db.session.commit()
            self.admin_email = admin_user.email

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # TEST A — CLEAN BROWSER
    def test_scenario_a_clean_browser(self):
        """Clean browser requesting / must redirect to /login, not /dashboard."""
        resp = self.client.get('/', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])
        self.assertNotIn('/dashboard', resp.headers['Location'])

        # Follow redirect and verify login page rendered
        follow_resp = self.client.get(resp.headers['Location'])
        self.assertEqual(follow_resp.status_code, 200)
        self.assertIn(b'Employee ID', follow_resp.data)

    # TEST B — DIRECT DASHBOARD
    def test_scenario_b_direct_dashboard(self):
        """Unauthenticated GET /dashboard must redirect to /login."""
        resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    # TEST C — LOGIN
    def test_scenario_c_login(self):
        """Valid employee login lands on Employee Dashboard."""
        login_resp = self.client.post('/login', data={
            'employee_id': 'AM-EMP-001',
            'password': 'Alice@2026Pass!'
        }, follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertIn('/dashboard', login_resp.headers['Location'])

        dash_resp = self.client.get('/dashboard')
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b'Alice', dash_resp.data)

    # TEST D — REFRESH
    def test_scenario_d_refresh(self):
        """Refreshing /dashboard keeps session active and returns 200."""
        self.client.post('/login', data={
            'employee_id': 'AM-EMP-001',
            'password': 'Alice@2026Pass!'
        }, follow_redirects=True)

        resp1 = self.client.get('/dashboard')
        self.assertEqual(resp1.status_code, 200)

        # Refresh
        resp2 = self.client.get('/dashboard')
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'Alice', resp2.data)

    # TEST E — LOGOUT
    def test_scenario_e_logout(self):
        """Sign out terminates session, redirects to /login, and sends cookie expiration headers."""
        self.client.post('/login', data={
            'employee_id': 'AM-EMP-001',
            'password': 'Alice@2026Pass!'
        }, follow_redirects=True)

        logout_resp = self.client.get('/logout', follow_redirects=False)
        self.assertEqual(logout_resp.status_code, 302)
        self.assertIn('/login', logout_resp.headers['Location'])

        # Verify Set-Cookie headers expire cookies (Max-Age=0 or 1970 Expires)
        set_cookies = logout_resp.headers.getlist('Set-Cookie')
        self.assertTrue(len(set_cookies) > 0)
        cookie_str = ' '.join(set_cookies)
        self.assertTrue('Max-Age=0' in cookie_str or 'Expires=Thu, 01 Jan 1970' in cookie_str)

    # TEST F — BACK BUTTON
    def test_scenario_f_back_button(self):
        """Dynamic responses send no-cache headers; server rejects re-requested dashboard after logout."""
        self.client.post('/login', data={
            'employee_id': 'AM-EMP-001',
            'password': 'Alice@2026Pass!'
        }, follow_redirects=True)

        dash_resp = self.client.get('/dashboard')
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn('no-store', dash_resp.headers.get('Cache-Control', ''))
        self.assertIn('no-cache', dash_resp.headers.get('Cache-Control', ''))

        # Logout
        self.client.get('/logout', follow_redirects=True)

        # Back button simulation: client requests /dashboard again
        back_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(back_resp.status_code, 302)
        self.assertIn('/login', back_resp.headers['Location'])

    # TEST G — DIRECT DASHBOARD AFTER LOGOUT
    def test_scenario_g_direct_dashboard_after_logout(self):
        """After logout, navigating directly to /dashboard redirects to /login."""
        self.client.post('/login', data={
            'employee_id': 'AM-EMP-001',
            'password': 'Alice@2026Pass!'
        }, follow_redirects=True)

        self.client.get('/logout', follow_redirects=True)

        dash_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash_resp.status_code, 302)
        self.assertIn('/login', dash_resp.headers['Location'])

    # TEST H — NEW TAB
    def test_scenario_h_new_tab(self):
        """A new client/tab without session cookies visiting /dashboard redirects to /login."""
        # Authenticate and then logout in first client
        self.client.post('/login', data={
            'employee_id': 'AM-EMP-001',
            'password': 'Alice@2026Pass!'
        }, follow_redirects=True)
        self.client.get('/logout', follow_redirects=True)

        # Simulate opening new tab with clean client
        new_tab_client = self.app.test_client()
        resp = new_tab_client.get('/dashboard', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    # TEST I — ADMIN ISOLATION
    def test_scenario_i_admin_isolation(self):
        """Employee cannot access /admin/*; Admin session cannot access /dashboard."""
        # 1. Employee session attempting /admin/dashboard
        self.client.post('/login', data={
            'employee_id': 'AM-EMP-001',
            'password': 'Alice@2026Pass!'
        }, follow_redirects=True)

        admin_resp = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(admin_resp.status_code, 403)

        self.client.get('/logout', follow_redirects=True)

        # 2. Admin session attempting /dashboard -> redirected to /admin/dashboard
        self.client.post('/admin/login', data={
            'email_or_id': self.admin_email,
            'password': 'Admin@Super2026!'
        }, follow_redirects=True)

        emp_dash_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(emp_dash_resp.status_code, 302)
        self.assertIn('/admin/dashboard', emp_dash_resp.headers['Location'])

    # TEST J — MULTIPLE EMPLOYEES
    def test_scenario_j_multiple_employees(self):
        """Employee A sees Alice's data; Employee B sees Bob's data. No leakage."""
        client_a = self.app.test_client()
        client_b = self.app.test_client()

        # Alice logs in
        client_a.post('/login', data={
            'employee_id': 'AM-EMP-001',
            'password': 'Alice@2026Pass!'
        }, follow_redirects=True)

        # Bob logs in
        client_b.post('/login', data={
            'employee_id': 'AM-EMP-002',
            'password': 'Bob@2026Pass!'
        }, follow_redirects=True)

        resp_a = client_a.get('/dashboard')
        resp_b = client_b.get('/dashboard')

        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_b.status_code, 200)

        self.assertIn(b'Alice', resp_a.data)
        self.assertNotIn(b'Bob', resp_a.data)

        self.assertIn(b'Bob', resp_b.data)
        self.assertNotIn(b'Alice', resp_b.data)


if __name__ == '__main__':
    unittest.main()
