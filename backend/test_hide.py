import ctypes
import time
import subprocess
import pygetwindow as gw

# Launch notepad
subprocess.Popen(["notepad.exe"])
time.sleep(1)

# Find notepad
wins = gw.getWindowsWithTitle("Notepad")
if wins:
    win = wins[0]
    print("Hiding window...")
    user32 = ctypes.windll.user32
    # SW_HIDE = 0
    user32.ShowWindow(win._hWnd, 0)
    print("Window hidden. Wait 5s...")
    time.sleep(5)
    # SW_SHOW = 5
    print("Showing window...")
    user32.ShowWindow(win._hWnd, 5)
    time.sleep(2)
    win.close()
