"""Apply scan_mode migration to Supabase via Management API."""
import urllib.request
import json

SUPABASE_URL = "https://xaqxspgbjmhznyfuesnt.supabase.co"
PROJECT_REF  = "xaqxspgbjmhznyfuesnt"
SERVICE_KEY  = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhhcXhzcGdiam1oem55ZnVlc250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTkzOTg4NywiZXhwIjoyMDk1NTE1ODg3fQ"
    ".Koec5C1T85q4TIVwyV-2D3I_bBLOCNCNcF7cR2TF-2w"
)

SQL_STATEMENTS = [
    "ALTER TABLE public.settings ADD COLUMN IF NOT EXISTS scan_mode TEXT DEFAULT 'auto'",
    "ALTER TABLE public.settings DROP CONSTRAINT IF EXISTS settings_scan_mode_check",
    "ALTER TABLE public.settings ADD CONSTRAINT settings_scan_mode_check CHECK (scan_mode IN ('auto', 'manual'))",
    "UPDATE public.settings SET scan_mode = 'auto' WHERE scan_mode IS NULL",
]

MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

print("=== ACE — Applying scan_mode migration to Supabase ===\n")

for i, sql in enumerate(SQL_STATEMENTS, 1):
    body = json.dumps({"query": sql}).encode("utf-8")
    req = urllib.request.Request(
        MGMT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = resp.read().decode("utf-8")
            print(f"  [{i}] OK: {result[:120]}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        # 'already exists' style = safe to ignore
        if any(x in err_body.lower() for x in ["already exists", "does not exist", "duplicate"]):
            print(f"  [{i}] Skipped (already applied): {err_body[:100]}")
        else:
            print(f"  [{i}] HTTP {e.code}: {err_body[:200]}")
    except Exception as ex:
        print(f"  [{i}] Error: {ex}")

print("\n=== Done — verifying column exists ===")

# Verify by querying the column via REST API
verify_url = f"{SUPABASE_URL}/rest/v1/settings?select=scan_mode&limit=2"
req = urllib.request.Request(
    verify_url,
    headers={
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
    },
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Column scan_mode confirmed in database! Sample rows: {data[:3]}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8")
    print(f"Verification failed ({e.code}): {body[:200]}")
    print("\nThe column may still need to be added manually.")
    print("Run this SQL in your Supabase SQL editor:")
    print("  https://supabase.com/dashboard/project/xaqxspgbjmhznyfuesnt/sql/new")
    print()
    print("  ALTER TABLE public.settings ADD COLUMN IF NOT EXISTS scan_mode TEXT DEFAULT 'auto';")
    print("  ALTER TABLE public.settings DROP CONSTRAINT IF EXISTS settings_scan_mode_check;")
    print("  ALTER TABLE public.settings ADD CONSTRAINT settings_scan_mode_check CHECK (scan_mode IN ('auto', 'manual'));")
    print("  UPDATE public.settings SET scan_mode = 'auto' WHERE scan_mode IS NULL;")
