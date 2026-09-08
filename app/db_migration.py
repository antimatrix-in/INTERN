import logging
from sqlalchemy import inspect, text
from app.extensions import db

logger = logging.getLogger('anti_matrix.migration')


def get_column_type_sql(column, dialect):
    """Compile SQLAlchemy column type to raw SQL string for the active dialect."""
    try:
        compiled = column.type.compile(dialect)
        return str(compiled)
    except Exception:
        # Fallback to general SQL types
        col_type = type(column.type).__name__.upper()
        if 'STRING' in col_type or 'VARCHAR' in col_type:
            length = getattr(column.type, 'length', 255) or 255
            return f"VARCHAR({length})"
        if 'INTEGER' in col_type:
            return "INTEGER"
        if 'BOOLEAN' in col_type:
            return "BOOLEAN"
        if 'DATETIME' in col_type or 'TIMESTAMP' in col_type:
            return "TIMESTAMP"
        if 'FLOAT' in col_type or 'NUMERIC' in col_type:
            return "FLOAT"
        if 'TEXT' in col_type:
            return "TEXT"
        return "TEXT"


def run_safe_schema_migrations(app=None):
    """
    Safely and idempotently inspect the connected database (PostgreSQL/Supabase or SQLite)
    and ensure all model tables and columns exist without dropping or losing any data.

    Specifically addresses:
    1. Adding missing `employee_id` to `users` table.
    2. Creating the unique index for `employee_id`.
    3. Safely backfilling existing users with NULL `employee_id`:
       - Admin users -> 'admin'
       - Student users -> student.student_uid
       - Mentor users -> 'AM-MTR-001'
    4. Automatically detecting and adding any other model columns missing from existing tables.
    """
    logger.info("Starting safe database schema inspection and migration...")
    engine = db.engine
    dialect_name = engine.dialect.name
    is_postgres = (dialect_name == 'postgresql')
    is_sqlite = (dialect_name == 'sqlite')

    # Step 0: Immediate raw DDL execution on PostgreSQL for guaranteed users.employee_id column and expanded column types
    if is_postgres:
        try:
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("ALTER TABLE IF EXISTS public.users ADD COLUMN IF NOT EXISTS employee_id VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS employee_id VARCHAR(100);"))
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_employee_id ON users (employee_id) WHERE employee_id IS NOT NULL;"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.users ALTER COLUMN name DROP NOT NULL;"))
                    conn.execute(text("ALTER TABLE IF EXISTS users ALTER COLUMN name DROP NOT NULL;"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.users ADD COLUMN IF NOT EXISTS full_name VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS full_name VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.users ADD COLUMN IF NOT EXISTS name VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS name VARCHAR(100);"))
                    conn.execute(text("UPDATE public.users SET full_name = name WHERE full_name IS NULL AND name IS NOT NULL;"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;"))
                    conn.execute(text("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP;"))
                    conn.execute(text("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP;"))
                    conn.execute(text("ALTER TABLE IF EXISTS applications ALTER COLUMN student_id DROP NOT NULL;"))
                    conn.execute(text("ALTER TABLE IF EXISTS applications ALTER COLUMN plan_id DROP NOT NULL;"))

                    # Safe non-destructive column expansion for students table (avoids StringDataRightTruncation)
                    conn.execute(text("ALTER TABLE IF EXISTS public.students ALTER COLUMN student_uid TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS students ALTER COLUMN student_uid TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.students ALTER COLUMN gender TYPE VARCHAR(30);"))
                    conn.execute(text("ALTER TABLE IF EXISTS students ALTER COLUMN gender TYPE VARCHAR(30);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.students ALTER COLUMN roll_number TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS students ALTER COLUMN roll_number TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.students ALTER COLUMN degree TYPE VARCHAR(150);"))
                    conn.execute(text("ALTER TABLE IF EXISTS students ALTER COLUMN degree TYPE VARCHAR(150);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.students ALTER COLUMN current_year TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS students ALTER COLUMN current_year TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.students ALTER COLUMN graduation_year TYPE VARCHAR(10);"))
                    conn.execute(text("ALTER TABLE IF EXISTS students ALTER COLUMN graduation_year TYPE VARCHAR(10);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.students ALTER COLUMN aadhaar_masked TYPE VARCHAR(30);"))
                    conn.execute(text("ALTER TABLE IF EXISTS students ALTER COLUMN aadhaar_masked TYPE VARCHAR(30);"))

                    # Safe non-destructive column expansion for applications table
                    conn.execute(text("ALTER TABLE IF EXISTS public.applications ALTER COLUMN candidate_gender TYPE VARCHAR(30);"))
                    conn.execute(text("ALTER TABLE IF EXISTS applications ALTER COLUMN candidate_gender TYPE VARCHAR(30);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.applications ALTER COLUMN course TYPE VARCHAR(150);"))
                    conn.execute(text("ALTER TABLE IF EXISTS applications ALTER COLUMN course TYPE VARCHAR(150);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.applications ALTER COLUMN year_of_study TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS applications ALTER COLUMN year_of_study TYPE VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.applications ALTER COLUMN aadhaar_masked TYPE VARCHAR(30);"))
                    conn.execute(text("ALTER TABLE IF EXISTS applications ALTER COLUMN aadhaar_masked TYPE VARCHAR(30);"))

                    # Safe synchronization and non-destructive DDL for payments table (Cashfree & order_id compatibility)
                    conn.execute(text("ALTER TABLE IF EXISTS public.payments ADD COLUMN IF NOT EXISTS cashfree_order_id VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS cashfree_order_id VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.payments ADD COLUMN IF NOT EXISTS order_id VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS order_id VARCHAR(100);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.payments ALTER COLUMN student_id DROP NOT NULL;"))
                    conn.execute(text("ALTER TABLE IF EXISTS payments ALTER COLUMN student_id DROP NOT NULL;"))
                    conn.execute(text("UPDATE public.payments SET cashfree_order_id = order_id WHERE cashfree_order_id IS NULL AND order_id IS NOT NULL;"))
                    conn.execute(text("UPDATE payments SET cashfree_order_id = order_id WHERE cashfree_order_id IS NULL AND order_id IS NOT NULL;"))
                    conn.execute(text("UPDATE public.payments SET order_id = cashfree_order_id WHERE order_id IS NULL AND cashfree_order_id IS NOT NULL;"))
                    conn.execute(text("UPDATE payments SET order_id = cashfree_order_id WHERE order_id IS NULL AND cashfree_order_id IS NOT NULL;"))

                    # Safe synchronization and non-destructive DDL for payments status & payment_status compatibility
                    conn.execute(text("ALTER TABLE IF EXISTS public.payments ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.payments ADD COLUMN IF NOT EXISTS status VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS status VARCHAR(50);"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.payments ADD COLUMN IF NOT EXISTS gateway VARCHAR(50) DEFAULT 'cashfree';"))
                    conn.execute(text("ALTER TABLE IF EXISTS payments ADD COLUMN IF NOT EXISTS gateway VARCHAR(50) DEFAULT 'cashfree';"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.payments ALTER COLUMN payment_status SET DEFAULT 'paid';"))
                    conn.execute(text("ALTER TABLE IF EXISTS payments ALTER COLUMN payment_status SET DEFAULT 'paid';"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.payments ALTER COLUMN gateway SET DEFAULT 'cashfree';"))
                    conn.execute(text("ALTER TABLE IF EXISTS payments ALTER COLUMN gateway SET DEFAULT 'cashfree';"))
                    conn.execute(text("ALTER TABLE IF EXISTS public.payments ALTER COLUMN status SET DEFAULT 'paid';"))
                    conn.execute(text("ALTER TABLE IF EXISTS payments ALTER COLUMN status SET DEFAULT 'paid';"))
                    conn.execute(text("UPDATE public.payments SET payment_status = CASE WHEN status IN ('SUCCESSFUL', 'SUCCESS', 'COMPLETED', 'paid') THEN 'paid' ELSE status END WHERE payment_status IS NULL AND status IS NOT NULL;"))
                    conn.execute(text("UPDATE payments SET payment_status = CASE WHEN status IN ('SUCCESSFUL', 'SUCCESS', 'COMPLETED', 'paid') THEN 'paid' ELSE status END WHERE payment_status IS NULL AND status IS NOT NULL;"))
                    conn.execute(text("UPDATE public.payments SET status = payment_status WHERE status IS NULL AND payment_status IS NOT NULL;"))
                    conn.execute(text("UPDATE payments SET status = payment_status WHERE status IS NULL AND payment_status IS NOT NULL;"))
                    conn.execute(text("UPDATE public.payments SET gateway = 'cashfree' WHERE gateway IS NULL;"))
                    conn.execute(text("UPDATE payments SET gateway = 'cashfree' WHERE gateway IS NULL;"))
            logger.info("Immediate PostgreSQL DDL for users, students, applications, and payments executed successfully.")
        except Exception as e:
            logger.warning(f"Immediate PostgreSQL DDL notice: {e}")

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    # Step 1: Ensure any missing tables from metadata are created first
    db.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    # Step 2: Specific migration for users.employee_id
    if 'users' in existing_tables:
        existing_user_cols = {c['name'] for c in inspector.get_columns('users')}
        if 'employee_id' not in existing_user_cols:
            logger.info("Migrating table 'users': adding missing column 'employee_id'...")
            with engine.connect() as conn:
                with conn.begin():
                    if is_postgres:
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_id VARCHAR(100);"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN employee_id VARCHAR(100);"))
            logger.info("Column 'users.employee_id' successfully added.")

        # Ensure unique index exists on users.employee_id
        try:
            with engine.connect() as conn:
                with conn.begin():
                    if is_postgres:
                        # Partial unique index allows existing multiple NULLs without collision
                        conn.execute(text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_employee_id ON users (employee_id) WHERE employee_id IS NOT NULL;"
                        ))
                    elif is_sqlite:
                        conn.execute(text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_employee_id ON users (employee_id);"
                        ))
            logger.info("Index 'ix_users_employee_id' verified.")
        except Exception as e:
            logger.warning(f"Note on index 'ix_users_employee_id': {e}")

        # Step 3: Backfill existing users with NULL employee_id safely and deterministically
        _backfill_existing_users(engine, is_postgres)

    # Step 3b: Ensure applications table allows nullable student_id and plan_id for career applicant records
    if 'applications' in existing_tables:
        try:
            with engine.connect() as conn:
                with conn.begin():
                    if is_postgres:
                        conn.execute(text("ALTER TABLE applications ALTER COLUMN student_id DROP NOT NULL;"))
                        conn.execute(text("ALTER TABLE applications ALTER COLUMN plan_id DROP NOT NULL;"))
                    elif is_sqlite:
                        cols_info = conn.execute(text("PRAGMA table_info(applications)")).fetchall()
                        st_info = [col for col in cols_info if col[1] == 'student_id']
                        if st_info and st_info[0][3] == 1:
                            conn.execute(text("PRAGMA foreign_keys = OFF;"))
                            col_names = [col[1] for col in cols_info]
                            cols_csv = ", ".join([f'"{c}"' for c in col_names])
                            conn.execute(text("ALTER TABLE applications RENAME TO applications_old;"))
                            sql = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='applications_old'")).fetchone()[0]
                            sql_new = sql.replace("applications_old", "applications")
                            sql_new = sql_new.replace("student_id INTEGER NOT NULL", "student_id INTEGER")
                            sql_new = sql_new.replace("plan_id INTEGER NOT NULL", "plan_id INTEGER")
                            conn.execute(text(sql_new))
                            conn.execute(text(f"INSERT INTO applications ({cols_csv}) SELECT {cols_csv} FROM applications_old;"))
                            conn.execute(text("DROP TABLE applications_old;"))
                            conn.execute(text("PRAGMA foreign_keys = ON;"))
        except Exception as e:
            logger.debug(f"Applications nullability sync: {e}")

    # Step 3c: Ensure payments table synchronizes cashfree_order_id/order_id and payment_status/status
    if 'payments' in existing_tables:
        try:
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("UPDATE payments SET cashfree_order_id = order_id WHERE cashfree_order_id IS NULL AND order_id IS NOT NULL;"))
                    conn.execute(text("UPDATE payments SET order_id = cashfree_order_id WHERE order_id IS NULL AND cashfree_order_id IS NOT NULL;"))
                    existing_payment_cols = {c['name'] for c in inspector.get_columns('payments')}
                    if 'payment_status' in existing_payment_cols and 'status' in existing_payment_cols:
                        conn.execute(text("UPDATE payments SET payment_status = CASE WHEN status IN ('SUCCESSFUL', 'SUCCESS', 'COMPLETED', 'paid') THEN 'paid' ELSE status END WHERE payment_status IS NULL AND status IS NOT NULL;"))
                        conn.execute(text("UPDATE payments SET status = payment_status WHERE status IS NULL AND payment_status IS NOT NULL;"))
                    if 'gateway' in existing_payment_cols:
                        conn.execute(text("UPDATE payments SET gateway = 'cashfree' WHERE gateway IS NULL;"))
        except Exception as e:
            logger.debug(f"Payments order_id and status synchronization: {e}")

    # Step 4: Comprehensive Column Sync across all other registered models
    # Prevents any subsequent UndefinedColumn errors on other tables
    for table in db.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue

        try:
            current_cols = {c['name'] for c in inspector.get_columns(table.name)}
        except Exception as e:
            logger.warning(f"Could not inspect columns for table '{table.name}': {e}")
            continue

        for column in table.columns:
            if column.name not in current_cols:
                col_type_sql = get_column_type_sql(column, engine.dialect)
                logger.info(f"Adding missing column '{table.name}.{column.name}' ({col_type_sql})...")
                try:
                    with engine.connect() as conn:
                        with conn.begin():
                            if is_postgres:
                                alter_sql = f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS "{column.name}" {col_type_sql};'
                            else:
                                alter_sql = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type_sql};'
                            conn.execute(text(alter_sql))
                    logger.info(f"Successfully added column '{table.name}.{column.name}'.")
                except Exception as ex:
                    # Ignore if column already exists (e.g. race condition or dialect variation)
                    if "already exists" in str(ex).lower() or "duplicate column" in str(ex).lower():
                        logger.debug(f"Column '{table.name}.{column.name}' already exists.")
                    else:
                        logger.error(f"Failed to add column '{table.name}.{column.name}': {ex}")

        # Step 4b: Check for existing VARCHAR column length expansion on PostgreSQL
        if is_postgres:
            try:
                table_cols_info = inspector.get_columns(table.name)
                for col_info in table_cols_info:
                    c_name = col_info['name']
                    c_type = col_info.get('type')
                    c_len = getattr(c_type, 'length', None)
                    if c_len:
                        model_col = table.columns.get(c_name)
                        if model_col is not None:
                            m_len = getattr(model_col.type, 'length', None)
                            if m_len and m_len > c_len:
                                logger.info(f"Expanding column '{table.name}.{c_name}' from VARCHAR({c_len}) to VARCHAR({m_len})...")
                                try:
                                    with engine.connect() as conn:
                                        with conn.begin():
                                            conn.execute(text(f'ALTER TABLE "{table.name}" ALTER COLUMN "{c_name}" TYPE VARCHAR({m_len});'))
                                    logger.info(f"Successfully expanded column '{table.name}.{c_name}' to VARCHAR({m_len}).")
                                except Exception as ex:
                                    logger.warning(f"Notice on expanding column '{table.name}.{c_name}': {ex}")
            except Exception as e:
                logger.debug(f"Column length sync check for '{table.name}': {e}")

    logger.info("Database schema inspection and migration completed successfully.")


def _backfill_existing_users(engine, is_postgres):
    """
    Deterministically populate NULL employee_id values for existing users:
    - Default/super-admin users -> 'admin'
    - Student users with associated student profile -> student.student_uid
    - Known mentor accounts -> 'AM-MTR-001'
    """
    try:
        # 1. Backfill Super Admin / Admin accounts
        with engine.connect() as conn:
            with conn.begin():
                # Check if an admin with employee_id='admin' already exists
                has_admin = conn.execute(
                    text("SELECT id FROM users WHERE lower(employee_id) = 'admin' LIMIT 1")
                ).fetchone()

                if not has_admin:
                    # Associate with admin@antimatrix.tech or admin@antimatrix.com or first super_admin
                    admin_row = conn.execute(
                        text("""
                            SELECT id FROM users 
                            WHERE lower(email) IN ('admin@antimatrix.tech', 'admin@antimatrix.com')
                               OR role = 'super_admin'
                            ORDER BY id ASC LIMIT 1
                        """)
                    ).fetchone()

                    if admin_row:
                        conn.execute(
                            text("UPDATE users SET employee_id = 'admin' WHERE id = :uid"),
                            {'uid': admin_row[0]}
                        )
                        logger.info(f"Associated existing admin user ID={admin_row[0]} with employee_id='admin'.")

                # Check mentor account
                has_mentor = conn.execute(
                    text("SELECT id FROM users WHERE lower(employee_id) = 'am-mtr-001' LIMIT 1")
                ).fetchone()
                if not has_mentor:
                    mentor_row = conn.execute(
                        text("SELECT id FROM users WHERE lower(email) = 'mentor@antimatrix.com' LIMIT 1")
                    ).fetchone()
                    if mentor_row:
                        conn.execute(
                            text("UPDATE users SET employee_id = 'AM-MTR-001' WHERE id = :uid"),
                            {'uid': mentor_row[0]}
                        )
                        logger.info(f"Associated mentor user ID={mentor_row[0]} with employee_id='AM-MTR-001'.")

                # 2. Backfill Student Users from students.student_uid
                # If a user is linked to a student record and employee_id is NULL, assign student_uid
                conn.execute(text("""
                    UPDATE users
                    SET employee_id = (
                        SELECT students.student_uid
                        FROM students
                        WHERE students.user_id = users.id
                        LIMIT 1
                    )
                    WHERE users.employee_id IS NULL
                      AND EXISTS (
                          SELECT 1 FROM students WHERE students.user_id = users.id
                      );
                """))
                logger.info("Backfilled student employee_ids from students.student_uid where applicable.")

    except Exception as e:
        logger.error(f"Error during existing user backfill: {e}")
