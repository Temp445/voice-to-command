import subprocess

try:
    res = subprocess.run(["git", "diff", "backend/automation/browser/tab_registry.py"], capture_output=True, text=True, check=True)
    print("=== tab_registry.py Diff ===")
    print(res.stdout[:5000])
    if len(res.stdout) > 5000:
        print("... truncated ...")
        
    res2 = subprocess.run(["git", "diff", "backend/automation/browser/browser_engine.py"], capture_output=True, text=True, check=True)
    print("=== browser_engine.py Diff ===")
    print(res2.stdout[:5000])
    if len(res2.stdout) > 5000:
        print("... truncated ...")
except Exception as e:
    print("Error:", e)
