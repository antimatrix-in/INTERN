import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'anti-matrix-super-secret-key-2026-production')
    
    # Handle database URL for Supabase / PostgreSQL / SQLite
    raw_db_url = os.environ.get('DATABASE_URL')
    if raw_db_url:
        # Standardize PostgreSQL dialect prefix for SQLAlchemy 2.x / psycopg2
        if raw_db_url.startswith('postgres://'):
            raw_db_url = raw_db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = raw_db_url
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
        }
    else:
        instance_dir = BASE_DIR / 'instance'
        os.makedirs(instance_dir, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{instance_dir / 'antimatrix.db'}"
        SQLALCHEMY_ENGINE_OPTIONS = {}
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Supabase API Integration (Optional REST / Client Integration)
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
    
    # Upload storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(BASE_DIR / 'app' / 'static' / 'uploads'))
    VIDEO_UPLOAD_FOLDER = os.environ.get('VIDEO_UPLOAD_FOLDER', str(BASE_DIR / 'instance' / 'uploads' / 'videos'))
    MAX_VIDEO_SIZE_MB = int(os.environ.get('MAX_VIDEO_SIZE_MB', 100))
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm'}
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 120 * 1024 * 1024)) # 120 MB
    
    # Base URL
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5050')

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 7 # 7 days
