-- ============================================================
-- Migration: Add crm_sites column to settings table
-- Description: Stores multiple CRM site entries (JSON array) so
--              each site has its own URL + trigger keywords.
--
-- Format: '[{"url":"https://...","keywords":"open crm, ..."}]'
-- ============================================================

ALTER TABLE public.settings
    ADD COLUMN IF NOT EXISTS crm_sites TEXT DEFAULT '[{"url":"https://crm.acesoftcloud.in/","keywords":"open my crm, open crm, open ace crm"}]';

-- Backfill any existing rows that have NULL
UPDATE public.settings
    SET crm_sites = '[{"url":"' || COALESCE(crm_url, 'https://crm.acesoftcloud.in/') || '","keywords":"' || COALESCE(crm_keywords, 'open my crm, open crm, open ace crm') || '"}]'
    WHERE crm_sites IS NULL;
