import sys
from pathlib import Path

# Add app to path
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

try:
    from app.routers.settings_router import router
    print("SUCCESS: settings_router loaded successfully!")
    print("Routes registered:")
    for route in router.routes:
        print(f"  {route.path} [{','.join(route.methods)}]")
except Exception as e:
    print("ERROR loading settings_router:", e)
    import traceback
    traceback.print_exc()
