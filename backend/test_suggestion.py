"""
Quick test: simulate a command execution and verify suggestions are returned.
Run from the backend directory: python test_suggestion.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.command_service import command_service

print("=" * 60)
print("TEST: Context-Aware Suggestion System")
print("=" * 60)

# 1. Test initial domain
print(f"\n[1] Initial domain: '{command_service.current_domain}'")
suggs = command_service.get_suggestions(limit=4)
print(f"    Suggestions: {suggs['suggestions']}")

# 2. Simulate 'open CRM' - set domain to browser
command_service.current_domain = "browser"
print(f"\n[2] After 'open CRM' (domain=browser):")
suggs = command_service.get_suggestions(limit=4)
if suggs["suggestions"]:
    quoted = [f'"{s}"' for s in suggs["suggestions"][:3]]
    hint = "Try: " + " · ".join(quoted)
    print(f"    Card text: {hint}")
    print(f"    ✅ PASS — suggestions found")
else:
    print(f"    ❌ FAIL — no suggestions returned for domain=browser")

# 3. Simulate voice command parsing to see if domain updates
print(f"\n[3] Running parse_and_execute simulation...")
import asyncio

async def test_command():
    result = await command_service.parse_and_execute("open notepad")
    print(f"    Command: 'open notepad'")
    print(f"    Status: {result.get('status')}")
    print(f"    Intent: {result.get('intent')}")
    print(f"    Domain after execution: '{command_service.current_domain}'")
    suggs2 = command_service.get_suggestions(limit=3)
    items = suggs2.get("suggestions", [])
    if items:
        quoted = [f'"{s}"' for s in items[:3]]
        hint = "Try: " + " · ".join(quoted)
        print(f"    Next suggestions: {hint}")
        print(f"    ✅ PASS — context-aware suggestions working")
    else:
        print(f"    ⚠️  No suggestions for domain '{command_service.current_domain}'")

asyncio.run(test_command())

print("\n" + "=" * 60)
print("Available domains in registry:")
domains = set(i.domain for i in command_service._intents)
for d in sorted(domains):
    count = len([i for i in command_service._intents if i.domain == d and i.examples])
    print(f"  {d}: {count} intents with examples")
print("=" * 60)
