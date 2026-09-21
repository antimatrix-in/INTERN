import unittest
import re
from app import create_app
from app.extensions import db
from app.models import User, Student, College, Department, Internship
from app.services.mentor_service import (
    get_approved_mentors, is_approved_mentor, get_canonical_mentor_name,
    APPROVED_MENTOR_EMAILS, APPROVED_MENTOR_NAMES
)
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class ProfileAndApprovedMentorsTestCase(unittest.TestCase):
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

    # ── MENTOR TESTS ─────────────────────────────────────────────────────────

    def test_approved_mentors_list(self):
        """Verify only the four approved mentors exist and are returned in order."""
        mentors = get_approved_mentors()
        self.assertEqual(len(mentors), 4)

        expected = [
            ('praveen@antimatrix.co.in', 'Praveen'),
            ('satishkumar@antimatrix.co.in', 'Satish Kumar'),
            ('rohit@antimatrix.co.in', 'Rohit'),
            ('bharatbabu@antimatrix.co.in', 'Bharat Babu'),
        ]
        for m, (exp_email, exp_name) in zip(mentors, expected):
            self.assertEqual(m.email, exp_email)
            self.assertEqual(m.full_name, exp_name)
            self.assertTrue(is_approved_mentor(m))
            self.assertEqual(get_canonical_mentor_name(m), exp_name)

    def test_invalid_mentor_rejected(self):
        """Ensure Dr. Rajesh Sharma is never considered an approved mentor."""
        fake_mentor = User(
            email='mentor@antimatrix.com',
            full_name='Dr. Rajesh Sharma (Lead Architect)',
            role='mentor'
        )
        self.assertFalse(is_approved_mentor(fake_mentor))
        self.assertIsNone(get_canonical_mentor_name(fake_mentor))

    def test_internship_assigned_mentor_property(self):
        """Test Internship.assigned_mentor returns approved mentor and hides invalid mentors."""
        internship = Internship.query.first()
        satish = User.query.filter_by(email='satishkumar@antimatrix.co.in').first()
        self.assertIsNotNone(satish)

        # Assign Satish Kumar
        internship.mentor_id = satish.id
        db.session.commit()
        self.assertEqual(internship.assigned_mentor.id, satish.id)
        self.assertEqual(internship.assigned_mentor_name, 'Satish Kumar')

        # Assign an invalid mentor
        bad_user = User(email='bad@mentor.com', password_hash='hash', full_name='Dr. Rajesh Sharma (Lead Architect)', role='mentor')
        db.session.add(bad_user)
        db.session.commit()
        internship.mentor_id = bad_user.id
        db.session.commit()
        self.assertIsNone(internship.assigned_mentor)
        self.assertIsNone(internship.assigned_mentor_name)

    def test_admin_can_assign_approved_mentor(self):
        """Admin can assign one of the 4 approved mentors via /employees/<id>/assign-mentor."""
        student = Student.query.first()
        satish = User.query.filter_by(email='satishkumar@antimatrix.co.in').first()

        # Login as admin
        self.client.post('/admin/login', data={'email_or_id': 'admin', 'password': 'Admin@12345'}, follow_redirects=True)

        # Post valid mentor assignment
        resp = self.client.post(f'/admin/employees/{student.id}/assign-mentor', data={'mentor_id': satish.id})
        self.assertEqual(resp.status_code, 302)

        internship = student.active_internship
        db.session.refresh(internship)
        self.assertEqual(internship.mentor_id, satish.id)
        self.assertEqual(internship.assigned_mentor_name, 'Satish Kumar')

        # Attempt to assign invalid mentor ID
        resp_invalid = self.client.post(f'/admin/employees/{student.id}/assign-mentor', data={'mentor_id': 9999})
        self.assertEqual(resp_invalid.status_code, 302)
        # Mentor remains Satish Kumar
        db.session.refresh(internship)
        self.assertEqual(internship.mentor_id, satish.id)

    # ── FIRST-TIME PROFILE ONBOARDING PROMPT TESTS ───────────────────────────

    def test_scenario_a_complete_profile_flow(self):
        """
        Scenario A: First login -> password change -> dashboard -> prompt appears ->
        click complete profile -> /profile -> edit fields -> Save -> return to dashboard ->
        prompt hidden on subsequent visits.
        """
        user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
        user.must_change_password = True
        student = user.student_profile
        student.profile_completed = False
        db.session.commit()

        # Step 1: Login
        self.client.post('/login', data={'employee_id': 'AM-INT-2026-001', 'password': 'Student@2026Password!'})

        # Step 2: Change password
        self.client.post('/change-password', data={
            'current_password': 'Student@2026Password!',
            'new_password': 'NewPassword@2026!',
            'confirm_password': 'NewPassword@2026!'
        })

        # Step 3: Access dashboard - Onboarding prompt should be visible
        resp_dash = self.client.get('/dashboard')
        self.assertEqual(resp_dash.status_code, 200)
        self.assertIn('Complete Your Profile', resp_dash.get_data(as_text=True))
        self.assertIn('profileOnboardingPrompt', resp_dash.get_data(as_text=True))

        # Step 4: Visit /profile and update the four editable fields
        college = College.query.first()
        dept = college.departments[0]
        resp_save = self.client.post('/profile', data={
            'college_id': college.id,
            'department_id': dept.id,
            'current_year': '4th Year',
            'mobile_number': '+91 9123456780'
        }, follow_redirects=True)
        self.assertEqual(resp_save.status_code, 200)
        self.assertIn('Profile updated successfully.', resp_save.get_data(as_text=True))

        # Verify database was updated
        db.session.refresh(student)
        db.session.refresh(user)
        self.assertEqual(student.college_id, college.id)
        self.assertEqual(student.department_id, dept.id)
        self.assertEqual(student.current_year, '4th Year')
        self.assertEqual(user.phone, '+91 9123456780')
        self.assertTrue(student.profile_completed)

        # Step 5: Return to dashboard - Onboarding prompt must NOT appear
        resp_dash2 = self.client.get('/dashboard')
        self.assertNotIn('profileOnboardingPrompt', resp_dash2.get_data(as_text=True))

    def test_scenario_b_skip_for_now_flow(self):
        """
        Scenario B: First login -> change password -> dashboard -> prompt appears ->
        click Skip for Now -> prompt dismissed -> dashboard accessible -> edit later from My Profile.
        """
        user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
        student = user.student_profile
        student.profile_completed = False
        db.session.commit()

        # Login
        self.client.post('/login', data={'employee_id': 'AM-INT-2026-001', 'password': 'Student@2026Password!'})

        # Dashboard shows prompt
        resp = self.client.get('/dashboard')
        self.assertIn('profileOnboardingPrompt', resp.get_data(as_text=True))

        # Click "Skip for Now"
        resp_skip = self.client.post('/profile/skip-onboarding', follow_redirects=True)
        self.assertEqual(resp_skip.status_code, 200)

        # Verify profile fields were NOT deleted or altered
        db.session.refresh(student)
        self.assertTrue(student.profile_completed)
        self.assertIsNotNone(student.roll_number)
        self.assertIsNotNone(student.degree)

        # Dashboard no longer shows prompt
        self.assertNotIn('profileOnboardingPrompt', resp_skip.get_data(as_text=True))

        # Later: can still update profile from /profile
        college = College.query.all()[1]
        dept = college.departments[0]
        resp_update = self.client.post('/profile', data={
            'college_id': college.id,
            'department_id': dept.id,
            'current_year': 'Final Year',
            'mobile_number': '+91 9988776655'
        }, follow_redirects=True)
        self.assertEqual(resp_update.status_code, 200)
        self.assertIn('Profile updated successfully.', resp_update.get_data(as_text=True))
        db.session.refresh(student)
        self.assertEqual(student.current_year, 'Final Year')

    def test_scenario_c_subsequent_login_no_prompt(self):
        """Scenario C: After onboarding handled, subsequent logins do NOT show prompt."""
        user = User.query.filter_by(employee_id='AM-INT-2026-001').first()
        student = user.student_profile
        student.profile_completed = True
        db.session.commit()

        # Login
        self.client.post('/login', data={'employee_id': 'AM-INT-2026-001', 'password': 'Student@2026Password!'})
        resp = self.client.get('/dashboard')
        self.assertNotIn('profileOnboardingPrompt', resp.get_data(as_text=True))

    def test_scenario_d_authorization_boundary(self):
        """Scenario D: Profile editing strictly scoped to current user session (IDOR protection)."""
        # Log in as Student 1 (AM-INT-2026-001)
        self.client.post('/login', data={'employee_id': 'AM-INT-2026-001', 'password': 'Student@2026Password!'})

        student2 = Student.query.filter_by(student_uid='AM-INT-2026-002').first()
        original_student2_phone = student2.user.phone
        original_student2_year = student2.current_year

        college = College.query.first()
        dept = college.departments[0]

        # Post edit request - client cannot specify target student
        self.client.post('/profile', data={
            'college_id': college.id,
            'department_id': dept.id,
            'current_year': '2nd Year',
            'mobile_number': '+91 8888888888'
        })

        # Ensure student2 was NOT modified
        db.session.refresh(student2)
        self.assertEqual(student2.user.phone, original_student2_phone)
        self.assertEqual(student2.current_year, original_student2_year)

    def test_profile_validation_rejects_invalid_inputs(self):
        """Server-side validation rejects invalid colleges, mismatched depts, invalid years, bad phones."""
        self.client.post('/login', data={'employee_id': 'AM-INT-2026-001', 'password': 'Student@2026Password!'})

        # 1. Invalid College ID
        resp = self.client.post('/profile', data={
            'college_id': 99999,
            'department_id': 1,
            'current_year': '3rd Year',
            'mobile_number': '+91 9876543210'
        })
        self.assertIn('Please select a valid College', resp.get_data(as_text=True))

        # 2. Mismatched Department (Dept belonging to College 2 passed with College 1)
        colleges = College.query.all()
        col1 = colleges[0]
        col2 = colleges[1]
        col2_dept = col2.departments[0]
        resp = self.client.post('/profile', data={
            'college_id': col1.id,
            'department_id': col2_dept.id,
            'current_year': '3rd Year',
            'mobile_number': '+91 9876543210'
        })
        self.assertIn('Please select a valid Academic Department for the selected college', resp.get_data(as_text=True))

        # 3. Invalid Current Year
        col1_dept = col1.departments[0]
        resp = self.client.post('/profile', data={
            'college_id': col1.id,
            'department_id': col1_dept.id,
            'current_year': '10th Year',
            'mobile_number': '+91 9876543210'
        })
        self.assertIn('Please select a valid Current Year', resp.get_data(as_text=True))

        # 4. Invalid Phone Number
        resp = self.client.post('/profile', data={
            'college_id': col1.id,
            'department_id': col1_dept.id,
            'current_year': '3rd Year',
            'mobile_number': '123'
        })
        self.assertIn('Please enter a valid mobile number', resp.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
