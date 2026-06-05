"""
advanced_view.py
Flat inline-styled advanced view. Neon teal/magenta, 150% fonts.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt
from graph_widget import SpeedGraph
from simple_view import fmt_speed_str, fmt_bytes, DL, UL, DIM, DIMMER, BRIGHT


def _divider():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("border-top: 1px solid rgba(57, 255, 20, 0.40); max-height:1px; background:transparent;")
    return f


def _sec(text):
    l = QLabel(text)
    l.setStyleSheet(
        "color: rgba(255,255,255,0.90); font-size: 10px; font-weight: normal;"
        " letter-spacing: 2.5px; background: transparent; margin-top: 4px;"
    )
    return l


class _Row(QWidget):
    def __init__(self, label: str, color: str = BRIGHT, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(0)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(
            "color: rgba(255,255,255,0.90); font-size: 11px; font-weight: 400; background: transparent;"
        )

        self._val = QLabel("—")
        self._val.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: normal; background: transparent;"
        )
        self._val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore  # type: ignore # pyre-ignore

        lay.addWidget(self._lbl)
        lay.addStretch()
        lay.addWidget(self._val)

    def set(self, v: str):
        self._val.setText(v)


class AdvancedView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._peak_dl = self._peak_ul = 0.0
        self._count = self._sum_dl = self._sum_ul = 0
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 18)
        root.setSpacing(5)

        self._graph = SpeedGraph()
        self._graph.setFixedHeight(155)
        self._graph.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        root.addWidget(self._graph)

        root.addWidget(_divider())

        # Live speeds
        root.addWidget(_sec("LIVE"))
        self._r_dl = _Row("↓  Download", DL)
        self._r_ul = _Row("↑  Upload", UL)
        root.addWidget(self._r_dl)
        root.addWidget(self._r_ul)

        root.addWidget(_divider())

        # Stats/Peaks
        root.addWidget(_sec("STATS"))
        self._r_pk_dl = _Row("Peak download", DL)
        self._r_pk_ul = _Row("Peak upload", UL)
        self._r_av_dl = _Row("Avg download", DL)
        self._r_av_ul = _Row("Avg upload", UL)
        for w in (self._r_pk_dl, self._r_pk_ul, self._r_av_dl, self._r_av_ul):
            root.addWidget(w)

        root.addWidget(_divider())

        # Network
        root.addWidget(_sec("NETWORK"))
        self._r_iface = _Row("Interface",          BRIGHT)
        self._r_pr    = _Row("Packets recv",       DIM)
        self._r_ps    = _Row("Packets sent",       DIM)
        self._r_err   = _Row("Errors  in / out",  "rgba(251,191,36,0.80)")
        self._r_drop  = _Row("Drops   in / out",  "rgba(251,191,36,0.80)")
        self._r_eta   = _Row("ETA to 1 GB ↓",     DIM)
        for w in (self._r_iface, self._r_pr, self._r_ps,
                  self._r_err, self._r_drop, self._r_eta):
            root.addWidget(w)

        root.addStretch()

    def update_stats(self, s: dict):
        dl, ul = s["download_speed"], s["upload_speed"]
        self._peak_dl = max(self._peak_dl, dl)
        self._peak_ul = max(self._peak_ul, ul)
        self._count  += 1
        self._sum_dl += dl
        self._sum_ul += ul

        eta = "∞"
        if dl > 0:
            t = 1_073_741_824 / dl
            eta = f"{int(t//60)}m {int(t%60)}s" if t < 3600 else f"{t/3600:.1f} hr"

        self._graph.update_data(s["dl_history"], s["ul_history"])
        self._r_dl.set(fmt_speed_str(dl))
        self._r_ul.set(fmt_speed_str(ul))
        self._r_pk_dl.set(fmt_speed_str(self._peak_dl))
        self._r_pk_ul.set(fmt_speed_str(self._peak_ul))
        self._r_av_dl.set(fmt_speed_str(self._sum_dl / self._count))
        self._r_av_ul.set(fmt_speed_str(self._sum_ul / self._count))
        self._r_iface.set(s["interface"])
        self._r_pr.set(f"{s['packets_recv']:,}")
        self._r_ps.set(f"{s['packets_sent']:,}")
        self._r_err.set(f"{s['errin']}  /  {s['errout']}")
        self._r_drop.set(f"{s['dropin']}  /  {s['dropout']}")
        self._r_eta.set(eta)

    def reset_all(self):
        self._peak_dl = self._peak_ul = 0.0
        self._count = self._sum_dl = self._sum_ul = 0
        self._graph.update_data([], [])
        self._r_dl.set("0 B/s")
        self._r_ul.set("0 B/s")
        self._r_pk_dl.set("0 B/s")
        self._r_pk_ul.set("0 B/s")
        self._r_av_dl.set("0 B/s")
        self._r_av_ul.set("0 B/s")
        self._r_pr.set("0")
        self._r_ps.set("0")
        self._r_err.set("0  /  0")
        self._r_drop.set("0  /  0")
        self._r_eta.set("—")

