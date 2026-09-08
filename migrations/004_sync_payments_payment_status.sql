-- ==============================================================================
-- ANTI MATRIX INTERNSHIP PORTAL — SUPABASE POSTGRESQL SCHEMA MIGRATION
-- File: 004_sync_payments_payment_status.sql
-- Description: Safely and idempotently ensures `payments` table has both `payment_status`
--              and `status` columns, sets safe default 'SUCCESSFUL', and synchronizes
--              existing values bi-directionally between both columns.
-- 
-- SAFE TO RUN IN SUPABASE SQL EDITOR:
-- - Zero data loss: Uses ADD COLUMN IF NOT EXISTS and non-destructive backfill
-- - Never drops tables, never recreates tables, never drops constraints
-- - Never deletes or overwrites existing production payment records
-- - Fully idempotent (safe to run repeatedly)
-- ==============================================================================

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'payments') THEN
        -- 1. Ensure columns exist
        ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50);
        ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS status VARCHAR(50);
        ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS gateway VARCHAR(50) DEFAULT 'cashfree';
        
        -- 2. Set safe canonical defaults for future raw inserts (preserves NOT NULL constraints)
        ALTER TABLE public.payments ALTER COLUMN payment_status SET DEFAULT 'paid';
        ALTER TABLE public.payments ALTER COLUMN gateway SET DEFAULT 'cashfree';
        ALTER TABLE public.payments ALTER COLUMN status SET DEFAULT 'paid';
        
        -- 3. Synchronize existing values bi-directionally without losing or altering valid data
        UPDATE public.payments 
        SET payment_status = CASE 
            WHEN status IN ('SUCCESSFUL', 'SUCCESS', 'COMPLETED', 'paid') THEN 'paid'
            ELSE status 
        END
        WHERE payment_status IS NULL AND status IS NOT NULL;

        UPDATE public.payments 
        SET status = payment_status 
        WHERE status IS NULL AND payment_status IS NOT NULL;

        UPDATE public.payments
        SET gateway = 'cashfree'
        WHERE gateway IS NULL;
    END IF;

    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'payments') THEN
        ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50);
        ALTER TABLE payments ADD COLUMN IF NOT EXISTS status VARCHAR(50);
        ALTER TABLE payments ADD COLUMN IF NOT EXISTS gateway VARCHAR(50) DEFAULT 'cashfree';
        
        ALTER TABLE payments ALTER COLUMN payment_status SET DEFAULT 'paid';
        ALTER TABLE payments ALTER COLUMN gateway SET DEFAULT 'cashfree';
        ALTER TABLE payments ALTER COLUMN status SET DEFAULT 'paid';
        
        UPDATE payments 
        SET payment_status = CASE 
            WHEN status IN ('SUCCESSFUL', 'SUCCESS', 'COMPLETED', 'paid') THEN 'paid'
            ELSE status 
        END
        WHERE payment_status IS NULL AND status IS NOT NULL;

        UPDATE payments 
        SET status = payment_status 
        WHERE status IS NULL AND payment_status IS NOT NULL;

        UPDATE payments
        SET gateway = 'cashfree'
        WHERE gateway IS NULL;
    END IF;
END $$;

COMMIT;

-- Verification Queries (Can be run in Supabase SQL Editor):
-- SELECT id, transaction_id, order_id, cashfree_order_id, status, payment_status FROM payments LIMIT 10;
