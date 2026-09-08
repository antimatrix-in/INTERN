-- ==============================================================================
-- ANTI MATRIX INTERNSHIP PORTAL — SUPABASE POSTGRESQL SCHEMA MIGRATION
-- File: 003_sync_payments_cashfree_order_id.sql
-- Description: Safely and idempotently ensures `payments` table has both `order_id`
--              and `cashfree_order_id`, synchronizes values between the two columns,
--              and ensures `student_id` is nullable for standalone career payments.
-- 
-- SAFE TO RUN IN SUPABASE SQL EDITOR:
-- - Zero data loss: Uses ADD COLUMN IF NOT EXISTS and non-destructive backfill
-- - Never drops tables, never recreates tables, never deletes payment records
-- - Fully idempotent (safe to run repeatedly)
-- ==============================================================================

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'payments') THEN
        -- 1. Ensure both columns exist
        ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS cashfree_order_id VARCHAR(100);
        ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS order_id VARCHAR(100);
        
        -- 2. Allow nullable student_id for payments made prior to student enrollment
        ALTER TABLE public.payments ALTER COLUMN student_id DROP NOT NULL;
        
        -- 3. Synchronize existing values bi-directionally without losing data
        UPDATE public.payments 
        SET cashfree_order_id = order_id 
        WHERE cashfree_order_id IS NULL AND order_id IS NOT NULL;

        UPDATE public.payments 
        SET order_id = cashfree_order_id 
        WHERE order_id IS NULL AND cashfree_order_id IS NOT NULL;
    END IF;

    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'payments') THEN
        ALTER TABLE payments ADD COLUMN IF NOT EXISTS cashfree_order_id VARCHAR(100);
        ALTER TABLE payments ADD COLUMN IF NOT EXISTS order_id VARCHAR(100);
        ALTER TABLE payments ALTER COLUMN student_id DROP NOT NULL;
        
        UPDATE payments 
        SET cashfree_order_id = order_id 
        WHERE cashfree_order_id IS NULL AND order_id IS NOT NULL;

        UPDATE payments 
        SET order_id = cashfree_order_id 
        WHERE order_id IS NULL AND cashfree_order_id IS NOT NULL;
    END IF;
END $$;

COMMIT;

-- Verification Queries (Can be run in Supabase SQL Editor):
-- SELECT id, transaction_id, order_id, cashfree_order_id, status FROM payments LIMIT 10;
