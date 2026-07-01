import os
import sys

# Ensure the backend root is in the path
backend_root = os.path.dirname(os.path.abspath(__file__))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# Now we can safely import the app module
from app.main import app
from app.config import settings
import uvicorn

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--overlay":
        from automation.desktop.overlay.__main__ import main as overlay_main
        overlay_main()
    else:
        # In PyInstaller, we must pass the app instance directly, not a string "app.main:app"
        # because uvicorn's string importer doesn't play well with PyInstaller's archive format.
        uvicorn.run(
            app,
            host=settings.backend_host,
            port=settings.backend_port,
            reload=False,           # Cannot be used inside PyInstaller binary
            log_level="warning",    # Loguru middleware handles request logging — suppress uvicorn noise
            access_log=False,       # Disable uvicorn's own access log (our middleware logs with timing)
            timeout_graceful_shutdown=5,
        )
