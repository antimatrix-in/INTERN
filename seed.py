from app import create_app
from app.extensions import db
from app.db_migration import run_safe_schema_migrations
from app.seed import seed_initial_data

app = create_app()

def seed_database():
    with app.app_context():
        # Ensure tables and columns exist safely
        run_safe_schema_migrations(app)
        # Seed data idempotently
        seed_initial_data()
        print("[OK] Anti Matrix Database initialized, migrated, and seeded successfully.")

if __name__ == '__main__':
    seed_database()
