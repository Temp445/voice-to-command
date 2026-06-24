-- Migration to add Deepgram API key support to User Settings
-- Run this query in your Supabase SQL Editor:

ALTER TABLE public.settings ADD COLUMN IF NOT EXISTS deepgram_api_key_encrypted TEXT;
