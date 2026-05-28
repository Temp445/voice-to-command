"""
ACE Voice Controller — System Power & Lock Management
"""

import os
import subprocess
import ctypes


class PowerManager:
    def sleep(self) -> None:
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    def shutdown(self) -> None:
        os.system("shutdown /s /t 5")

    def restart(self) -> None:
        os.system("shutdown /r /t 5")

    def lock_screen(self) -> None:
        ctypes.windll.user32.LockWorkStation()
