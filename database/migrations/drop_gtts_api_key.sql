-- Migration: Remove gtts_api_key_encrypted from settings
-- Run this in your Supabase SQL editor

ALTER TABLE public.settings
    DROP COLUMN IF EXISTS gtts_api_key_encrypted;
