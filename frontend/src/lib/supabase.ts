import { createClient } from "@supabase/supabase-js";

// Ensure fallback placeholder values are used so the app doesn't crash if .env.local is missing
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabasePublishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "placeholder-publishable-key";

// Initialize Supabase client
export const supabase = createClient(supabaseUrl, supabasePublishableKey);
