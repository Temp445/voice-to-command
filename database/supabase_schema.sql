-- ============================================================
-- ACE Voice Controller — Supabase PostgreSQL Schema
-- Run this in your Supabase SQL editor to create all tables
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Users ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT UNIQUE NOT NULL,
    display_name    TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    supabase_uid    UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Settings ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.settings (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    wake_word               TEXT DEFAULT 'alexa',
    whisper_model           TEXT DEFAULT 'base',
    tts_provider            TEXT DEFAULT 'gtts',
    gtts_api_key_encrypted  TEXT,
    piper_voice             TEXT DEFAULT 'en_US-lessac-medium',
    theme                   TEXT DEFAULT 'dark',
    sidebar_collapsed       BOOLEAN DEFAULT FALSE,
    browser_type            TEXT DEFAULT 'chromium',
    startup_on_boot         BOOLEAN DEFAULT TRUE,
    minimize_to_tray        BOOLEAN DEFAULT TRUE,
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- ─── Command History ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.command_history (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES public.users(id) ON DELETE CASCADE,
    raw_text        TEXT NOT NULL,
    intent          TEXT,
    parameters      JSONB DEFAULT '{}',
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','running','success','failed')),
    result          TEXT,
    source          TEXT DEFAULT 'voice' CHECK (source IN ('voice','text')),
    duration_ms     INTEGER,
    executed_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Workflows ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.workflows (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    trigger_phrase  TEXT,
    steps           JSONB DEFAULT '[]',
    is_active       BOOLEAN DEFAULT TRUE,
    run_count       INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Automation Logs ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.automation_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES public.users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    target      TEXT,
    status      TEXT DEFAULT 'success',
    details     TEXT,
    level       TEXT DEFAULT 'info' CHECK (level IN ('debug','info','warning','error')),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Shortcuts ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.shortcuts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    trigger_phrase  TEXT NOT NULL,
    action_type     TEXT NOT NULL,
    action_payload  JSONB DEFAULT '{}',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Voice Profiles ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.voice_profiles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    tts_provider    TEXT DEFAULT 'piper',
    voice_id        TEXT NOT NULL,
    speed           FLOAT DEFAULT 1.0,
    pitch           FLOAT DEFAULT 1.0,
    is_default      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Row-Level Security ──────────────────────────────────────
ALTER TABLE public.users            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.settings         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.command_history  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflows        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.automation_logs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shortcuts        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voice_profiles   ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY "Users own data" ON public.settings
    FOR ALL USING (auth.uid() = (SELECT supabase_uid FROM public.users WHERE id = user_id));

CREATE POLICY "Users own commands" ON public.command_history
    FOR ALL USING (auth.uid() = (SELECT supabase_uid FROM public.users WHERE id = user_id));

CREATE POLICY "Users own workflows" ON public.workflows
    FOR ALL USING (auth.uid() = (SELECT supabase_uid FROM public.users WHERE id = user_id));

CREATE POLICY "Users own logs" ON public.automation_logs
    FOR ALL USING (auth.uid() = (SELECT supabase_uid FROM public.users WHERE id = user_id));

CREATE POLICY "Users own shortcuts" ON public.shortcuts
    FOR ALL USING (auth.uid() = (SELECT supabase_uid FROM public.users WHERE id = user_id));

CREATE POLICY "Users own voice profiles" ON public.voice_profiles
    FOR ALL USING (auth.uid() = (SELECT supabase_uid FROM public.users WHERE id = user_id));

-- ─── Indexes ─────────────────────────────────────────────────
CREATE INDEX idx_command_history_user   ON public.command_history(user_id, executed_at DESC);
CREATE INDEX idx_automation_logs_user   ON public.automation_logs(user_id, created_at DESC);
CREATE INDEX idx_workflows_user         ON public.workflows(user_id);
CREATE INDEX idx_shortcuts_user         ON public.shortcuts(user_id);

-- ─── Updated_at trigger ──────────────────────────────────────
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_settings_updated_at
    BEFORE UPDATE ON public.settings
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER trg_workflows_updated_at
    BEFORE UPDATE ON public.workflows
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
