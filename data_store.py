"""
data_store.py
Persists cumulative (all-sessions) network data to disk.
"""

import json
import time
from pathlib import Path
import psutil


_DATA_DIR = Path.home() / ".net-widget"
_DATA_FILE = _DATA_DIR / "data.json"


def _ensure_dir():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _default_data():
    return {
        "all_sessions_recv": 0,
        "all_sessions_sent": 0,
        "last_boot_time": 0.0,
        "last_boot_session_recv": 0,
        "last_boot_session_sent": 0,
        "last_interface": "",
        "this_session_baseline_recv": 0,
        "this_session_baseline_sent": 0,
        "session_count": 0,
    }


def load():
    _ensure_dir()
    if _DATA_FILE.exists():
        try:
            with open(_DATA_FILE, "r") as f:
                data = json.load(f)
                # Migration of old keys if present
                if "all_time_recv" in data:
                    data.setdefault("all_sessions_recv", data.pop("all_time_recv"))
                if "all_time_sent" in data:
                    data.setdefault("all_sessions_sent", data.pop("all_time_sent"))
                # Ensure all keys exist (forward compatibility)
                defaults = _default_data()
                for k, v in defaults.items():
                    data.setdefault(k, v)
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return _default_data()


def save(data: dict):
    _ensure_dir()
    try:
        with open(_DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


class DataStore:
    """High-level interface for session + all-time data."""

    def __init__(self):
        self._data = load()
        self._data["session_count"] += 1
        save(self._data)
        self._last_save_time = time.monotonic()

    @property
    def all_time_recv(self) -> int:
        return self._data["all_time_recv"]

    @property
    def all_time_sent(self) -> int:
        return self._data["all_time_sent"]

    @property
    def session_count(self) -> int:
        return self._data["session_count"]

    def add_session_data(self, recv_bytes: int, sent_bytes: int):
        """Called on app close to accumulate session totals."""
        self._data["all_time_recv"] += recv_bytes
        self._data["all_time_sent"] += sent_bytes
        save(self._data)

    def reset_all_time(self):
        """Wipe all-time counters."""
        self._data["all_time_recv"] = 0
        self._data["all_time_sent"] = 0
        save(self._data)

    def get_snapshot(self):
        return dict(self._data)

    @property
    def all_sessions_recv(self) -> int:
        return self._data["all_sessions_recv"]

    @property
    def all_sessions_sent(self) -> int:
        return self._data["all_sessions_sent"]

    @property
    def this_session_baseline_recv(self) -> int:
        return self._data["this_session_baseline_recv"]

    @property
    def this_session_baseline_sent(self) -> int:
        return self._data["this_session_baseline_sent"]

    def update_all_sessions(
        self, this_session_recv: int, this_session_sent: int, interface: str
    ):
        """Update all-sessions data by checking for reboot/wraparound and computing differences."""
        import psutil

        boot = psutil.boot_time()

        # If we booted after the last save, or interface changed, reset baseline
        if (
            abs(self._data["last_boot_time"] - boot) > 5.0
            or self._data["last_interface"] != interface
        ):
            self._data["last_boot_time"] = boot
            self._data["last_interface"] = interface
            self._data["last_boot_session_recv"] = this_session_recv
            self._data["last_boot_session_sent"] = this_session_sent
            save(self._data)
            self._last_save_time = time.monotonic()
            return

        # Calculate delta since last boot stats
        delta_recv = max(0, this_session_recv - self._data["last_boot_session_recv"])
        delta_sent = max(0, this_session_sent - self._data["last_boot_session_sent"])

        if delta_recv >= 0 and delta_sent >= 0:
            if this_session_recv >= self._data["last_boot_session_recv"]:
                self._data["all_sessions_recv"] += (
                    this_session_recv - self._data["last_boot_session_recv"]
                )
                self._data["last_boot_session_recv"] = this_session_recv

                if this_session_sent >= self._data["last_boot_session_sent"]:
                    self._data["all_sessions_sent"] += (
                        this_session_sent - self._data["last_boot_session_sent"]
                    )
                    self._data["last_boot_session_sent"] = this_session_sent

                    # Periodic save (every 5 seconds)
                    now = time.monotonic()
                    if now - self._last_save_time >= 5.0:
                        save(self._data)
                        self._last_save_time = now
            else:
                # Counters wrapped or reset, update baseline
                self._data["last_boot_session_recv"] = this_session_recv
                self._data["last_boot_session_sent"] = this_session_sent

                save(self._data)
                self._last_save_time = time.monotonic()

    def reset_all_sessions(
        self, this_session_recv: int, this_session_sent: int, interface: str
    ):
        """Wipe all-sessions counters and align with current boot session totals."""
        self._data["all_sessions_recv"] = 0
        self._data["all_sessions_sent"] = 0
        self._data["last_boot_time"] = psutil.boot_time()
        self._data["last_boot_session_recv"] = this_session_recv
        self._data["last_boot_session_sent"] = this_session_sent
        self._data["last_interface"] = interface

        save(self._data)
        self._last_save_time = time.monotonic()

    def reset_this_session(self, raw_recv: int, raw_sent: int):
        """Wipe this-session counters by aligning the baseline with current raw stats."""
        self._data["this_session_baseline_recv"] = raw_recv
        self._data["this_session_baseline_sent"] = raw_sent
        save(self._data)
        self._last_save_time = time.monotonic()

    def save_to_disk(self):
        save(self._data)
        self._last_save_time = time.monotonic()
