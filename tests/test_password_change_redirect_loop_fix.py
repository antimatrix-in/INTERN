"""
Comprehensive Tests for Password Change -> Dashboard Redirect Loop Fix.
Covers required scenarios TEST A through TEST I and shared Supabase role compatibility.
"""

import unittest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import (
    User, Student, College, Department, Application, Internship,
    InternshipPlan, Project, Employee, EmployeeOnboardingCredential, JobApplication
)
from tests.test_config import TestConfig


class PasswordChangeRedirectLoopTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed essential plan, college, and department
        self.plan = InternshipPlan(
            plan_code='1_MONTH_PROJECT',
            title='1 Month Project Internship',
            duration_months=1,
            fee=1499.00,
            currency='INR',
            description='Project internship program',
            features_json='["Project"]',
            is_active=True
        )
        db.session.add(self.plan)

        self.college = College(
            code='COL-001',
            name='Alpha Institute of Technology',
            state='Karnataka',
            city='Bengaluru',
            is_active=True
        )
        db.session.add(self.college)
        db.session.flush()

        self.department = Department(
            college_id=self.college.id,
            code='CSE',
            name='Computer Science and Engineering',
            is_active=True
        )
        db.session.add(self.department)
        db.session.flush()

        # Seed a Project for allocation
        self.project = Project(
            project_code='AM-PRJ-001',
            title='AI Powered Analytics Dashboard',
            domain='Artificial Intelligence & Data Science',
            duration_months=1,
            duration_weeks=4,
            is_active=True
        )
        db.session.add(self.project)

        # Seed Admin user for Admin Login Test (TEST H)
        self.admin = User(
            email='admin@antimatrix.tech',
            employee_id='AM-ADM-001',
            full_name='System Administrator',
            role='super_admin',
            is_active=True,
            must_change_password=False
        )
        self.admin.set_password('AdminSecurePass@2026')
        db.session.add(self.admin)

        # Create sample corporate JobApplication for test employee
        self.job_app = JobApplication(
            application_code='AM-APP-2026-901',
            full_name='Test Employee',
            first_name='Test',
            last_name='Employee',
            email='employee@antimatrix.tech',
            phone='+919876543210',
            duration='1_month',
            college=self.college.name,
            department=self.department.name,
            degree='B.Tech',
            graduation_year='2026',
            payment_status='paid',
            status='SHORTLISTED'
        )
        db.session.add(self.job_app)
        db.session.flush()

        # Create sample corporate Employee
        self.emp_id = 'AM7586'
        self.temp_password = 'TempPass@2026#Secure'
        self.new_password = 'NewSecurePass@2026!Unique'

        self.employee = Employee(
            employee_id=self.emp_id,
            application_id=self.job_app.id,
            account_status='active',
            temporary_password_active=True
        )
        self.employee.set_password(self.temp_password)
        db.session.add(self.employee)
        db.session.flush()

        # Create onboarding credential row (ACTIVE)
        self.onboarding_cred = EmployeeOnboardingCredential(
            employee_id=self.emp_id,
            temporary_password_hash=generate_password_hash(self.temp_password),
            temporary_password_encrypted='encrypted_token_placeholder',
            status='ACTIVE'
        )
        db.session.add(self.onboarding_cred)
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # ─── TEST A: Temporary login → /change-password → submit new password → /dashboard loads
    def test_a_temporary_login_change_password_to_dashboard(self):
        # 1. Login with temporary password
        login_resp = self.client.post('/login', data={
            'employee_id': self.emp_id,
            'password': self.temp_password
        }, follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertIn('/change-password', login_resp.headers['Location'])

        # Follow redirect to /change-password
        change_page = self.client.get('/change-password')
        self.assertEqual(change_page.status_code, 200)
        self.assertIn(b'CHANGE TEMPORARY PASSWORD', change_page.data)

        # 2. Submit new secure password
        submit_resp = self.client.post('/change-password', data={
            'current_password': self.temp_password,
            'new_password': self.new_password,
            'confirm_password': self.new_password
        }, follow_redirects=False)

        # Must redirect directly to /dashboard
        self.assertEqual(submit_resp.status_code, 302)
        self.assertIn('/dashboard', submit_resp.headers['Location'])

        # 3. Request /dashboard - MUST LOAD 200 OK without redirect loop
        dash_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b'Dashboard', dash_resp.data)

        # Verify DB state
        u = User.query.filter_by(employee_id=self.emp_id).first()
        self.assertIsNotNone(u)
        self.assertFalse(u.must_change_password)
        self.assertIsNotNone(u.password_changed_at)

        cred = EmployeeOnboardingCredential.query.filter_by(employee_id=self.emp_id).first()
        self.assertEqual(cred.status, 'RESET')
        self.assertIsNotNone(cred.password_reset_at)

    # ─── TEST B: Refresh /dashboard → dashboard still loads
    def test_b_refresh_dashboard_remains_loaded(self):
        # First perform change password
        self.test_a_temporary_login_change_password_to_dashboard()

        # Refresh dashboard multiple times
        for _ in range(3):
            dash_resp = self.client.get('/dashboard', follow_redirects=False)
            self.assertEqual(dash_resp.status_code, 200)
            self.assertIn(b'Dashboard', dash_resp.data)

    # ─── TEST C: Logout → /login
    def test_c_logout_redirects_to_login(self):
        self.test_a_temporary_login_change_password_to_dashboard()

        logout_resp = self.client.get('/logout', follow_redirects=False)
        self.assertEqual(logout_resp.status_code, 302)
        self.assertIn('/login', logout_resp.headers['Location'])

        # Unauthenticated access to /dashboard now redirects to /login
        unauth_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(unauth_resp.status_code, 302)
        self.assertIn('/login', unauth_resp.headers['Location'])

    # ─── TEST D: Login using the NEW password → /dashboard
    def test_d_login_using_new_password(self):
        # Perform password change first
        self.test_a_temporary_login_change_password_to_dashboard()

        # Logout
        self.client.get('/logout')

        # Old temporary password MUST FAIL
        fail_resp = self.client.post('/login', data={
            'employee_id': self.emp_id,
            'password': self.temp_password
        }, follow_redirects=False)
        self.assertEqual(fail_resp.status_code, 200) # Re-renders login with error
        self.assertIn(b'Invalid Employee ID or password', fail_resp.data)

        # Login with NEW password succeeds and goes straight to /dashboard
        login_resp = self.client.post('/login', data={
            'employee_id': self.emp_id,
            'password': self.new_password
        }, follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertIn('/dashboard', login_resp.headers['Location'])

        # Dashboard loads 200 OK
        dash_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash_resp.status_code, 200)

    # ─── TEST E: Refresh dashboard → remains authenticated
    def test_e_refresh_after_new_password_login(self):
        self.test_d_login_using_new_password()

        dash_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash_resp.status_code, 200)

    # ─── TEST F: Open /login while authenticated → correct dashboard, no loop
    def test_f_open_login_while_authenticated_redirects_cleanly(self):
        self.test_d_login_using_new_password()

        # While authenticated, hitting /login redirects directly to /dashboard
        login_resp = self.client.get('/login', follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertIn('/dashboard', login_resp.headers['Location'])

        # Following to /dashboard loads 200 OK without loop
        dash_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash_resp.status_code, 200)

    # ─── TEST G: User whose must_change_password is already false → normal login → dashboard
    def test_g_normal_user_login_direct_to_dashboard(self):
        # Create normal student user whose must_change_password is False
        normal_user = User(
            email='normal.student@antimatrix.tech',
            employee_id='AM-NORM-001',
            full_name='Normal Student',
            role='student',
            is_active=True,
            must_change_password=False
        )
        normal_user.set_password('NormalPass@2026#Secure')
        db.session.add(normal_user)
        db.session.commit()

        login_resp = self.client.post('/login', data={
            'employee_id': 'AM-NORM-001',
            'password': 'NormalPass@2026#Secure'
        }, follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertIn('/dashboard', login_resp.headers['Location'])

        dash_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash_resp.status_code, 200)

    # ─── TEST H: Admin login → admin dashboard → existing admin authentication still works
    def test_h_admin_login_works(self):
        login_resp = self.client.post('/login', data={
            'employee_id': 'admin@antimatrix.tech',
            'password': 'AdminSecurePass@2026'
        }, follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertIn('/admin/dashboard', login_resp.headers['Location'])

        admin_dash = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(admin_dash.status_code, 200)

    # ─── TEST I: Invalid current temporary password → normal validation error, no loop
    def test_i_invalid_current_temporary_password_validation_error(self):
        # Login with temporary password
        self.client.post('/login', data={
            'employee_id': self.emp_id,
            'password': self.temp_password
        })

        # Submit WRONG current password
        resp = self.client.post('/change-password', data={
            'current_password': 'WrongTempPassword123!',
            'new_password': self.new_password,
            'confirm_password': self.new_password
        }, follow_redirects=False)

        # Must NOT redirect to dashboard or cause loop - must re-render form
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Current temporary password is incorrect', resp.data)

    # ─── TEST J: User with role='member' / 'candidate' from shared Supabase DB
    def test_j_shared_supabase_user_role_member_no_redirect_loop(self):
        """
        Critical edge case: User already exists in shared DB with role='member'
        and employee_id initially None or different.
        Must seamlessly authenticate, update password, link employee, and load dashboard.
        """
        # Pre-existing user in shared DB with role='member'
        existing_member = User(
            email='member.candidate@antimatrix.tech',
            full_name='Existing Platform Member',
            role='member',
            is_active=True,
            must_change_password=False
        )
        existing_member.set_password('OldPlatformPass@2026')
        db.session.add(existing_member)
        db.session.commit()

        # Link JobApplication with this email
        app_code = 'AM-APP-MEMBER-01'
        emp_code = 'AM9911'
        job_app2 = JobApplication(
            application_code=app_code,
            full_name='Existing Platform Member',
            email='member.candidate@antimatrix.tech',
            duration='1_month',
            college=self.college.name,
            department=self.department.name,
            degree='B.Tech',
            graduation_year='2026',
            payment_status='paid',
            status='SHORTLISTED'
        )
        db.session.add(job_app2)
        db.session.flush()

        emp2 = Employee(
            employee_id=emp_code,
            application_id=job_app2.id,
            account_status='active',
            temporary_password_active=True
        )
        emp2.set_password('TempPassMember@2026')
        db.session.add(emp2)
        db.session.flush()

        cred2 = EmployeeOnboardingCredential(
            employee_id=emp_code,
            temporary_password_hash=generate_password_hash('TempPassMember@2026'),
            status='ACTIVE'
        )
        db.session.add(cred2)
        db.session.commit()

        # 1. Login with employee ID and temp password
        login_resp = self.client.post('/login', data={
            'employee_id': emp_code,
            'password': 'TempPassMember@2026'
        }, follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertIn('/change-password', login_resp.headers['Location'])

        # 2. Change password
        submit_resp = self.client.post('/change-password', data={
            'current_password': 'TempPassMember@2026',
            'new_password': 'NewSecurePassMember@2026!',
            'confirm_password': 'NewSecurePassMember@2026!'
        }, follow_redirects=False)
        self.assertEqual(submit_resp.status_code, 302)
        self.assertIn('/dashboard', submit_resp.headers['Location'])

        # 3. Dashboard loads without redirect loop!
        dash_resp = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b'Dashboard', dash_resp.data)
