"""
graph_widget.py
Professional scrolling speed graph using pyqtgraph.
Download = electric cyan, Upload = soft violet.
"""

import pyqtgraph as pg
from PyQt5.QtGui import QColor

pg.setConfigOptions(antialias=True, background=(0, 0, 0, 0))

_DL = "#3dd9ff"
_UL = "#a78bfa"


class SpeedGraph(pg.PlotWidget):
    MAX_POINTS = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup()

    def _setup(self):
        self.setBackground(QColor(0, 0, 0, 0))

        pi = self.getPlotItem()
        pi.setContentsMargins(0, 0, 0, 0)
        pi.layout.setContentsMargins(2, 4, 8, 2)

        # Axes
        left = self.getAxis("left")
        bottom = self.getAxis("bottom")
        dim_pen = pg.mkPen(color=(255, 255, 255, 18), width=1)
        txt_clr = (255, 255, 255, 50)
        for ax in (left, bottom):
            ax.setPen(dim_pen)
            ax.setTextPen(pg.mkPen(color=txt_clr))

        left.setStyle(tickLength=-6)
        bottom.setStyle(tickLength=-4)
        left.tickStrings = self._tick_strings
        bottom.setLabel("", units="")

        self.showGrid(x=False, y=True, alpha=0.06)

        # Legend
        legend = self.addLegend(
            offset=(-10, 10),
            labelTextColor=(220, 220, 220, 160),
            brush=pg.mkBrush(11, 13, 20, 200),
            pen=pg.mkPen(255, 255, 255, 18),
        )

        # Download curve
        self._dl = self.plot(
            pen=pg.mkPen(color=(61, 217, 255, 76), width=1.5),
            fillLevel=0,
            brush=pg.mkBrush(61, 217, 255, 76),
            name="↓ DL",
        )

        # Upload curve
        self._ul = self.plot(
            pen=pg.mkPen(color=(167, 139, 250, 76), width=1.5),
            fillLevel=0,
            brush=pg.mkBrush(167, 139, 250, 76),
            name="↑ UL",
        )

        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)

    def _tick_strings(self, values, scale, spacing):
        return [_fmt(v) for v in values]

    def update_data(self, dl: list, ul: list):
        n = max(len(dl), len(ul), 1)
        x_dl = list(range(-len(dl) + 1, 1))
        x_ul = list(range(-len(ul) + 1, 1))
        self._dl.setData(x_dl, dl)
        self._ul.setData(x_ul, ul)
        peak = max(max(dl, default=0), max(ul, default=0))
        self.setYRange(0, max(peak * 1.25, 1024))


def _fmt(bps: float) -> str:
    if bps >= 1_048_576:
        return f"{bps / 1_048_576:.0f}M"
    elif bps >= 1_024:
        return f"{bps / 1_024:.0f}K"
    return f"{int(bps)}"
