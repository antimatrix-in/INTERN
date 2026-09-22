"""Unit test suite for the 'Delete All Employees' admin action."""
import unittest
from flask import session
from app import create_app
from app.extensions import db
from app.models import (
    User, Student, Internship, InternshipPlan, Project, ProjectAssignment,
    WeeklyMilestone, WeeklyTask, WeeklySubmission, Evaluation, College, Department,
    AuditLog, Employee, EmployeeOnboardingCredential, Application
)
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class DeleteAllEmployeesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.drop_all()
        db.create_all()
        seed_initial_data()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login_admin(self):
        """Helper to establish an authenticated admin session."""
        return self.client.post('/admin/login', data={
            'email_or_id': 'admin@antimatrix.ai',
            'password': 'Admin@AntiMatrix2026!'
        }, follow_redirects=True)

    def _login_employee(self, emp_id='AM-INT-2026-001', password='Student@2026Password!'):
        """Helper to establish an authenticated employee session."""
        return self.client.post('/login', data={
            'employee_id': emp_id,
            'password': password
        }, follow_redirects=True)

    # ─── 1. Access Control / Authorization ────────────────────────────────────────

    def test_01_unauthenticated_request_is_redirected(self):
        """Unauthenticated POST to /admin/employees/delete-all must redirect to login."""
        resp = self.client.post('/admin/employees/delete-all', data={
            'confirmation_phrase': 'DELETE ALL EMPLOYEES'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers.get('Location', ''))

    def test_02_employee_session_cannot_access_delete_all(self):
        """Employee attempting to call /admin/employees/delete-all must get 403 Forbidden."""
        self._login_employee()
        resp = self.client.post('/admin/employees/delete-all', data={
            'confirmation_phrase': 'DELETE ALL EMPLOYEES'
        })
        self.assertEqual(resp.status_code, 403)

    # ─── 2. Phrase Verification ───────────────────────────────────────────────────

    def test_03_invalid_phrase_is_rejected(self):
        """Any phrase other than exact 'DELETE ALL EMPLOYEES' must be rejected."""
        self._login_admin()
        
        # Test lowercase
        resp1 = self.client.post('/admin/employees/delete-all', data={
            'confirmation_phrase': 'delete all employees'
        }, follow_redirects=True)
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b'Confirmation phrase did not match', resp1.data)

        # Test partial / with whitespace
        resp2 = self.client.post('/admin/employees/delete-all', data={
            'confirmation_phrase': ' DELETE ALL EMPLOYEES '
        }, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'Confirmation phrase did not match', resp2.data)

        # Test empty
        resp3 = self.client.post('/admin/employees/delete-all', data={
            'confirmation_phrase': ''
        }, follow_redirects=True)
        self.assertEqual(resp3.status_code, 200)
        self.assertIn(b'Confirmation phrase did not match', resp3.data)

    # ─── 3. Dependency Safety / Rollback ──────────────────────────────────────────

    def test_04_dependent_submissions_block_deletion(self):
        """If employees have historical submissions, deletion must halt and rollback."""
        self._login_admin()

        # Add a submission to Student 1
        student = Student.query.first()
        milestone = WeeklyMilestone.query.first()
        submission = WeeklySubmission(
            milestone_id=milestone.id,
            student_id=student.id,
            repo_url='https://github.com/test/repo',
            status='SUBMITTED'
        )
        db.session.add(submission)
        db.session.commit()

        resp = self.client.post('/admin/employees/delete-all', data={
            'confirmation_phrase': 'DELETE ALL EMPLOYEES'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Employees could not be deleted because related records require attention', resp.data)

        # Ensure student is still active
        active_count = Student.query.join(Internship).filter(Internship.status == 'ACTIVE').count()
        self.assertGreater(active_count, 0)

    def test_05_dependent_evaluations_block_deletion(self):
        """If employees have historical evaluations, deletion must halt and rollback."""
        self._login_admin()

        # Add an evaluation to Student 1
        student = Student.query.first()
        admin_user = User.query.filter_by(role='admin').first()
        evaluation = Evaluation(
            employee_id=student.id,
            admin_id=admin_user.id,
            total_score=95,
            feedback='Excellent milestone delivery',
            action='APPROVE'
        )
        db.session.add(evaluation)
        db.session.commit()

        resp = self.client.post('/admin/employees/delete-all', data={
            'confirmation_phrase': 'DELETE ALL EMPLOYEES'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Employees could not be deleted because related records require attention', resp.data)

    # ─── 4. Successful Deletion of Eligible Employees ─────────────────────────────

    def test_06_successful_deletion_of_eligible_employees(self):
        """When no blocking evaluations/submissions exist, eligible employees are removed."""
        self._login_admin()

        # Clean up any seeded meetings on demo students for eligible test
        student1 = Student.query.first()
        from app.models import Meeting
        Meeting.query.filter_by(student_id=student1.id).delete()
        db.session.commit()

        resp = self.client.post('/admin/employees/delete-all', data={
            'confirmation_phrase': 'DELETE ALL EMPLOYEES'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'All eligible employee records have been deleted successfully', resp.data)

        # Verify employee directory now shows 0 Active Interns
        resp_dir = self.client.get('/admin/employees')
        self.assertEqual(resp_dir.status_code, 200)
        self.assertIn(b'0 Active Interns', resp_dir.data)

        # Verify audit log was created
        audit = AuditLog.query.filter_by(action='DELETE_ALL_EMPLOYEES').first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.target_entity, 'employees')

        # Verify admin user remains active
        admin_user = User.query.filter_by(email='admin@antimatrix.ai').first()
        self.assertIsNotNone(admin_user)
        self.assertTrue(admin_user.is_active)
        self.assertEqual(admin_user.role, 'admin')


if __name__ == '__main__':
    unittest.main()
