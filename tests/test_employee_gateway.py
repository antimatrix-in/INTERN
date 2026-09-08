import unittest
from datetime import datetime, timezone
import hashlib
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import User, Student
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class EmployeeGatewayTestCase(unittest.TestCase):
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

    # ── Test A: Correct Employee ID + correct password -> Login succeeds ──────
    def test_a_correct_employee_id_form_login_succeeds(self):
        """Test Form POST /login with valid Employee ID and temporary password."""
        resp = self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Aarav Kumar', resp.data)
        self.assertIn(b'AI-Based Student Performance Analysis System', resp.data)

    def test_a_correct_employee_id_json_login_succeeds(self):
        """Test JSON POST /api/auth/employee-login with valid Employee ID."""
        resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['full_name'], 'Aarav Kumar')
        self.assertIn('redirect_url', data)
        # Ensure password and hash are NOT returned
        self.assertNotIn('password', data['user'])
        self.assertNotIn('password_hash', data['user'])

    # ── Test B: Correct Employee ID + incorrect password -> Login fails ──────
    def test_b_correct_employee_id_wrong_password_fails(self):
        """Test that incorrect password fails with generic error (no enumeration)."""
        # Form endpoint
        resp_form = self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'IncorrectPassword123'
        }, follow_redirects=True)
        self.assertEqual(resp_form.status_code, 200)
        self.assertIn(b'Invalid Employee ID or password', resp_form.data)

        # JSON endpoint
        resp_json = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'IncorrectPassword123'
        })
        self.assertEqual(resp_json.status_code, 401)
        data = resp_json.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid Employee ID or password.')

    # ── Test C: Incorrect Employee ID + any password -> Login fails ──────────
    def test_c_unknown_employee_id_fails(self):
        """Test that non-existent Employee ID returns same generic error."""
        resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-NON-EXISTENT-999',
            'password': 'SomePassword123!'
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid Employee ID or password.')

    # ── Test D: Empty Employee ID -> Validation error ─────────────────────────
    def test_d_empty_employee_id_validation_error(self):
        """Test that empty Employee ID returns 400 Bad Request."""
        resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': '',
            'password': 'SomePassword123!'
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Employee ID', data['error'])

    # ── Test E: Empty password -> Validation error ────────────────────────────
    def test_e_empty_password_validation_error(self):
        """Test that empty password returns 400 Bad Request."""
        resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': ''
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn('password', data['error'])

    # ── Test F: Logged-out user opening protected dashboard -> Redirected ────
    def test_f_unauthenticated_protected_route_redirects(self):
        """Test that unauthenticated requests to protected student routes are redirected."""
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

        resp_me = self.client.get('/api/auth/me')
        self.assertEqual(resp_me.status_code, 401)
        data = resp_me.get_json()
        self.assertFalse(data['authenticated'])

    # ── Test G: Employee data isolation (IDOR protection) ─────────────────────
    def test_g_employee_data_isolation(self):
        """Test that Employee A cannot access Employee B's project assignments."""
        # 1. Login as Employee A (Aarav Kumar, AM-INT-2026-001)
        login_resp = self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })
        self.assertEqual(login_resp.status_code, 200)

        with self.app.app_context():
            s1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            s2 = Student.query.filter_by(student_uid='AM-INT-2026-002').first()
            s1_assign_id = s1.active_internship.active_assignment.id
            s2_assign_id = s2.active_internship.active_assignment.id

        # Employee A accessing own project -> 200 OK
        resp_own = self.client.get(f'/project/{s1_assign_id}')
        self.assertEqual(resp_own.status_code, 200)

        # Employee A attempting to access Employee B's project -> 403 Forbidden
        resp_other = self.client.get(f'/project/{s2_assign_id}')
        self.assertEqual(resp_other.status_code, 403)

    # ── Test H: Logout invalidates session ────────────────────────────────────
    def test_h_logout_invalidates_session(self):
        """Test that logout terminates the session and prevents protected access."""
        # 1. Login
        self.client.post('/api/auth/employee-login', json={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        })

        # 2. Verify active session
        resp_me = self.client.get('/api/auth/me')
        self.assertEqual(resp_me.status_code, 200)
        self.assertTrue(resp_me.get_json()['authenticated'])

        # 3. Logout
        resp_logout = self.client.post('/logout', json={})
        self.assertEqual(resp_logout.status_code, 200)

        # 4. Verify session is dead
        resp_me_after = self.client.get('/api/auth/me')
        self.assertEqual(resp_me_after.status_code, 401)

        # 5. Accessing protected dashboard redirects to login
        resp_dash = self.client.get('/dashboard')
        self.assertEqual(resp_dash.status_code, 302)
        self.assertIn('/login', resp_dash.headers['Location'])

    # ── Password Hash Compatibility: Multi-Algorithm Support ─────────────────
    def test_multi_algorithm_password_hashing(self):
        """
        Verify that User.check_password correctly validates Werkzeug scrypt,
        pbkdf2:sha256, bcrypt ($2b$), and sha256 hashes generated by Anti-Matrix.
        """
        with self.app.app_context():
            user = User.query.filter_by(email='aarav.kumar@example.com').first()
            self.assertIsNotNone(user)

            # 1. Werkzeug default (scrypt)
            user.password_hash = generate_password_hash('WerkzeugPass123!')
            db.session.commit()
            self.assertTrue(user.check_password('WerkzeugPass123!'))
            self.assertFalse(user.check_password('WrongPass!'))

            # 2. PBKDF2:SHA256
            user.password_hash = generate_password_hash('Pbkdf2Pass123!', method='pbkdf2:sha256')
            db.session.commit()
            self.assertTrue(user.check_password('Pbkdf2Pass123!'))
            self.assertFalse(user.check_password('WrongPass!'))

            # 3. SHA256 hex digest
            user.password_hash = hashlib.sha256('Sha256Pass123!'.encode('utf-8')).hexdigest()
            db.session.commit()
            self.assertTrue(user.check_password('Sha256Pass123!'))
            self.assertFalse(user.check_password('WrongPass!'))

            # 4. Bcrypt hash if bcrypt installed
            try:
                import bcrypt
                salt = bcrypt.gensalt()
                user.password_hash = bcrypt.hashpw('BcryptPass123!'.encode('utf-8'), salt).decode('utf-8')
                db.session.commit()
                self.assertTrue(user.check_password('BcryptPass123!'))
                self.assertFalse(user.check_password('WrongPass!'))
            except ImportError:
                pass


if __name__ == '__main__':
    unittest.main()
