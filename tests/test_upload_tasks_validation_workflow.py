import io
import json
import unittest
from app import create_app
from app.extensions import db
from app.models import User, Project, ProjectWeek, ProjectTask, TaskImportHistory
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class UploadTasksValidationWorkflowTestCase(unittest.TestCase):
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

    def login_admin(self):
        self.client.get('/logout')
        return self.client.post('/admin/login', data={
            'email_or_id': 'admin',
            'password': 'Admin@12345'
        }, follow_redirects=True)

    def login_employee(self, emp_id='AM-INT-2026-001', password='Student@2026Password!'):
        self.client.get('/logout')
        return self.client.post('/login', data={
            'employee_id': emp_id,
            'password': password
        }, follow_redirects=True)

    # ── 1. Valid 1-Month JSON Validation & Preview (Read-Only) ─────────────────

    def test_01_valid_1m_json_validation_and_preview(self):
        with self.app.app_context():
            self.login_admin()
            json_data = {
                "internship": {
                    "problem_id": "P1M-TEST-001",
                    "domain": "Web Development",
                    "duration": "1 Month",
                    "level": "Easy",
                    "project_title": "Full-Stack Task Manager",
                    "milestones": [
                        {"week": 1, "title": "Setup & DB", "completion": "25%", "tasks": ["Task 1", "Task 2"]},
                        {"week": 2, "title": "Auth API", "completion": "50%", "tasks": ["Task 3"]},
                        {"week": 3, "title": "Dashboard UI", "completion": "75%", "tasks": ["Task 4", "Task 5"]},
                        {"week": 4, "title": "Testing & Deploy", "completion": "100%", "tasks": ["Task 6"]}
                    ]
                }
            }

            file_bytes = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'TaskPlan_1M.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.is_json)
            data = resp.get_json()

            self.assertTrue(data['success'])
            self.assertTrue(data['valid'])
            self.assertEqual(data['errors'], [])
            self.assertIsNotNone(data['preview'])
            self.assertEqual(data['preview']['problem_id'], 'P1M-TEST-001')
            self.assertEqual(data['preview']['total_weeks'], 4)
            self.assertEqual(data['preview']['total_tasks'], 6)
            self.assertFalse(data['is_duplicate'])

            # Verify Database was NOT modified (Read-Only Invariant)
            proj = Project.query.filter_by(project_code='P1M-TEST-001').first()
            self.assertIsNone(proj, "Validation MUST NOT insert projects into database")

    # ── 2. Valid 3-Month 4-Phase JSON Validation (Normalizes to 12 Weeks) ──────

    def test_02_valid_3m_4phase_json_validation_and_preview(self):
        with self.app.app_context():
            self.login_admin()
            json_data = {
                "internship": {
                    "problem_id": "P3M-PHASE-001",
                    "domain": "AI & ML",
                    "duration": "3 Months",
                    "level": "Advanced",
                    "project_title": "Deep Learning Pipeline",
                    "milestones": [
                        {
                            "phase": 1,
                            "weeks": "1-3",
                            "completion": "25%",
                            "title": "Data Preprocessing",
                            "tasks": ["Data Cleaning", "Feature Extraction", "Normalization"]
                        },
                        {
                            "phase": 2,
                            "weeks": "4-6",
                            "completion": "50%",
                            "title": "Model Architecture",
                            "tasks": ["Baseline Model", "Hyperparameter Tuning"]
                        },
                        {
                            "phase": 3,
                            "weeks": "7-9",
                            "completion": "75%",
                            "title": "Optimization & Inference",
                            "tasks": ["Model Pruning", "ONNX Export"]
                        },
                        {
                            "phase": 4,
                            "weeks": "10-12",
                            "completion": "100%",
                            "title": "Deployment & Web UI",
                            "tasks": ["API Endpoints", "Dockerization"]
                        }
                    ]
                }
            }

            file_bytes = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'TaskPlan_3M.json'),
                'duration': '3 Months'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.is_json)
            data = resp.get_json()

            self.assertTrue(data['success'])
            self.assertTrue(data['valid'])
            self.assertEqual(data['errors'], [])
            self.assertEqual(data['preview']['total_weeks'], 12)
            self.assertEqual(len(data['preview']['weeks']), 12)

            # Check phase preservation across weeks
            weeks = data['preview']['weeks']
            self.assertEqual(weeks[0]['phase_number'], 1)
            self.assertEqual(weeks[2]['phase_number'], 1)
            self.assertEqual(weeks[3]['phase_number'], 2)
            self.assertEqual(weeks[5]['phase_number'], 2)
            self.assertEqual(weeks[6]['phase_number'], 3)
            self.assertEqual(weeks[8]['phase_number'], 3)
            self.assertEqual(weeks[9]['phase_number'], 4)
            self.assertEqual(weeks[11]['phase_number'], 4)

            # DB Read-Only check
            proj = Project.query.filter_by(project_code='P3M-PHASE-001').first()
            self.assertIsNone(proj)

    # ── 3. Valid 3-Month 12-Week JSON (like task1(3m).json) ───────────────────

    def test_03_valid_3m_12week_json_validation(self):
        with self.app.app_context():
            self.login_admin()
            # Schema with root-level metadata and 12 weekly milestone items
            json_data = {
                "title": "AI Career Intelligence Platform",
                "problem_code": "P3M-AIML-099",
                "domain": "AI & Machine Learning",
                "duration": "3 Months",
                "difficulty": "Advanced",
                "internship": {
                    "milestones": [
                        {"week": i, "title": f"Milestone Week {i}", "tasks": [f"Task W{i}-1", f"Task W{i}-2"]}
                        for i in range(1, 13)
                    ]
                }
            }

            file_bytes = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'task1(3m).json'),
                'duration': '3 Months'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.is_json)
            data = resp.get_json()

            self.assertTrue(data['success'])
            self.assertTrue(data['valid'])
            self.assertEqual(data['preview']['problem_id'], 'P3M-AIML-099')
            self.assertEqual(data['preview']['total_weeks'], 12)
            self.assertEqual(data['preview']['total_tasks'], 24)

    # ── 4. Malformed JSON Returns Clean JSON Error ────────────────────────────

    def test_04_malformed_json_returns_clean_json_error(self):
        with self.app.app_context():
            self.login_admin()
            bad_content = b'{"broken_json": true, incomplete'
            file_bytes = io.BytesIO(bad_content)

            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'broken.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 400)
            self.assertTrue(resp.is_json)
            data = resp.get_json()

            self.assertFalse(data['success'])
            self.assertFalse(data['valid'])
            self.assertGreater(len(data['errors']), 0)
            self.assertIn('Invalid JSON', data['errors'][0])

    # ── 5. Missing Required Field Returns Clean JSON Error ────────────────────

    def test_05_missing_required_field_returns_clean_json_error(self):
        with self.app.app_context():
            self.login_admin()
            # Missing project title
            json_data = {
                "internship": {
                    "problem_id": "P1M-NOTITLE",
                    "domain": "AI",
                    "duration": "1 Month",
                    "milestones": [
                        {"week": 1, "tasks": []}, {"week": 2, "tasks": []},
                        {"week": 3, "tasks": []}, {"week": 4, "tasks": []}
                    ]
                }
            }

            file_bytes = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'no_title.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 400)
            self.assertTrue(resp.is_json)
            data = resp.get_json()

            self.assertFalse(data['success'])
            self.assertFalse(data['valid'])
            self.assertIn('Project title is required', data['errors'][0])

    # ── 6. Duplicate Problem ID Detection ─────────────────────────────────────

    def test_06_duplicate_problem_id_detected(self):
        with self.app.app_context():
            # Seed an existing project
            existing = Project(
                project_code='P3M-DUP-01',
                title='Existing Platform',
                domain='AI & ML',
                duration_weeks=12,
                duration_months=3,
                is_active=True
            )
            db.session.add(existing)
            db.session.commit()

            self.login_admin()
            json_data = {
                "internship": {
                    "problem_id": "P3M-DUP-01",
                    "domain": "AI & ML",
                    "duration": "3 Months",
                    "project_title": "New Import Same Code",
                    "milestones": [
                        {"phase": 1, "weeks": "1-3", "tasks": ["T1"]},
                        {"phase": 2, "weeks": "4-6", "tasks": ["T2"]},
                        {"phase": 3, "weeks": "7-9", "tasks": ["T3"]},
                        {"phase": 4, "weeks": "10-12", "tasks": ["T4"]}
                    ]
                }
            }

            file_bytes = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'duplicate.json'),
                'duration': '3 Months'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.is_json)
            data = resp.get_json()

            self.assertTrue(data['success'])
            self.assertTrue(data['valid'])
            self.assertTrue(data['is_duplicate'])
            self.assertEqual(data['existing_project_code'], 'P3M-DUP-01')
            self.assertGreater(len(data['warnings']), 0)
            self.assertIn('already exists', data['warnings'][0])

            # Existing project was not changed
            check = Project.query.filter_by(project_code='P3M-DUP-01').first()
            self.assertEqual(check.title, 'Existing Platform')

    # ── 7. Duration Mismatch Rejection ────────────────────────────────────────

    def test_07_duration_mismatch_rejected(self):
        with self.app.app_context():
            self.login_admin()
            json_data = {
                "internship": {
                    "project_title": "3M Project",
                    "duration": "3 Months",
                    "milestones": [{"phase": 1, "tasks": []}, {"phase": 2, "tasks": []}, {"phase": 3, "tasks": []}, {"phase": 4, "tasks": []}]
                }
            }
            file_bytes = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            # User selected 1 Month in dropdown but uploaded 3 Months JSON
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'plan.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 400)
            self.assertTrue(resp.is_json)
            data = resp.get_json()
            self.assertFalse(data['success'])
            self.assertIn('does not match', data['errors'][0])

    # ── 8. Unauthenticated Request Returns JSON 401 ───────────────────────────

    def test_08_unauthenticated_request_returns_json_401(self):
        with self.app.app_context():
            self.client.get('/logout')
            # Request without login
            file_bytes = io.BytesIO(b'{"dummy": true}')
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'plan.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 401)
            self.assertTrue(resp.is_json)
            data = resp.get_json()
            self.assertFalse(data['success'])
            self.assertIn('session has expired', data['errors'][0])

    # ── 9. Non-Admin Request Returns JSON 403 ─────────────────────────────────

    def test_09_non_admin_request_returns_json_403(self):
        with self.app.app_context():
            # Log in as employee / student
            self.login_employee()
            file_bytes = io.BytesIO(b'{"dummy": true}')
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'plan.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 403)
            self.assertTrue(resp.is_json)
            data = resp.get_json()
            self.assertFalse(data['success'])
            self.assertIn('Access restricted', data['errors'][0])

    # ── 10. Invalid File Extension Rejected ───────────────────────────────────

    def test_10_invalid_file_extension_rejected(self):
        with self.app.app_context():
            self.login_admin()
            file_bytes = io.BytesIO(b'Some text content')
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'plan.txt'),
                'duration': '1 Month'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 400)
            self.assertTrue(resp.is_json)
            data = resp.get_json()
            self.assertFalse(data['success'])
            self.assertIn('Only .json files are permitted', data['errors'][0])

    # ── 11. Empty JSON File Rejected ──────────────────────────────────────────

    def test_11_empty_json_file_rejected(self):
        with self.app.app_context():
            self.login_admin()
            file_bytes = io.BytesIO(b'   \n\t  ')
            resp = self.client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'empty.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            self.assertEqual(resp.status_code, 400)
            self.assertTrue(resp.is_json)
            data = resp.get_json()
            self.assertFalse(data['success'])
            self.assertIn('empty', data['errors'][0].lower())

    # ── 12. Missing CSRF Token Returns JSON 400 When CSRF Active ──────────────

    def test_12_missing_csrf_returns_json_400_when_csrf_enabled(self):
        # Create an app instance with CSRF explicitly enabled
        class CSRFActiveConfig(TestConfig):
            WTF_CSRF_ENABLED = True

        csrf_app = create_app(CSRFActiveConfig)
        with csrf_app.app_context():
            db.create_all()
            seed_initial_data()
            client = csrf_app.test_client()

            # Make POST request without CSRF token
            file_bytes = io.BytesIO(b'{"test": 1}')
            resp = client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'test.json'),
                'duration': '1 Month'
            }, content_type='multipart/form-data', headers={'Accept': 'application/json'})

            # Must return JSON 400, NOT HTML!
            self.assertEqual(resp.status_code, 400)
            self.assertTrue(resp.is_json)
            data = resp.get_json()
            self.assertFalse(data['success'])
            self.assertIn('CSRF', data['errors'][0])

    # ── 13. Valid CSRF Token Succeeds When CSRF Active ───────────────────────

    def test_13_valid_csrf_token_succeeds_when_csrf_active(self):
        import re
        class CSRFActiveConfig(TestConfig):
            WTF_CSRF_ENABLED = True

        csrf_app = create_app(CSRFActiveConfig)
        with csrf_app.app_context():
            db.create_all()
            seed_initial_data()
            client = csrf_app.test_client()

            # 1. Fetch login page to establish session & get CSRF token
            login_page = client.get('/admin/login')
            html = login_page.data.decode('utf-8')
            m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
            login_csrf = m.group(1) if m else None
            self.assertIsNotNone(login_csrf, "Should extract CSRF token from login form")

            # 2. Login admin with CSRF token
            login_resp = client.post('/admin/login', data={
                'email_or_id': 'admin',
                'password': 'Admin@12345',
                'csrf_token': login_csrf
            }, follow_redirects=True)
            self.assertEqual(login_resp.status_code, 200)

            # 3. Fetch upload-tasks page to get page's meta csrf-token
            upload_page = client.get('/admin/upload-tasks')
            self.assertEqual(upload_page.status_code, 200)
            html2 = upload_page.data.decode('utf-8')
            m2 = re.search(r'name="csrf-token"\s+content="([^"]+)"', html2)
            page_csrf = m2.group(1) if m2 else None
            self.assertIsNotNone(page_csrf)

            # 4. Post validation with the valid CSRF token in header & body
            json_data = {
                "internship": {
                    "problem_id": "P1M-CSRF-OK",
                    "domain": "AI",
                    "duration": "1 Month",
                    "project_title": "CSRF Valid Test",
                    "milestones": [
                        {"week": i, "title": f"W{i}", "tasks": [f"T{i}"]} for i in range(1, 5)
                    ]
                }
            }
            file_bytes = io.BytesIO(json.dumps(json_data).encode('utf-8'))
            resp = client.post('/admin/upload-tasks/validate', data={
                'file': (file_bytes, 'test.json'),
                'duration': '1 Month',
                'csrf_token': page_csrf
            }, headers={'X-CSRFToken': page_csrf, 'Accept': 'application/json'}, content_type='multipart/form-data')

            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.is_json)
            data = resp.get_json()
            self.assertTrue(data['success'])
            self.assertTrue(data['valid'])
            self.assertEqual(data['preview']['problem_id'], 'P1M-CSRF-OK')



if __name__ == '__main__':
    unittest.main()

