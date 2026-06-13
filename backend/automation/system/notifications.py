"""Native Windows Notifications using plyer."""

from loguru import logger

class NotificationManager:
    """Handles native desktop notifications."""

    def send_toast(self, title: str, message: str, timeout: int = 10) -> str:
        """Send a native OS notification bubble."""
        try:
            from plyer import notification
            import sys
            
            # App icon must be an .ico on Windows. For now, we omit it so it uses default.
            notification.notify(
                title=title,
                message=message,
                app_name="ACE Voice Controller",
                timeout=timeout
            )
            return "Notification sent."
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return f"Failed to send notification: {e}"
