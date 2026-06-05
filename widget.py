"""
widget.py
Main frameless always-on-top widget — professional dark theme.
Uses QStackedWidget so both views are always parented (no deletion bug).
"""

import math
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QApplication,
    QStackedWidget,
    QLineEdit,
    QSlider,
)
from PyQt5.QtCore import Qt, QPoint, QSettings, QTimer, pyqtSlot, pyqtSignal, QRectF
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QFont, QTransform

from network_monitor import NetworkMonitor
from data_store import DataStore
from simple_view import SimpleView
from advanced_view import AdvancedView
from hardware_monitor import HardwareSampler


_SETTINGS_ORG = "net-widget"
_SETTINGS_APP = "NetWidget"


def _load_qss() -> str:
    p = Path(__file__).parent / "style.qss"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _tray_icon() -> QPixmap:
    px = QPixmap(32, 32)
    px.fill(Qt.GlobalColor.transparent)  # type: ignore  # type: ignore # pyre-ignore
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)  # type: ignore  # type: ignore # pyre-ignore
    p.setBrush(QColor(0, 255, 180, 210))
    p.drawEllipse(5, 5, 22, 22)
    p.end()
    return px


# ── Animated Logo ────────────────────────────────────────────────────────────
BUTTON_COLORS = {
    "Simple": ("0, 255, 180", "#00ffb4"),
    "Advanced": ("167, 139, 250", "#a78bfa"),
    "MO": ("6, 182, 212", "#06b6d4"),
    "IO": ("217, 70, 239", "#d946ef"),
    "Win": ("59, 130, 246", "#3b82f6"),
    "TOP": ("6, 182, 212", "#06b6d4"),
    "LOCK": ("249, 115, 22", "#f97316"),
    "RESETS": ("236, 72, 153", "#ec4899"),
    "SL": ("34, 197, 94", "#22c55e"),
    "SD": ("239, 68, 68", "#ef4444"),
    "SR": ("234, 179, 8", "#eab308"),
}


class ContentAreaWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ContentArea")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # 12% opacity green border
        border_color = QColor(57, 255, 20, 30)  # 30/255 = 11.7% ~ 12%
        bg_color = QColor(9, 11, 18)

        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        p.setBrush(bg_color)
        p.setPen(QPen(border_color, 1.0))
        p.drawRoundedRect(rect, 14.0, 14.0)
        p.end()


class AnimatedLogo(QWidget):
    icon_updated = pyqtSignal(QIcon)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 30)
        self._phase = 0.0
        self._phase_increment = 0.05
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)  # ~33 fps

    def set_speed(self, interval_ms: int):
        if interval_ms <= 0:
            interval_ms = 1000
        # Base interval is 1000ms => 0.05 increment
        self._phase_increment = 0.05 * (1000.0 / interval_ms)

    def _tick(self):
        self._phase += self._phase_increment
        if self._phase > 2 * math.pi:
            self._phase -= 2 * math.pi
        self.update()

        # Render to taskbar icon
        px = QPixmap(32, 32)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(5, 16)
        for i in range(5):
            h = math.sin(self._phase - i * 0.5) * 8 + 10
            alpha = int(abs(math.sin(self._phase - i * 0.5)) * 255)
            p.setPen(Qt.NoPen)  # type: ignore
            p.setBrush(QColor(0, 255, 180, alpha))
            p.drawRoundedRect(i * 5, int(-h / 2), 4, int(h), 2, 2)
        p.end()
        self.icon_updated.emit(QIcon(px))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Draw animated data bars
        p.translate(5, 15)
        for i in range(5):
            h = math.sin(self._phase - i * 0.5) * 6 + 8
            alpha = int(abs(math.sin(self._phase - i * 0.5)) * 255)
            p.setPen(Qt.NoPen)  # type: ignore
            p.setBrush(QColor(0, 255, 180, alpha))
            p.drawRoundedRect(i * 6, int(-h / 2), 4, int(h), 2, 2)
        p.end()


class Rotating3DText(QWidget):
    def __init__(self, text: str = "ATK", parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 30)
        self._text = text
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)  # ~33 fps

    def _tick(self):
        self._angle += 0.05
        if self._angle > 2 * math.pi:
            self._angle -= 2 * math.pi
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        font = QFont("Outfit", 14, QFont.Black)
        font.setPixelSize(18)
        p.setFont(font)

        cx = self.width() / 2
        cy = self.height() / 2

        cos_val = math.cos(self._angle)
        sin_val = math.sin(self._angle)

        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(self._text)
        th = fm.height()

        num_layers = 5
        for i in range(num_layers - 1, -1, -1):
            z_offset = i * 0.8
            x_layer = cx + (z_offset * sin_val)

            if i == 0:
                brightness = int(abs(cos_val) * 100) + 155
                color = QColor(0, 255, 180, brightness)
            else:
                color = QColor(0, 100, 70, 180 - i * 30)

            transform = QTransform()
            transform.translate(x_layer, cy)
            transform.scale(cos_val, 1.0)
            transform.shear(0.0, -0.08 * sin_val)
            transform.translate(-tw / 2, th / 3)

            if i == 0:
                brightness = int(abs(cos_val) * 100) + 155
                face_color = QColor(0, 255, 180, brightness)

                # Bevel Shadow (bottom-right offset)
                shadow_transform = QTransform(transform)
                shadow_transform.translate(0.8, 0.8)
                p.setTransform(shadow_transform)
                p.setPen(QColor(0, 70, 45, 220))
                p.drawText(0, 0, self._text)

                # Bevel Highlight (top-left offset)
                highlight_transform = QTransform(transform)
                highlight_transform.translate(-0.8, -0.8)
                p.setTransform(highlight_transform)
                p.setPen(QColor(255, 255, 255, 230))
                p.drawText(0, 0, self._text)

                # Main Face
                p.setTransform(transform)
                p.setPen(face_color)
                p.drawText(0, 0, self._text)
            else:
                color = QColor(0, 100, 70, 180 - i * 30)
                p.setTransform(transform)
                p.setPen(color)
                p.drawText(0, 0, self._text)


# ── Custom Vector QPixmaps for System Info Icons ─────────────────────────────
def get_cpu_pixmap() -> QPixmap:
    px = QPixmap(18, 18)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)

    color = QColor("#fbbf24")

    # Draw pins
    p.setPen(QPen(color, 1.0))
    for x in [5, 7, 9, 11, 13]:
        p.drawLine(x, 1, x, 2)
        p.drawLine(x, 15, x, 16)
    for y in [5, 7, 9, 11, 13]:
        p.drawLine(1, y, 2, y)
        p.drawLine(15, y, 16, y)

    # Draw chip substrate
    p.setPen(QPen(color, 1.2))
    p.setBrush(QColor(251, 191, 36, 30))
    p.drawRoundedRect(3, 3, 12, 12, 1, 1)

    # Draw silicon die (core)
    p.setPen(QPen(color, 0.8))
    p.setBrush(QColor(251, 191, 36, 120))
    p.drawRect(7, 7, 4, 4)

    p.end()
    return px


def get_gpu_pixmap() -> QPixmap:
    px = QPixmap(18, 18)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)

    color = QColor("#a78bfa")

    # PCIe bracket (left edge)
    p.setPen(QPen(color, 1.2))
    p.drawLine(1, 2, 1, 15)
    p.drawLine(0, 4, 1, 4)
    p.drawLine(0, 12, 1, 12)

    # Shroud
    p.setPen(QPen(color, 1.0))
    p.setBrush(QColor(167, 139, 250, 30))
    p.drawRoundedRect(2, 4, 14, 10, 1, 1)

    # Fan
    p.setBrush(QColor(167, 139, 250, 70))
    p.drawEllipse(7, 7, 4, 4)
    p.drawLine(9, 7, 9, 11)
    p.drawLine(7, 9, 11, 9)

    # PCIe gold fingers (bottom connector)
    for x in range(4, 15, 2):
        p.drawLine(x, 15, x, 15)

    p.end()
    return px


def get_ram_pixmap() -> QPixmap:
    px = QPixmap(18, 18)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)

    color = QColor("#00ffb4")

    # RAM stick PCB (horizontal)
    p.setPen(QPen(color, 1.0))
    p.setBrush(QColor(0, 255, 180, 25))
    p.drawRoundedRect(1, 6, 16, 6, 1, 1)

    # Chips
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRect(3, 8, 2, 3)
    p.drawRect(7, 8, 2, 3)
    p.drawRect(11, 8, 2, 3)

    # Pins
    p.setPen(QPen(color, 0.8))
    for x in range(2, 16, 2):
        if x != 9:  # notch
            p.drawLine(x, 13, x, 14)

    p.end()
    return px


def get_hdd_pixmap() -> QPixmap:
    px = QPixmap(18, 18)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)

    color = QColor("#ec4899")

    # Outer drive casing
    p.setPen(QPen(color, 1.2))
    p.setBrush(QColor(236, 72, 153, 25))
    p.drawRoundedRect(3, 2, 12, 14, 2, 2)

    # Inner platter
    p.setPen(QPen(color, 1.0))
    p.drawEllipse(5, 6, 8, 8)

    # Spindle hole
    p.setBrush(color)
    p.drawEllipse(8, 9, 2, 2)

    # Reader arm
    p.drawLine(12, 14, 9, 10)

    p.end()
    return px


def get_uptime_pixmap() -> QPixmap:
    px = QPixmap(18, 18)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)

    color = QColor("#60a5fa")

    # Outer ring
    p.setPen(QPen(color, 1.2))
    p.setBrush(QColor(96, 165, 250, 25))
    p.drawEllipse(3, 3, 12, 12)

    # Hands
    p.drawLine(9, 9, 9, 5)
    p.drawLine(9, 9, 12, 9)

    # Buttons
    p.setBrush(color)
    p.drawRect(8, 1, 2, 2)

    p.end()
    return px


# drive accent palette (cycles if more drives than colors)
_DRIVE_COLORS = ("#00ffb4", "#fbbf24", "#a78bfa", "#ff3c8c", "#60a5fa", "#f87171")


# ── System Info Bar ─────────────────────────────────────────────────────────────────────────────────────────
class _SysInfoBar(QWidget):
    drive_added = pyqtSignal()  # type: ignore

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background: rgba(255,255,255,0.02);"
            "border-top: 1px solid rgba(57,255,20,0.14);"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 5, 8, 5)
        root.setSpacing(3)

        def _icon_lbl(pixmap: QPixmap) -> QLabel:
            l = QLabel()
            l.setPixmap(pixmap)
            l.setStyleSheet(
                "background: transparent; border: none; padding-right: 1px;"
            )
            l.setAlignment(Qt.AlignCenter)  # type: ignore
            return l

        def _val(color: str, min_w: int = 54) -> QLabel:
            l = QLabel("—")
            l.setStyleSheet(
                f"color: {color}; font-size: 17px; font-weight: normal; "
                f"background: transparent; border: none; min-width: {min_w}px;"
            )
            return l

        def _dot() -> QLabel:
            l = QLabel("·")
            l.setStyleSheet(
                "color: rgba(255,255,255,0.20); font-size: 17px; "
                "background: transparent; border: none; padding: 0 4px;"
            )
            return l

        row1 = QHBoxLayout()
        row1.setSpacing(3)
        row1.setContentsMargins(0, 0, 0, 0)

        row1.addWidget(_icon_lbl(get_cpu_pixmap()))
        self._cpu_val = _val("#fbbf24")
        row1.addWidget(self._cpu_val)
        row1.addWidget(_dot())

        row1.addWidget(_icon_lbl(get_gpu_pixmap()))
        self._gpu_val = _val("#a78bfa")
        row1.addWidget(self._gpu_val)
        row1.addWidget(_dot())

        row1.addWidget(_icon_lbl(get_ram_pixmap()))
        self._ram_val = _val("#00ffb4")
        row1.addWidget(self._ram_val)
        row1.addWidget(_dot())

        row1.addWidget(_icon_lbl(get_hdd_pixmap()))
        self._hdd_val = _val("#ec4899")
        row1.addWidget(self._hdd_val)
        row1.addWidget(_dot())

        row1.addWidget(_icon_lbl(get_uptime_pixmap()))
        self._up_val = _val("#60a5fa", min_w=84)
        row1.addWidget(self._up_val)
        row1.addStretch()
        root.addLayout(row1)
        root.addSpacing(6)

        self._drive_container = QWidget()
        self._drive_container.setStyleSheet("background: transparent;")
        self._drives_layout = QGridLayout(self._drive_container)
        self._drives_layout.setContentsMargins(0, 0, 0, 0)
        self._drives_layout.setSpacing(2)
        self._drives_layout.setColumnStretch(0, 1)
        self._drives_layout.setColumnStretch(1, 1)
        root.addWidget(self._drive_container)

        self._drive_rows = {}

    def _get_or_create_drive_row(self, name: str):
        if name in self._drive_rows:
            return self._drive_rows[name]

        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(2, 0, 2, 0)
        row_lay.setSpacing(3)

        dot = QLabel("●")
        dot.setFixedWidth(12)
        dot.setStyleSheet(
            "color: rgba(255,255,255,0.18); font-size: 12px; background: transparent; border: none;"
        )
        row_lay.addWidget(dot)

        name_lbl = QLabel(name)
        name_lbl.setFixedWidth(30)
        name_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.60); font-size: 16px; font-weight: normal;"
            " background: transparent; border: none;"
        )
        row_lay.addWidget(name_lbl)

        read_arrow = QLabel("↓")
        read_arrow.setStyleSheet(
            "color: rgba(255, 255, 255, 0.25); font-size: 14px; background: transparent; border: none;"
        )
        read_arrow.setFixedWidth(12)
        row_lay.addWidget(read_arrow)

        read_lbl = QLabel("0B")
        read_lbl.setFixedWidth(60)
        read_lbl.setStyleSheet(
            "color: rgba(255, 255, 255, 0.25); font-size: 16px; font-weight: normal;"
            " background: transparent; border: none;"
        )
        row_lay.addWidget(read_lbl)

        write_arrow = QLabel("↑")
        write_arrow.setStyleSheet(
            "color: rgba(255, 255, 255, 0.25); font-size: 14px; background: transparent; border: none;"
        )
        write_arrow.setFixedWidth(12)
        row_lay.addWidget(write_arrow)

        write_lbl = QLabel("0B")
        write_lbl.setFixedWidth(60)
        write_lbl.setStyleSheet(
            "color: rgba(255, 255, 255, 0.25); font-size: 16px; font-weight: normal;"
            " background: transparent; border: none;"
        )
        row_lay.addWidget(write_lbl)

        idx = len(self._drive_rows)
        grid_row = idx // 2
        grid_col = idx % 2
        self._drives_layout.addWidget(row_w, grid_row, grid_col)
        self._drive_rows[name] = (
            row_w,
            name_lbl,
            read_lbl,
            write_lbl,
            dot,
            read_arrow,
            write_arrow,
        )

        n_grid_rows = math.ceil(len(self._drive_rows) / 2)
        new_h = 56 + 6 + n_grid_rows * 22
        self.setFixedHeight(new_h)
        self.drive_added.emit()  # type: ignore

        return self._drive_rows[name]

    @staticmethod
    def _fmt(bps: float) -> str:
        if bps >= 1_048_576:
            return f"{bps / 1_048_576:.1f}M"
        if bps >= 1_024:
            return f"{bps / 1_024:.0f}K"
        return f"{int(bps)}B"

    @staticmethod
    def _fmt_uptime(secs: float) -> str:
        s = int(secs)
        d, rem = divmod(s, 86400)
        h, rem = divmod(rem, 3600)
        m, s2 = divmod(rem, 60)
        if d:
            return f"{d}d {h}h {m}m"
        return f"{h}h {m:02d}m" if h else f"{m}m {s2:02d}s"

    def update_sysinfo(
        self,
        cpu: float | None,
        gpu: float | None,
        ram: float | None,
        hdd: float | None,
        uptime: float,
        disk_speeds: dict,
    ):
        self._cpu_val.setText(f"{cpu:.0f}%" if cpu is not None else "N/A")
        self._gpu_val.setText(f"{gpu:.0f}%" if gpu is not None else "N/A")
        self._ram_val.setText(f"{ram:.0f}%" if ram is not None else "N/A")
        self._hdd_val.setText(f"{hdd:.0f}%" if hdd is not None else "N/A")
        self._up_val.setText(self._fmt_uptime(uptime))

        for name, (rbps, wbps) in disk_speeds.items():
            _, _name_lbl, read_lbl, write_lbl, dot, read_arrow, write_arrow = (
                self._get_or_create_drive_row(name)
            )

            if rbps > 0:
                read_lbl.setText(self._fmt(rbps))
                read_lbl.setStyleSheet(
                    "color: #39ff14; font-size: 16px; font-weight: normal; background: transparent; border: none;"
                )
                read_arrow.setStyleSheet(
                    "color: #39ff14; font-size: 14px; background: transparent; border: none;"
                )
            else:
                read_lbl.setText("0B")
                read_lbl.setStyleSheet(
                    "color: rgba(255, 255, 255, 0.25); font-size: 16px; font-weight: normal; background: transparent; border: none;"
                )
                read_arrow.setStyleSheet(
                    "color: rgba(255, 255, 255, 0.25); font-size: 14px; background: transparent; border: none;"
                )

            if wbps > 0:
                write_lbl.setText(self._fmt(wbps))
                write_lbl.setStyleSheet(
                    "color: #ff3333; font-size: 16px; font-weight: normal; background: transparent; border: none;"
                )
                write_arrow.setStyleSheet(
                    "color: #ff3333; font-size: 14px; background: transparent; border: none;"
                )
            else:
                write_lbl.setText("0B")
                write_lbl.setStyleSheet(
                    "color: rgba(255, 255, 255, 0.25); font-size: 16px; font-weight: normal; background: transparent; border: none;"
                )
                write_arrow.setStyleSheet(
                    "color: rgba(255, 255, 255, 0.25); font-size: 14px; background: transparent; border: none;"
                )

            if rbps > 0 and wbps > 0:
                dot.setStyleSheet(
                    "color: #fbbf24; font-size: 12px; background: transparent; border: none;"
                )
            elif rbps > 0:
                dot.setStyleSheet(
                    "color: #39ff14; font-size: 12px; background: transparent; border: none;"
                )
            elif wbps > 0:
                dot.setStyleSheet(
                    "color: #ff3333; font-size: 12px; background: transparent; border: none;"
                )
            else:
                dot.setStyleSheet(
                    "color: rgba(255,255,255,0.18); font-size: 12px; background: transparent; border: none;"
                )

    def reset(self):
        self._cpu_val.setText("0%")
        self._gpu_val.setText("0%")
        self._ram_val.setText("0%")
        self._hdd_val.setText("0%")
        self._up_val.setText("0s")
        for name, (
            _,
            _name_lbl,
            read_lbl,
            write_lbl,
            dot,
            read_arrow,
            write_arrow,
        ) in self._drive_rows.items():
            read_lbl.setText("0B")
            read_lbl.setStyleSheet(
                "color: rgba(255, 255, 255, 0.25); font-size: 16px; font-weight: normal; background: transparent; border: none;"
            )
            read_arrow.setStyleSheet(
                "color: rgba(255, 255, 255, 0.25); font-size: 14px; background: transparent; border: none;"
            )
            write_lbl.setText("0B")
            write_lbl.setStyleSheet(
                "color: rgba(255, 255, 255, 0.25); font-size: 16px; font-weight: normal; background: transparent; border: none;"
            )
            write_arrow.setStyleSheet(
                "color: rgba(255, 255, 255, 0.25); font-size: 14px; background: transparent; border: none;"
            )
            dot.setStyleSheet(
                "color: rgba(255,255,255,0.18); font-size: 12px; background: transparent; border: none;"
            )


# ─────────────────────────────────────────────────────────────────────────────
class TitleBar(QWidget):
    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self._drag: QPoint | None = None
        self.setObjectName("TitleBar")
        self.setFixedHeight(46)
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 8, 0)
        lay.setSpacing(6)

        self.logo = AnimatedLogo()
        self.logo.setObjectName("AppLogo")
        lay.addWidget(self.logo)
        lay.addSpacing(15)

        # 1. Dots widget on the left
        self._dots = {}
        self._dots_widget = QWidget()
        d_lay = QHBoxLayout(self._dots_widget)
        d_lay.setContentsMargins(0, 0, 0, 0)
        d_lay.setSpacing(6)

        excluded = {"SL", "SD", "SR", "MO", "Win", "RESETS", "Simple", "Advanced"}
        for name, (_, hex_col) in BUTTON_COLORS.items():
            if name in excluded:
                continue
            l = QLabel()
            l.setFixedSize(6, 6)
            l.setStyleSheet("background: rgba(100, 100, 100, 0.4); border-radius: 3px;")
            l.setToolTip(name)
            self._dots[name] = l
            d_lay.addWidget(l)

        lay.addWidget(self._dots_widget)

        # 2. Stretch to push rotating text and window controls to the right
        lay.addStretch()

        # 3. Rotating "ATK" logo on the right
        title = Rotating3DText("ATK")
        title.setObjectName("AppTitle")
        lay.addWidget(title)

        lay.addSpacing(10)

        # 4. Window controls
        min_b = QPushButton("–")
        min_b.setObjectName("WinBtn")
        min_b.setCursor(Qt.PointingHandCursor)  # type: ignore
        min_b.clicked.connect(self._win.showMinimized)  # type: ignore

        close_b = QPushButton("✕")
        close_b.setObjectName("WinBtn")
        close_b.setProperty("role", "close")
        close_b.setCursor(Qt.PointingHandCursor)  # type: ignore
        close_b.clicked.connect(self._win.close_app)  # type: ignore

        lay.addWidget(min_b)
        lay.addWidget(close_b)

    def mousePressEvent(self, a0):
        if a0.button() == Qt.LeftButton and not self._win.position_locked:  # type: ignore  # type: ignore # pyre-ignore
            self._drag = a0.globalPos() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, a0):
        if (
            self._drag
            and a0.buttons() & Qt.LeftButton
            and not self._win.position_locked
        ):  # type: ignore  # type: ignore # pyre-ignore
            self._win.move(a0.globalPos() - self._drag)

    def mouseReleaseEvent(self, a0):
        self._drag = None


# ─────────────────────────────────────────────────────────────────────────────
class NetWidget(QMainWindow):
    SW, SH = 520, 415  # Simple   size
    AW, AH = 460, 769  # Advanced size

    def __init__(self):
        super().__init__()
        self._mode = "simple"
        self._always_on_top = True  # default: on top
        self._pos_locked = False  # default: draggable
        self._store = DataStore()
        self._monitor = NetworkMonitor()
        self._last_recv = self._last_sent = 0

        self._setup_window()
        self._apply_qss()
        self._build_ui()
        self._setup_tray()

        # ── Hardware temp sampler (display: 0.1 s, sensor read: 1 s) ─
        self._hw = HardwareSampler(interval=1.0)  # sensor read stays at 1 s
        self._temp_timer = QTimer(self)
        self._temp_timer.setInterval(100)  # push cached value every 0.1 s
        self._temp_timer.timeout.connect(self._on_temp_tick)
        self._temp_timer.start()

        self._restore_pos()
        self._monitor.stats_updated.connect(self._on_stats)
        self._simple_view.reset_session.connect(self._on_reset_session)  # type: ignore
        self._simple_view.reset_all_time.connect(self._on_reset_all_time)  # type: ignore
        self._monitor.start()

    # ── Window ───────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowMinimizeButtonHint)  # type: ignore  # type: ignore # pyre-ignore
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # type: ignore  # type: ignore # pyre-ignore

        self.setWindowTitle("Net Monitor")

    def _apply_qss(self):
        qss = _load_qss()
        if qss:
            self.setStyleSheet(qss)

    def _build_ui(self):
        outer = QWidget()
        outer.setObjectName("MainWidget")
        self.setCentralWidget(outer)
        o_lay = QVBoxLayout(outer)
        o_lay.setContentsMargins(6, 6, 6, 6)
        o_lay.setSpacing(0)

        content = ContentAreaWidget()
        content.setObjectName("ContentArea")
        o_lay.addWidget(content)

        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(0)

        self._title_bar = TitleBar(self)
        c_lay.addWidget(self._title_bar)

        # Sync animated logo to window and tray icon
        self._title_bar.logo.icon_updated.connect(self._on_logo_icon_updated)

        # Stack — both views always parented, never destroyed
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        self._simple_view = SimpleView()
        self._advanced_view = AdvancedView()
        self._stack.addWidget(self._simple_view)  # 0
        self._stack.addWidget(self._advanced_view)  # 1
        self._stack.setCurrentIndex(0)
        c_lay.addWidget(self._stack)

        # ── Bottom Control Bar ──────────────────────────
        c_lay.addWidget(self._build_bottom_bar())
        self._sysinfo_bar.drive_added.connect(self._on_drive_added)

        self.setFixedSize(self.SW, self.SH)

    @pyqtSlot(QIcon)
    def _on_logo_icon_updated(self, icon: QIcon):
        self.setWindowIcon(icon)
        if hasattr(self, "_tray") and self._tray is not None:
            self._tray.setIcon(icon)

    def _update_dot(self, name: str, active: bool):
        dot = self._title_bar._dots.get(name)
        if dot:
            if active:
                hex_col = BUTTON_COLORS[name][1]
                dot.setStyleSheet(f"background: {hex_col}; border-radius: 3px;")
            else:
                dot.setStyleSheet(
                    "background: rgba(100, 100, 100, 0.4); border-radius: 3px;"
                )

    def _on_drive_added(self):
        """Grow the simple-mode window height to accommodate a new drive row."""
        n_drives = len(self._sysinfo_bar._drive_rows)
        n_rows = math.ceil(n_drives / 2)
        extra = 0
        if n_rows > 0:
            extra = 28 + (n_rows - 1) * 22

        self.SH = 415 + extra
        if self._mode == "simple":
            self.setFixedSize(self.SW, self.SH)

    def _build_bottom_bar(self) -> QWidget:
        container = QWidget()
        vlay = QVBoxLayout(container)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        def _make_btn(
            style_key, display_text, slot, checkable=False, checked=False, active=False
        ):
            b = QPushButton(display_text)
            b.setCursor(Qt.PointingHandCursor)  # type: ignore

            rgb, hex_col = BUTTON_COLORS[style_key]
            qss = (
                "QPushButton {"
                "  background: rgba(255,255,255,0.03);"
                "  color: rgba(255,255,255,0.60);"
                "  border: 1px solid rgba(255, 255, 255, 0.12);"
                "  border-radius: 0px;"
                "  font-size: 11px; font-weight: 600;"
                "  padding: 5px 6px;"
                "}"
                "QPushButton:hover {"
                f"  background: rgba({rgb}, 0.1);"
                "}"
                f'QPushButton:checked, QPushButton[active="true"] {{'
                f"  color: {hex_col};"
                f"  background: rgba({rgb}, 0.15);"
                f"  border: 1px solid {hex_col};"
                "}"
            )
            b.setStyleSheet(qss)
            if checkable:
                b.setCheckable(True)
                b.setChecked(checked)
                self._update_dot(style_key, checked)
                b.toggled.connect(lambda c, key=style_key: self._update_dot(key, c))  # type: ignore
                b.clicked.connect(slot)  # type: ignore
            else:
                b.setProperty("active", active)
                self._update_dot(style_key, active)
                b.clicked.connect(slot)  # type: ignore
            return b

        # ── System info bar (CPU%, GPU%, uptime, disk I/O) ────────────────
        self._sysinfo_bar = _SysInfoBar()
        vlay.addWidget(self._sysinfo_bar)

        # Row 1: System controls + utility
        r1 = QWidget()
        r1.setFixedHeight(46)
        r1.setStyleSheet(
            "QWidget {"
            "  background: transparent;"
            "  border-top: 1px solid rgba(57, 255, 20, 0.20);"
            "}"
        )
        l1 = QHBoxLayout(r1)
        l1.setContentsMargins(14, 4, 14, 4)
        l1.setSpacing(8)

        self._os_lock_btn = _make_btn("SL", "PC Lock", self._on_os_lock)
        self._shutdown_btn = _make_btn("SD", "Shutdown", self._on_shutdown)
        self._restart_btn = _make_btn("SR", "Restart", self._on_restart)
        self._mon_btn = _make_btn("MO", "Monitor Off", self._on_monitor_off)
        self._int_btn = _make_btn("IO", "Internet Off", self._on_internet_off)

        l1.addWidget(self._os_lock_btn)
        l1.addWidget(self._shutdown_btn)
        l1.addWidget(self._restart_btn)
        l1.addStretch()
        l1.addWidget(self._mon_btn)
        l1.addWidget(self._int_btn)

        vlay.addWidget(r1)

        # Row 2: Toggles & Inputs
        r2 = QWidget()
        r2.setFixedHeight(46)
        r2.setStyleSheet(
            "QWidget {"
            "  background: rgba(0,255,180,0.03);"
            "  border-bottom-left-radius: 14px;"
            "  border-bottom-right-radius: 14px;"
            "}"
        )
        l2 = QHBoxLayout(r2)
        l2.setContentsMargins(14, 4, 14, 4)
        l2.setSpacing(10)

        # Badge
        self._badge = QLabel("—")
        self._badge.setStyleSheet(
            "color: #00ff41; font-size: 10px; font-weight: normal; background: transparent; border: none;"
        )
        l2.addWidget(self._badge)

        l2.addStretch()

        # Opacity Slider
        lbl_op = QLabel("OPACITY")
        lbl_op.setStyleSheet(
            "color: rgba(255,255,255,0.70); font-size: 9px; font-weight: normal; background: transparent; border: none;"
        )
        l2.addWidget(lbl_op)

        self._opacity_slider = QSlider(Qt.Horizontal)  # type: ignore
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setFixedWidth(70)
        self._opacity_slider.setCursor(Qt.PointingHandCursor)  # type: ignore
        self._opacity_slider.setStyleSheet(
            "QSlider {"
            "  background: transparent;"
            "}"
            "QSlider::groove:horizontal {"
            "  background: rgba(255,255,255,0.08);"
            "  height: 4px;"
            "  border-radius: 2px;"
            "}"
            "QSlider::sub-page:horizontal {"
            "  background: #00ffb4;"
            "  border-radius: 2px;"
            "}"
            "QSlider::handle:horizontal {"
            "  background: #ffffff;"
            "  border: 1px solid #00ffb4;"
            "  width: 10px;"
            "  height: 10px;"
            "  margin-top: -3px;"
            "  margin-bottom: -3px;"
            "  border-radius: 5px;"
            "}"
            "QSlider::handle:horizontal:hover {"
            "  background: #00ffb4;"
            "}"
        )
        self._opacity_slider.valueChanged.connect(self._on_slider_opacity)  # type: ignore
        l2.addWidget(self._opacity_slider)

        # Interval Input
        lbl_int = QLabel("INTERVAL")
        lbl_int.setStyleSheet(
            "color: rgba(255,255,255,0.70); font-size: 9px; font-weight: normal; background: transparent; border: none;"
        )
        l2.addWidget(lbl_int)

        self._interval_input = QLineEdit("1000")
        self._interval_input.setFixedWidth(34)
        self._interval_input.setStyleSheet(
            "background: rgba(0,0,0,0.3); color: #00ffb4; border: 1px solid rgba(57,255,20,0.3); border-radius: 3px; font-size: 10px;"
        )
        self._interval_input.setAlignment(Qt.AlignCenter)  # type: ignore
        self._interval_input.returnPressed.connect(self._on_input_interval)  # type: ignore
        self._interval_input.textEdited.connect(self._on_interval_edited)  # type: ignore
        self._interval_input.editingFinished.connect(self._on_input_interval)  # type: ignore
        l2.addWidget(self._interval_input)

        # Toggles
        self._pin_btn = _make_btn(
            "TOP", "AOT", self._on_pin_toggled, checkable=True, checked=True
        )
        self._lock_btn = _make_btn(
            "LOCK", "LOCK", self._on_lock_toggled, checkable=True, checked=False
        )
        self._reset_btn = _make_btn("RESETS", "Reset", self._on_reset)

        l2.addWidget(self._pin_btn)
        l2.addWidget(self._lock_btn)
        l2.addWidget(self._reset_btn)

        vlay.addWidget(r2)
        return container

    def _set_interface(self, name: str):
        self._badge.setText(name if len(name) <= 18 else name[:16] + "…")

    def _update_mode_btns(self, mode: str):
        self._update_dot("Simple", mode == "simple")
        self._update_dot("Advanced", mode == "advanced")

    # ── Tray ─────────────────────────────────────────────────────────────

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(QIcon(_tray_icon()), self)
        self._tray.setToolTip("Net Monitor")
        m = QMenu()
        m.setStyleSheet(self.styleSheet())
        for txt, fn in [
            ("Show", self.show_widget),
            (None, None),
            ("Simple mode", lambda: self.set_mode("simple")),
            ("Advanced mode", lambda: self.set_mode("advanced")),
            (None, None),
            ("Exit", self.close_app),
        ]:
            if txt is None:
                m.addSeparator()
            else:
                a = QAction(txt, self)
                a.triggered.connect(fn)
                m.addAction(a)  # type: ignore
        self._tray.setContextMenu(m)
        self._tray.activated.connect(
            lambda r: self.show_widget() if r == QSystemTrayIcon.DoubleClick else None  # type: ignore  # type: ignore # pyre-ignore
        )
        self._tray.show()

    # ── Mode ─────────────────────────────────────────────────────────────

    def set_mode(self, mode: str):
        if self._mode == mode:
            return
        self._mode = mode
        self._update_mode_btns(mode)
        self._stack.setCurrentIndex(0 if mode == "simple" else 1)
        self._apply_size(mode)
        self._save()

    def _apply_size(self, mode: str):
        w, h = (self.SW, self.SH) if mode == "simple" else (self.AW, self.AH)
        self.setFixedSize(w, h)

    # ── Opacity ──────────────────────────────────────────────

    def _on_slider_opacity(self, val: int):
        self._apply_opacity(val)

    def _apply_opacity(self, pct: int):
        alpha = pct / 100.0
        self.setWindowOpacity(alpha)

    def _on_input_interval(self):
        try:
            v = int(self._interval_input.text())
            v = max(10, min(10000, v))
        except ValueError:
            v = 100
        self._interval_input.setText(str(v))
        self._monitor.interval = v / 1000.0
        self._hw.interval = v / 1000.0
        self._temp_timer.setInterval(v)
        self._title_bar.logo.set_speed(v)

    def _on_interval_edited(self, text: str):
        try:
            v = int(text)
            if 10 <= v <= 10000:
                self._monitor.interval = v / 1000.0
                self._hw.interval = v / 1000.0
                self._temp_timer.setInterval(v)
                self._title_bar.logo.set_speed(v)
        except ValueError:
            pass

    # ── Stats ─────────────────────────────────────────────────────────────

    @pyqtSlot(dict)
    def _on_stats(self, s: dict):
        self._last_recv = s["session_recv"]
        self._last_sent = s["session_sent"]
        self._set_interface(s["interface"])
        self._store.update_all_sessions(
            self._last_recv, self._last_sent, s["interface"]
        )

        # Adjust session statistics using baseline
        disp_recv = max(0, self._last_recv - self._store.this_session_baseline_recv)
        disp_sent = max(0, self._last_sent - self._store.this_session_baseline_sent)

        s_disp = dict(s)
        s_disp["session_recv"] = disp_recv
        s_disp["session_sent"] = disp_sent

        self._simple_view.update_stats(
            s_disp, self._store.all_sessions_recv, self._store.all_sessions_sent
        )
        self._advanced_view.update_stats(s_disp)

    @pyqtSlot()
    def _on_reset_session(self):
        self._store.reset_this_session(self._last_recv, self._last_sent)
        self._simple_view.update_stats(
            {
                "download_speed": 0.0,
                "upload_speed": 0.0,
                "session_recv": 0,
                "session_sent": 0,
            },
            self._store.all_sessions_recv,
            self._store.all_sessions_sent,
        )

    @pyqtSlot()
    def _on_reset_all_time(self):
        self._store.reset_all_sessions(
            self._last_recv, self._last_sent, self._monitor.interface_name
        )
        # Instantly update SimpleView so the UI reflects 0 immediately
        disp_recv = max(0, self._last_recv - self._store.this_session_baseline_recv)
        disp_sent = max(0, self._last_sent - self._store.this_session_baseline_sent)
        self._simple_view.update_stats(
            {
                "download_speed": 0.0,
                "upload_speed": 0.0,
                "session_recv": disp_recv,
                "session_sent": disp_sent,
            },
            0,
            0,
        )

        # 6. Instantly refresh AdvancedView UI to display 0s
        self._advanced_view.update_stats(
            {
                "download_speed": 0.0,
                "upload_speed": 0.0,
                "session_recv": 0,
                "session_sent": 0,
                "packets_recv": 0,
                "packets_sent": 0,
                "errin": 0,
                "errout": 0,
                "dropin": 0,
                "dropout": 0,
                "interface": self._monitor.interface_name,
                "dl_history": [],
                "ul_history": [],
            }
        )

        # 7. Reset CPU/GPU temperature values in SimpleView to 0
        self._simple_view.reset_temps()

    @pyqtSlot()
    def _on_reset(self):
        # 1. Reset This Session baseline in store
        self._store.reset_this_session(self._last_recv, self._last_sent)
        # 2. Reset All Sessions totals in store
        self._store.reset_all_sessions(
            self._last_recv, self._last_sent, self._monitor.interface_name
        )

        # 3. Reset AdvancedView peaks and averages
        self._advanced_view._peak_dl = self._advanced_view._peak_ul = 0.0
        self._advanced_view._count = self._advanced_view._sum_dl = (
            self._advanced_view._sum_ul
        ) = 0

        # 4. Clear monitor graph history
        self._monitor.dl_history.clear()
        self._monitor.ul_history.clear()

        # 5. Instantly refresh SimpleView UI to display 0s
        self._simple_view.update_stats(
            {
                "download_speed": 0.0,
                "upload_speed": 0.0,
                "session_recv": 0,
                "session_sent": 0,
            },
            0,
            0,
        )

        # 6. Instantly refresh AdvancedView UI to display 0s
        self._advanced_view.update_stats(
            {
                "download_speed": 0.0,
                "upload_speed": 0.0,
                "session_recv": 0,
                "session_sent": 0,
                "packets_recv": 0,
                "packets_sent": 0,
                "errin": 0,
                "errout": 0,
                "dropin": 0,
                "dropout": 0,
                "interface": self._monitor.interface_name,
                "dl_history": [],
                "ul_history": [],
            }
        )
        self._simple_view.reset_all()
        self._sysinfo_bar.reset()
        self._monitor.reset_counters()

    def _on_os_lock(self):
        try:
            import ctypes

            ctypes.windll.user32.LockWorkStation()
        except Exception as e:
            print(f"OS lock failed: {e}")

    def _on_shutdown(self):
        try:
            import subprocess

            subprocess.run(
                ["shutdown", "/s", "/t", "0"],
                capture_output=True,
                creationflags=0x08000000,
            )
        except Exception as e:
            print(f"Shutdown failed: {e}")

    def _on_restart(self):
        try:
            import subprocess

            subprocess.run(
                ["shutdown", "/r", "/t", "0"],
                capture_output=True,
                creationflags=0x08000000,
            )
        except Exception as e:
            print(f"Restart failed: {e}")

    def _on_monitor_off(self):
        try:
            import ctypes

            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        except Exception as e:
            print(f"Monitor off failed: {e}")

    def _on_internet_off(self):
        import subprocess

        # Toggle state based on current text
        if self._int_btn.text() == "Internet Off":
            subprocess.run(
                ["ipconfig", "/release"], capture_output=True, creationflags=0x08000000
            )
            self._int_btn.setText("Internet On")
            self._int_btn.setProperty("active", True)
        else:
            subprocess.run(
                ["ipconfig", "/renew"], capture_output=True, creationflags=0x08000000
            )
            self._int_btn.setText("Internet Off")
            self._int_btn.setProperty("active", False)

        style = self._int_btn.style()
        if style:
            style.unpolish(self._int_btn)
            style.polish(self._int_btn)

    def _on_pin_toggled(self, checked: bool):
        self._always_on_top = checked
        self._apply_window_flags()
        self._save()

    def _on_lock_toggled(self, checked: bool):
        self._pos_locked = checked
        self._save()

    def _apply_window_flags(self):
        flags = Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint
        if self._always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    @property
    def position_locked(self) -> bool:
        return self._pos_locked

    # ── Hardware temps ─────────────────────────────────────────────

    def _on_temp_tick(self):
        cpu = self._hw.cpu_temp
        gpu = self._hw.gpu_temp
        self._simple_view.update_temps(cpu, gpu)
        self._sysinfo_bar.update_sysinfo(
            self._hw.cpu_usage,
            self._hw.gpu_usage,
            self._hw.ram_usage,
            self._hw.hdd_usage,
            self._hw.uptime_secs,
            self._hw.disk_speeds,
        )

    # ── Persistence ───────────────────────────────────────────────────────

    def _restore_pos(self):
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        pos = s.value("position")
        mode = s.value("mode", "simple")
        opacity = int(s.value("opacity", 100))
        always_top = s.value("always_top", "true") == "true"
        pos_locked = s.value("pos_locked", "false") == "true"

        if pos:
            self.move(pos)
        else:
            r = QApplication.primaryScreen().geometry()  # type: ignore
            self.move(r.right() - self.width() - 30, r.bottom() - self.height() - 60)

        opacity = max(10, min(100, opacity))
        self._opacity_slider.setValue(opacity)
        self._apply_opacity(opacity)

        self._always_on_top = always_top
        self._pos_locked = pos_locked
        self._pin_btn.setChecked(always_top)
        self._lock_btn.setChecked(pos_locked)
        self._apply_window_flags()
        self.set_mode(mode)

        interval = int(s.value("interval", 1000))
        self._interval_input.setText(str(interval))
        self._monitor.interval = interval / 1000.0
        self._hw.interval = interval / 1000.0
        self._temp_timer.setInterval(interval)
        self._title_bar.logo.set_speed(interval)

    def _save(self):
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue("position", self.pos())
        s.setValue("mode", self._mode)
        s.setValue("opacity", str(self._opacity_slider.value()))
        s.setValue("always_top", str(self._always_on_top).lower())
        s.setValue("pos_locked", str(self._pos_locked).lower())
        s.setValue("interval", self._interval_input.text())

    # ── Close ─────────────────────────────────────────────────────────────

    def show_widget(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def close_app(self):
        self._temp_timer.stop()
        self._hw.stop()
        self._monitor.stop()
        self._store.save_to_disk()
        self._save()
        self._tray.hide()
        QApplication.quit()

    def closeEvent(self, a0):
        a0.ignore()
        self.hide()

    def contextMenuEvent(self, event):
        m = QMenu(self)
        m.setStyleSheet(self.styleSheet())
        other = "advanced" if self._mode == "simple" else "simple"
        a = QAction(f"Switch to {other.capitalize()}", self)
        a.triggered.connect(lambda: self.set_mode(other))
        q = QAction("Exit", self)
        q.triggered.connect(self.close_app)
        m.addAction(a)
        m.addSeparator()
        m.addAction(q)
        m.exec_(event.globalPos())
