import unittest
from app import create_app
from app.extensions import db
from app.models import User, Student, College, Department
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class ProfileTypeableFieldsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
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

    def test_profile_page_ui_elements(self):
        """Verify the EDITABLE badge is removed, and all 4 fields are active and typeable."""
        self.client.post('/login', data={'employee_id': 'AM-INT-2026-001', 'password': 'Student@2026Password!'})
        resp = self.client.get('/profile')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # 1. "YOUR PROFILE" header exists without "EDITABLE" badge
        self.assertIn('YOUR PROFILE', html)
        self.assertNotIn('EDITABLE', html)

        # 2. "OFFICIAL INTERNSHIP INFORMATION" header exists without "READ-ONLY" badge
        self.assertIn('OFFICIAL INTERNSHIP INFORMATION', html)
        self.assertNotIn('READ-ONLY', html)

        # 3. Informational lock/note box is completely removed
        self.assertNotIn('remain read-only', html)
        self.assertNotIn('Official registration and project allocation records', html)

        # 4. Redundant academic block is removed from the left profile card
        self.assertNotIn('Graduation: <strong', html)
        self.assertNotIn('Roll No: <strong', html)

        # 5. All 12 official fields remain intact in Official Internship Information
        official_fields = [
            'Full Legal Name',
            'Allocated Employee ID',
            'Registered Email Address',
            'Degree',
            'Graduation Year',
            'Roll Number',
            'Internship Track',
            'Program Duration',
            'Commencement Date',
            'Expected Completion Date',
            'Assigned Technical Mentor',
            'Allocated Project Code',
        ]
        for field in official_fields:
            self.assertIn(field, html)

        # 6. Four fields exist as active, non-disabled, non-readonly form controls
        self.assertIn('id="college_input"', html)
        self.assertNotIn('id="college_input" readonly', html)
        self.assertNotIn('id="college_input" disabled', html)

        self.assertIn('id="department_input"', html)
        self.assertNotIn('id="department_input" readonly', html)
        self.assertNotIn('id="department_input" disabled', html)

        self.assertIn('id="current_year"', html)
        self.assertNotIn('id="current_year" disabled', html)

        self.assertIn('id="mobile_number"', html)
        self.assertNotIn('id="mobile_number" readonly', html)
        self.assertNotIn('id="mobile_number" disabled', html)

        # 7. Save Profile button exists
        self.assertIn('Save Profile', html)

    def test_profile_submission_with_typed_values(self):
        """Verify submitting typed college name, department name, year, and phone works and updates student profile."""
        user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
        student = user.student_profile
        initial_roll = student.roll_number
        initial_degree = student.degree
        initial_grad_year = student.graduation_year

        self.client.post('/login', data={'employee_id': 'AM-INT-2026-001', 'password': 'Student@2026Password!'})

        # Submit typed values matching the prompt example
        resp = self.client.post('/profile', data={
            'college': 'Other Autonomous / University College',
            'department': 'Computer Science and Engineering',
            'current_year': '3rd Year',
            'mobile_number': '+91 98765 43210'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('Profile updated successfully.', resp.get_data(as_text=True))

        db.session.refresh(student)
        db.session.refresh(user)

        # Verify the 4 editable fields were saved
        other_college = College.query.filter_by(code='OTHER-COLLEGE').first()
        self.assertEqual(student.college_id, other_college.id)
        self.assertEqual(student.current_year, '3rd Year')
        self.assertEqual(user.phone, '+91 98765 43210')
        self.assertEqual(student.department.name, 'Computer Science and Engineering')

        # Verify official records remain unchanged
        self.assertEqual(student.roll_number, initial_roll)
        self.assertEqual(student.degree, initial_degree)
        self.assertEqual(student.graduation_year, initial_grad_year)


if __name__ == '__main__':
    unittest.main()
