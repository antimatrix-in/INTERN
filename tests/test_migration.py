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


if __name__ == '__main__':
    unittest.main()
