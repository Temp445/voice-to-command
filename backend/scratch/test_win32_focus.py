import asyncio
import sys
import psutil
import ctypes
from pywinauto import Desktop
from automation.desktop.window_manager import WindowManager

async def main():
    wm = WindowManager()
    
    # 1. Find PIDs of processes matching ACE\BrowserProfile
    print("Scanning for ACE automated browser processes...")
    ace_pids = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name']
            if name and name.lower() in ['chrome.exe', 'msedge.exe', 'firefox.exe', 'chrome', 'firefox']:
                cmdline = proc.info.get('cmdline')
                if cmdline and any('ACE\\BrowserProfile' in str(arg) or 'ACE/BrowserProfile' in str(arg) for arg in cmdline):
                    print(f"Found ACE process: {name} (PID: {proc.info['pid']})")
                    ace_pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    print(f"ACE PIDs: {ace_pids}")
    
    # 2. Find windows belonging to those PIDs
    print("Searching for visible windows belonging to ACE PIDs...")
    target_win = None
    for win in Desktop(backend="win32").windows():
        try:
            if not win.is_visible() or not win.window_text():
                continue
            pid = win.process_id()
            if pid in ace_pids:
                print(f"-> MATCHED window for PID {pid}: '{win.window_text()}'")
                target_win = win
                break
        except Exception:
            continue
            
    if not target_win:
        print("No ACE browser window found. Falling back to any Chrome window...")
        target_win = wm._find_window_by_title("chrome")
        
    if not target_win:
        print("No windows found to test.")
        return
        
    print(f"Testing window: '{target_win.window_text()}' (PID: {target_win.process_id()})")
    print("Minimizing window...")
    target_win.minimize()
    
    print("Waiting 3 seconds in minimized state...")
    await asyncio.sleep(3)
    
    print("Attempting to force focus, maximize, and foreground...")
    hwnd = target_win.handle
    user32 = ctypes.windll.user32
    
    # Ultimate focus-forcing sequence
    try:
        # 1. Timeout bypass
        timeout = ctypes.c_uint()
        user32.SystemParametersInfoW(0x2000, 0, ctypes.byref(timeout), 0)
        user32.SystemParametersInfoW(0x2001, 0, ctypes.c_void_p(0), 0x02)
        
        # 2. Minimize & Maximize
        user32.ShowWindow(hwnd, 6) # SW_MINIMIZE
        await asyncio.sleep(0.1)
        user32.ShowWindow(hwnd, 3) # SW_SHOWMAXIMIZED
        user32.PostMessageW(hwnd, 0x0112, 0xF030, 0)
        
        # 3. Undocumented SwitchToThisWindow
        user32.SwitchToThisWindow(hwnd, True)
        
        # 4. Bring to top
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        
        # 5. Thread Attachment and Alt key simulation
        foreground_hwnd = user32.GetForegroundWindow()
        if hwnd != foreground_hwnd:
            foreground_thread = user32.GetWindowThreadProcessId(foreground_hwnd, None)
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            if foreground_thread != current_thread:
                # Simulate Alt key
                user32.keybd_event(0x12, 0, 0, 0)
                user32.keybd_event(0x12, 0, 2, 0)
                
                user32.AttachThreadInput(current_thread, foreground_thread, True)
                user32.SetForegroundWindow(hwnd)
                user32.SetFocus(hwnd)
                user32.AttachThreadInput(current_thread, foreground_thread, False)
                
        # Restore timeout
        user32.SystemParametersInfoW(0x2001, 0, ctypes.c_void_p(timeout.value), 0x02)
        print("Applied focus sequence.")
    except Exception as e:
        print(f"Error in focus sequence: {e}")
    
    print("Waiting 5 seconds to inspect result...")
    await asyncio.sleep(5)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
