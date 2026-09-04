import json
import unittest
from datetime import date
from app import create_app
from app.extensions import db
from app.models import (
    User, Student, Internship, Project, ProjectAssignment,
    ProjectWeek, ProjectTask, WeeklyMilestone, WeeklyTask,
    Application, College, Department, InternshipPlan
)
from app.seed import seed_initial_data
from tests.test_config import TestConfig


class ProjectManagementTestCase(unittest.TestCase):
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
        return self.client.post('/admin/login', data={
            'email_or_id': 'admin',
            'password': 'Admin@12345'
        }, follow_redirects=True)

    def login_student(self, email_or_id='AM-INT-2026-001', password='Student@2026Password!'):
        return self.client.post('/login', data={
            'employee_id': email_or_id,
            'password': password
        }, follow_redirects=True)

    # 1. Admin can log in
    def test_01_admin_login(self):
        resp = self.login_admin()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Dashboard', resp.data)

    # 2. Admin Dashboard loads
    def test_02_admin_dashboard_loads(self):
        self.login_admin()
        resp = self.client.get('/admin/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Dashboard', resp.data)
        self.assertIn(b'Project Database', resp.data)

    # 3. Employees -> 1 Month shows only current active 1-month employees
    def test_03_employees_1_month_filter(self):
        self.login_admin()
        resp = self.client.get('/admin/employees?duration=1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Aarav Kumar', resp.data)
        self.assertNotIn(b'Sneha Patel', resp.data)

    # 4. Employees -> 3 Months shows only current active 3-month employees
    def test_04_employees_3_month_filter(self):
        self.login_admin()
        resp = self.client.get('/admin/employees?duration=3')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Sneha Patel', resp.data)
        self.assertNotIn(b'Aarav Kumar', resp.data)

    # 5. Project Database -> 1 Month shows only 1-month projects
    def test_05_projects_1_month_filter(self):
        self.login_admin()
        resp = self.client.get('/admin/projects?duration=1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'AI-Based Student Performance Analysis System', resp.data)
        self.assertNotIn(b'Autonomous Cloud Microservices Security Gateway', resp.data)

    # 6. Project Database -> 3 Months shows only 3-month projects
    def test_06_projects_3_month_filter(self):
        self.login_admin()
        resp = self.client.get('/admin/projects?duration=3')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Autonomous Cloud Microservices Security Gateway', resp.data)
        self.assertNotIn(b'AI-Based Student Performance Analysis System', resp.data)

    # 7. Create Project -> 1 Month creates exactly 4 weeks
    def test_07_create_project_1_month_creates_4_weeks(self):
        self.login_admin()
        post_data = {
            'project_code': 'AM-1M-101',
            'title': 'Smart Campus Energy Management',
            'domain': 'IoT & Green Tech',
            'description': 'IoT energy monitoring and control platform.',
            'problem_statement': 'Campuses waste power due to lack of real-time monitoring.',
            'expected_outcome': 'Live energy consumption dashboard with anomaly alerts.',
            'duration_months': '1',
            'difficulty': 'Intermediate',
            'status': 'ACTIVE',
            'tech_stack': 'Python, Flask, MQTT, PostgreSQL',
            'objectives': 'Build telemetry ingestion\nCreate dashboard',
            'week_1_title': 'Week 1: Architecture & Sensor Ingestion',
            'week_2_title': 'Week 2: Backend API & Database Storage',
            'week_3_title': 'Week 3: Frontend Analytics UI',
            'week_4_title': 'Week 4: Live Deployment & Defense'
        }
        resp = self.client.post('/admin/projects/create', data=post_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            p = Project.query.filter_by(project_code='AM-1M-101').first()
            self.assertIsNotNone(p)
            self.assertEqual(p.duration_weeks, 4)
            self.assertEqual(p.duration_months, 1)
            self.assertEqual(p.project_weeks.count(), 4)

    # 8. Create Project -> 3 Months creates exactly 12 weeks
    def test_08_create_project_3_month_creates_12_weeks(self):
        self.login_admin()
        post_data = {
            'project_code': 'AM-3M-101',
            'title': 'Enterprise Supply Chain Security Platform',
            'domain': 'Cloud & Blockchain',
            'description': 'Zero-knowledge provenance verification system.',
            'duration_months': '3',
            'difficulty': 'Advanced',
            'status': 'ACTIVE',
            'tech_stack': 'Python, Flask, Docker, PostgreSQL'
        }
        resp = self.client.post('/admin/projects/create', data=post_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            p = Project.query.filter_by(project_code='AM-3M-101').first()
            self.assertIsNotNone(p)
            self.assertEqual(p.duration_weeks, 12)
            self.assertEqual(p.duration_months, 3)
            self.assertEqual(p.project_weeks.count(), 12)

    # 9. Tasks are stored in the database
    def test_09_tasks_stored_in_database(self):
        self.login_admin()
        tasks_json = json.dumps([
            {
                'title': 'Requirement Analysis',
                'description': 'Analyze project requirements and design architecture.',
                'instructions': 'Review problem statement and create specification doc.',
                'expected_output': 'Requirements analysis document.',
                'priority': 'High',
                'estimated_hours': 5.0
            }
        ])
        post_data = {
            'project_code': 'AM-1M-201',
            'title': 'Smart Attendance System',
            'domain': 'Computer Vision',
            'description': 'Facial recognition attendance system.',
            'duration_months': '1',
            'status': 'ACTIVE',
            'week_1_title': 'Week 1: Requirements',
            'week_1_tasks': tasks_json
        }
        self.client.post('/admin/projects/create', data=post_data, follow_redirects=True)

        with self.app.app_context():
            p = Project.query.filter_by(project_code='AM-1M-201').first()
            self.assertIsNotNone(p)
            w1 = p.project_weeks.filter_by(week_number=1).first()
            self.assertIsNotNone(w1)
            t = w1.tasks.first()
            self.assertIsNotNone(t)
            self.assertEqual(t.title, 'Requirement Analysis')
            self.assertEqual(t.priority, 'High')
            self.assertEqual(t.estimated_hours, 5.0)

    # 10. Multiple tasks can exist in one week
    def test_10_multiple_tasks_in_one_week(self):
        self.login_admin()
        tasks_json = json.dumps([
            {'title': 'Task 1: Setup Environment', 'priority': 'High', 'estimated_hours': 2.0},
            {'title': 'Task 2: Database Schema', 'priority': 'High', 'estimated_hours': 4.0},
            {'title': 'Task 3: Architecture Diagram', 'priority': 'Medium', 'estimated_hours': 3.0}
        ])
        post_data = {
            'project_code': 'AM-1M-202',
            'title': 'Multi-Task Project Test',
            'domain': 'Software Engineering',
            'description': 'Test project with multiple tasks per week.',
            'duration_months': '1',
            'status': 'ACTIVE',
            'week_1_tasks': tasks_json
        }
        self.client.post('/admin/projects/create', data=post_data, follow_redirects=True)

        with self.app.app_context():
            p = Project.query.filter_by(project_code='AM-1M-202').first()
            w1 = p.project_weeks.filter_by(week_number=1).first()
            self.assertEqual(w1.tasks.count(), 3)

    # 11. Projects have unique Project IDs
    def test_11_project_id_uniqueness(self):
        self.login_admin()
        post_data_1 = {
            'project_code': 'AM-P001',
            'title': 'Project Unique 1',
            'domain': 'AI',
            'description': 'Unique project 1',
            'duration_months': '1'
        }
        resp1 = self.client.post('/admin/projects/create', data=post_data_1, follow_redirects=True)
        self.assertIn(b'created successfully', resp1.data)

        # Attempt to create second project with identical project_code
        post_data_2 = {
            'project_code': 'AM-P001',
            'title': 'Duplicate Code Project',
            'domain': 'AI',
            'description': 'Duplicate project',
            'duration_months': '1'
        }
        resp2 = self.client.post('/admin/projects/create', data=post_data_2, follow_redirects=True)
        self.assertIn(b'already exists', resp2.data)

    # 12. Project IDs cannot be changed after creation
    def test_12_project_id_immutability(self):
        self.login_admin()
        with self.app.app_context():
            p = Project(
                project_code='AM-P999',
                title='Original Title',
                domain='Web',
                description='Original Description',
                objectives_json='[]',
                tech_stack_json='[]',
                requirements_json='[]',
                instructions_md='test',
                reference_links_json='[]',
                duration_weeks=4,
                duration_months=1
            )
            db.session.add(p)
            db.session.commit()
            p_id = p.id

        # Attempt to POST update with a new project_code
        edit_data = {
            'project_code': 'MODIFIED-CODE',
            'title': 'Updated Title',
            'domain': 'Updated Domain',
            'description': 'Updated Description'
        }
        resp = self.client.post(f'/admin/projects/{p_id}/edit', data=edit_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            p_check = db.session.get(Project, p_id)
            # project_code must remain unchanged
            self.assertEqual(p_check.project_code, 'AM-P999')
            self.assertEqual(p_check.title, 'Updated Title')

    # Helper to create active students from specific colleges
    def create_test_student(self, email, employee_id, college_name, plan_duration=1):
        with self.app.app_context():
            # Get or create college
            col = College.query.filter_by(name=college_name).first()
            if not col:
                col = College(code=college_name[:6].upper().replace(' ', ''), name=college_name, state='Tamil Nadu', city='Chennai')
                db.session.add(col)
                db.session.flush()
            dept = Department.query.filter_by(college_id=col.id).first()
            if not dept:
                dept = Department(college_id=col.id, code='CSE', name='Computer Science')
                db.session.add(dept)
                db.session.flush()

            plan = InternshipPlan.query.filter_by(duration_months=plan_duration).first()

            user = User(email=email, employee_id=employee_id, full_name=f'Student {employee_id}', role='student', is_active=True)
            user.set_password('Student@2026Password!')
            db.session.add(user)
            db.session.flush()

            student = Student(
                user_id=user.id,
                student_uid=employee_id,
                college_id=col.id,
                department_id=dept.id,
                roll_number='ROLL-' + employee_id,
                degree='B.Tech',
                current_year='3rd Year',
                graduation_year='2026',
                is_verified=True
            )
            db.session.add(student)
            db.session.flush()

            internship = Internship(
                internship_no='INT-' + employee_id,
                student_id=student.id,
                plan_id=plan.id,
                status='ACTIVE',
                start_date='01 Sep 2026',
                end_date='30 Sep 2026',
                progress_percent=0
            )
            db.session.add(internship)
            db.session.commit()
            return student.id

    # 13. Employee from Velammal College can receive Project P001
    def test_13_assign_project_to_first_college_student_allowed(self):
        s_id = self.create_test_student('velammal1@test.com', 'AM-V1', 'Velammal Institute of Technology', 1)
        self.login_admin()

        with self.app.app_context():
            p = Project.query.filter_by(duration_months=1, is_active=True).first()
            p_id = p.id
            p_code = p.project_code

        resp = self.client.post(f'/admin/assign-project/{s_id}', data={'project_id': p_id}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'successfully assigned', resp.data)

        with self.app.app_context():
            s = db.session.get(Student, s_id)
            self.assertIsNotNone(s.active_internship.active_assignment)
            self.assertEqual(s.active_internship.active_assignment.project_id, p_id)

    # 14. Another active Velammal student CANNOT receive Project P001 (Same college conflict)
    def test_14_assign_same_project_to_same_college_active_student_blocked(self):
        # Student A from Velammal receives project
        s_a_id = self.create_test_student('velammal_a@test.com', 'AM-VA', 'Velammal Institute of Technology', 1)
        s_b_id = self.create_test_student('velammal_b@test.com', 'AM-VB', 'Velammal Institute of Technology', 1)
        self.login_admin()

        with self.app.app_context():
            p = Project.query.filter_by(duration_months=1, is_active=True).first()
            p_id = p.id
            p_code = p.project_code

        # Assign to Student A
        self.client.post(f'/admin/assign-project/{s_a_id}', data={'project_id': p_id}, follow_redirects=True)

        # Attempt to assign the same project to Student B from the same college
        resp = self.client.post(f'/admin/assign-project/{s_b_id}', data={'project_id': p_id}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'already been assigned to another active student from Velammal Institute of Technology', resp.data)

        # Verify Student B did NOT get the project
        with self.app.app_context():
            s_b = db.session.get(Student, s_b_id)
            self.assertIsNone(s_b.active_internship.active_assignment)

    # 15. Student from Jaya College CAN receive Project P001 (Different college allowed)
    def test_15_assign_same_project_to_different_college_allowed(self):
        s_velammal = self.create_test_student('velammal_user@test.com', 'AM-VEL-1', 'Velammal Institute of Technology', 1)
        s_jaya = self.create_test_student('jaya_user@test.com', 'AM-JAY-1', 'Jaya College of Engineering & Technology', 1)
        self.login_admin()

        with self.app.app_context():
            p = Project.query.filter_by(duration_months=1, is_active=True).first()
            p_id = p.id

        # Assign to Velammal student
        self.client.post(f'/admin/assign-project/{s_velammal}', data={'project_id': p_id}, follow_redirects=True)

        # Assign to Jaya student -> MUST BE ALLOWED
        resp = self.client.post(f'/admin/assign-project/{s_jaya}', data={'project_id': p_id}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'successfully assigned', resp.data)

        with self.app.app_context():
            s_j = db.session.get(Student, s_jaya)
            self.assertIsNotNone(s_j.active_internship.active_assignment)
            self.assertEqual(s_j.active_internship.active_assignment.project_id, p_id)

    # 16. Inactive/completed assignment does not permanently block the project
    def test_16_completed_assignment_allows_new_same_college_assignment(self):
        s_old = self.create_test_student('old_velammal@test.com', 'AM-OLD-1', 'Velammal Institute of Technology', 1)
        s_new = self.create_test_student('new_velammal@test.com', 'AM-NEW-1', 'Velammal Institute of Technology', 1)
        self.login_admin()

        with self.app.app_context():
            p = Project.query.filter_by(duration_months=1, is_active=True).first()
            p_id = p.id

        # Assign to Old student
        self.client.post(f'/admin/assign-project/{s_old}', data={'project_id': p_id}, follow_redirects=True)

        # Mark old student's internship and assignment as COMPLETED
        with self.app.app_context():
            s_old_rec = db.session.get(Student, s_old)
            s_old_rec.active_internship.status = 'COMPLETED'
            s_old_rec.active_internship.active_assignment.status = 'COMPLETED'
            db.session.commit()

        # Now assign to New student from the same college -> MUST BE ALLOWED
        resp = self.client.post(f'/admin/assign-project/{s_new}', data={'project_id': p_id}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'successfully assigned', resp.data)

    # 17. Only duration-compatible projects appear / can be assigned
    def test_17_duration_compatibility_enforced(self):
        s_1m = self.create_test_student('intern_1m@test.com', 'AM-1M-USER', 'Indian Institute of Technology Madras', 1)
        self.login_admin()

        with self.app.app_context():
            p_3m = Project.query.filter_by(duration_months=3, is_active=True).first()
            p_3m_id = p_3m.id

        # Attempt to assign 3-month project to 1-month student
        resp = self.client.post(f'/admin/assign-project/{s_1m}', data={'project_id': p_3m_id}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'does not match student internship duration', resp.data)

    # 18. Only ACTIVE projects can be assigned
    def test_18_inactive_project_assignment_blocked(self):
        s_id = self.create_test_student('active_intern@test.com', 'AM-ACT-1', 'PSG College of Technology', 1)
        self.login_admin()

        with self.app.app_context():
            p = Project(
                project_code='AM-INACTIVE-01',
                title='Inactive Project Test',
                domain='DevOps',
                description='Inactive project',
                objectives_json='[]',
                tech_stack_json='[]',
                requirements_json='[]',
                instructions_md='instructions',
                reference_links_json='[]',
                duration_weeks=4,
                duration_months=1,
                is_active=False
            )
            db.session.add(p)
            db.session.commit()
            p_id = p.id

        resp = self.client.post(f'/admin/assign-project/{s_id}', data={'project_id': p_id}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'is currently inactive and cannot be assigned', resp.data)

    # 19. Backend performs the college/project uniqueness check
    def test_19_backend_enforces_college_uniqueness_post(self):
        # Raw POST direct verification test
        s1 = self.create_test_student('user_col1_a@test.com', 'AM-C1A', 'National Institute of Technology Karnataka', 1)
        s2 = self.create_test_student('user_col1_b@test.com', 'AM-C1B', 'National Institute of Technology Karnataka', 1)
        self.login_admin()

        with self.app.app_context():
            p = Project.query.filter_by(duration_months=1, is_active=True).first()
            p_id = p.id

        # First assignment succeeds
        self.client.post(f'/admin/assign-project/{s1}', data={'project_id': p_id})
        # Second assignment to same college must fail
        resp = self.client.post(f'/admin/assign-project/{s2}', data={'project_id': p_id}, follow_redirects=True)
        self.assertIn(b'already been assigned to another active student', resp.data)

    # 20. Unauthorized users cannot access admin project management
    def test_20_unauthorized_user_blocked_from_project_management(self):
        # Student logs in
        self.login_student()

        # Student attempts to access admin create project
        resp = self.client.get('/admin/projects/create')
        self.assertIn(resp.status_code, [302, 403])

        # Student attempts to post project creation
        resp_post = self.client.post('/admin/projects/create', data={'title': 'Hacked Project'})
        self.assertIn(resp_post.status_code, [302, 403])

    # 21. Existing application data is not deleted
    def test_21_existing_application_data_preserved(self):
        with self.app.app_context():
            apps = Application.query.all()
            self.assertGreater(len(apps), 0)
            self.assertTrue(any(a.application_no == 'AM-APP-2026-001' for a in apps))

    # 22. Existing functionality continues to work
    def test_22_existing_functionality_works(self):
        self.login_admin()
        # Test employee list, detail, and project weeks API
        resp_emp = self.client.get('/admin/employees')
        self.assertEqual(resp_emp.status_code, 200)

        with self.app.app_context():
            s = Student.query.first()
            s_id = s.id
            p = Project.query.first()
            p_id = p.id

        resp_detail = self.client.get(f'/admin/employees/{s_id}')
        self.assertEqual(resp_detail.status_code, 200)

        resp_api = self.client.get(f'/admin/api/project/{p_id}/weeks')
        self.assertEqual(resp_api.status_code, 200)
        data = json.loads(resp_api.data)
        self.assertTrue(data.get('success'))


if __name__ == '__main__':
    unittest.main()
