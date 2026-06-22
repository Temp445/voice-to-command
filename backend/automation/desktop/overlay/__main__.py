from loguru import logger
import sys
import json
import asyncio
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QSize
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QBrush, QPen, QRadialGradient, QLinearGradient
import websockets
import qasync
from .app import OverlayApp

active_websocket = None

async def websocket_client(overlay: OverlayApp):
    global active_websocket
    import os
    port = os.environ.get("BACKEND_PORT", "8000")
    uri = f"ws://127.0.0.1:{port}/ws"
    has_connected = False
    retries = 0
    while True:
        try:
            async with websockets.connect(uri) as ws:
                has_connected = True
                retries = 0
                active_websocket = ws
                overlay.update_status_signal.emit("Connected")
                overlay.update_state_signal.emit("idle")
                
                # Wait for websocket messages
                async for message in ws:
                    try:
                        data = json.loads(message)
                        etype = data.get("event", "")
                        payload = data.get("data", {})

                        if etype == "connected":
                            if "wake_word" in payload:
                                overlay.update_settings_signal.emit({"wake_word": payload["wake_word"]})
                        
                        elif etype == "pipeline_state":
                            state = payload.get("state", "idle")
                            overlay.update_state_signal.emit(state)
                            
                        elif etype == "settings_updated":
                            overlay.update_settings_signal.emit(payload)

                        elif etype == "transcript":
                            text = payload.get("text", "")
                            if text:
                                if text.startswith("__"):
                                    overlay.update_status_signal.emit(text)
                                else:
                                    overlay.update_status_signal.emit(f'"{text}"')

                        elif etype == "command_executed":
                            raw = payload.get("raw_text", "")
                            ok  = payload.get("status", "") == "success"
                            overlay.update_status_signal.emit(f"✓ {raw}" if ok else "✗ Failed")

                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            logger.error(f"[{__name__}] {type(e).__name__}: {e}")
            if has_connected:
                import sys
                print("Lost connection to backend. Exiting to prevent orphaned process.")
                sys.exit(0)
            else:
                retries += 1
                if retries > 10:
                    import sys
                    print("Could not connect to backend. Exiting.")
                    sys.exit(0)
                
            active_websocket = None
            overlay.update_status_signal.emit("Reconnecting...")
            overlay.update_state_signal.emit("idle")
            await asyncio.sleep(2)

def main():
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    overlay = OverlayApp()
    
    def on_send_command(cmd: str):
        if active_websocket:
            payload = {"type": cmd}
            asyncio.create_task(active_websocket.send(json.dumps(payload)))
            
    overlay.send_command_signal.connect(on_send_command)

    # Start hidden, only show when WebSocket state changes

    loop.create_task(websocket_client(overlay))
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()

