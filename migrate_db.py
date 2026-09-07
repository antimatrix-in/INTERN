#!/usr/bin/env python
"""
Standalone Database Migration & Schema Sync CLI for Anti Matrix Portal.
Executes idempotent schema synchronization to ensure all columns (including users.employee_id)
and indexes exist in the Supabase PostgreSQL or local database without any data loss.
"""
import sys
import logging
from app import create_app
from app.db_migration import run_safe_schema_migrations

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def main():
    print("=" * 60)
    print("ANTI MATRIX — Safe Database Schema Migration")
    print("=" * 60)
    app = create_app()
    with app.app_context():
        try:
            run_safe_schema_migrations(app)
            print("[SUCCESS] All tables, columns, and indexes verified/migrated safely.")
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Migration failed: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    main()
