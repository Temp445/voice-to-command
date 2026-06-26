import re

pattern = re.compile(r'^(?:log\s*in|login|sign\s*in)(?:\s+(?:to\s+)?(?:the\s+)?crm)?$', re.IGNORECASE)
tests = [
    'sign in crm',
    'sign in to crm',
    'sign in to the crm',
    'sign in',
    'login',
    'log in crm',
    'login to crm',
    'sign in payroll',   # should NOT match crm_login
]
print("=== crm_login regex tests ===")
for t in tests:
    m = pattern.match(t)
    print(f"  {t!r:35} -> {'MATCH' if m else 'NO MATCH'}")

# Also test the new explicit crm auth bypass pattern
bypass = re.compile(
    r'\b(?:sign\s*in|log\s*in|login|signin)\b.{0,20}\bcrm\b'
    r'|\bcrm\b.{0,20}\b(?:sign\s*in|log\s*in|login|signin)\b',
    re.IGNORECASE
)
print("\n=== explicit_crm_auth bypass pattern tests ===")
for t in tests:
    m = bypass.search(t)
    print(f"  {t!r:35} -> {'MATCH' if m else 'NO MATCH'}")
