"""
simple_view.py
Flat layout — all styling inline to avoid QSS cascade conflicts.
Neon teal/magenta palette, 150% font sizes, proper alignment.
"""

# Hello! I just added this comment so you can see the file update live!
import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath

# ── Color palette ──────────────────────────────────────────────────────────────────────────────
DL = "#00ffb4"  # neon teal   — download
UL = "#ff3c8c"  # neon magenta — upload
DIM = "rgba(255,255,255,0.90)"
DIMMER = "rgba(255,255,255,0.90)"
BRIGHT = "rgba(255,255,255,0.95)"


# ── Helpers ────────────────────────────────────────────────────────────────────
def fmt_speed(bps: float):
    """Returns (value_str, unit_str)."""
    if bps >= 1_073_741_824:
        return f"{bps / 1_073_741_824:.2f}", "GB/s"
    if bps >= 1_048_576:
        return f"{bps / 1_048_576:.2f}", "MB/s"
    if bps >= 1_024:
        return f"{bps / 1_024:.1f}", "KB/s"
    return f"{int(bps)}", "B/s"


def fmt_speed_str(bps: float) -> str:
    v, u = fmt_speed(bps)
    return f"{v} {u}"


def fmt_bytes(b: int) -> str:
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.2f} GB"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.2f} MB"
    if b >= 1_024:
        return f"{b / 1_024:.1f} KB"
    return f"{b} B"


def _lbl(text, style) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(style)
    return l


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(
        "color: rgba(57, 255, 20, 0.05); border-top: 1px solid rgba(57, 255, 20, 0.05); max-height:1px;"
    )
    return f


def _v_divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setStyleSheet(
        "color: rgba(57, 255, 20, 0.05); border-left: 1px solid rgba(57, 255, 20, 0.05); max-width:1px;"
    )
    return f


# ── Speed panel (one side) ─────────────────────────────────────────────────────
class _SpeedPanel(QWidget):
    def __init__(self, arrow: str, label: str, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self._history = [0.0] * 30  # Keep last 30 samples

        obj = f"SpeedPanel_{arrow.strip()}"
        self.setObjectName(obj)
        self.setStyleSheet(
            f"QWidget#{obj} {{  background: transparent;  border: none;}}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 16, 10, 16)
        root.setSpacing(4)

        # Values row: current + min/max
        vals = QHBoxLayout()
        vals.setSpacing(0)
        vals.setContentsMargins(0, 2, 0, 0)

        self._min_val = QLabel("0")
        self._min_val.setStyleSheet(
            f"color: {DL}; font-size: 19px; font-weight: normal; opacity: 0.7;"
        )
        self._min_val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # type: ignore

        self._val = QLabel("0")
        self._val.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)  # type: ignore
        self._val.setStyleSheet(
            "color: #fbbf24; font-size: 24px; font-weight: normal; letter-spacing: -0.5px;"
        )

        self._max_val = QLabel("0")
        self._max_val.setStyleSheet(
            f"color: {UL}; font-size: 19px; font-weight: normal; opacity: 0.7;"
        )
        self._max_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore

        vals.addWidget(self._min_val)
        vals.addStretch(1)
        vals.addWidget(self._val)
        vals.addStretch(1)
        vals.addWidget(self._max_val)
        root.addLayout(vals)

        self._min_bps = float("inf")
        self._max_bps = 0.0

    def reset(self):
        self._min_bps = float("inf")
        self._max_bps = 0.0
        self._history = [0.0] * 30
        self._val.setText("0")
        self._min_val.setText("0")
        self._max_val.setText("0")
        self.update()

    def set_speed(self, bps: float):
        self._history.append(bps)
        if len(self._history) > 30:
            self._history.pop(0)

        v, u = fmt_speed(bps)
        self._val.setText(v)

        # Calculate dynamic min and max over the rolling history window
        min_bps = min(self._history)
        max_bps = max(self._history)

        min_v, min_u = fmt_speed(min_bps)
        max_v, max_u = fmt_speed(max_bps)
        self._min_val.setText(f"{min_v}")
        self._max_val.setText(f"{max_v}")
        self.update()

    def paintEvent(self, a0):
        super().paintEvent(a0)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        max_val = max(self._history)
        min_val = min(self._history)
        val_range = max_val - min_val
        if val_range <= 0.0:
            val_range = 1.0

        t = time.time()

        # Draw actual sparkline
        path = QPainterPath()
        num_points = len(self._history)

        points = []
        for i, val in enumerate(self._history):
            x = (i / (num_points - 1)) * w
            y = (h - 4) - ((val - min_val) / val_range) * (h * 0.65)
            points.append((x, y))

        if points:
            path.moveTo(points[0][0], points[0][1])
            for pt in points[1:]:
                path.lineTo(pt[0], pt[1])

            # Draw thin sparkline stroke
            pen_color = QColor(self._color)
            pen_color.setAlpha(38)
            p.setPen(QPen(pen_color, 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

            # Fill region under the line
            path.lineTo(w, h)
            path.lineTo(0, h)
            path.closeSubpath()

            fill_line = QColor(self._color)
            fill_line.setAlpha(26)
            p.setPen(Qt.NoPen)
            p.setBrush(fill_line)
            p.drawPath(path)

        p.end()


# ── Usage row ─────────────────────────────────────────────────────────────────
class _UsageRow(QWidget):
    reset_triggered = pyqtSignal()  # type: ignore

    def __init__(self, label: str, has_reset_btn: bool = False, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 5, 0, 5)
        lay.setSpacing(6)

        # Row label (fixed width so values align across both rows)
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            f"color: {DIMMER}; font-size: 12px; font-weight: normal; background: transparent;"
        )
        self._lbl.setFixedWidth(102)
        lay.addWidget(self._lbl)

        lay.addStretch()

        if has_reset_btn:
            from PyQt5.QtWidgets import QPushButton

            self._reset_btn = QPushButton()
            self._reset_btn.setToolTip(f"Reset {label}")
            self._reset_btn.setFixedSize(12, 12)
            self._reset_btn.setCursor(Qt.PointingHandCursor)  # type: ignore
            self._reset_btn.setStyleSheet(
                "QPushButton {"
                "  background: #10b981; /* emerald green */"
                "  border-radius: 0px;"
                "  border: none;"
                "}"
                "QPushButton:hover {"
                "  background: #fbbf24; /* yellow */"
                "QPushButton:pressed {"
                "  background: #ef4444; /* red */"
                "}"
            )
            self._reset_btn.clicked.connect(self.reset_triggered.emit)
            lay.addWidget(self._reset_btn)
            lay.addSpacing(8)
        else:
            lay.addSpacing(20)
            lay.addSpacing(20)

        # Download: arrow + value (fixed width)
        dl_arrow = QLabel("↓")
        dl_arrow.setStyleSheet(
            "color: #60a5fa; font-size: 11px; font-weight: normal; background: transparent;"
        )
        self._dl = QLabel("—")
        self._dl.setStyleSheet(
            "color: #60a5fa; font-size: 12px; font-weight: normal; background: transparent;"
        )
        self._dl.setFixedWidth(76)
        self._dl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore # pyre-ignore

        # Upload: arrow + value (fixed width)
        ul_arrow = QLabel("↑")
        ul_arrow.setStyleSheet(
            "color: #fbbf24; font-size: 11px; font-weight: normal; background: transparent;"
        )
        self._ul = QLabel("—")
        self._ul.setStyleSheet(
            "color: #fbbf24; font-size: 12px; font-weight: normal; background: transparent;"
        )
        self._ul.setFixedWidth(76)
        self._ul.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore # pyre-ignore

        lay.addWidget(dl_arrow)
        lay.addWidget(self._dl)
        lay.addSpacing(8)
        lay.addWidget(ul_arrow)
        lay.addWidget(self._ul)

    def set_values(self, recv: int, sent: int):
        self._dl.setText(fmt_bytes(recv))
        self._ul.setText(fmt_bytes(sent))


# ── Temperature chip ──────────────────────────────────────────────────────────
class _TempChip(QWidget):
    def __init__(self, icon: str, label: str, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self._history = [0.0] * 30  # Keep last 30 samples

        obj = f"TempChip_{label}"
        self.setObjectName(obj)
        self.setStyleSheet(
            f"QWidget#{obj} {{  background: transparent;  border: none;}}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 12, 10, 18)
        root.setSpacing(4)

        # ── Values row: current + min/max ─────
        vals = QHBoxLayout()
        vals.setSpacing(0)
        vals.setContentsMargins(0, 2, 0, 0)

        self._min_val = QLabel("—")
        self._min_val.setStyleSheet(
            f"color: {DL}; font-size: 21px; font-weight: normal; opacity: 0.7;"
        )
        self._min_val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # type: ignore

        self._val = QLabel("—")
        self._val.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)  # type: ignore
        self._val.setStyleSheet(
            f"color: {color}; font-size: 26px; font-weight: normal; letter-spacing: -0.5px;"
        )

        self._max_val = QLabel("—")
        self._max_val.setStyleSheet(
            f"color: {UL}; font-size: 21px; font-weight: normal; opacity: 0.7;"
        )
        self._max_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore

        vals.addWidget(self._min_val)
        vals.addStretch(1)
        vals.addWidget(self._val)
        vals.addStretch(1)
        vals.addWidget(self._max_val)
        root.addLayout(vals)

        self._min = float("inf")
        self._max = -float("inf")

    def reset(self):
        self._min = float("inf")
        self._max = -float("inf")
        self._history = [0.0] * 30
        self._val.setText("0")
        self._min_val.setText("0°")
        self._max_val.setText("0°")
        self.update()

    def set_temp(self, celsius: float | None):
        val_to_store = celsius if celsius is not None else 0.0
        self._history.append(val_to_store)
        if len(self._history) > 30:
            self._history.pop(0)

        if celsius is None:
            self._val.setText("N/A")
            return
        self._val.setText(f"{celsius:.0f}")

        # Calculate dynamic min and max temperature over the rolling history window
        valid_temps = [t for t in self._history if t > 0.0]
        min_t = min(valid_temps) if valid_temps else 0.0
        max_t = max(valid_temps) if valid_temps else 0.0

        self._min_val.setText(f"{min_t:.0f}°")
        self._max_val.setText(f"{max_t:.0f}°")
        self.update()

    def paintEvent(self, a0):
        super().paintEvent(a0)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        max_val = max(self._history)
        min_val = min(self._history)
        val_range = max_val - min_val
        if val_range <= 0.0:
            val_range = 1.0

        t = time.time()

        # Draw actual sparkline
        path = QPainterPath()
        num_points = len(self._history)

        points = []
        for i, val in enumerate(self._history):
            x = (i / (num_points - 1)) * w
            y = (h - 4) - ((val - min_val) / val_range) * (h * 0.65)
            points.append((x, y))

        if points:
            path.moveTo(points[0][0], points[0][1])
            for pt in points[1:]:
                path.lineTo(pt[0], pt[1])

            # Draw thin sparkline stroke
            pen_color = QColor(self._color)
            pen_color.setAlpha(38)
            p.setPen(QPen(pen_color, 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

            # Fill region under the line
            path.lineTo(w, h)
            path.lineTo(0, h)
            path.closeSubpath()

            fill_line = QColor(self._color)
            fill_line.setAlpha(26)
            p.setPen(Qt.NoPen)
            p.setBrush(fill_line)
            p.drawPath(path)

        p.end()


class SimpleView(QWidget):
    reset_session = pyqtSignal()
    reset_all_time = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 0, 14, 8)
        root.setSpacing(0)

        root.addWidget(_divider())

        # ── Speed panels ──────────────────────────────────────────────
        panels = QHBoxLayout()
        panels.setSpacing(0)
        self._dl_panel = _SpeedPanel("↓", "Download", DL)
        self._ul_panel = _SpeedPanel("↑", "Upload", UL)
        panels.addWidget(self._dl_panel)
        panels.addWidget(_v_divider())
        panels.addWidget(self._ul_panel)
        root.addLayout(panels)

        root.addWidget(_divider())

        # ── Temperature chips ─────────────────────────────────────────
        chips = QHBoxLayout()
        chips.setSpacing(0)
        self._cpu_chip = _TempChip("▣", "CPU", "#38bdf8")  # sky blue
        self._dgpu_chip = _TempChip("◈", "dGPU", "#a78bfa")  # violet (NVIDIA RTX)
        self._igpu_chip = _TempChip("◈", "iGPU", "#34d399")  # emerald (AMD Radeon)
        chips.addWidget(self._cpu_chip)
        chips.addWidget(_v_divider())
        chips.addWidget(self._dgpu_chip)
        chips.addWidget(_v_divider())
        chips.addWidget(self._igpu_chip)
        root.addLayout(chips)

        root.addWidget(_divider())

        # ── Usage rows ────────────────────────────────────────────────
        self._session_row = _UsageRow("This Session", has_reset_btn=True)
        self._alltime_row = _UsageRow("All Sessions", has_reset_btn=True)
        self._session_row.reset_triggered.connect(self.reset_session.emit)
        self._alltime_row.reset_triggered.connect(self.reset_all_time.emit)

        root.addWidget(self._session_row)
        root.addWidget(_divider())
        root.addWidget(self._alltime_row)
        root.addWidget(_divider())

    def update_stats(self, stats: dict, all_time_recv: int, all_time_sent: int):
        self._dl_panel.set_speed(stats["download_speed"])
        self._ul_panel.set_speed(stats["upload_speed"])
        self._session_row.set_values(stats["session_recv"], stats["session_sent"])
        self._alltime_row.set_values(all_time_recv, all_time_sent)

    def update_temps(
        self,
        cpu: float | None,
        dgpu: float | None,
        igpu: float | None = None,
        top_cpu_name: str = "System",
        top_cpu_pct: float = 0.0,
        top_gpu_name: str = "Idle",
        top_gpu_pct: float = 0.0,
        dgpu_name: str = "NVIDIA GeForce RTX 3050",
        igpu_name: str = "AMD Radeon(TM) Graphics",
    ):
        self._cpu_chip.set_temp(cpu)
        self._dgpu_chip.set_temp(dgpu)
        self._igpu_chip.set_temp(igpu)

        if cpu is not None:
            self._cpu_chip.setToolTip(f"CPU Temp: {cpu:.1f}°C\nTop CPU: {top_cpu_name} ({top_cpu_pct:.1f}%)")
        if dgpu is not None:
            self._dgpu_chip.setToolTip(f"dGPU ({dgpu_name}): {dgpu:.1f}°C\nTop GPU: {top_gpu_name} ({top_gpu_pct:.1f}%)")
        if igpu is not None:
            self._igpu_chip.setToolTip(f"iGPU ({igpu_name}): {igpu:.1f}°C\nTop GPU: {top_gpu_name} ({top_gpu_pct:.1f}%)")

    def reset_temps(self):
        self._cpu_chip.reset()
        self._dgpu_chip.reset()
        self._igpu_chip.reset()

    def reset_all(self):
        self._dl_panel.reset()
        self._ul_panel.reset()
        self.reset_temps()
        self._session_row.set_values(0, 0)
        self._alltime_row.set_values(0, 0)
