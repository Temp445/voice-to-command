-- ============================================================
-- Migration: Add scan_mode column to settings table
-- Description: Adds scan_mode ('auto' | 'manual') to control
--              whether app/file discovery runs automatically
--              on startup or only when manually triggered.
-- ============================================================

ALTER TABLE public.settings
    ADD COLUMN IF NOT EXISTS scan_mode TEXT DEFAULT 'auto';

-- Add a check constraint to enforce valid values
ALTER TABLE public.settings
    DROP CONSTRAINT IF EXISTS settings_scan_mode_check;

ALTER TABLE public.settings
    ADD CONSTRAINT settings_scan_mode_check
    CHECK (scan_mode IN ('auto', 'manual'));

-- Backfill any existing rows that might have NULL
UPDATE public.settings
    SET scan_mode = 'auto'
    WHERE scan_mode IS NULL;
