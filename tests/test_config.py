"""Shared test configuration for ANTI MATRIX portal test suites."""
from config import Config


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key-do-not-use-in-production'
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
