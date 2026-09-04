import io
import os
import unittest
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    User, Student, Internship, Project, ProjectAssignment,
    ProjectWeek, ProjectTask, WeeklyMilestone, WeeklyTask,
    WeeklySubmission, Evaluation, Application, College, Department, InternshipPlan
)
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class EmployeeTasksTestCase(unittest.TestCase):
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

    # ── Helpers ────────────────────────────────────────────────────────────────

    def login_admin(self):
        self.client.get('/logout')
        return self.client.post('/admin/login', data={
            'email_or_id': 'admin',
            'password': 'Admin@12345'
        }, follow_redirects=True)

    def login_student1(self):
        """Student 1 (AM-INT-2026-001), 1-Month project."""
        self.client.get('/logout')
        return self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-001',
            'password': 'Student@2026Password!'
        }, follow_redirects=True)

    def login_student2(self):
        """Student 2 (AM-INT-2026-002), 3-Month project."""
        self.client.get('/logout')
        return self.client.post('/login', data={
            'employee_id': 'AM-INT-2026-002',
            'password': 'Student@2026Password!'
        }, follow_redirects=True)

    # ── Test 1: Employee Login & Dashboard Access ─────────────────────────────

    def test_01_employee_login_and_dashboard(self):
        """Employee logs in and reaches /dashboard displaying their profile."""
        response = self.login_student1()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Aarav Kumar', response.data)
        self.assertIn(b'AM-INT-2026-001', response.data)

    # ── Test 2: Employee Sees Only Assigned Project ───────────────────────────

    def test_02_employee_sees_only_assigned_project(self):
        """Employee dashboard shows only the project assigned to that employee."""
        self.login_student1()
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AI-Based Student Performance Analysis', response.data)
        self.assertIn(b'AM-PRJ-001', response.data)
        # Should NOT show student 2's project
        self.assertNotIn(b'Autonomous Cloud Microservices Security Gateway', response.data)

    # ── Test 3: IDOR Protection on Project & Milestones ───────────────────────

    def test_03_idor_protection_between_employees(self):
        """Student 1 cannot access Student 2's project or milestone details."""
        with self.app.app_context():
            student2 = Student.query.filter_by(student_uid='AM-INT-2026-002').first()
            s2_assignment = student2.active_internship.active_assignment
            s2_w1 = s2_assignment.weekly_milestones.filter_by(week_number=1).first()
            s2_assign_id = s2_assignment.id
            s2_milestone_id = s2_w1.id

        self.login_student1()

        # Try accessing student 2's project detail
        resp1 = self.client.get(f'/project/{s2_assign_id}')
        self.assertEqual(resp1.status_code, 403)

        # Try accessing student 2's milestone detail
        resp2 = self.client.get(f'/week/{s2_milestone_id}')
        self.assertEqual(resp2.status_code, 403)

    # ── Test 4: Week 1 Available Initially & Weeks 2-4 Locked ─────────────────

    def test_04_initial_week_status(self):
        """Week 1 is initially AVAILABLE and subsequent weeks are LOCKED."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student1.active_internship.active_assignment
            milestones = assignment.weekly_milestones.order_by(WeeklyMilestone.week_number.asc()).all()

            self.assertEqual(milestones[0].status, 'AVAILABLE')
            self.assertEqual(milestones[0].display_status, 'AVAILABLE')
            for m in milestones[1:]:
                self.assertEqual(m.status, 'LOCKED')
                self.assertEqual(m.display_status, 'LOCKED')

    # ── Test 5: Employee Views Week 1 Tasks from Database ─────────────────────

    def test_05_view_week_tasks_from_database(self):
        """Viewing Week 1 displays tasks fetched dynamically from database."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            w1_id = w1.id

        self.login_student1()
        response = self.client.get(f'/week/{w1_id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Project Understanding, Architecture', response.data)
        self.assertIn(b'Understand project requirements', response.data)

    # ── Test 6: Task Toggle Completion ────────────────────────────────────────

    def test_06_toggle_task_completion(self):
        """Employee can check off and toggle task completion."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            task1 = w1.tasks.first()
            w1_id = w1.id
            task1_id = task1.id

        self.login_student1()

        # Toggle to True
        resp = self.client.post(f'/week/{w1_id}/task/{task1_id}/toggle', headers={'Accept': 'application/json'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_completed'])

        # Toggle back to False
        resp2 = self.client.post(f'/week/{w1_id}/task/{task1_id}/toggle', headers={'Accept': 'application/json'})
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertFalse(data2['is_completed'])

    # ── Test 7: Submission Blocked When Tasks Incomplete ──────────────────────

    def test_07_submission_blocked_when_tasks_incomplete(self):
        """Employee cannot submit week deliverables while tasks remain incomplete."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            w1_id = w1.id
            # Ensure tasks are incomplete
            for t in w1.tasks.all():
                t.is_completed = False
            db.session.commit()

        self.login_student1()
        data = {
            'github_url': 'https://github.com/student/ai-performance',
            'demo_video': (io.BytesIO(b'dummy video content'), 'demo.mp4')
        }
        response = self.client.post(f'/submissions/submit/{w1_id}', data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Complete all required tasks before submitting your work', response.data)

        # Milestone should NOT be submitted
        with self.app.app_context():
            m = db.session.get(WeeklyMilestone, w1_id)
            self.assertEqual(m.status, 'AVAILABLE')

    # ── Test 8: GitHub URL Validation ─────────────────────────────────────────

    def test_08_github_url_validation(self):
        """Invalid GitHub URLs are rejected."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            w1_id = w1.id
            # Mark all tasks complete
            for t in w1.tasks.all():
                t.is_completed = True
            db.session.commit()

        self.login_student1()

        # Invalid URL test
        data = {
            'github_url': 'https://not-github.com/malicious/repo',
            'demo_video': (io.BytesIO(b'dummy video content'), 'demo.mp4')
        }
        response = self.client.post(f'/submissions/submit/{w1_id}', data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please provide a valid GitHub repository URL', response.data)

    # ── Test 9: Video Upload Validation ───────────────────────────────────────

    def test_09_video_upload_validation(self):
        """Invalid video formats (e.g. .exe) are rejected."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            w1_id = w1.id
            for t in w1.tasks.all():
                t.is_completed = True
            db.session.commit()

        self.login_student1()

        data = {
            'github_url': 'https://github.com/aarav-kumar/ai-performance',
            'demo_video': (io.BytesIO(b'binary content'), 'malicious.exe')
        }
        response = self.client.post(f'/submissions/submit/{w1_id}', data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid video format', response.data)

    # ── Test 10: Successful Submission Workflow ───────────────────────────────

    def test_10_successful_submission(self):
        """With tasks completed, valid video, and valid GitHub URL, submission succeeds."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            w1_id = w1.id
            for t in w1.tasks.all():
                t.is_completed = True
            db.session.commit()

        self.login_student1()

        data = {
            'github_url': 'https://github.com/aarav-kumar/ai-performance',
            'demo_video': (io.BytesIO(b'valid mp4 video bytes'), 'walkthrough.mp4'),
            'submission_notes': 'Implemented data pipelines and baseline model.'
        }
        response = self.client.post(f'/submissions/submit/{w1_id}', data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'UNDER REVIEW', response.data)

        # Verify in database
        with self.app.app_context():
            m = db.session.get(WeeklyMilestone, w1_id)
            self.assertEqual(m.status, 'UNDER_REVIEW')
            self.assertEqual(m.submissions.count(), 1)
            sub = m.latest_submission
            self.assertEqual(sub.status, 'UNDER_REVIEW')
            self.assertEqual(sub.github_url, 'https://github.com/aarav-kumar/ai-performance')
            self.assertIn('walkthrough', sub.demo_video_path)

    # ── Test 11: Duplicate Submission Blocked While Under Review ──────────────

    def test_11_duplicate_submission_blocked_while_under_review(self):
        """Cannot submit again while current submission is UNDER_REVIEW."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            w1.status = 'UNDER_REVIEW'
            w1_id = w1.id
            for t in w1.tasks.all():
                t.is_completed = True
            db.session.commit()

        self.login_student1()
        data = {
            'github_url': 'https://github.com/aarav-kumar/ai-performance',
            'demo_video': (io.BytesIO(b'valid video bytes'), 'demo.mp4')
        }
        response = self.client.post(f'/submissions/submit/{w1_id}', data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'already currently under review', response.data)

    # ── Test 12: Secure Video Streaming Authorization ─────────────────────────

    def test_12_video_streaming_security(self):
        """Only owning student or admin can stream submission video; other students get 403."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()

            # Create mock video file in upload folder
            upload_dir = self.app.config['VIDEO_UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            video_filename = 'test_demo_sample.mp4'
            with open(os.path.join(upload_dir, video_filename), 'wb') as f:
                f.write(b'video test payload')

            sub = WeeklySubmission(
                milestone_id=w1.id,
                student_id=student1.id,
                github_url='https://github.com/aarav/project',
                demo_video_path=video_filename,
                status='UNDER_REVIEW'
            )
            db.session.add(sub)
            db.session.commit()
            sub_id = sub.id

        # 1. Student 1 (owner) can stream
        self.login_student1()
        resp_s1 = self.client.get(f'/employee/submission/{sub_id}/video')
        self.assertEqual(resp_s1.status_code, 200)

        # 2. Student 2 (unauthorized) gets 403
        self.login_student2()
        resp_s2 = self.client.get(f'/employee/submission/{sub_id}/video')
        self.assertEqual(resp_s2.status_code, 403)

        # 3. Admin can stream
        self.login_admin()
        resp_admin = self.client.get(f'/admin/submission/{sub_id}/video')
        self.assertEqual(resp_admin.status_code, 200)

    # ── Test 13: Admin Manage Employee Tasks Dashboard ────────────────────────

    def test_13_admin_employee_tasks_dashboard(self):
        """Admin can view the Manage Employee Tasks dashboard with filters & search."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            sub = WeeklySubmission(
                milestone_id=w1.id,
                student_id=student1.id,
                github_url='https://github.com/aarav/project',
                status='UNDER_REVIEW'
            )
            db.session.add(sub)
            db.session.commit()

        self.login_admin()
        response = self.client.get('/admin/employee-tasks')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'MANAGE EMPLOYEE TASKS', response.data)
        self.assertIn(b'Aarav Kumar', response.data)

        # Filter by 1M
        resp_1m = self.client.get('/admin/employee-tasks?duration=1m')
        self.assertEqual(resp_1m.status_code, 200)
        self.assertIn(b'Aarav Kumar', resp_1m.data)

        # Filter by 3M
        resp_3m = self.client.get('/admin/employee-tasks?duration=3m')
        self.assertEqual(resp_3m.status_code, 200)
        self.assertNotIn(b'Aarav Kumar', resp_3m.data)

        # Search by name
        resp_search = self.client.get('/admin/employee-tasks?q=Aarav')
        self.assertEqual(resp_search.status_code, 200)
        self.assertIn(b'Aarav Kumar', resp_search.data)

    # ── Test 14: Admin Review Page Details ────────────────────────────────────

    def test_14_admin_review_page(self):
        """Admin can view submission review page with candidate details, tasks, and GitHub link."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            sub = WeeklySubmission(
                milestone_id=w1.id,
                student_id=student1.id,
                github_url='https://github.com/aarav/project',
                status='UNDER_REVIEW'
            )
            db.session.add(sub)
            db.session.commit()
            sub_id = sub.id

        self.login_admin()
        response = self.client.get(f'/admin/submissions/{sub_id}/review')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Aarav Kumar', response.data)
        self.assertIn(b'AM-INT-2026-001', response.data)
        self.assertIn(b'https://github.com/aarav/project', response.data)
        self.assertIn(b'PROCEED TO NEXT', response.data)
        self.assertIn(b'REDO', response.data)
        self.assertIn(b'VERIFY', response.data)

    # ── Test 15: Admin REDO Action Workflow ───────────────────────────────────

    def test_15_admin_redo_workflow(self):
        """Admin REDO action marks submission REDO_REQUIRED and records feedback."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            w1.status = 'UNDER_REVIEW'
            sub = WeeklySubmission(
                milestone_id=w1.id,
                student_id=student1.id,
                github_url='https://github.com/aarav/project',
                status='UNDER_REVIEW'
            )
            db.session.add(sub)
            db.session.commit()
            sub_id = sub.id
            w1_id = w1.id

        self.login_admin()
        response = self.client.post(f'/admin/submissions/{sub_id}/redo', data={
            'admin_remarks': 'Please improve unit test coverage and add error handling.'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'REDO REQUIRED', response.data)

        # Check DB states
        with self.app.app_context():
            s = db.session.get(WeeklySubmission, sub_id)
            m = db.session.get(WeeklyMilestone, w1_id)
            self.assertEqual(s.status, 'REDO_REQUIRED')
            self.assertEqual(m.status, 'REDO_REQUIRED')
            self.assertEqual(m.display_status, 'REDO_REQUIRED')
            self.assertIn('improve unit test', s.review_feedback)

            # Evaluation log created
            eval_log = Evaluation.query.filter_by(submission_id=sub_id, action='REDO').first()
            self.assertIsNotNone(eval_log)
            self.assertEqual(eval_log.action, 'REDO')

    # ── Test 16: Resubmission Preserves Submission History ────────────────────

    def test_16_resubmission_preserves_history(self):
        """Student resubmits after REDO; previous submission is preserved (audit trail)."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            w1 = student1.active_internship.active_assignment.weekly_milestones.filter_by(week_number=1).first()
            w1.status = 'REDO_REQUIRED'
            w1_id = w1.id
            for t in w1.tasks.all():
                t.is_completed = True

            # First submission (marked REDO_REQUIRED)
            sub1 = WeeklySubmission(
                milestone_id=w1.id,
                student_id=student1.id,
                github_url='https://github.com/aarav/initial-version',
                status='REDO_REQUIRED',
                review_feedback='Need better data visualization.'
            )
            db.session.add(sub1)
            db.session.commit()

        self.login_student1()
        data = {
            'github_url': 'https://github.com/aarav/improved-version',
            'demo_video': (io.BytesIO(b'new video bytes'), 'resubmission.mp4'),
            'submission_notes': 'Added matplotlib charts and correlation matrices.'
        }
        response = self.client.post(f'/submissions/submit/{w1_id}', data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Check DB history
        with self.app.app_context():
            m = db.session.get(WeeklyMilestone, w1_id)
            self.assertEqual(m.submissions.count(), 2)
            all_subs = WeeklySubmission.query.filter_by(milestone_id=w1_id).order_by(WeeklySubmission.id.asc()).all()
            # Sub 1 remains REDO_REQUIRED
            self.assertEqual(all_subs[0].status, 'REDO_REQUIRED')
            self.assertEqual(all_subs[0].github_url, 'https://github.com/aarav/initial-version')
            # Sub 2 is UNDER_REVIEW
            self.assertEqual(all_subs[1].status, 'UNDER_REVIEW')
            self.assertEqual(all_subs[1].github_url, 'https://github.com/aarav/improved-version')

    # ── Test 17: Admin VERIFY Action Workflow ─────────────────────────────────

    def test_17_admin_verify_action(self):
        """Admin VERIFY action marks submission approved without unlocking next week."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student1.active_internship.active_assignment
            w1 = assignment.weekly_milestones.filter_by(week_number=1).first()
            w2 = assignment.weekly_milestones.filter_by(week_number=2).first()
            w1.status = 'UNDER_REVIEW'
            sub = WeeklySubmission(
                milestone_id=w1.id,
                student_id=student1.id,
                github_url='https://github.com/aarav/project',
                status='UNDER_REVIEW'
            )
            db.session.add(sub)
            db.session.commit()
            sub_id = sub.id
            w2_id = w2.id

        self.login_admin()
        response = self.client.post(f'/admin/submissions/{sub_id}/verify', data={
            'admin_remarks': 'Verified code and demo.'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            s = db.session.get(WeeklySubmission, sub_id)
            w2 = db.session.get(WeeklyMilestone, w2_id)
            self.assertEqual(s.status, 'APPROVED')
            # CRITICAL: Week 2 MUST STILL BE LOCKED after only VERIFY
            self.assertEqual(w2.status, 'LOCKED')

    # ── Test 18: Admin PROCEED TO NEXT Progression ────────────────────────────

    def test_18_admin_proceed_to_next_progression(self):
        """PROCEED TO NEXT marks Week 1 COMPLETED and unlocks Week 2 as AVAILABLE immediately."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student1.active_internship.active_assignment
            w1 = assignment.weekly_milestones.filter_by(week_number=1).first()
            w2 = assignment.weekly_milestones.filter_by(week_number=2).first()
            w3 = assignment.weekly_milestones.filter_by(week_number=3).first()
            w1.status = 'UNDER_REVIEW'
            sub = WeeklySubmission(
                milestone_id=w1.id,
                student_id=student1.id,
                github_url='https://github.com/aarav/project',
                status='UNDER_REVIEW'
            )
            db.session.add(sub)
            db.session.commit()
            sub_id = sub.id
            w1_id = w1.id
            w2_id = w2.id
            w3_id = w3.id

        self.login_admin()
        response = self.client.post(f'/admin/submissions/{sub_id}/proceed-next', data={
            'admin_remarks': 'Excellent work on Week 1 architecture.'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Check DB states
        with self.app.app_context():
            w1 = db.session.get(WeeklyMilestone, w1_id)
            w2 = db.session.get(WeeklyMilestone, w2_id)
            w3 = db.session.get(WeeklyMilestone, w3_id)

            # Week 1 is COMPLETED
            self.assertEqual(w1.status, 'COMPLETED')
            self.assertEqual(w1.display_status, 'COMPLETED')
            self.assertIsNotNone(w1.completed_at)

            # Week 2 is AVAILABLE with initialized 7-day deadline
            self.assertEqual(w2.status, 'AVAILABLE')
            self.assertEqual(w2.display_status, 'AVAILABLE')
            self.assertIsNotNone(w2.started_at)
            self.assertIsNotNone(w2.due_at)

            # Week 3 remains LOCKED
            self.assertEqual(w3.status, 'LOCKED')

            # Evaluation audit created
            eval_log = Evaluation.query.filter_by(submission_id=sub_id, action='PROCEED_TO_NEXT').first()
            self.assertIsNotNone(eval_log)

    # ── Test 19: 7-Day Rule: Does NOT Unlock Next Week Automatically ──────────

    def test_19_seven_days_overdue_does_not_unlock_next_week(self):
        """Incomplete week past 7 days displays OVERDUE/PENDING; next week remains LOCKED."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student1.active_internship.active_assignment
            w1 = assignment.weekly_milestones.filter_by(week_number=1).first()
            w2 = assignment.weekly_milestones.filter_by(week_number=2).first()

            # Set started 10 days ago, due 3 days ago (overdue)
            past_date = datetime.utcnow() - timedelta(days=10)
            due_date = datetime.utcnow() - timedelta(days=3)
            w1.started_at = past_date
            w1.due_at = due_date
            w1.status = 'IN_PROGRESS'
            db.session.commit()
            w1_id = w1.id
            w2_id = w2.id

        with self.app.app_context():
            w1 = db.session.get(WeeklyMilestone, w1_id)
            w2 = db.session.get(WeeklyMilestone, w2_id)

            # Week 1 is overdue
            self.assertTrue(w1.is_overdue)
            self.assertEqual(w1.display_status, 'OVERDUE')

            # CRITICAL RULE: Next week MUST REMAIN LOCKED
            self.assertEqual(w2.status, 'LOCKED')
            self.assertEqual(w2.display_status, 'LOCKED')

    # ── Test 20: Final Week Progression Completes Project (100%) ──────────────

    def test_20_final_week_progression(self):
        """Proceeding on final week (Week 4) marks project and internship 100% COMPLETED."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student1.active_internship.active_assignment
            # Mark Weeks 1..3 completed
            for m in assignment.weekly_milestones.filter(WeeklyMilestone.week_number < 4).all():
                m.status = 'COMPLETED'
                m.completed_at = datetime.utcnow()

            w4 = assignment.weekly_milestones.filter_by(week_number=4).first()
            w4.status = 'UNDER_REVIEW'
            sub = WeeklySubmission(
                milestone_id=w4.id,
                student_id=student1.id,
                github_url='https://github.com/aarav/final-project',
                status='UNDER_REVIEW'
            )
            db.session.add(sub)
            db.session.commit()
            sub_id = sub.id
            assign_id = assignment.id

        self.login_admin()
        response = self.client.post(f'/admin/submissions/{sub_id}/proceed-next', data={
            'admin_remarks': 'Final defense passed. Excellent project execution.'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            assignment = db.session.get(ProjectAssignment, assign_id)
            self.assertEqual(assignment.status, 'COMPLETED')
            self.assertEqual(assignment.internship.status, 'COMPLETED')
            self.assertEqual(assignment.progress_percent, 100)

    # ── Test 21: Proceed to Next Double Click Protection ──────────────────────

    def test_21_double_click_protection(self):
        """Clicking PROCEED TO NEXT on an already completed milestone is idempotent."""
        with self.app.app_context():
            student1 = Student.query.filter_by(student_uid='AM-INT-2026-001').first()
            assignment = student1.active_internship.active_assignment
            w1 = assignment.weekly_milestones.filter_by(week_number=1).first()
            w1.status = 'COMPLETED'
            sub = WeeklySubmission(
                milestone_id=w1.id,
                student_id=student1.id,
                status='COMPLETED'
            )
            db.session.add(sub)
            db.session.commit()
            sub_id = sub.id

        self.login_admin()
        # Second click attempt
        response = self.client.post(f'/admin/submissions/{sub_id}/proceed-next', data={
            'admin_remarks': 'Duplicate click'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'already been completed', response.data)
