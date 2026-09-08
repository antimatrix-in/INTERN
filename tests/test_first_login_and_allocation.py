import unittest
from datetime import datetime, timezone
import json
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import (
    User, Student, College, Department, Application, Internship,
    InternshipPlan, Project, ProjectAssignment, WeeklyMilestone
)
from app.seed import seed_initial_data
from app.services.problem_allocation_service import ProblemAllocationService
from tests.test_config import TestConfig


class FirstLoginAndAllocationTestCase(unittest.TestCase):
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

    # ── Test A & B: Temporary Credentials Login + First Login Detection ──────
    def test_first_login_redirects_to_change_password(self):
        """
        New employee with must_change_password=True logs in with temporary credentials
        and is immediately redirected to /change-password.
        """
        with self.app.app_context():
            # Mark user as first login
            user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
            user.must_change_password = True
            db.session.commit()

        # Web Form login
        resp = self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/change-password', resp.headers['Location'])

        # API login endpoint
        resp_api = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })
        self.assertEqual(resp_api.status_code, 200)
        data = resp_api.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['must_change_password'])
        self.assertIn('/change-password', data['redirect_url'])

    def test_first_login_guard_blocks_dashboard_access(self):
        """
        User with must_change_password=True attempting to access /dashboard
        is blocked and redirected to /change-password.
        """
        with self.app.app_context():
            user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
            user.must_change_password = True
            db.session.commit()

        # Login
        self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })

        # Try to access dashboard
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/change-password', resp.headers['Location'])

    # ── Test C: Incorrect Current Temporary Password Rejected ────────────────
    def test_change_password_wrong_current_password_rejected(self):
        """Entering incorrect current temporary password returns an error."""
        with self.app.app_context():
            user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
            user.must_change_password = True
            db.session.commit()

        self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })

        resp = self.client.post('/api/auth/change-password', json={
            'current_password': 'WrongCurrentPassword!',
            'new_password': 'BrandNewPassword@2026',
            'confirm_password': 'BrandNewPassword@2026'
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()['success'])
        self.assertIn('Current temporary password is incorrect', resp.get_json()['error'])

    # ── Test D: Mismatched New Password and Confirmation Rejected ────────────
    def test_change_password_mismatched_confirm_rejected(self):
        """Mismatched new password and confirmation is rejected."""
        with self.app.app_context():
            user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
            user.must_change_password = True
            db.session.commit()

        self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })

        resp = self.client.post('/api/auth/change-password', json={
            'current_password': 'Student@2026Password!',
            'new_password': 'BrandNewPassword@2026',
            'confirm_password': 'DifferentPassword@2026'
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()['success'])
        self.assertIn('do not match', resp.get_json()['error'])

    # ── Test E: New Password Same As Temporary Password Rejected ─────────────
    def test_change_password_reusing_temporary_password_rejected(self):
        """Setting new password identical to current temporary password is rejected."""
        with self.app.app_context():
            user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
            user.must_change_password = True
            db.session.commit()

        self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })

        resp = self.client.post('/api/auth/change-password', json={
            'current_password': 'Student@2026Password!',
            'new_password': 'Student@2026Password!',
            'confirm_password': 'Student@2026Password!'
        })
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()['success'])
        self.assertIn('cannot be the same', resp.get_json()['error'])

    # ── Test F through N: Full First-Login Workflow + New Password Login ──────
    def test_full_first_login_workflow_and_relogin_with_new_password(self):
        """
        Complete end-to-end workflow:
        1. Login with temporary password
        2. Change password successfully
        3. must_change_password is cleared
        4. Dashboard opens and displays project
        5. Logout
        6. Old temporary password fails
        7. New password succeeds
        8. Existing project assignment is preserved (not recreated)
        """
        with self.app.app_context():
            user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
            user.must_change_password = True
            db.session.commit()

        # 1. Login with temporary credentials
        login_resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })
        self.assertEqual(login_resp.status_code, 200)

        # 2. Change password
        change_resp = self.client.post('/api/auth/change-password', json={
            'current_password': 'Student@2026Password!',
            'new_password': 'MySecurePassword@2026!',
            'confirm_password': 'MySecurePassword@2026!'
        })
        self.assertEqual(change_resp.status_code, 200)
        self.assertTrue(change_resp.get_json()['success'])

        # 3. Verify user model updated in DB
        with self.app.app_context():
            u = User.query.filter_by(employee_id='AM-INT-2026-001').first()
            self.assertFalse(u.must_change_password)
            self.assertIsNotNone(u.password_changed_at)
            self.assertTrue(u.check_password('MySecurePassword@2026!'))
            self.assertFalse(u.check_password('Student@2026Password!'))

        # 4. Open dashboard
        dash_resp = self.client.get('/dashboard')
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b'Aarav Kumar', dash_resp.data)
        self.assertIn(b'AM-INT-2026-001', dash_resp.data)

        # 5. Logout
        self.client.post('/logout')

        # 6. Old temporary password fails
        fail_resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })
        self.assertEqual(fail_resp.status_code, 401)

        # 7. New password succeeds
        success_resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'MySecurePassword@2026!'
        })
        self.assertEqual(success_resp.status_code, 200)
        self.assertFalse(success_resp.get_json()['must_change_password'])

        # 8. Check assignment preserved
        with self.app.app_context():
            s = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            self.assertEqual(s.active_internship.assignments.count(), 1)

    # ── Test Q & R: Same-College Uniqueness & Different-College Reuse ─────────
    def test_same_college_uniqueness_and_different_college_reuse(self):
        """
        Verify:
        - Students from the SAME college and duration pool receive DIFFERENT Problem IDs.
        - Students from DIFFERENT colleges MAY receive the same Problem ID.
        """
        with self.app.app_context():
            col_1 = College.query.filter_by(code='VIT-CHN').first() or College.query.first()
            col_2 = College.query.filter_by(code='JAYA').first()
            if not col_2:
                col_2 = College(code='JAYA', name='Jaya Engineering College', state='TN', city='Chennai')
                db.session.add(col_2)
                db.session.commit()

            # Ensure at least 2 distinct 1-Month AI/ML projects exist
            p1 = Project.query.filter_by(project_code='AM-PRJ-001').first()
            p2 = Project.query.filter_by(project_code='AM-PRJ-001-ALT').first()
            if not p2:
                p2 = Project(
                    project_code='AM-PRJ-001-ALT',
                    title='IoT Threat Detection and Security Analytics',
                    domain='Artificial Intelligence & Data Science',
                    duration_months=1,
                    duration_weeks=4,
                    is_active=True
                )
                db.session.add(p2)
                db.session.commit()

            # Student 1 from College 1 has p1 actively assigned
            s1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            s1.college_id = col_1.id
            db.session.commit()

            # Eligible problems for College 1 (1-Month) must EXCLUDE p1
            eligible_col1 = ProblemAllocationService.get_eligible_problems(
                college_id=col_1.id,
                duration_months=1,
                domain='Artificial Intelligence & Data Science'
            )
            col1_project_ids = [p.id for p in eligible_col1]
            self.assertNotIn(p1.id, col1_project_ids)
            self.assertIn(p2.id, col1_project_ids)

            # Eligible problems for College 2 (1-Month) MUST INCLUDE p1 (different college reuse allowed!)
            eligible_col2 = ProblemAllocationService.get_eligible_problems(
                college_id=col_2.id,
                duration_months=1,
                domain='Artificial Intelligence & Data Science'
            )
            col2_project_ids = [p.id for p in eligible_col2]
            self.assertIn(p1.id, col2_project_ids)

    # ── Test S: No Eligible Problem Blocks Safely ─────────────────────────────
    def test_no_eligible_problem_blocks_safely_with_clear_error(self):
        """
        When all projects in the pool for a college/duration/domain are actively assigned,
        allocation returns (None, error_message) and does NOT create fake or duplicate assignments.
        """
        with self.app.app_context():
            col = College.query.first()
            
            # Deactivate all projects or assign all of them for this college
            all_1m = Project.query.filter_by(duration_months=1).all()
            for proj in all_1m:
                proj.is_active = False
            db.session.commit()

            problem, err = ProblemAllocationService.allocate_random_problem(
                college_id=col.id,
                duration_months=1,
                domain='Artificial Intelligence & Data Science'
            )
            self.assertIsNone(problem)
            self.assertIsNotNone(err)
            self.assertIn('No available', err)
            self.assertIn('Please add another', err)


if __name__ == '__main__':
    unittest.main()
