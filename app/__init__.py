import os
from flask import Flask
from config import Config
from app.extensions import db, login_manager, csrf

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'resumes'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'identity'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'college_ids'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'photos'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'generated_docs'), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register Blueprints
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.student.routes import student_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    # Safe database schema initialization & idempotent seeding
    with app.app_context():
        from app import models  # noqa: F401 (Ensure models are registered on db.metadata)
        db.create_all()
        from app.seed import seed_initial_data
        seed_initial_data()

    # Custom context processors & template filters
    @app.context_processor
    def inject_global_vars():
        from app.models import InternshipPlan
        plans = InternshipPlan.query.filter_by(is_active=True).order_by(InternshipPlan.duration_months.asc()).all()
        return {
            'company_name': 'ANTI MATRIX',
            'company_tagline': 'Enterprise Internship Management Portal',
            'support_email': 'internships@antimatrix.tech',
            'global_plans': plans
        }

    return app
