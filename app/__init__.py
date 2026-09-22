import os
from flask import Flask, request, jsonify, redirect, url_for, flash
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from app.extensions import db, login_manager, csrf

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Respect reverse proxy headers from Render (X-Forwarded-Proto, X-Forwarded-For, X-Forwarded-Host)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=1
    )

    # Ensure upload directories exist safely without blocking read-only environments (e.g. Vercel /var/task)
    is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    if not is_serverless:
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            for sub_dir in ('resumes', 'identity', 'college_ids', 'photos', 'generated_docs'):
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], sub_dir), exist_ok=True)
            if 'VIDEO_UPLOAD_FOLDER' in app.config:
                os.makedirs(app.config['VIDEO_UPLOAD_FOLDER'], exist_ok=True)
        except OSError:
            pass

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # API & Session Authentication Handlers
    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if (request.path.startswith('/admin/upload-tasks') or 
            request.is_json or 
            'application/json' in request.headers.get('Accept', '') or 
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
            return jsonify({
                'success': False,
                'valid': False,
                'errors': ['Your admin session has expired. Please sign in again.'],
                'error': 'Your admin session has expired. Please sign in again.'
            }), 401
        flash('Please log in to access your Anti Matrix portal.', 'warning')
        return redirect(url_for('auth.login', next=request.url))

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        reason = getattr(e, 'description', 'The CSRF token is missing or invalid.')
        if (request.path.startswith('/admin/upload-tasks') or 
            request.is_json or 
            'application/json' in request.headers.get('Accept', '') or 
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
            return jsonify({
                'success': False,
                'valid': False,
                'errors': [f'CSRF token validation failed: {reason}'],
                'error': f'CSRF token validation failed: {reason}'
            }), 400
        return f"<!doctype html><title>400 Bad Request</title><h1>Bad Request</h1><p>{reason}</p>", 400

    @app.errorhandler(500)
    def handle_500_error(e):
        if (request.path.startswith('/admin/upload-tasks') or 
            request.is_json or 
            'application/json' in request.headers.get('Accept', '') or 
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
            return jsonify({
                'success': False,
                'valid': False,
                'errors': ['Task plan validation failed due to a server error.'],
                'error': 'Task plan validation failed due to a server error.'
            }), 500
        return "<!doctype html><title>500 Internal Server Error</title><h1>Internal Server Error</h1>", 500

    # Register Blueprints
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.student.routes import student_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    # Register models & provide CLI commands for pre-deploy operations
    with app.app_context():
        from app import models  # noqa: F401 (Ensure models are registered on db.metadata)
        if os.environ.get('RUN_MIGRATIONS_ON_STARTUP', 'false').strip().lower() in ('1', 'true', 'yes'):
            from app.db_migration import run_safe_schema_migrations
            run_safe_schema_migrations(app)
        if os.environ.get('RUN_SEED_ON_STARTUP', 'false').strip().lower() in ('1', 'true', 'yes'):
            from app.seed import seed_initial_data
            seed_initial_data()

        # Safely maintain and reconcile primary administrator credentials on startup
        try:
            from app.seed import reconcile_primary_admin
            reconcile_primary_admin(app)
        except Exception:
            pass

    @app.cli.command('db-migrate')
    def cli_db_migrate():
        """Run safe schema migrations on demand."""
        from app.db_migration import run_safe_schema_migrations
        run_safe_schema_migrations(app)

    @app.cli.command('db-seed')
    def cli_db_seed():
        """Seed initial database roles and permissions on demand."""
        from app.seed import seed_initial_data
        seed_initial_data()

    # Custom context processors & template filters
    @app.context_processor
    def inject_global_vars():
        return {
            'company_name': 'ANTI MATRIX',
            'company_tagline': 'Enterprise Internship Management Portal',
            'support_email': 'internships@antimatrix.tech'
        }

    # Security & Cache Control headers for dynamic/authenticated responses
    @app.after_request
    def set_security_and_cache_headers(response):
        """
        Prevent browser bfcache and CDN edge proxies from caching dynamic/authenticated pages.
        Forces the browser to always revalidate with the server so that logging out or clicking
        Back strictly requires valid authentication.
        """
        if not request.path.startswith('/static'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    return app


def __getattr__(name):
    """
    Lazy module attribute resolution (PEP 562).
    Allows WSGI servers configured with `gunicorn app:app` to resolve
    the canonical application instance from `run.py` without creating
    duplicate Flask instances or side-effects during tests/imports.
    """
    if name == 'app':
        from run import app as _app
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
