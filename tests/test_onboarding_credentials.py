"""
Unit and Integration Tests for Employee Onboarding Credentials & Authentication Gateway.
Tests all lifecycle states: temporary credential verification, first-login password change,
RESET transition, old password rejection, new password verification, and employee data isolation.
"""

import unittest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app import create_app
from app.extensions import db
from app.models import (
    User, Student, College, Department, Application, Internship,
    InternshipPlan, Project, ProjectAssignment, WeeklyMilestone,
    Employee, EmployeeOnboardingCredential, JobApplication
)
from tests.test_config import TestConfig


class OnboardingCredentialsTestCase(unittest.TestCase):
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

        # Create sample corporate JobApplication
        self.job_app = JobApplication(
            application_code='AM-APP-2026-901',
            full_name='Vikram Sharma',
            first_name='Vikram',
            last_name='Sharma',
            email='vikram.sharma@example.com',
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
        self.emp_id = 'AM2981'
        self.temp_password = 'TempPass@2026#Secure'
        self.employee = Employee(
            employee_id=self.emp_id,
            application_id=self.job_app.id,
            account_status='active'
        )
        self.employee.set_password(self.temp_password)
        db.session.add(self.employee)
        db.session.flush()

        # Create onboarding credential row
        self.onboarding_cred = EmployeeOnboardingCredential(
            employee_id=self.emp_id,
            temporary_password_hash=generate_password_hash(self.temp_password),
            temporary_password_encrypted='encrypted_placeholder_token',
            status='ACTIVE'
        )
        db.session.add(self.onboarding_cred)
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # ─── 1. Model & Verification Tests ──────────────────────────────────────────

    def test_01_onboarding_credential_model_verification(self):
        """Verify EmployeeOnboardingCredential attributes and password verification."""
        cred = EmployeeOnboardingCredential.query.filter_by(employee_id=self.emp_id).first()
        self.assertIsNotNone(cred)
        self.assertEqual(cred.employee_id, self.emp_id)
        self.assertEqual(cred.status, 'ACTIVE')
        self.assertTrue(cred.is_active)
        self.assertIsNone(cred.password_reset_at)

        # Correct password verifies
        self.assertTrue(cred.verify_password(self.temp_password))

        # Wrong password fails
        self.assertFalse(cred.verify_password('WrongPassword123!'))

    def test_02_onboarding_credential_mark_reset(self):
        """Verify mark_reset updates status, timestamp, and clears encrypted temp password."""
        cred = EmployeeOnboardingCredential.query.filter_by(employee_id=self.emp_id).first()
        cred.mark_reset()
        db.session.commit()

        refreshed = EmployeeOnboardingCredential.query.filter_by(employee_id=self.emp_id).first()
        self.assertEqual(refreshed.status, 'RESET')
        self.assertFalse(refreshed.is_active)
        self.assertIsNotNone(refreshed.password_reset_at)
        self.assertIsNone(refreshed.temporary_password_encrypted)

        # Old password must strictly return False once RESET
        self.assertFalse(refreshed.verify_password(self.temp_password))

    # ─── 2. Authentication Gateway Tests ───────────────────────────────────────

    def test_03_login_with_active_temporary_credential_succeeds_and_requires_password_change(self):
        """Active onboarding credential authenticates, sets must_change_password, and redirects."""
        # Test API Gateway
        resp_api = self.client.post('/api/auth/employee-login', json={
            'employee_id': self.emp_id,
            'password': self.temp_password
        })
        self.assertEqual(resp_api.status_code, 200)
        data = resp_api.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['must_change_password'])
        self.assertIn('/change-password', data['redirect_url'])
        self.assertEqual(data['user']['employee_id'], self.emp_id)

        # Verify User and Student records were created and linked without duplicate
        user = User.query.filter_by(employee_id=self.emp_id).first()
        self.assertIsNotNone(user)
        self.assertTrue(user.must_change_password)
        self.assertIsNotNone(user.student_profile)
        self.assertEqual(user.student_profile.student_uid, self.emp_id)

        # Test Web form login
        resp_web = self.client.post('/login', data={
            'employee_id': self.emp_id,
            'password': self.temp_password
        }, follow_redirects=False)
        self.assertEqual(resp_web.status_code, 302)
        self.assertIn('/change-password', resp_web.headers['Location'])

    def test_04_login_with_wrong_password_fails_with_generic_error(self):
        """Wrong password fails with 401 and generic error message to prevent enumeration."""
        resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': self.emp_id,
            'password': 'CompletelyWrongPassword123!'
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid Employee ID or password.')

    def test_05_login_with_invalid_employee_id_fails_with_generic_error(self):
        """Non-existent Employee ID fails with 401 and identical generic error."""
        resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM999999',
            'password': 'AnyPassword123!'
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid Employee ID or password.')

    def test_06_login_empty_fields_fail(self):
        """Missing Employee ID or password returns 400."""
        resp1 = self.client.post('/api/auth/employee-login', json={
            'employee_id': '',
            'password': 'password'
        })
        self.assertEqual(resp1.status_code, 400)

        resp2 = self.client.post('/api/auth/employee-login', json={
            'employee_id': self.emp_id,
            'password': ''
        })
        self.assertEqual(resp2.status_code, 400)

    # ─── 3. Account Activation & Password Change Tests ─────────────────────────

    def test_07_complete_first_login_password_change_lifecycle(self):
        """
        Complete flow:
        1. Login with temporary password -> must_change_password=True.
        2. Attempt dashboard -> redirected to /change-password.
        3. Submit new permanent password.
        4. Onboarding credential is marked RESET.
        5. Old temporary password fails.
        6. New permanent password succeeds without must_change_password.
        """
        # 1. Login with temporary password
        resp_login = self.client.post('/api/auth/employee-login', json={
            'employee_id': self.emp_id,
            'password': self.temp_password
        })
        self.assertEqual(resp_login.status_code, 200)

        # 2. Access dashboard before password change -> blocked / redirected
        resp_dash = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(resp_dash.status_code, 302)
        self.assertIn('/change-password', resp_dash.headers['Location'])

        # 3. Change password via API
        new_permanent_password = 'PermanentSecretPass2026!#'
        resp_change = self.client.post('/api/auth/change-password', json={
            'current_password': self.temp_password,
            'new_password': new_permanent_password,
            'confirm_password': new_permanent_password
        })
        self.assertEqual(resp_change.status_code, 200)
        change_data = resp_change.get_json()
        self.assertTrue(change_data['success'])

        # 4. Verify DB state
        cred = EmployeeOnboardingCredential.query.filter_by(employee_id=self.emp_id).first()
        self.assertEqual(cred.status, 'RESET')
        self.assertIsNotNone(cred.password_reset_at)
        self.assertIsNone(cred.temporary_password_encrypted)

        user = User.query.filter_by(employee_id=self.emp_id).first()
        self.assertFalse(user.must_change_password)
        self.assertTrue(user.check_password(new_permanent_password))
        self.assertFalse(user.check_password(self.temp_password))

        # Logout
        self.client.get('/logout')

        # 5. Old temporary password now FAILS
        resp_old_pw = self.client.post('/api/auth/employee-login', json={
            'employee_id': self.emp_id,
            'password': self.temp_password
        })
        self.assertEqual(resp_old_pw.status_code, 401)
        self.assertEqual(resp_old_pw.get_json()['error'], 'Invalid Employee ID or password.')

        # 6. New permanent password SUCCEEDS and does not require change
        resp_new_pw = self.client.post('/api/auth/employee-login', json={
            'employee_id': self.emp_id,
            'password': new_permanent_password
        })
        self.assertEqual(resp_new_pw.status_code, 200)
        new_data = resp_new_pw.get_json()
        self.assertTrue(new_data['success'])
        self.assertFalse(new_data['must_change_password'])
        self.assertIn('/dashboard', new_data['redirect_url'])

    def test_08_password_change_validations(self):
        """Verify change-password validations: current password mismatch, short password, confirmation mismatch."""
        # Login first
        self.client.post('/api/auth/employee-login', json={
            'employee_id': self.emp_id,
            'password': self.temp_password
        })

        # Wrong current password
        resp1 = self.client.post('/api/auth/change-password', json={
            'current_password': 'WrongCurrentPassword!',
            'new_password': 'ValidNewPass123!',
            'confirm_password': 'ValidNewPass123!'
        })
        self.assertEqual(resp1.status_code, 400)
        self.assertIn('Current temporary password is incorrect', resp1.get_json()['error'])

        # New password same as current
        resp2 = self.client.post('/api/auth/change-password', json={
            'current_password': self.temp_password,
            'new_password': self.temp_password,
            'confirm_password': self.temp_password
        })
        self.assertEqual(resp2.status_code, 400)
        self.assertIn('New password cannot be the same', resp2.get_json()['error'])

        # Passwords don't match
        resp3 = self.client.post('/api/auth/change-password', json={
            'current_password': self.temp_password,
            'new_password': 'ValidNewPass123!',
            'confirm_password': 'DifferentPass123!'
        })
        self.assertEqual(resp3.status_code, 400)
        self.assertIn('do not match', resp3.get_json()['error'])

        # Password too short (< 6 chars)
        resp4 = self.client.post('/api/auth/change-password', json={
            'current_password': self.temp_password,
            'new_password': 'abc',
            'confirm_password': 'abc'
        })
        self.assertEqual(resp4.status_code, 400)
        self.assertIn('at least 6 characters', resp4.get_json()['error'])

    # ─── 4. Employee Data Isolation (IDOR Protection) ──────────────────────────

    def test_09_employee_data_isolation_idor_prevention(self):
        """Verify Employee A cannot access Employee B's project assignments or data."""
        # Create second employee B
        emp_b_id = 'AM3042'
        emp_b = Employee(
            employee_id=emp_b_id,
            account_status='active'
        )
        emp_b.set_password('PassB@2026Secure')
        db.session.add(emp_b)

        cred_b = EmployeeOnboardingCredential(
            employee_id=emp_b_id,
            temporary_password_hash=generate_password_hash('PassB@2026Secure'),
            status='ACTIVE'
        )
        db.session.add(cred_b)
        db.session.commit()

        # Login as Employee A and complete activation
        self.client.post('/api/auth/employee-login', json={
            'employee_id': self.emp_id,
            'password': self.temp_password
        })
        self.client.post('/api/auth/change-password', json={
            'current_password': self.temp_password,
            'new_password': 'PermanentPassA123!',
            'confirm_password': 'PermanentPassA123!'
        })

        # Login as Employee B and complete activation
        self.client.get('/logout')
        self.client.post('/api/auth/employee-login', json={
            'employee_id': emp_b_id,
            'password': 'PassB@2026Secure'
        })
        self.client.post('/api/auth/change-password', json={
            'current_password': 'PassB@2026Secure',
            'new_password': 'PermanentPassB123!',
            'confirm_password': 'PermanentPassB123!'
        })

        # Get Employee B's assignment ID
        user_b = User.query.filter_by(employee_id=emp_b_id).first()
        student_b = user_b.student_profile
        internship_b = student_b.active_internship
        project_b = Project(
            project_code='PRJ-TEST-B',
            title='Project B Dedicated',
            duration_months=1,
            domain='AI',
            problem_statement='Problem B'
        )
        db.session.add(project_b)
        db.session.flush()

        assign_b = ProjectAssignment(
            internship_id=internship_b.id,
            project_id=project_b.id,
            assigned_by=user_b.id,
            deadline='30 Oct 2026',
            status='IN_PROGRESS'
        )
        db.session.add(assign_b)

        # Also ensure Employee A has an active assignment
        user_a = User.query.filter_by(employee_id=self.emp_id).first()
        student_a = user_a.student_profile
        internship_a = student_a.active_internship
        project_a = Project(
            project_code='PRJ-TEST-A',
            title='Project A Dedicated',
            duration_months=1,
            domain='Web',
            problem_statement='Problem A'
        )
        db.session.add(project_a)
        db.session.flush()
        assign_a = ProjectAssignment(
            internship_id=internship_a.id,
            project_id=project_a.id,
            assigned_by=user_a.id,
            deadline='30 Oct 2026',
            status='IN_PROGRESS'
        )
        db.session.add(assign_a)
        db.session.commit()

        # Now switch back and login as Employee A
        self.client.get('/logout')
        self.client.post('/api/auth/employee-login', json={
            'employee_id': self.emp_id,
            'password': 'PermanentPassA123!'
        })

        # Employee A attempts to access Employee B's project by ID in URL
        resp_idor = self.client.get(f'/project/{assign_b.id}')
        # Should be forbidden (403)
        self.assertEqual(resp_idor.status_code, 403)


if __name__ == '__main__':
    unittest.main()
