-- Alter users table to add role
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user';

-- Alter settings table to add screen_settings_visible_to_users
ALTER TABLE public.settings ADD COLUMN IF NOT EXISTS screen_settings_visible_to_users BOOLEAN DEFAULT TRUE;

-- Create user_policies table
CREATE TABLE IF NOT EXISTS public.user_policies (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
    permissions JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.user_policies ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users read own policy" ON public.user_policies;
DROP POLICY IF EXISTS "Admins full control user policies" ON public.user_policies;

-- Create policies
CREATE POLICY "Users read own policy" ON public.user_policies
    FOR SELECT USING (auth.uid() = (SELECT supabase_uid FROM public.users WHERE id = user_id));

CREATE POLICY "Admins full control user policies" ON public.user_policies
    FOR ALL USING (
        (SELECT role FROM public.users WHERE supabase_uid = auth.uid()) = 'admin'
    );

-- Add update_at trigger
DROP TRIGGER IF EXISTS trg_user_policies_updated_at ON public.user_policies;
CREATE TRIGGER trg_user_policies_updated_at
    BEFORE UPDATE ON public.user_policies
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
