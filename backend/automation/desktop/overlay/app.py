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
from .widgets import MicButton, IconButton
from .drop_zone import DropZoneWindow

class OverlayApp(QWidget):
    update_status_signal = pyqtSignal(str)
    update_state_signal = pyqtSignal(str)
    show_card_signal = pyqtSignal(str, str)
    update_settings_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.current_state = "idle"
        self._drag_pos = None
        self._ws_connected = False
        self._card_mode = None          # "suggestion" | "replay" | None
        self._is_pinned = False         # If true, auto-hide is disabled
        self._wake_word = "alexa"
        self._card_hide_timer = QTimer(self)
        self._card_hide_timer.setSingleShot(True)
        self._card_hide_timer.timeout.connect(self._hide_card)
        
        self._sub_label_timer = QTimer(self)
        self._sub_label_timer.setSingleShot(True)
        self._sub_label_timer.timeout.connect(self._reset_sub_label)

        self._last_transcript = ""
        self._transcript_clear_timer = QTimer(self)
        self._transcript_clear_timer.setSingleShot(True)
        self._transcript_clear_timer.timeout.connect(self._clear_transcript)

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._do_auto_hide)
        
        self.drop_zone = DropZoneWindow()
        screen = QApplication.primaryScreen().geometry()
        self.drop_zone.move(screen.width() // 2 - self.drop_zone.width() // 2, screen.height() // 2 - self.drop_zone.height() // 2)
        
        self.initUI()

        self.update_status_signal.connect(self._on_status)
        self.update_state_signal.connect(self._on_state)
        self.show_card_signal.connect(self._show_card)
        self.update_settings_signal.connect(self._on_settings_update)

        # Single timer drives all animations (60 fps feel at 80ms)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._tick)
        self.anim_timer.start(80)

        # Do not show initially, stay hidden until activated by WebSocket

    # ── UI Construction ───────────────────────────────────────────────────────

    def initUI(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Outer layout fills transparent window
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # The visible pill container
        self.pill = QWidget()
        self.pill.setObjectName("Pill")
        outer.addWidget(self.pill)

        pill_layout = QHBoxLayout(self.pill)
        pill_layout.setContentsMargins(8, 6, 14, 6)
        pill_layout.setSpacing(10)

        # ── Mic button (big, circular) ─────────────────────────────────────
        self.mic_btn = MicButton()
        self.mic_btn.clicked.connect(self._on_mic_clicked)
        pill_layout.addWidget(self.mic_btn)

        # ── Status + sub-status ────────────────────────────────────────────
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        text_col.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("ACE is ready")
        self.status_label.setFont(QFont("Segoe UI Semibold", 10, QFont.Weight.DemiBold))

        self.sub_label = QLabel(f"Wake word: {self._wake_word}")
        self.sub_label.setFont(QFont("Segoe UI", 8))

        text_col.addWidget(self.status_label)
        text_col.addWidget(self.sub_label)
        pill_layout.addLayout(text_col)

        pill_layout.addStretch(1)

        # Pin: toggles auto-hide
        self.pin_btn = IconButton(
            "pin", "Pin to screen (disable auto-hide)",
            enabled_icon_color="#e5e7eb",
            disabled_icon_color="#e5e7eb",
        )
        self.pin_btn.clicked.connect(self._on_pin_clicked)
        pill_layout.addWidget(self.pin_btn)


        # Replay: white when enabled, dim white when disabled
        self.replay_btn = IconButton(
            "rotate_ccw", "Replay last response",
            enabled_icon_color="#e5e7eb",   # white
            disabled_icon_color="#e5e7eb",  # same — opacity handles disabled look
        )
        self.replay_btn.clicked.connect(self._on_replay_clicked)
        pill_layout.addWidget(self.replay_btn)

        # Stop: red when enabled, dim white when disabled
        self.stop_btn = IconButton(
            "stop", "Stop current action",
            enabled_icon_color="#ef4444",   # red
            disabled_icon_color="#e5e7eb",
        )
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        pill_layout.addWidget(self.stop_btn)

        # ── Style ──────────────────────────────────────────────────────────
        self.setStyleSheet("""
            QWidget#Pill {
                background-color: rgba(18, 18, 24, 235);
                border-radius: 26px;
                border: 1px solid rgba(255, 255, 255, 30);
            }
            QLabel {
                color: #e5e7eb;
                background: transparent;
            }
        """)

        self.resize(360, 58)
        self._center_top()

        # ── Info card (hidden by default) ──────────────────────────────────
        self.card = QWidget(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.card.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.card.setFixedWidth(360)
        self.card.hide()

        card_inner = QWidget(self.card)
        card_inner.setObjectName("CardInner")
        card_layout = QVBoxLayout(card_inner)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        
        self.card_title = QLabel("Suggestion")
        self.card_title.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.card_title.setStyleSheet("color: #9ca3af;")
        
        self.card_close_btn = QPushButton("✕")
        self.card_close_btn.setFixedSize(16, 16)
        self.card_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_close_btn.setStyleSheet("""
            QPushButton {
                color: #9ca3af;
                background: transparent;
                border: none;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #f3f4f6;
            }
        """)
        self.card_close_btn.clicked.connect(self._hide_card)
        
        title_row.addWidget(self.card_title)
        title_row.addStretch(1)
        title_row.addWidget(self.card_close_btn)

        self.card_body = QLabel("")
        self.card_body.setFont(QFont("Segoe UI", 10))
        self.card_body.setStyleSheet("color: #f3f4f6;")
        self.card_body.setWordWrap(True)

        card_layout.addLayout(title_row)
        card_layout.addWidget(self.card_body)

        card_inner.setStyleSheet("""
            QWidget#CardInner {
                background-color: rgba(24, 24, 32, 240);
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,25);
            }
        """)

        outer_card = QVBoxLayout(self.card)
        outer_card.setContentsMargins(0, 0, 0, 0)
        outer_card.addWidget(card_inner)

    # ── Positioning ───────────────────────────────────────────────────────────

    def _center_top(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        self.move(x, 14)

    # ── Animation tick ────────────────────────────────────────────────────────

    def _tick(self):
        self.mic_btn.tick()
        if self.current_state == "idle":
            self._update_border_idle()

    def _update_border_idle(self):
        pass  # pill border stays static for idle

    # ── State management ──────────────────────────────────────────────────────

    def _clear_transcript(self):
        self._last_transcript = ""
        if self.current_state in ("idle", "error"):
            self._on_state(self.current_state)

    def _do_auto_hide(self):
        if not self._is_pinned and self.current_state in ("idle", "error") and not self._last_transcript and not self._card_mode:
            self.hide()

    def _on_state(self, state: str):
        self.current_state = state
        self.mic_btn.set_state(state)
        is_idle = state in ("idle", "error")

        # Enable replay only when ACE is idle
        self.replay_btn.set_enabled_state(is_idle)
        # Enable stop only when ACE is active
        self.stop_btn.set_enabled_state(not is_idle)

        if state == "listening":
            self._auto_hide_timer.stop()
            self.show()
            self.raise_()
            self._last_transcript = ""
            self.status_label.setText("Listening...")
            self.sub_label.setText("Click mic to stop  ·  Speak now")
            self.status_label.setStyleSheet("color: #f87171;")
            self._set_pill_accent("#ef4444")
            self._hide_card()  # Auto-hide card when a new command starts
        elif state == "processing":
            self._auto_hide_timer.stop()
            self.show()
            self.raise_()
            self.status_label.setText(self._last_transcript if self._last_transcript else "Processing...")
            self.sub_label.setText("Executing your command")
            self.status_label.setStyleSheet("color: #fbbf24;")
            self._set_pill_accent("#eab308")
            self._hide_card()  # Auto-hide card when a new command starts
        elif state == "speaking":
            self._auto_hide_timer.stop()
            self.show()
            self.raise_()
            self.status_label.setText(self._last_transcript if self._last_transcript else "Speaking...")
            self.sub_label.setText("ACE is responding")
            self.status_label.setStyleSheet("color: #60a5fa;")
            self._set_pill_accent("#3b82f6")
        else:
            if self._last_transcript:
                self.show()
                self.raise_()
                self.status_label.setText(self._last_transcript)
                if self._last_transcript.startswith('✓'):
                    self.status_label.setStyleSheet("color: #10b981;")
                elif self._last_transcript.startswith('✗'):
                    self.status_label.setStyleSheet("color: #ef4444;")
                else:
                    self.status_label.setStyleSheet("color: #fbbf24;")
                self._transcript_clear_timer.start(6000)
            else:
                self.status_label.setText("ACE is ready")
                self.status_label.setStyleSheet("color: #e5e7eb;")
                self.sub_label.setText(f"Wake word: {self._wake_word}")
                self._set_pill_accent(None)
                
                # If it's already visible (e.g., finishing a command), start the auto-hide timer
                if self.isVisible() and not self._auto_hide_timer.isActive():
                    self._auto_hide_timer.start(3000)

    def _on_settings_update(self, settings_data: dict):
        if "wake_word" in settings_data:
            self._wake_word = settings_data["wake_word"]
            self._reset_sub_label()

    def _reset_sub_label(self):
        """Revert the sub-label text back to default if ACE is idle."""
        if self.current_state in ("idle", "error"):
            self.sub_label.setText(f"Wake word: {self._wake_word}")

    def _set_pill_accent(self, hex_color):
        if hex_color:
            self.pill.setStyleSheet(f"""
                QWidget#Pill {{
                    background-color: rgba(18, 18, 24, 235);
                    border-radius: 26px;
                    border: 1px solid {hex_color}80;
                }}
                QLabel {{ color: #e5e7eb; background: transparent; }}
            """)
        else:
            self.pill.setStyleSheet("""
                QWidget#Pill {
                    background-color: rgba(18, 18, 24, 235);
                    border-radius: 26px;
                    border: 1px solid rgba(255, 255, 255, 30);
                }
                QLabel { color: #e5e7eb; background: transparent; }
            """)

    def _on_status(self, text: str):
        """Handle special prefixed messages from backend."""
        if text.startswith("__replay__"):
            content = text[len("__replay__"):]
            self.show_card_signal.emit("🔁 Last Response", content)
        elif text == "__replay_empty__":
            self.show_card_signal.emit("🔁 Last Response", "Nothing to replay yet.")
        elif text.startswith('"') or text.startswith('✓') or text.startswith('✗'):
            self._last_transcript = text
            if self.current_state in ("processing", "speaking", "idle", "listening"):
                self.status_label.setText(text)
                if text.startswith('✓'):
                    self.status_label.setStyleSheet("color: #10b981;")
                elif text.startswith('✗'):
                    self.status_label.setStyleSheet("color: #ef4444;")
                else:
                    self.status_label.setStyleSheet("color: #fbbf24;")
                    
            if self.current_state in ("idle", "error"):
                self._transcript_clear_timer.start(6000)
        elif text not in ("Listening...", "Processing...", "Speaking...", "ACE is idle", "ACE is ready", "Connected"):
            self.sub_label.setText(text)
            self._sub_label_timer.start(4000)

    def _show_card(self, title: str, body: str):
        """Display a floating card below the pill and activate the triggering button."""
        self._auto_hide_timer.stop()
        self.show()
        self.raise_()
        
        self._card_mode = "replay"
        self.replay_btn.set_active(True)

        self.card_title.setText(title)
        self.card_body.setText(body)
        self.card.adjustSize()

        # Position card just below the pill
        pill_pos = self.mapToGlobal(self.pill.pos())
        card_x = pill_pos.x()
        card_y = self.y() + self.height() + 6
        self.card.move(card_x, card_y)
        self.card.show()
        self.card.raise_()

        self._card_hide_timer.start(8000)

    def _hide_card(self):
        self.card.hide()
        self._card_mode = None
        self.replay_btn.set_active(False)
        if self.current_state in ("idle", "error") and not self._last_transcript:
            if not self._auto_hide_timer.isActive():
                self._auto_hide_timer.start(3000)

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_mic_clicked(self):
        if self.current_state == "listening":
            # STOP listening — go idle immediately, backend will confirm
            asyncio.create_task(send_command("stop_listen"))
            self._on_state("idle")
            self.status_label.setText("Mic stopped")
            self.sub_label.setText("Click mic to start listening")
        elif self.current_state in ("idle", "error"):
            # START listening
            self._on_state("listening")
            asyncio.create_task(send_command("trigger_listen"))
        # if processing or speaking, ignore click



    def _on_replay_clicked(self):
        """Request the backend to replay the last spoken TTS."""
        if self.current_state in ("idle", "error"):
            # The backend `replay` command triggers the TTS.
            asyncio.create_task(send_command("replay"))

    def _on_stop_clicked(self):
        """Request the backend to forcefully stop the current pipeline action."""
        if self.current_state not in ("idle", "error"):
            asyncio.create_task(send_command("stop"))

    def _on_pin_clicked(self):
        self._is_pinned = not self._is_pinned
        self.pin_btn.set_active(self._is_pinned)
        # If unpinned while idle, start auto-hide
        if not self._is_pinned and self.current_state in ("idle", "error") and not self._last_transcript:
            if not self._auto_hide_timer.isActive():
                self._auto_hide_timer.start(3000)

    # ── Dragging ──────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._over_drop_zone = False
            self.drop_zone.set_hover(False)
            self.drop_zone.show()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            
            # Check intersection with drop zone
            pill_rect = self.geometry()
            dz_rect = self.drop_zone.geometry()
            self._over_drop_zone = pill_rect.intersects(dz_rect)
            self.drop_zone.set_hover(self._over_drop_zone)
            
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            self.drop_zone.hide()
            
            if getattr(self, '_over_drop_zone', False):
                self._disable_overlay()
                self.close()
                sys.exit(0)
                
        super().mouseReleaseEvent(event)

    def _disable_overlay(self):
        import urllib.request
        import json
        import os
        try:
            port = os.environ.get("BACKEND_PORT", "8000")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/settings",
                data=json.dumps({"enable_desktop_overlay": False}).encode(),
                headers={"Content-Type": "application/json"},
                method="PATCH"
            )
            urllib.request.urlopen(req, timeout=2)
        except Exception as e:
            print(f"Failed to disable overlay via API: {e}")

