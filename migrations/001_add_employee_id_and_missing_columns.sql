-- ==============================================================================
-- ANTI MATRIX INTERNSHIP PORTAL — SUPABASE POSTGRESQL SCHEMA MIGRATION
-- File: 001_add_employee_id_and_missing_columns.sql
-- Description: Safely adds employee_id to users table, creates index, backfills
--              existing users, and ensures all table columns match SQLAlchemy models.
-- 
-- SAFE TO RUN IN SUPABASE SQL EDITOR:
-- - Zero data loss: Uses ADD COLUMN IF NOT EXISTS
-- - Never drops tables or truncates rows
-- - Fully idempotent (safe to run repeatedly)
-- ==============================================================================

BEGIN;

-- 1. Migrate `users` table
ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_id VARCHAR(100);

-- Create partial unique index (prevents collisions between active IDs while safely allowing multiple NULLs)
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_employee_id ON users (employee_id) WHERE employee_id IS NOT NULL;

-- Backfill Administrator account: associate with 'admin' if not already assigned
UPDATE users 
SET employee_id = 'admin'
WHERE employee_id IS NULL
  AND (lower(email) IN ('admin@antimatrix.tech', 'admin@antimatrix.com') OR role = 'super_admin')
  AND NOT EXISTS (SELECT 1 FROM users WHERE lower(employee_id) = 'admin');

-- Backfill Mentor account if present
UPDATE users 
SET employee_id = 'AM-MTR-001'
WHERE employee_id IS NULL
  AND lower(email) = 'mentor@antimatrix.com'
  AND NOT EXISTS (SELECT 1 FROM users WHERE lower(employee_id) = 'am-mtr-001');

-- Backfill Student accounts from existing student_uid
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


-- 2. Ensure `applications` table has career & employee conversion columns and nullable student_id / plan_id
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'applications') THEN
        ALTER TABLE applications ALTER COLUMN student_id DROP NOT NULL;
        ALTER TABLE applications ALTER COLUMN plan_id DROP NOT NULL;
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS is_converted_to_employee BOOLEAN DEFAULT FALSE;
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS converted_employee_id VARCHAR(50);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS candidate_name VARCHAR(150);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS candidate_email VARCHAR(150);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS candidate_phone VARCHAR(30);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS candidate_dob VARCHAR(20);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS candidate_gender VARCHAR(20);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS college_name VARCHAR(200);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS department_name VARCHAR(150);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS course VARCHAR(100);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS year_of_study VARCHAR(20);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS roll_number VARCHAR(50);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS applied_role VARCHAR(100);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS city VARCHAR(100);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS state VARCHAR(100);
        ALTER TABLE applications ADD COLUMN IF NOT EXISTS aadhaar_masked VARCHAR(20);
    END IF;
END $$;


-- 3. Ensure `projects` table has Problem ID, task plan, and duration columns
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'projects') THEN
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS problem_statement TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS expected_outcome TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS objectives_json TEXT DEFAULT '[]';
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS tech_stack_json TEXT DEFAULT '[]';
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS requirements_json TEXT DEFAULT '[]';
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS instructions_md TEXT DEFAULT '';
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS reference_links_json TEXT DEFAULT '[]';
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_type VARCHAR(100);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS deployment VARCHAR(100);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS cloud_required BOOLEAN DEFAULT FALSE;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS paid_api_required BOOLEAN DEFAULT FALSE;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS github_required BOOLEAN DEFAULT TRUE;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS modules_json TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS restrictions_json TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS final_deliverable_json TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS evaluation_json TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS source_json TEXT;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS source_json_name VARCHAR(255);
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS duration_weeks INTEGER DEFAULT 4;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS duration_months INTEGER DEFAULT 1;
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS difficulty VARCHAR(50) DEFAULT 'Intermediate';
    END IF;
END $$;


-- 4. Ensure `project_weeks` table has phase breakdown and roadmap fields
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'project_weeks') THEN
        ALTER TABLE project_weeks ADD COLUMN IF NOT EXISTS phase_number INTEGER;
        ALTER TABLE project_weeks ADD COLUMN IF NOT EXISTS phase_title VARCHAR(200);
        ALTER TABLE project_weeks ADD COLUMN IF NOT EXISTS weeks_label VARCHAR(50);
        ALTER TABLE project_weeks ADD COLUMN IF NOT EXISTS completion_percentage VARCHAR(20);
        ALTER TABLE project_weeks ADD COLUMN IF NOT EXISTS goal TEXT;
        ALTER TABLE project_weeks ADD COLUMN IF NOT EXISTS expected_features_json TEXT;
        ALTER TABLE project_weeks ADD COLUMN IF NOT EXISTS demo_output_json TEXT;
        ALTER TABLE project_weeks ADD COLUMN IF NOT EXISTS github_requirement TEXT;
        ALTER TABLE project_weeks ADD COLUMN IF NOT EXISTS completion_condition TEXT;
    END IF;
END $$;


-- 5. Ensure `project_tasks` table has extended metadata
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'project_tasks') THEN
        ALTER TABLE project_tasks ADD COLUMN IF NOT EXISTS instructions TEXT;
        ALTER TABLE project_tasks ADD COLUMN IF NOT EXISTS expected_output TEXT;
        ALTER TABLE project_tasks ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'Medium';
        ALTER TABLE project_tasks ADD COLUMN IF NOT EXISTS estimated_hours FLOAT;
        ALTER TABLE project_tasks ADD COLUMN IF NOT EXISTS order_num INTEGER DEFAULT 1;
    END IF;
END $$;


-- 6. Ensure `evaluations` table has score breakdown columns
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'evaluations') THEN
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS action VARCHAR(50);
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS remarks TEXT;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS technical_score INTEGER DEFAULT 0;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS functionality_score INTEGER DEFAULT 0;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS ui_ux_score INTEGER DEFAULT 0;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS documentation_score INTEGER DEFAULT 0;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS demo_score INTEGER DEFAULT 0;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS originality_score INTEGER DEFAULT 0;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS presentation_score INTEGER DEFAULT 0;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS total_score INTEGER DEFAULT 0;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS result VARCHAR(30);
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS feedback TEXT;
        ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS revision_notes TEXT;
    END IF;
END $$;

COMMIT;

-- Verification Queries (Can be run to verify schema):
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'employee_id';
-- SELECT id, email, role, employee_id FROM users WHERE employee_id = 'admin';
