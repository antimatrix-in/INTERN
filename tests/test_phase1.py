import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models import User, Student, College, InternshipPlan, CertificateVerification

class Phase1TestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_homepage_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ANTI MATRIX', response.data)
        self.assertIn(b'1 Month Project Internship', response.data)
        self.assertIn(b'3 Month Professional Internship', response.data)

    def test_internship_pages(self):
        r1 = self.client.get('/internships')
        self.assertEqual(r1.status_code, 200)

        r2 = self.client.get('/internships/1-month')
        self.assertEqual(r2.status_code, 200)
        self.assertIn(b'1 Month Project Internship', r2.data)

        r3 = self.client.get('/internships/3-month')
        self.assertEqual(r3.status_code, 200)
        self.assertIn(b'3 Month Professional Internship', r3.data)

    def test_certificate_verification(self):
        response = self.client.get('/verify/AM-CERT-2026-00184')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'CERTIFICATE VERIFIED', response.data)
        self.assertIn(b'Aarav Kumar', response.data)

    def test_departments_api(self):
        with self.app.app_context():
            col = College.query.first()
            if col:
                response = self.client.get(f'/auth/api/departments/{col.id}')
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertIsInstance(data, list)
                self.assertTrue(len(data) > 0)

    def test_student_login_and_dashboard(self):
        response = self.client.post('/auth/login', data={
            'email': 'aarav.kumar@example.com',
            'password': 'Student@2026Password!',
            'remember_me': False
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome, Aarav Kumar', response.data)
        self.assertIn(b'AM-INT-2026-00184', response.data)

    def test_new_student_registration(self):
        with self.app.app_context():
            col = College.query.first()
            dept = col.departments[0]

            response = self.client.post('/auth/register', data={
                'full_name': 'Sneha Patel',
                'email': 'sneha.patel@test.edu',
                'phone': '9876543210',
                'password': 'SecurePassword@2026',
                'confirm_password': 'SecurePassword@2026',
                'college_id': col.id,
                'department_id': dept.id,
                'degree': 'B.Tech / B.E',
                'roll_number': '22IT099',
                'current_year': '3rd Year',
                'graduation_year': '2026',
                'plan_code': '1_MONTH_PROJECT',
                'consent_agreed': True
            }, follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Sneha Patel', response.data)

if __name__ == '__main__':
    unittest.main()
