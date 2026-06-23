import subprocess
import time
import os

profile_path = os.path.abspath("./tmp-profile-bg")
os.makedirs(profile_path, exist_ok=True)

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# Or let playwright find it, but we can just use start chrome

cmd = [
    chrome_path,
    f"--user-data-dir={profile_path}",
    "--remote-debugging-port=9223",
    "--no-startup-window",
    "--disable-blink-features=AutomationControlled",
    "--no-first-run"
]

print("Launching chrome in background...")
p = subprocess.Popen(cmd)
time.sleep(5)
print("Chrome is running? ", p.poll() is None)
p.terminate()
