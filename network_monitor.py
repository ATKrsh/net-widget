"""
network_monitor.py
Background QThread that samples psutil network counters every 0.1 s
and emits real-time speed + cumulative totals.
"""

import time
import psutil
from PyQt5.QtCore import QThread, pyqtSignal


def _get_best_interface():
    """Return the name of the active interface with the most traffic, or None for aggregate."""
    counters = psutil.net_io_counters(pernic=True)
    if_stats = psutil.net_if_stats()
    best = None
    best_total = -1
    for name, stats in counters.items():
        if name in if_stats and not if_stats[name].isup:
            continue
        # Skip loopback and virtual adapters
        if any(
            skip in name.lower()
            for skip in ("loopback", "lo", "vmware", "vethernet", "vbox")
        ):
            continue
        total = stats.bytes_recv + stats.bytes_sent
        if total > best_total:
            best_total = total
            best = name
    return best


class NetworkMonitor(QThread):
    """
    Emits network stats every second.
    Signal payload (dict):
        download_speed   – bytes/sec download
        upload_speed     – bytes/sec upload
        session_recv     – bytes received this session
        session_sent     – bytes sent this session
        total_recv       – cumulative bytes_recv from psutil (all-time in OS session)
        total_sent       – cumulative bytes_sent from psutil
        packets_recv     – total packets received

        packets_sent     – total packets sent
        errin            – input errors
        errout           – output errors
        dropin           – dropped incoming packets
        dropout          – dropped outgoing packets
        interface        – interface name being monitored
        dl_history       – download history list
        ul_history       – upload history list
    """

    stats_updated = pyqtSignal(dict)  # type: ignore

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._interface = _get_best_interface()
        self.interval = 0.1

        self._session_baseline = self._read_counters()
        self._prev_counters = self._session_baseline
        self._prev_time = time.monotonic()

        self.dl_history = []
        self.ul_history = []
        self._max_history = 1200

    def _read_counters(self):
        if self._interface:
            counters = psutil.net_io_counters(pernic=True)
            if self._interface in counters:
                return counters[self._interface]
        return psutil.net_io_counters()

    def set_interface(self, name):
        self._interface = name
        self.reset_counters()

    def reset_counters(self):
        self._session_baseline = self._read_counters()
        self._prev_counters = self._session_baseline
        self._prev_time = time.monotonic()

        self.dl_history.clear()
        self.ul_history.clear()

    def get_available_interfaces(self):
        return list(psutil.net_io_counters(pernic=True).keys())

    @property
    def interface_name(self):
        name = self._interface or "All Interfaces"
        # Map eth/wlan to Ethernet/Wi-Fi in Docker Desktop on Windows for visual consistency
        import os
        if os.path.exists('/.dockerenv') and os.path.exists('/run/desktop/mnt/host/wslg'):
            if name.lower().startswith("eth"):
                return "Ethernet"
            elif name.lower().startswith("wlan"):
                return "Wi-Fi"
        return name

    def run(self):
        self._running = True
        while self._running:
            time.sleep(self.interval)
            if not self._running:
                break
            self._emit_stats()

    def _emit_stats(self):
        now = time.monotonic()
        curr = self._read_counters()
        elapsed = now - self._prev_time

        if elapsed <= 0:
            return

        dl_speed = max(0, (curr.bytes_recv - self._prev_counters.bytes_recv) / elapsed)
        ul_speed = max(0, (curr.bytes_sent - self._prev_counters.bytes_sent) / elapsed)

        session_recv = curr.bytes_recv
        session_sent = curr.bytes_sent

        # Update history
        self.dl_history.append(dl_speed)
        self.ul_history.append(ul_speed)
        if len(self.dl_history) > self._max_history:
            self.dl_history.pop(0)
        if len(self.ul_history) > self._max_history:
            self.ul_history.pop(0)

        self._prev_counters = curr
        self._prev_time = now

        payload = {
            "download_speed": dl_speed,
            "upload_speed": ul_speed,
            "session_recv": session_recv,
            "session_sent": session_sent,
            "total_recv": curr.bytes_recv,
            "total_sent": curr.bytes_sent,
            "packets_recv": max(
                0, curr.packets_recv - self._session_baseline.packets_recv
            ),
            "packets_sent": max(
                0, curr.packets_sent - self._session_baseline.packets_sent
            ),
            "errin": max(0, curr.errin - self._session_baseline.errin),
            "errout": max(0, curr.errout - self._session_baseline.errout),
            "dropin": max(0, curr.dropin - self._session_baseline.dropin),
            "dropout": max(0, curr.dropout - self._session_baseline.dropout),
            "interface": self.interface_name,
            "dl_history": list(self.dl_history),
            "ul_history": list(self.ul_history),
        }
        self.stats_updated.emit(payload)

    def stop(self):
        self._running = False
        self.wait(2000)
