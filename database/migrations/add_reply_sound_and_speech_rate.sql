-- Add reply_sound and speech_rate columns to public.settings table
ALTER TABLE public.settings 
ADD COLUMN IF NOT EXISTS reply_sound BOOLEAN DEFAULT TRUE;

ALTER TABLE public.settings 
ADD COLUMN IF NOT EXISTS speech_rate DOUBLE PRECISION DEFAULT 1.0;
