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

# ─── SVG Icon helper ─────────────────────────────────────────────────────────

_SVGS = {
    "mic": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>',
    "mic_off": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="2" x2="22" y1="2" y2="22"/><path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2"/><path d="M5 10v2a7 7 0 0 0 12 5"/><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12"/><line x1="12" x2="12" y1="19" y2="22"/></svg>',
    "lightbulb": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1.3.5 2.6 1.5 3.5.8.8 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>',
    "rotate_ccw": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>',
    "volume1": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/></svg>',
    "volume2": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>',
    "volume3": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>',
    "loader": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.5" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>',
    "x": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
}

def make_pixmap(name: str, color: str, size: int = 18, rotation: int = 0) -> QPixmap:
    svg = _SVGS[name].replace(b"{c}", color.encode()).replace(b"{s}", str(size).encode())
    pix = QPixmap()
    pix.loadFromData(svg, "SVG")
    if rotation:
        from PyQt6.QtGui import QTransform
        t = QTransform()
        t.translate(pix.width() / 2, pix.height() / 2)
        t.rotate(rotation)
        t.translate(-pix.width() / 2, -pix.height() / 2)
        pix = pix.transformed(t, Qt.TransformationMode.SmoothTransformation)
    return pix


# ─── Mic Button  ─────────────────────────────────────────────────────────────

class MicButton(QWidget):
    """A circular button with a glowing ring that toggles mic on/off."""
    clicked = pyqtSignal()

    # ring glow intensities for blink
    _IDLE_COLOR       = QColor(60, 60, 70)
    _LISTENING_COLOR  = QColor(239, 68, 68)     # red
    _PROCESSING_COLOR = QColor(234, 179, 8)     # yellow
    _SPEAKING_COLOR   = QColor(59, 130, 246)    # blue

    SIZE = 44

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._state = "idle"
        self._glow_alpha = 0
        self._glow_dir = 1
        self._blink = True
        self._spin_angle = 0
        self._vol_frame = 0
        self._hovered = False

    def set_state(self, state: str):
        self._state = state
        self._glow_alpha = 0
        self.update()

    def tick(self):
        """Called by the animation timer to advance frame."""
        if self._state == "listening":
            self._glow_alpha = min(255, max(60, self._glow_alpha + self._glow_dir * 25))
            if self._glow_alpha >= 255 or self._glow_alpha <= 60:
                self._glow_dir *= -1
        elif self._state == "processing":
            self._spin_angle = (self._spin_angle + 18) % 360
        elif self._state == "speaking":
            self._vol_frame += 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy, r = self.SIZE // 2, self.SIZE // 2, (self.SIZE // 2) - 2

        # ── Background circle ──────────────────────────────────────────────
        if self._state == "idle":
            base_color = QColor(40, 42, 54) if not self._hovered else QColor(60, 62, 74)
        elif self._state == "listening":
            base_color = QColor(80, 20, 20)
        elif self._state == "processing":
            base_color = QColor(60, 50, 10)
        elif self._state == "speaking":
            base_color = QColor(15, 40, 80)
        else:
            base_color = QColor(40, 42, 54)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(base_color))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # ── Outer glow ring ────────────────────────────────────────────────
        ring_color = self._ring_color()
        if ring_color:
            pen = QPen(ring_color, 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # ── Icon ───────────────────────────────────────────────────────────
        if self._state == "processing":
            pix = make_pixmap("loader", "#eab308", 20, self._spin_angle)
        elif self._state == "listening":
            alpha = self._glow_alpha
            col = f"#{alpha:02x}4444" if alpha < 255 else "#ef4444"
            pix = make_pixmap("mic", col, 20)
        elif self._state == "speaking":
            vol_icons = ["volume1", "volume2", "volume3"]
            pix = make_pixmap(vol_icons[self._vol_frame % 3], "#3b82f6", 20)
        else:
            # idle — show mic (white or mic_off if offline)
            col = "white" if self._hovered else "#a1a1aa"
            pix = make_pixmap("mic", col, 20)

        # center the pixmap
        px = cx - pix.width() // 2
        py = cy - pix.height() // 2
        p.drawPixmap(px, py, pix)
        p.end()

    def _ring_color(self):
        if self._state == "listening":
            c = QColor(self._LISTENING_COLOR)
            c.setAlpha(self._glow_alpha)
            return c
        elif self._state == "processing":
            return QColor(self._PROCESSING_COLOR)
        elif self._state == "speaking":
            return QColor(self._SPEAKING_COLOR)
        elif self._hovered and self._state == "idle":
            return QColor(90, 90, 110)
        return None

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)


# ─── Small icon button ────────────────────────────────────────────────────────

class IconButton(QWidget):
    clicked = pyqtSignal()

    # States: idle | hover | pressed | active | disabled
    # idle/hover colors are overridden per-instance via enabled_icon_color
    IDLE_BG      = QColor(255, 255, 255, 18)
    HOVER_BG     = QColor(255, 255, 255, 38)
    PRESSED_BG   = QColor(255, 255, 255, 60)
    ACTIVE_BG    = QColor(99, 102, 241, 60)
    ACTIVE_ICON  = "#a5b4fc"
    ACTIVE_RING  = QColor(99, 102, 241, 200)
    DISABLED_ALPHA = 0.30
    RING_WIDTH   = 1.5
    RADIUS       = 9
    SIZE         = 32

    def __init__(self, icon_name: str, tooltip: str = "",
                 enabled_icon_color: str = "#d1d5db",
                 disabled_icon_color: str = "#d1d5db",
                 parent=None):
        super().__init__(parent)
        self.icon_name             = icon_name
        self._enabled_icon_color   = enabled_icon_color   # e.g. yellow for bulb
        self._disabled_icon_color  = disabled_icon_color  # always white/grey
        self._is_active  = False
        self._is_enabled = True
        self._hovered    = False
        self._pressed    = False
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setToolTip(tooltip)
        self._update_cursor()

    # ── Public state API ──────────────────────────────────────────────────────

    def set_active(self, active: bool):
        self._is_active = active
        self.update()

    def set_enabled_state(self, enabled: bool):
        self._is_enabled = enabled
        self._update_cursor()
        self.update()

    def _update_cursor(self):
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if self._is_enabled
            else Qt.CursorShape.ForbiddenCursor
        )

    # ── Visual state resolver ─────────────────────────────────────────────────

    def _icon_color(self, vs: str) -> str:
        if vs == "active":   return self.ACTIVE_ICON
        if vs == "hover":    return "#ffffff"
        if vs == "pressed":  return "#ffffff"
        if vs == "disabled": return self._disabled_icon_color
        return self._enabled_icon_color  # idle

    def _visual_state(self) -> str:
        if not self._is_enabled:
            return "disabled"
        if self._pressed:
            return "pressed"
        if self._is_active:
            return "active"
        if self._hovered:
            return "hover"
        return "idle"

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        vs = self._visual_state()
        cx, cy = self.SIZE // 2, self.SIZE // 2

        # Apply global opacity for disabled state
        if vs == "disabled":
            p.setOpacity(self.DISABLED_ALPHA)

        # Background bubble
        bg_map = {
            "idle":    self.IDLE_BG,
            "hover":   self.HOVER_BG,
            "pressed": self.PRESSED_BG,
            "active":  self.ACTIVE_BG,
            "disabled": None,
        }
        bg = bg_map.get(vs)
        if bg:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(bg))
            p.drawRoundedRect(1, 1, self.SIZE - 2, self.SIZE - 2, self.RADIUS, self.RADIUS)

        # Active ring
        if vs == "active":
            pen = QPen(self.ACTIVE_RING)
            pen.setWidthF(self.RING_WIDTH)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(1, 1, self.SIZE - 2, self.SIZE - 2, self.RADIUS, self.RADIUS)

        # Icon — color driven by _icon_color()
        pix = make_pixmap(self.icon_name, self._icon_color(vs), 16)
        p.drawPixmap(cx - 8, cy - 8, pix)
        p.end()

    # ── Events ────────────────────────────────────────────────────────────────

    def enterEvent(self, e):
        if self._is_enabled:
            self._hovered = True
            self.update()

    def leaveEvent(self, e):
        self._hovered = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_enabled:
            self._pressed = True
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_enabled:
            self._pressed = False
            self.update()
            if self.rect().contains(event.pos()):
                self.clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


# ─── WebSocket command sender ─────────────────────────────────────────────────

active_websocket = None

async def send_command(cmd: str):
    global active_websocket
    if active_websocket is not None:
        try:
            await active_websocket.send(json.dumps({"type": cmd}))
        except Exception as e:
            print(f"WS Send Error: {e}")


# ─── Drop Zone Window ─────────────────────────────────────────────────────────

class DropZoneWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(80, 80)
        
        layout = QVBoxLayout(self)
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load a big X icon
        self.idle_pixmap = make_pixmap("x", "#9ca3af", 32)
        self.hover_pixmap = make_pixmap("x", "#ef4444", 38) # Red and bigger
        
        self.icon_label.setPixmap(self.idle_pixmap)
        layout.addWidget(self.icon_label)
        self.hide()
        
    def set_hover(self, hovered: bool):
        if hovered:
            self.icon_label.setPixmap(self.hover_pixmap)
        else:
            self.icon_label.setPixmap(self.idle_pixmap)


# ─── Main Overlay Window ──────────────────────────────────────────────────────

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
        
        self.drop_zone = DropZoneWindow()
        screen = QApplication.primaryScreen().geometry()
        self.drop_zone.move(screen.width() // 2 - self.drop_zone.width() // 2, 0)
        
        self.initUI()

        self.update_status_signal.connect(self._on_status)
        self.update_state_signal.connect(self._on_state)
        self.show_card_signal.connect(self._show_card)
        self.update_settings_signal.connect(self._on_settings_update)

        # Single timer drives all animations (60 fps feel at 80ms)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._tick)
        self.anim_timer.start(80)

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


        # Replay: white when enabled, dim white when disabled
        self.replay_btn = IconButton(
            "rotate_ccw", "Replay last response",
            enabled_icon_color="#e5e7eb",   # white
            disabled_icon_color="#e5e7eb",  # same — opacity handles disabled look
        )
        self.replay_btn.clicked.connect(self._on_replay_clicked)
        pill_layout.addWidget(self.replay_btn)

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

    def _on_state(self, state: str):
        self.current_state = state
        self.mic_btn.set_state(state)
        is_idle = state in ("idle", "error")

        # Enable replay only when ACE is idle
        self.replay_btn.set_enabled_state(is_idle)

        if state == "listening":
            self._last_transcript = ""
            self.status_label.setText("Listening...")
            self.sub_label.setText("Click mic to stop  ·  Speak now")
            self.status_label.setStyleSheet("color: #f87171;")
            self._set_pill_accent("#ef4444")
            self._hide_card()  # Auto-hide card when a new command starts
        elif state == "processing":
            self.status_label.setText(self._last_transcript if self._last_transcript else "Processing...")
            self.sub_label.setText("Executing your command")
            self.status_label.setStyleSheet("color: #fbbf24;")
            self._set_pill_accent("#eab308")
            self._hide_card()  # Auto-hide card when a new command starts
        elif state == "speaking":
            self.status_label.setText(self._last_transcript if self._last_transcript else "Speaking...")
            self.sub_label.setText("ACE is responding")
            self.status_label.setStyleSheet("color: #60a5fa;")
            self._set_pill_accent("#3b82f6")
        else:
            if self._last_transcript:
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
            if self.current_state in ("processing", "speaking", "idle"):
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


# ─── WebSocket client ─────────────────────────────────────────────────────────

async def websocket_client(overlay: OverlayApp):
    global active_websocket
    import os
    port = os.environ.get("BACKEND_PORT", "8000")
    uri = f"ws://127.0.0.1:{port}/ws"
    while True:
        try:
            async with websockets.connect(uri) as ws:
                active_websocket = ws
                overlay.update_status_signal.emit("Connected")
                overlay.update_state_signal.emit("idle")
                
                # Fetch initial settings
                try:
                    import urllib.request
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/settings") as response:
                        settings_data = json.loads(response.read().decode())
                        overlay.update_settings_signal.emit(settings_data)
                except Exception as e:
                    print(f"Failed to fetch initial settings: {e}")

                async for message in ws:
                    try:
                        data = json.loads(message)
                        etype = data.get("event", "")
                        payload = data.get("data", {})

                        if etype == "pipeline_state":
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

        except Exception:
            active_websocket = None
            overlay.update_status_signal.emit("Reconnecting...")
            overlay.update_state_signal.emit("idle")
            await asyncio.sleep(2)


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    overlay = OverlayApp()
    overlay.show()

    loop.create_task(websocket_client(overlay))
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
