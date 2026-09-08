-- ==============================================================================
-- ANTI MATRIX INTERNSHIP PORTAL — SUPABASE POSTGRESQL SCHEMA MIGRATION
-- File: 002_expand_student_and_application_columns.sql
-- Description: Safely and non-destructively expands column lengths in `students`
--              and `applications` tables to prevent StringDataRightTruncation
--              errors when inserting student degrees, year of study, and IDs.
-- 
-- SAFE TO RUN IN SUPABASE SQL EDITOR:
-- - Zero data loss: Only alters existing column types to larger VARCHAR sizes
-- - Never drops tables, never recreates tables, never truncates or deletes rows
-- - Fully idempotent (safe to run repeatedly)
-- ==============================================================================

BEGIN;

-- 1. Safely expand column lengths in `students` table
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'students') THEN
        -- student_uid: VARCHAR(30) -> VARCHAR(50)
        ALTER TABLE public.students ALTER COLUMN student_uid TYPE VARCHAR(50);
        
        -- gender: VARCHAR(20) -> VARCHAR(30)
        ALTER TABLE public.students ALTER COLUMN gender TYPE VARCHAR(30);
        
        -- roll_number: ensure VARCHAR(50)
        ALTER TABLE public.students ALTER COLUMN roll_number TYPE VARCHAR(50);
        
        -- degree: VARCHAR(20) / VARCHAR(100) -> VARCHAR(150)
        -- Accommodates legitimate values like 'B.Tech / B.E (Information Technology)'
        ALTER TABLE public.students ALTER COLUMN degree TYPE VARCHAR(150);
        
        -- current_year: VARCHAR(20) -> VARCHAR(50)
        -- Accommodates legitimate values like '4th Year / Final Year'
        ALTER TABLE public.students ALTER COLUMN current_year TYPE VARCHAR(50);
        
        -- graduation_year: VARCHAR(10)
        ALTER TABLE public.students ALTER COLUMN graduation_year TYPE VARCHAR(10);
        
        -- aadhaar_masked: VARCHAR(20) -> VARCHAR(30)
        ALTER TABLE public.students ALTER COLUMN aadhaar_masked TYPE VARCHAR(30);
    END IF;

    -- Also check unqualified 'students' if schema resolution differs
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'students') THEN
        ALTER TABLE students ALTER COLUMN student_uid TYPE VARCHAR(50);
        ALTER TABLE students ALTER COLUMN gender TYPE VARCHAR(30);
        ALTER TABLE students ALTER COLUMN roll_number TYPE VARCHAR(50);
        ALTER TABLE students ALTER COLUMN degree TYPE VARCHAR(150);
        ALTER TABLE students ALTER COLUMN current_year TYPE VARCHAR(50);
        ALTER TABLE students ALTER COLUMN graduation_year TYPE VARCHAR(10);
        ALTER TABLE students ALTER COLUMN aadhaar_masked TYPE VARCHAR(30);
    END IF;
END $$;


-- 2. Safely expand candidate fields in `applications` table to match Student model
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'applications') THEN
        -- candidate_gender: VARCHAR(20) -> VARCHAR(30)
        ALTER TABLE public.applications ALTER COLUMN candidate_gender TYPE VARCHAR(30);
        
        -- course: VARCHAR(100) -> VARCHAR(150) (matches degree)
        ALTER TABLE public.applications ALTER COLUMN course TYPE VARCHAR(150);
        
        -- year_of_study: VARCHAR(20) -> VARCHAR(50) (matches current_year)
        ALTER TABLE public.applications ALTER COLUMN year_of_study TYPE VARCHAR(50);
        
        -- aadhaar_masked: VARCHAR(20) -> VARCHAR(30)
        ALTER TABLE public.applications ALTER COLUMN aadhaar_masked TYPE VARCHAR(30);
    END IF;

    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'applications') THEN
        ALTER TABLE applications ALTER COLUMN candidate_gender TYPE VARCHAR(30);
        ALTER TABLE applications ALTER COLUMN course TYPE VARCHAR(150);
        ALTER TABLE applications ALTER COLUMN year_of_study TYPE VARCHAR(50);
        ALTER TABLE applications ALTER COLUMN aadhaar_masked TYPE VARCHAR(30);
    END IF;
END $$;

COMMIT;

-- Verification Queries (Can be run in Supabase SQL Editor to verify lengths):
-- SELECT column_name, character_maximum_length, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'students' 
--   AND column_name IN ('student_uid', 'gender', 'roll_number', 'degree', 'current_year', 'graduation_year', 'aadhaar_masked');
