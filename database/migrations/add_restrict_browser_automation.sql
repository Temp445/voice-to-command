-- ============================================================
-- Migration: Add restrict_browser_automation column to settings table
-- Description: Stores whether browser automation should be restricted
--              to configured Website Shortcuts.
-- ============================================================

ALTER TABLE public.settings
    ADD COLUMN IF NOT EXISTS restrict_browser_automation BOOLEAN DEFAULT FALSE;
