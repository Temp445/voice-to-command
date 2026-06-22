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

class DropZoneWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(180, 180)
        self._hovered = False
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load a big X icon
        self.idle_pixmap = make_pixmap("x", "#9ca3af", 48)
        self.hover_pixmap = make_pixmap("x", "#ef4444", 64) # Red and bigger
        
        self.icon_label.setPixmap(self.idle_pixmap)
        layout.addWidget(self.icon_label)
        
        self.text_label = QLabel("Drop to Close")
        self.text_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.text_label.setStyleSheet("color: #9ca3af; background: transparent;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)
        
        self.hide()
        
    def set_hover(self, hovered: bool):
        self._hovered = hovered
        if hovered:
            self.icon_label.setPixmap(self.hover_pixmap)
            self.text_label.setStyleSheet("color: #ef4444; background: transparent;")
        else:
            self.icon_label.setPixmap(self.idle_pixmap)
            self.text_label.setStyleSheet("color: #9ca3af; background: transparent;")
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._hovered:
            p.setBrush(QBrush(QColor(239, 68, 68, 60))) # Light red background
            pen = QPen(QColor(239, 68, 68, 200), 3, Qt.PenStyle.DashLine)
        else:
            p.setBrush(QBrush(QColor(24, 24, 32, 220))) # Dark semi-transparent
            pen = QPen(QColor(156, 163, 175, 150), 2, Qt.PenStyle.DashLine)
            
        p.setPen(pen)
        p.drawRoundedRect(2, 2, self.width() - 4, self.height() - 4, 24, 24)
        p.end()

