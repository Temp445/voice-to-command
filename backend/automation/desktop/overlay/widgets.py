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
    "stop": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="{c}" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="2" ry="2"/></svg>',
    "pin": b'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" x2="12" y1="17" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/></svg>',
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

