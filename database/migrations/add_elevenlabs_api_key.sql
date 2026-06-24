-- Migration to add ElevenLabs API key support to User Settings
-- Run this query in your Supabase SQL Editor:

ALTER TABLE public.settings ADD COLUMN IF NOT EXISTS elevenlabs_api_key_encrypted TEXT;
