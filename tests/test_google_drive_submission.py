"""Test suite for Google Drive demo video link submission workflow."""
import unittest
from tests.test_config import TestConfig
from app import create_app
from app.extensions import db
from app.models import WeeklyMilestone, Student, WeeklySubmission
from app.seed import seed_initial_data


class GoogleDriveSubmissionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        with self.app.app_context():
            db.create_all()
            seed_initial_data()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_complete_google_drive_workflow(self):
        # 1. Login as Student 1
        login_res = self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        with self.app.app_context():
            s = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = s.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            w1_id = w1.id
            for t in w1.tasks:
                t.is_completed = True
            db.session.commit()

        # 2. Inspect /week/<id> HTML
        week_res = self.client.get(f'/week/{w1_id}')
        html = week_res.data.decode('utf-8')

        # Old file upload elements must be completely absent
        self.assertNotIn('UPLOAD DEMO VIDEO', html)
        self.assertNotIn('Supported: MP4, MOV, WEBM', html)
        self.assertNotIn('Max 100MB', html)
        self.assertNotIn('type="file"', html)
        self.assertNotIn("type='file'", html)

        # New Google Drive elements must be present
        self.assertIn('DEMO VIDEO — GOOGLE DRIVE LINK *', html)
        self.assertIn('name="demo_video_url"', html)
        self.assertIn('https://drive.google.com/file/d/.../view', html)
        self.assertIn('Upload your demo video to Google Drive', html)

        # 3. Validation: Empty link
        empty_res = self.client.post(f'/submissions/submit/{w1_id}', data={
            'github_url': 'https://github.com/aarav/test-repo',
            'demo_video_url': ''
        }, follow_redirects=True)
        self.assertIn('Demo video Google Drive link is required', empty_res.data.decode('utf-8'))

        # 4. Validation: Invalid URL
        invalid_res = self.client.post(f'/submissions/submit/{w1_id}', data={
            'github_url': 'https://github.com/aarav/test-repo',
            'demo_video_url': 'https://youtube.com/watch?v=123'
        }, follow_redirects=True)
        self.assertIn('Please provide a valid Google Drive demo video link', invalid_res.data.decode('utf-8'))

        # 5. Validation: Valid Google Drive submission
        drive_url = 'https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/view?usp=sharing'
        valid_res = self.client.post(f'/submissions/submit/{w1_id}', data={
            'github_url': 'https://github.com/aarav/test-repo',
            'demo_video_url': drive_url,
            'submission_notes': 'Testing complete Google Drive link submission workflow.'
        }, follow_redirects=True)
        self.assertIn('UNDER REVIEW', valid_res.data.decode('utf-8'))

        with self.app.app_context():
            m = db.session.get(WeeklyMilestone, w1_id)
            sub = m.latest_submission
            self.assertEqual(sub.demo_video_url, drive_url)
            sub_id = sub.id

        # 6. Admin Review: Watch Demo button
        self.client.get('/logout')
        self.client.post('/admin/login', data={
            'email_or_id': 'admin',
            'password': 'Admin@12345'
        }, follow_redirects=True)

        admin_res = self.client.get(f'/admin/submissions/{sub_id}/review')
        admin_html = admin_res.data.decode('utf-8')
        self.assertIn('Watch Demo', admin_html)
        self.assertIn(drive_url, admin_html)
        self.assertIn('target="_blank"', admin_html)
        self.assertIn('rel="noopener noreferrer"', admin_html)


if __name__ == '__main__':
    unittest.main()
