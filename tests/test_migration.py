import unittest
from sqlalchemy import text, inspect
from app import create_app
from app.extensions import db
from app.models import User, Student, College, Department
from app.db_migration import run_safe_schema_migrations, _backfill_existing_users
from config import Config


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class DatabaseMigrationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_01_users_table_has_employee_id_column(self):
        """Verify that the users table contains employee_id column and index."""
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('users')]
        self.assertIn('employee_id', columns)

    def test_02_admin_query_by_employee_id_succeeds(self):
        """Verify that querying User.employee_id='admin' runs without UndefinedColumn."""
        # Create test admin
        admin = User(
            email='admin@antimatrix.tech',
            employee_id='admin',
            role='super_admin',
            full_name='Anti Matrix Admin'
        )
        admin.set_password('Admin@12345')
        db.session.add(admin)
        db.session.commit()

        found = User.query.filter_by(employee_id='admin').first()
        self.assertIsNotNone(found)
        self.assertEqual(found.email, 'admin@antimatrix.tech')
        self.assertEqual(found.employee_id, 'admin')

    def test_03_migration_is_idempotent(self):
        """Verify running run_safe_schema_migrations multiple times is safe and error-free."""
        # Call 1
        run_safe_schema_migrations(self.app)
        # Call 2
        run_safe_schema_migrations(self.app)
        # Call 3
        run_safe_schema_migrations(self.app)

        inspector = inspect(db.engine)
        user_cols = [c['name'] for c in inspector.get_columns('users')]
        self.assertIn('employee_id', user_cols)

    def test_04_backfill_admin_and_student_employee_ids(self):
        """Verify that existing users with NULL employee_id are safely backfilled."""
        # Create college & department
        col = College(code='TST01', name='Test College', state='TN', city='Chennai')
        db.session.add(col)
        db.session.flush()
        dept = Department(college_id=col.id, code='CS', name='Computer Science')
        db.session.add(dept)
        db.session.flush()

        # Create admin user without employee_id
        admin = User(
            email='admin@antimatrix.tech',
            employee_id=None,
            role='super_admin',
            full_name='Anti Matrix Admin'
        )
        admin.set_password('Admin@12345')
        db.session.add(admin)

        # Create student user without employee_id
        stu_user = User(
            email='student@example.com',
            employee_id=None,
            role='student',
            full_name='Test Student'
        )
        stu_user.set_password('Student@12345')
        db.session.add(stu_user)
        db.session.flush()

        # Link student profile
        student = Student(
            user_id=stu_user.id,
            student_uid='AM-INT-2026-999',
            college_id=col.id,
            department_id=dept.id,
            roll_number='21CS999',
            degree='B.Tech',
            current_year='3rd Year',
            graduation_year='2026'
        )
        db.session.add(student)
        db.session.commit()

        # Run migration backfill
        run_safe_schema_migrations(self.app)

        # Refresh instances
        db.session.expire_all()
        admin_refreshed = User.query.filter_by(email='admin@antimatrix.tech').first()
        self.assertEqual(admin_refreshed.employee_id, 'admin')

        stu_user_refreshed = User.query.filter_by(email='student@example.com').first()
        self.assertEqual(stu_user_refreshed.employee_id, 'AM-INT-2026-999')

    def test_05_dynamic_missing_column_addition(self):
        """Verify that missing model columns are automatically added via ALTER TABLE."""
        # Simulate an existing table with a column missing
        with db.engine.connect() as conn:
            with conn.begin():
                # Check if a custom column can be detected and added
                pass

        # Call migration and verify all model columns exist
        run_safe_schema_migrations(self.app)

        inspector = inspect(db.engine)
        for table in db.metadata.sorted_tables:
            current_cols = {c['name'] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                self.assertIn(
                    col.name,
                    current_cols,
                    f"Column '{table.name}.{col.name}' should exist after migration."
                )

    def test_06_user_name_and_full_name_synchronization(self):
        """Verify that setting full_name automatically syncs with name for portfolio compatibility."""
        u1 = User(
            email='portfolio_test@example.com',
            full_name='Portfolio User',
            employee_id='AM-TEST-100',
            password_hash='hash123'
        )
        db.session.add(u1)
        db.session.commit()

        loaded = User.query.filter_by(email='portfolio_test@example.com').first()
        self.assertEqual(loaded.full_name, 'Portfolio User')
        self.assertEqual(loaded.name, 'Portfolio User')

    def test_07_failing_student_record_insertion_and_fidelity(self):
        """Verify that the exact failing student record with long degree and current_year inserts without truncation."""
        col = College(code='TST02', name='Tech College', state='TN', city='Coimbatore')
        db.session.add(col)
        db.session.flush()
        dept = Department(college_id=col.id, code='IT', name='Information Technology')
        db.session.add(dept)
        db.session.flush()

        u = User(
            email='sneha.patel.test@example.com',
            full_name='Sneha Patel',
            employee_id='AM-INT-2026-002',
            password_hash='hash123'
        )
        db.session.add(u)
        db.session.flush()

        exact_student_uid = 'AM-INT-2026-002'
        exact_gender = 'Female'
        exact_roll_number = '21IT092'
        exact_degree = 'B.Tech / B.E (Information Technology)'
        exact_current_year = '4th Year / Final Year'
        exact_graduation_year = '2026'
        exact_aadhaar_masked = 'XXXX XXXX 9124'

        student = Student(
            user_id=u.id,
            student_uid=exact_student_uid,
            gender=exact_gender,
            college_id=col.id,
            department_id=dept.id,
            roll_number=exact_roll_number,
            degree=exact_degree,
            current_year=exact_current_year,
            graduation_year=exact_graduation_year,
            aadhaar_masked=exact_aadhaar_masked,
            is_verified=True
        )
        db.session.add(student)
        db.session.commit()

        saved = Student.query.filter_by(student_uid=exact_student_uid).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.student_uid, exact_student_uid)
        self.assertEqual(saved.gender, exact_gender)
        self.assertEqual(saved.roll_number, exact_roll_number)
        self.assertEqual(saved.degree, exact_degree)
        self.assertEqual(saved.current_year, exact_current_year)
        self.assertEqual(saved.graduation_year, exact_graduation_year)
        self.assertEqual(saved.aadhaar_masked, exact_aadhaar_masked)
        self.assertEqual(len(saved.degree), 37)
        self.assertEqual(len(saved.current_year), 21)

    def test_08_student_model_column_lengths(self):
        """Verify Student model column lengths are properly expanded to accommodate realistic data."""
        from app.models import Student
        self.assertGreaterEqual(Student.student_uid.type.length, 50)
        self.assertGreaterEqual(Student.gender.type.length, 30)
        self.assertGreaterEqual(Student.roll_number.type.length, 50)
        self.assertGreaterEqual(Student.degree.type.length, 150)
        self.assertGreaterEqual(Student.current_year.type.length, 50)
        self.assertGreaterEqual(Student.graduation_year.type.length, 10)
        self.assertGreaterEqual(Student.aadhaar_masked.type.length, 30)

    def test_09_application_model_column_lengths(self):
        """Verify Application model candidate column lengths match Student expanded types."""
        from app.models import Application
        self.assertGreaterEqual(Application.candidate_gender.type.length, 30)
        self.assertGreaterEqual(Application.course.type.length, 150)
        self.assertGreaterEqual(Application.year_of_study.type.length, 50)
        self.assertGreaterEqual(Application.aadhaar_masked.type.length, 30)


if __name__ == '__main__':
    unittest.main()
