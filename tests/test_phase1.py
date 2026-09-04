import unittest
from app import create_app
from app.extensions import db
from app.models import User, Student, ProjectAssignment, WeeklyMilestone, WeeklySubmission, Meeting, Notification
from app.seed import seed_initial_data
from tests.test_config import TestConfig

class Phase1PortalTestCase(unittest.TestCase):
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

    def test_root_and_unauthenticated_redirect(self):
        """Unauthenticated requests to root or dashboard should redirect to login."""
        r1 = self.client.get('/')
        self.assertEqual(r1.status_code, 302)
        self.assertIn('/login', r1.headers['Location'])

        r2 = self.client.get('/dashboard')
        self.assertEqual(r2.status_code, 302)
        self.assertIn('/login', r2.headers['Location'])

    def test_student_login_with_employee_id(self):
        """Student should log in successfully using Employee ID + Password."""
        response = self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Aarav Kumar', response.data)
        self.assertIn(b'AI-Based Student Performance Analysis System', response.data)
        self.assertIn(b'WEEK 1', response.data)

    def test_invalid_login_credentials(self):
        """Invalid employee ID or password should return clean error message."""
        response = self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'WrongPassword!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid Employee ID or password', response.data)

    def test_project_ownership_and_idor_protection(self):
        """Student A must NEVER be able to access Student B's project or milestone."""
        # 1. Log in as Student 1 (Aarav Kumar, ID: AM-INT-2026-001)
        self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })

        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            student2 = Student.query.filter_by(student_uid='AM-INT-2026-002').first()
            
            s1_assignment = student1.active_internship.active_assignment
            s2_assignment = student2.active_internship.active_assignment
            
            s1_w1 = s1_assignment.weekly_milestones.filter_by(week_number=1).first()
            s2_w1 = s2_assignment.weekly_milestones.filter_by(week_number=1).first()

        # Student 1 accessing their own project -> 200 OK
        resp_own_proj = self.client.get(f'/project/{s1_assignment.id}')
        self.assertEqual(resp_own_proj.status_code, 200)
        self.assertIn(b'AI-Based Student Performance Analysis System', resp_own_proj.data)

        # Student 1 attempting to access Student 2's project -> 403 Forbidden
        resp_other_proj = self.client.get(f'/project/{s2_assignment.id}')
        self.assertEqual(resp_other_proj.status_code, 403)

        # Student 1 accessing their own milestone -> 200 OK
        resp_own_week = self.client.get(f'/week/{s1_w1.id}')
        self.assertEqual(resp_own_week.status_code, 200)

        # Student 1 attempting to access Student 2's milestone -> 403 Forbidden
        resp_other_week = self.client.get(f'/week/{s2_w1.id}')
        self.assertEqual(resp_other_week.status_code, 403)

    def test_locked_weeks_and_manual_admin_unlocking(self):
        """Week 1 is initially available, Weeks 2/3/4 locked. Admin approval unlocks Week 2."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student1.active_internship.active_assignment
            w1 = assignment.weekly_milestones.filter_by(week_number=1).first()
            w2 = assignment.weekly_milestones.filter_by(week_number=2).first()
            w3 = assignment.weekly_milestones.filter_by(week_number=3).first()
            w4 = assignment.weekly_milestones.filter_by(week_number=4).first()

            # Verify initial statuses
            self.assertEqual(w1.status, 'AVAILABLE')
            self.assertEqual(w2.status, 'LOCKED')
            self.assertEqual(w3.status, 'LOCKED')
            self.assertEqual(w4.status, 'LOCKED')
            self.assertEqual(assignment.progress_percent, 0)
            w1_id = w1.id

        # 1. Log in as Student 1 and submit Week 1 work
        self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })

        sub_resp = self.client.post(f'/submissions/submit/{w1_id}', data={
            'repo_url': 'https://github.com/aarav-antimatrix/ai-student-analysis',
            'live_demo_url': 'https://student-ai.antimatrix.tech',
            'demo_video_url': 'https://youtube.com/watch?v=demo123',
            'submission_notes': 'Completed Exploratory Data Analysis, ER architecture diagrams, and requirements document.'
        }, follow_redirects=True)
        self.assertEqual(sub_resp.status_code, 200)

        with self.app.app_context():
            w1_refreshed = db.session.get(WeeklyMilestone, w1_id)
            self.assertEqual(w1_refreshed.status, 'SUBMITTED')

        # 2. Log in as Admin and approve Week 1
        self.client.get('/logout')
        self.client.post('/admin/login', data={
            'email_or_id': 'admin@antimatrix.com',
            'password': 'Admin@2026Password!'
        })

        approve_resp = self.client.post(f'/admin/milestone/{w1_id}/review', data={
            'action': 'approve',
            'feedback': 'Excellent dataset architecture and clear ER modeling. Approved for Week 2.'
        }, follow_redirects=True)
        self.assertEqual(approve_resp.status_code, 200)

        # Verify: Week 1 is COMPLETED, Week 2 is AVAILABLE, Weeks 3 & 4 remain LOCKED
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student1.active_internship.active_assignment
            w1_after = assignment.weekly_milestones.filter_by(week_number=1).first()
            w2_after = assignment.weekly_milestones.filter_by(week_number=2).first()
            w3_after = assignment.weekly_milestones.filter_by(week_number=3).first()
            w4_after = assignment.weekly_milestones.filter_by(week_number=4).first()

            self.assertEqual(w1_after.status, 'COMPLETED')
            self.assertEqual(w2_after.status, 'AVAILABLE')
            self.assertEqual(w3_after.status, 'LOCKED')
            self.assertEqual(w4_after.status, 'LOCKED')
            # 1 of 4 weeks completed -> 25%
            self.assertEqual(assignment.progress_percent, 25)

    def test_admin_authorization_restriction(self):
        """Student accounts must NOT be able to access administrator routes."""
        # Log in as regular student
        self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })

        resp = self.client.get('/admin/dashboard')
        self.assertEqual(resp.status_code, 403)

        resp2 = self.client.get('/admin/students')
        self.assertEqual(resp2.status_code, 403)

    def test_documents_section_sample_buttons(self):
        """Documents section should render sample cards without throwing errors."""
        self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })

        resp = self.client.get('/documents')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Official Offer Letter', resp.data)
        self.assertIn(b'Official Joining Letter', resp.data)
        self.assertIn(b'Internship Completion Certificate', resp.data)
        self.assertIn(b'Official Experience Letter', resp.data)

if __name__ == '__main__':
    unittest.main()
