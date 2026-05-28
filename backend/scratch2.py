import subprocess
import time
exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
print("Launching edge...")
p = subprocess.Popen([exe], shell=False)
print("Launched! PID:", p.pid)
time.sleep(2)
p.kill()
print("Killed!")
