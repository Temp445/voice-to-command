import argparse
import os
import sys
import time
import subprocess
import psutil
import httpx
from pathlib import Path
from loguru import logger

def get_default_chrome_profile() -> str:
    """Returns the path to the default Chrome profile for the current OS."""
    if sys.platform == "win32":
        return os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    elif sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:
        return os.path.expanduser("~/.config/google-chrome")

def get_chrome_executable() -> str:
    """Returns the path to the Chrome executable for the current OS."""
    if sys.platform == "win32":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return "chrome.exe"
    elif sys.platform == "darwin":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    else:
        return "google-chrome"

def is_cdp_open(port: int = 9222) -> bool:
    """Checks if the Chrome DevTools Protocol port is open."""
    import urllib.request
    try:
        req = urllib.request.Request(f"http://localhost:{port}/json/version")
        with urllib.request.urlopen(req, timeout=0.5) as response:
            return response.status == 200
    except Exception as e:
        logger.error(f"Error: {e}")
        return False

def kill_chrome_processes():
    """Forcefully terminates all running Chrome processes."""
    logger.info("Killing existing Chrome processes...")
    killed = 0
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    if killed > 0:
        logger.info(f"Terminated {killed} Chrome processes.")
        time.sleep(2)  # Give the OS time to release file locks

def launch_chrome(profile_dir: str, port: int = 9222):
    """Launches Chrome with CDP enabled."""
    exe = get_chrome_executable()
    args = [
        exe,
        f"--remote-debugging-port={port}",
        "--start-maximized",
        "--profile-directory=Default",
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--restore-last-session"
    ]
    
    if profile_dir:
        args.append(f"--user-data-dir={profile_dir}")
        
    logger.info(f"Launching Chrome: {' '.join(args)}")
    # Use creationflags to detach the process so it doesn't die when the server restarts
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)

def main():
    parser = argparse.ArgumentParser(description="ACE Launch Chrome with CDP")
    parser.add_argument("--no-kill", action="store_true", help="Do not kill existing Chrome processes")
    parser.add_argument("--profile-dir", type=str, help="Override default profile directory")
    parser.add_argument("--port", type=int, default=9222, help="CDP port (default 9222)")
    args = parser.parse_args()

    if is_cdp_open(args.port):
        logger.info(f"CDP port {args.port} is already open. Nothing to do.")
        sys.exit(0)

    if not args.no_kill:
        kill_chrome_processes()

    profile_dir = args.profile_dir if args.profile_dir else get_default_chrome_profile()
    if not os.path.exists(profile_dir):
        logger.warning(f"Profile directory {profile_dir} does not exist. A new one will be created.")

    launch_chrome(profile_dir, args.port)

    # Wait for CDP to become available
    logger.info("Waiting for CDP port to open...")
    for _ in range(10):
        if is_cdp_open(args.port):
            logger.success(f"Success! Chrome is ready on port {args.port}")
            sys.exit(0)
        time.sleep(1)

    logger.error("Failed to detect CDP port after launch.")
    sys.exit(1)

if __name__ == "__main__":
    main()
