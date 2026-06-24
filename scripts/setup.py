"""
ACE Voice Controller — First-Run Setup Script
Checks prerequisites, creates .env, downloads voice models, initialises DB.
"""

import subprocess
import sys
import shutil
import os
import venv
from pathlib import Path

ROOT = Path(__file__).parent.parent
VENV_DIR = ROOT / "backend" / "venv"

def get_venv_python() -> str:
    if os.name == 'nt':
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python")


def check(name: str, cmd: str) -> bool:
    result = shutil.which(cmd)
    status = "✅" if result else "❌"
    print(f"  {status} {name}: {result or 'NOT FOUND'}")
    return bool(result)


def pip_install(*packages, requirements: str | None = None) -> int:
    """Run pip install with trusted-host flags to bypass SSL cert issues."""
    cmd = [
        get_venv_python(), "-m", "pip", "install",
        "--trusted-host", "pypi.org",
        "--trusted-host", "pypi.python.org",
        "--trusted-host", "files.pythonhosted.org",
    ]
    if requirements:
        cmd += ["-r", requirements]
    else:
        cmd += list(packages)
    return subprocess.run(cmd).returncode


def main():
    print("\n🚀 ACE Voice Controller — Setup Wizard\n" + "=" * 45)

    print("\n📋 Checking prerequisites...")
    python_ok = check("Python (executable)", "python")
    
    # Strict Python Version Check
    major, minor = sys.version_info[:2]
    if major != 3 or minor < 11 or minor >= 13:
        print(f"\n❌ Incompatible Python version detected: {major}.{minor}")
        print("   ACE Voice Controller requires Python 3.11 or 3.12.")
        print("   Newer versions (3.13, 3.14+) may break dependencies like Playwright.")
        sys.exit(1)
    else:
        print(f"  ✅ Python version: {major}.{minor} (Supported)")
    node_ok    = check("Node.js", "node")
    npm_ok     = check("npm", "npm")
    rust_ok    = check("Rust (rustup)", "rustup")

    if not python_ok:
        print("\n❌ Python not found. Install from https://python.org")
        sys.exit(1)

    if not rust_ok:
        print("\n  ℹ️  Rust NOT required to run the backend + voice pipeline.")
        print("     Install Rust later from https://rustup.rs only if you want")
        print("     to package the app as a .exe (Tauri desktop build).")

    print("\n📦 Setting up virtual environment...")
    if not VENV_DIR.exists():
        print(f"  Creating venv at {VENV_DIR}...")
        venv.create(VENV_DIR, with_pip=True)
    else:
        print("  ℹ️  venv already exists")

    print("\n📁 Creating .env file from template...")
    env_template = ROOT / ".env.example"
    env_file = ROOT / ".env"
    if not env_file.exists() and env_template.exists():
        shutil.copy(env_template, env_file)
        print("  ✅ .env created — edit it with your Supabase credentials")
    else:
        print("  ℹ️  .env already exists")

    print("\n🐍 Installing Python dependencies...")
    req_files = [
        ROOT / "backend" / "requirements.txt",
        ROOT / "backend" / "requirements-automation.in",
        ROOT / "backend" / "requirements-voice.in"
    ]
    
    any_failed = False
    for req_file in req_files:
        if req_file.exists():
            print(f"  Installing from {req_file.name}...")
            rc = pip_install(requirements=str(req_file))
            if rc != 0:
                print(f"  ⚠️  Failed to install dependencies from {req_file.name}")
                any_failed = True
        else:
            print(f"  ⚠️  Requirements file not found: {req_file}")
            any_failed = True

    if any_failed:
        print("  ⚠️  Some packages failed. Retrying with core packages fallback...")
        # Install critical packages individually as fallback
        for pkg in ["fastapi", "uvicorn[standard]", "sqlalchemy", "pydantic", "loguru", "httpx", "psutil"]:
            pip_install(pkg)

    print("\n📥 Downloading Piper TTS voice model...")
    subprocess.run([get_venv_python(), str(ROOT / "scripts" / "download_models.py")])

    print("\n🎭 Setting up Playwright...")
    pw_check = subprocess.run(
        [get_venv_python(), "-c", "import playwright"],
        capture_output=True,
    )
    if pw_check.returncode != 0:
        print("  ⚙️  playwright not yet installed — installing now...")
        pip_install("playwright==1.44.0")

    pw_result = subprocess.run([get_venv_python(), "-m", "playwright", "install", "chromium"])
    if pw_result.returncode == 0:
        print("  ✅ Playwright Chromium installed")
    else:
        print("  ⚠️  Playwright browser install failed — browser automation won't work until fixed")

    print("\n\n✅ Setup complete!")
    print("=" * 45)
    print("\nNext steps:")
    print("  1️⃣  Edit .env → add your SUPABASE_URL + SUPABASE_PUBLISHABLE_KEY")
    print("  2️⃣  Run Supabase SQL: database/supabase_schema.sql")
    print("  3️⃣  Start backend:  cd backend && python -m app.main")
    print("  4️⃣  Start frontend: cd frontend && npm install")
    if rust_ok:
        print("       then: npm run tauri:dev   ← full desktop app")
    else:
        print("       then: npm run dev         ← runs in browser (no Rust needed)")
        print()
        print("  Optional: Install Rust from https://rustup.rs to build the .exe later")


if __name__ == "__main__":
    main()
