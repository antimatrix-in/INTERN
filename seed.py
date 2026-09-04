from app import create_app
from app.extensions import db
from app.seed import seed_initial_data

app = create_app()

def seed_database():
    with app.app_context():
        # Ensure tables exist
        db.create_all()
        # Seed data idempotently
        seed_initial_data()
        print("[OK] Anti Matrix Database initialized and seeded successfully.")

if __name__ == '__main__':
    seed_database()
