"""Colours and marks of the Android app (res/values/colors.xml, drawable/ic_stat_dog.xml, design/logo.svg)."""
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

BG = QColor("#12241F")
SURFACE = QColor("#183029")
SURFACE_HI = QColor("#21403A")
LINE = QColor("#2E544B")
GOLD = QColor("#E7B55C")
GOLD_DARK = QColor("#B9832F")
CREAM = QColor("#F6EBD6")
MUTED = QColor("#8FA69E")
RED = QColor("#E4572E")
GREEN = QColor("#6FCF97")
BLUE = QColor("#5AB0F2")

HERE = Path(__file__).resolve().parent
_LOGO = [HERE / "res" / "logo.svg", HERE.parent.parent / "design" / "logo.svg"]

# the head of the mark (ic_stat_dog.xml), viewport 62 x 62 after the translation
_DOG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 62 62"><g transform="translate(-28.7 -28)">'
        '<path fill="{c}" d="M33.5 84 C32.5 74 32 66 33.5 58 C34 50 35.5 43 40 37.5 C44.5 32 51 29.5 57.5 30.5 '
        'C62 31.2 65.5 33.5 67.5 37 C69 39.6 71.5 41 75 41.6 C79.5 42.4 83.5 43.4 85.6 45.6 C87.4 47.5 87.3 50.3 '
        '85.6 52 C84.6 53 83.2 53.6 81.8 53.8 C82.6 55.2 82.2 57 80.6 57.8 C76.5 59.8 71 60.6 66.5 60.4 '
        'C63.6 60.3 61.6 61.6 61 64.4 C60.2 68.4 61.4 73 63.6 77.5 C64.8 80 65.6 82 66 84 C58 89 42 89 33.5 84Z"/>'
        '</g></svg>')
_dog_cache = {}


def draw_dog(p, center, size, color):
    key = color.name()
    r = _dog_cache.get(key)
    if r is None:
        r = _dog_cache[key] = QSvgRenderer(QByteArray(_DOG.format(c=key).encode()))
    r.render(p, QRectF(center.x() - size / 2, center.y() - size / 2, size, size))


def logo_icon():
    icon = QIcon()
    for path in _LOGO:
        if path.exists():
            r = QSvgRenderer(str(path))
            for s in (16, 24, 32, 48, 64, 128, 256):
                pm = QPixmap(s, s)
                pm.fill(QColor(0, 0, 0, 0))
                p = QPainter(pm)
                r.render(p)
                p.end()
                icon.addPixmap(pm)
            break
    return icon


STYLE = f"""
* {{ color: {CREAM.name()}; }}
QMainWindow, QDialog, QWidget#page {{ background: {BG.name()}; }}
QLabel#muted, QLabel.muted {{ color: {MUTED.name()}; }}
QFrame#card {{ background: {SURFACE.name()}; border: 1px solid {LINE.name()}; border-radius: 10px; }}
QLabel#tileLabel {{ color: {MUTED.name()}; font-size: 9pt; }}
QLabel#tileValue {{ font-size: 13pt; font-weight: 600; }}
QLabel#big {{ font-size: 22pt; font-weight: 700; color: {GOLD.name()}; }}
QLabel#head {{ font-size: 15pt; font-weight: 700; }}
QPushButton {{ background: {SURFACE_HI.name()}; border: 1px solid {LINE.name()}; border-radius: 8px;
              padding: 6px 14px; }}
QPushButton:hover {{ border-color: {GOLD.name()}; }}
QPushButton:disabled {{ color: {MUTED.name()}; }}
QPushButton#primary {{ background: {GOLD.name()}; color: {BG.name()}; font-weight: 600; border: none; }}
QPushButton#danger {{ color: {RED.name()}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {MUTED.name()}; padding: 8px 18px; font-size: 11pt;
               border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {GOLD.name()}; border-bottom: 2px solid {GOLD.name()}; }}
QComboBox, QLineEdit, QListWidget {{ background: {SURFACE.name()}; border: 1px solid {LINE.name()};
               border-radius: 6px; padding: 4px 6px; }}
QComboBox QAbstractItemView {{ background: {SURFACE.name()}; selection-background-color: {SURFACE_HI.name()}; }}
QListWidget::item:selected {{ background: {SURFACE_HI.name()}; }}
QMenu {{ background: {SURFACE.name()}; border: 1px solid {LINE.name()}; }}
QMenu::item:selected {{ background: {SURFACE_HI.name()}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QToolTip {{ background: {SURFACE.name()}; color: {CREAM.name()}; border: 1px solid {LINE.name()}; }}
"""
