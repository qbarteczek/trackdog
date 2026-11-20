"""Compass and speed chart (CompassView.kt and SpeedChartView in TrailView.kt)."""
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from . import theme
from .fmt import FAST_KMH


class Tile(QFrame):
    """a card with a small label and a value"""

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        self.label = QLabel(label)
        self.label.setObjectName("tileLabel")
        self.value = QLabel("—")
        self.value.setObjectName("tileValue")
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.label)
        lay.addWidget(self.value)

    def set(self, text):
        self.value.setText(text)


class Compass(QWidget):
    """North is up (a computer has no compass); the dog's head on the rim shows the direction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bearing = None
        self.title = "—"
        self.subtitle = ""
        self.alarm = False
        self.setMinimumSize(220, 220)

    def set(self, bearing, title, subtitle, alarm=False):
        self.bearing, self.title, self.subtitle, self.alarm = bearing, title, subtitle, alarm
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        r = min(self.width(), self.height()) / 2 - 16
        if r <= 0:
            return
        accent = theme.RED if self.alarm else theme.GOLD
        c = QPointF(cx, cy)
        p.setPen(QPen(accent, 3))
        p.setBrush(theme.SURFACE)
        p.drawEllipse(c, r, r)
        p.setPen(QPen(theme.LINE, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, r * 0.62, r * 0.62)
        for deg in range(0, 360, 5):
            major = deg % 30 == 0
            ln = 12 if deg % 90 == 0 else 9 if major else 4
            p.setPen(QPen(accent if major else theme.LINE, 2 if major else 1.2))
            a = math.radians(deg)
            sx, sy = math.sin(a), -math.cos(a)
            p.drawLine(QPointF(cx + sx * (r - 5), cy + sy * (r - 5)), QPointF(cx + sx * (r - 5 - ln), cy + sy * (r - 5 - ln)))
        f = QFont(self.font())
        f.setPointSizeF(12)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        for i, letter in enumerate("NESW"):
            a = math.radians(i * 90)
            pos = QPointF(cx + math.sin(a) * (r - 30), cy - math.cos(a) * (r - 30))
            p.setPen(theme.RED if i == 0 else theme.MUTED)
            p.drawText(QRectF(pos.x() - 15, pos.y() - 12, 30, 24), Qt.AlignmentFlag.AlignCenter, letter)

        if self.bearing is not None:
            b = self.bearing
            glow = QColor(accent)
            glow.setAlpha(46)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawPie(QRectF(cx - r, cy - r, 2 * r, 2 * r), int((90 - b - 14) * 16), 28 * 16)
            p.save()
            p.translate(cx, cy)
            p.rotate(b)
            path = QPainterPath(QPointF(0, -r - 3))
            path.lineTo(-9, -r + 15)
            path.lineTo(0, -r + 10)
            path.lineTo(9, -r + 15)
            path.closeSubpath()
            p.setBrush(accent)
            p.drawPath(path)
            p.restore()
            a = math.radians(b)
            h = QPointF(cx + math.sin(a) * r * 0.78, cy - math.cos(a) * r * 0.78)
            hs = min(15, r * 0.12)
            p.setPen(QPen(accent, 1.5))
            p.setBrush(theme.SURFACE)
            p.drawEllipse(h, hs + 6, hs + 6)
            theme.draw_dog(p, h, hs * 2, accent)

        f = QFont(self.font())
        f.setWeight(QFont.Weight.Light)
        f.setPixelSize(int(min(r * 0.34, 48)))
        p.setFont(f)
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(self.title)
        if w > r * 1.1:
            f.setPixelSize(max(10, int(f.pixelSize() * r * 1.1 / w)))
            p.setFont(f)
        p.setPen(theme.CREAM)
        p.drawText(QRectF(cx - r, cy - r * 0.3, 2 * r, r * 0.5), Qt.AlignmentFlag.AlignCenter, self.title)
        f = QFont(self.font())
        f.setPointSizeF(9.5)
        p.setFont(f)
        p.setPen(theme.RED if self.alarm else theme.MUTED)
        p.drawText(QRectF(cx - r * 0.75, cy + r * 0.2, 1.5 * r, r * 0.25), Qt.AlignmentFlag.AlignCenter, self.subtitle)
        p.end()


class SpeedChart(QWidget):
    """Speed over the time of the day's trail."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.setMinimumHeight(110)

    def set(self, points):
        self.points = points
        self.update()

    def paintEvent(self, ev):
        pts = [p for p in self.points if p.speed_kmh is not None]
        if len(pts) < 2:
            return
        t0, t1 = pts[0].r.time, pts[-1].r.time
        if t1 <= t0:
            return
        top = max(8.0, min(max(p.speed_kmh for p in pts), 60.0) * 1.15)
        left, right = 12, self.width() - 12
        bottom, top_y = self.height() - 18, 16

        def x(t):
            return left + (right - left) * (t - t0) / (t1 - t0)

        def y(v):
            return bottom - (bottom - top_y) * (min(v, top) / top)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(theme.LINE, 1))
        p.drawLine(QPointF(left, y(FAST_KMH)), QPointF(right, y(FAST_KMH)))   # the "running" threshold
        p.drawLine(QPointF(left, bottom), QPointF(right, bottom))
        area = QPainterPath(QPointF(x(t0), bottom))
        for pt in pts:
            area.lineTo(x(pt.r.time), y(pt.speed_kmh))
        area.lineTo(x(t1), bottom)
        area.closeSubpath()
        fill = QColor(theme.GOLD)
        fill.setAlpha(45)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawPath(area)
        line = QPainterPath(QPointF(x(pts[0].r.time), y(pts[0].speed_kmh)))
        for pt in pts[1:]:
            line.lineTo(x(pt.r.time), y(pt.speed_kmh))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(theme.GOLD, 2))
        p.drawPath(line)
        p.setPen(theme.MUTED)
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        p.drawText(QPointF(left, self.height() - 4), time.strftime("%H:%M", time.localtime(t0 / 1000)))
        p.drawText(QPointF(left, 11), "km/h")
        end = time.strftime("%H:%M", time.localtime(t1 / 1000))
        p.drawText(QPointF(right - p.fontMetrics().horizontalAdvance(end), self.height() - 4), end)
        p.end()
