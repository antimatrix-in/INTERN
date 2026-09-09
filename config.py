import os
import urllib.parse
import socket
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


def normalize_database_url(raw_url: str) -> str:
    """
    Safely parses and normalizes database connection strings for SQLAlchemy & Supabase.
    - Normalizes 'postgres://' to 'postgresql://'.
    - Handles unencoded special characters in passwords (e.g. '@', ':', '#', '%', '+').
    - Handles Supabase IPv6 direct URLs by routing through IPv4 Supabase pooler if needed.
    - Prevents double-encoding.
    """
    if not raw_url:
        return raw_url
    url = raw_url.strip()
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if not url.startswith('postgresql://'):
        return url
    
    scheme, remainder = url.split('://', 1)
    if '@' in remainder:
        # Split on the LAST '@' to isolate host[:port]/database from user:password
        auth_part, host_part = remainder.rsplit('@', 1)
        if ':' in auth_part:
            username, password = auth_part.split(':', 1)
        else:
            username, password = auth_part, ''
        
        # Unquote first to avoid double-encoding pre-encoded components
        username = urllib.parse.unquote(username)
        password = urllib.parse.unquote(password)
        
        host = host_part
        port = 5432
        db_and_query = 'postgres'
        
        if '/' in host_part:
            host_and_port, db_and_query = host_part.split('/', 1)
        else:
            host_and_port = host_part
            
        if ':' in host_and_port:
            host, port_str = host_and_port.split(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 5432
        else:
            host = host_and_port

        # Supabase Direct IPv6 to Pooler IPv4 translation fallback:
        if host.startswith('db.') and host.endswith('.supabase.co'):
            project_ref = host[3:-len('.supabase.co')]
            resolves = False
            try:
                socket.getaddrinfo(host, port)
                resolves = True
            except Exception:
                resolves = False
            
            if not resolves:
                host = 'aws-0-ap-south-1.pooler.supabase.com'
                if not username.endswith(f'.{project_ref}'):
                    username = f"{username}.{project_ref}" if username else f"postgres.{project_ref}"

        # RFC 3986 percent-encode user and password
        encoded_username = urllib.parse.quote(username, safe='')
        encoded_password = urllib.parse.quote(password, safe='')
        
        url = f"{scheme}://{encoded_username}:{encoded_password}@{host}:{port}/{db_and_query}"
    return url


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'anti-matrix-super-secret-key-2026-production')
    
    # Handle database URL for Supabase / PostgreSQL / SQLite
    raw_db_url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DATABASE_URL')
    if raw_db_url:
        SQLALCHEMY_DATABASE_URI = normalize_database_url(raw_db_url)
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
    SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
    
    # Upload storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(BASE_DIR / 'app' / 'static' / 'uploads'))
    VIDEO_UPLOAD_FOLDER = os.environ.get('VIDEO_UPLOAD_FOLDER', str(BASE_DIR / 'instance' / 'uploads' / 'videos'))
    MAX_VIDEO_SIZE_MB = int(os.environ.get('MAX_VIDEO_SIZE_MB', 100))
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm'}
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 120 * 1024 * 1024)) # 120 MB
    
    # Base URL
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5050')

    # Security & Session Management
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN', None)
    # Enforce secure cookies in production/HTTPS on Render while allowing dev/testing
    _cookie_secure_env = os.environ.get('SESSION_COOKIE_SECURE')
    if _cookie_secure_env is not None:
        SESSION_COOKIE_SECURE = _cookie_secure_env.strip().lower() in ('1', 'true', 'yes')
    else:
        SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production' or not os.environ.get('FLASK_DEBUG', '1') == '1'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 7 # 7 days

