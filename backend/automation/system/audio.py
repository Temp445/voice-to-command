"""Advanced Audio Control using PyCAW."""

import sys
import os
from ctypes import cast, POINTER
from loguru import logger

# Only import Windows-specific COM libraries if on Windows
if sys.platform == "win32":
    try:
        import comtypes
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError:
        pass

class AudioController:
    """Controls Windows system audio mixer via PyCAW."""

    def __init__(self):
        pass

    def _get_volume_interface(self):
        try:
            comtypes.CoInitialize()
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            logger.error(f"Failed to get audio interface: {e}")
            return None

    def set_system_volume(self, level: int) -> str:
        """Set the master system volume (0-100)."""
        level = max(0, min(100, int(level)))
        
        if sys.platform == "darwin":
            # Mac: Use osascript
            os.system(f"osascript -e 'set volume output volume {level}'")
            return f"Mac system volume set to {level}%."
            
        elif sys.platform == "win32":
            # Windows: Use pycaw
            try:
                volume = self._get_volume_interface()
                if not volume:
                    return "Audio control is unavailable."
                
                # PyCAW uses scalar values 0.0 to 1.0 for master volume
                scalar_level = float(level) / 100.0
                volume.SetMasterVolumeLevelScalar(scalar_level, None)
                return f"System volume set to {level}%."
            except Exception as e:
                return f"Failed to set volume: {e}"
            finally:
                if 'comtypes' in sys.modules:
                    comtypes.CoUninitialize()
                    
        return f"Volume control not supported on {sys.platform}."

    def mute_system(self, mute: bool = True) -> str:
        """Mute or unmute the system audio."""
        if sys.platform == "darwin":
            # Mac: Use osascript
            mute_str = "true" if mute else "false"
            os.system(f"osascript -e 'set volume output muted {mute_str}'")
            return "Mac system muted." if mute else "Mac system unmuted."
            
        elif sys.platform == "win32":
            try:
                volume = self._get_volume_interface()
                if not volume:
                    return "Audio control is unavailable."
                
                volume.SetMute(1 if mute else 0, None)
                return "System muted." if mute else "System unmuted."
            except Exception as e:
                return f"Failed to mute system: {e}"
            finally:
                if 'comtypes' in sys.modules:
                    comtypes.CoUninitialize()
                    
        return f"Mute control not supported on {sys.platform}."

    def set_app_volume(self, app_name: str, level: int) -> str:
        """Set the volume of a specific application (0-100)."""
        if sys.platform != "win32":
            return "Per-app volume control is currently only supported on Windows."
            
        level = max(0, min(100, int(level)))
        app_name = app_name.lower().strip()
        try:
            comtypes.CoInitialize()
            sessions = AudioUtilities.GetAllSessions()
            found = False
            for session in sessions:
                if session.Process and session.Process.name().lower() == f"{app_name}.exe":
                    volume = session.SimpleAudioVolume
                    # 0.0 to 1.0
                    volume.SetMasterVolume(float(level) / 100.0, None)
                    found = True
                    break
                    
            if not found:
                # Fallback fuzzy match
                for session in sessions:
                    if session.Process and app_name in session.Process.name().lower():
                        volume = session.SimpleAudioVolume
                        volume.SetMasterVolume(float(level) / 100.0, None)
                        return f"Volume for {session.Process.name()} set to {level}%."

            return f"Volume for {app_name} set to {level}%." if found else f"Could not find active audio session for '{app_name}'."
        except Exception as e:
            return f"Failed to set app volume: {e}"
        finally:
            if 'comtypes' in sys.modules:
                comtypes.CoUninitialize()

    def mute_app(self, app_name: str, mute: bool = True) -> str:
        """Mute or unmute a specific application."""
        if sys.platform != "win32":
            return "Per-app mute control is currently only supported on Windows."
            
        app_name = app_name.lower().strip()
        try:
            comtypes.CoInitialize()
            sessions = AudioUtilities.GetAllSessions()
            found = False
            for session in sessions:
                if session.Process and session.Process.name().lower() == f"{app_name}.exe":
                    volume = session.SimpleAudioVolume
                    volume.SetMute(1 if mute else 0, None)
                    found = True
                    break
                    
            if not found:
                for session in sessions:
                    if session.Process and app_name in session.Process.name().lower():
                        volume = session.SimpleAudioVolume
                        volume.SetMute(1 if mute else 0, None)
                        return f"Muted {session.Process.name()}." if mute else f"Unmuted {session.Process.name()}."

            if found:
                return f"Muted {app_name}." if mute else f"Unmuted {app_name}."
            return f"Could not find active audio session for '{app_name}'."
        except Exception as e:
            return f"Failed to mute app: {e}"
        finally:
            if 'comtypes' in sys.modules:
                comtypes.CoUninitialize()
