import { createClient } from "@supabase/supabase-js";

// Ensure fallback placeholder values are used so the app doesn't crash if .env.local is missing
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://placeholder.supabase.co";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "placeholder-anon-key";

// Initialize Supabase client
export const supabase = createClient(supabaseUrl, supabaseAnonKey);
