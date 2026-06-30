-- ============================================================
-- ACE Voice Controller — Create Global Website Shortcuts Table
-- Run this in your Supabase SQL editor:
-- https://supabase.com/dashboard/project/xaqxspgbjmhznyfuesnt/sql/new
-- ============================================================

CREATE TABLE IF NOT EXISTS public.global_website_shortcuts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    keywords TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS
ALTER TABLE public.global_website_shortcuts ENABLE ROW LEVEL SECURITY;

-- Allow read access to all users
DROP POLICY IF EXISTS "Allow read for all users" ON public.global_website_shortcuts;
CREATE POLICY "Allow read for all users" ON public.global_website_shortcuts
    FOR SELECT USING (true);

-- Allow write/manage access for admin users OR if the user policy has mutable = true
DROP POLICY IF EXISTS "Allow write/manage based on roles and policies" ON public.global_website_shortcuts;
CREATE POLICY "Allow write/manage based on roles and policies" ON public.global_website_shortcuts
    FOR ALL USING (
        (SELECT role FROM public.users WHERE supabase_uid = auth.uid()) = 'admin'
        OR
        (SELECT (permissions->'global_website_shortcuts'->>'mutable')::boolean FROM public.user_policies WHERE user_id = (SELECT id FROM public.users WHERE supabase_uid = auth.uid())) = true
    )
    WITH CHECK (
        (SELECT role FROM public.users WHERE supabase_uid = auth.uid()) = 'admin'
        OR
        (SELECT (permissions->'global_website_shortcuts'->>'mutable')::boolean FROM public.user_policies WHERE user_id = (SELECT id FROM public.users WHERE supabase_uid = auth.uid())) = true
    );
