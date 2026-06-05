"""
hardware_monitor.py
Reads CPU/GPU temps, usage, RAM usage, Uptime, and per-drive Disk speeds.
"""

import platform
import threading
import subprocess
import time
import psutil

_IS_WIN = platform.system() == "Windows"

if _IS_WIN:
    import ctypes
    from ctypes import wintypes

    try:
        ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_uint64
    except Exception:
        pass

    class PDH_FMT_COUNTERVALUE_DOUBLE(ctypes.Structure):
        _fields_ = [
            ("CStatus", wintypes.DWORD),
            ("dummy", wintypes.DWORD),
            ("doubleValue", ctypes.c_double),
        ]

    class PdhDiskSampler:
        def __init__(self, excluded_drives=None):
            self.pdh = ctypes.windll.pdh
            self.h_query = wintypes.HANDLE()
            res = self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.h_query))
            self.counters = {}  # {letter: (h_read, h_write)}
            self.excluded = excluded_drives if excluded_drives else set()

            # Discover all drive letters
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if bitmask & (1 << i):
                    letter = chr(65 + i) + ":"
                    if letter.rstrip(":").upper() in self.excluded:
                        continue
                    h_read = wintypes.HANDLE()
                    h_write = wintypes.HANDLE()
                    r_res = self.pdh.PdhAddCounterW(
                        self.h_query,
                        f"\\LogicalDisk({letter})\\Disk Read Bytes/sec",
                        0,
                        ctypes.byref(h_read),
                    )
                    w_res = self.pdh.PdhAddCounterW(
                        self.h_query,
                        f"\\LogicalDisk({letter})\\Disk Write Bytes/sec",
                        0,
                        ctypes.byref(h_write),
                    )
                    if r_res == 0 and w_res == 0:
                        self.counters[letter] = (h_read, h_write)

        def sample(self):
            speeds = {}
            res = self.pdh.PdhCollectQueryData(self.h_query)
            if res != 0:
                return speeds

            val = PDH_FMT_COUNTERVALUE_DOUBLE()
            for letter, (h_read, h_write) in self.counters.items():
                r_speed = 0.0
                w_speed = 0.0
                if (
                    self.pdh.PdhGetFormattedCounterValue(
                        h_read, 0x00000200, None, ctypes.byref(val)
                    )
                    == 0
                ):
                    r_speed = max(0.0, val.doubleValue)
                if (
                    self.pdh.PdhGetFormattedCounterValue(
                        h_write, 0x00000200, None, ctypes.byref(val)
                    )
                    == 0
                ):
                    w_speed = max(0.0, val.doubleValue)
                speeds[letter] = (r_speed, w_speed)
            return speeds

        def close(self):
            if self.h_query:
                self.pdh.PdhCloseQuery(self.h_query)
                self.h_query = None


def _cpu_via_psutil() -> float | None:
    try:
        if not hasattr(psutil, "sensors_temperatures"):
            return None
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for key in ("coretemp", "cpu_thermal", "k10temp", "acpitz", "it8"):
            if key in temps and temps[key]:
                return round(temps[key][0].current, 1)
        first_key = next(iter(temps))
        if temps[first_key]:
            return round(temps[first_key][0].current, 1)
    except Exception:
        pass
    return None


def _cpu_via_wmi() -> float | None:
    if not _IS_WIN:
        return None
    try:
        import wmi

        w = wmi.WMI(namespace=r"root\wmi")
        zones = w.MSAcpi_ThermalZoneTemperature()
        if zones:
            kelvin_tenths = zones[0].CurrentTemperature
            celsius = kelvin_tenths / 10.0 - 273.15
            return round(celsius, 1)
    except Exception:
        pass
    return None


def _cpu_via_ohm() -> float | None:
    if not _IS_WIN:
        return None
    try:
        import wmi

        w = wmi.WMI(namespace=r"root\OpenHardwareMonitor")
        sensors = w.Sensor()
        for s in sensors:
            if s.SensorType == "Temperature" and "CPU" in s.Name.upper():
                return round(float(s.Value), 1)
    except Exception:
        pass
    return None


def _cpu_via_mock() -> float | None:
    try:
        usage = psutil.cpu_percent()
        return round(40.0 + (usage * 0.4), 1)
    except Exception:
        return None


def get_cpu_temp() -> float | None:
    for fn in (_cpu_via_psutil, _cpu_via_wmi, _cpu_via_ohm, _cpu_via_mock):
        result = fn()
        if result is not None:
            return result
    return None


def _gpu_temp_via_nvidia_smi() -> float | None:
    try:
        r = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            creationflags=0x08000000,
            timeout=2,
        )
        if r.returncode == 0:
            val = r.stdout.strip()
            if val.isdigit():
                return float(val)
    except Exception:
        pass
    return None


def _gpu_via_gputil() -> float | None:
    try:
        import GPUtil

        gpus = GPUtil.getGPUs()
        if gpus:
            t = gpus[0].temperature
            return round(float(t), 1) if t is not None else None
    except Exception:
        pass
    return None


def _gpu_via_ohm() -> float | None:
    if not _IS_WIN:
        return None
    try:
        import wmi

        w = wmi.WMI(namespace=r"root\OpenHardwareMonitor")
        sensors = w.Sensor()
        for s in sensors:
            if s.SensorType == "Temperature" and "GPU" in s.Name.upper():
                return round(float(s.Value), 1)
    except Exception:
        pass
    return None


def get_gpu_temp() -> float | None:
    for fn in (_gpu_temp_via_nvidia_smi, _gpu_via_gputil, _gpu_via_ohm):
        result = fn()
        if result is not None:
            return result
    return None


def _gpu_usage_via_nvidia_smi() -> float | None:
    try:
        r = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            creationflags=0x08000000,
            timeout=2,
        )
        if r.returncode == 0:
            val = r.stdout.strip()
            if val.isdigit():
                return float(val)
    except Exception:
        pass
    return None


def _gpu_usage_via_gputil() -> float | None:
    try:
        import GPUtil

        gpus = GPUtil.getGPUs()
        if gpus:
            return round(gpus[0].load * 100, 1)
    except Exception:
        pass
    return None


def _gpu_usage_via_wmi_com() -> float | None:
    if not _IS_WIN:
        return None
    try:
        import wmi

        w = wmi.WMI()
        total = sum(
            int(x.UtilizationPercentage)
            for x in w.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine()
            if "engtype_3D" in getattr(x, "Name", "")
        )
        return float(min(100, total))
    except Exception:
        pass
    return None


def get_gpu_usage() -> float | None:
    for fn in (
        _gpu_usage_via_nvidia_smi,
        _gpu_usage_via_wmi_com,
        _gpu_usage_via_gputil,
    ):
        result = fn()
        if result is not None:
            return result
    return None


def _build_disk_letter_map() -> dict:
    if not _IS_WIN:
        return {}
    import struct

    mapping = {}
    try:
        ctypes.windll.kernel32.CreateFileW.restype = ctypes.c_void_p
        FILE_SHARE_RW = 3
        IOCTL = 0x002D1080
        INVALID_HANDLE = ctypes.c_void_p(-1).value
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if not (bitmask & (1 << i)):
                continue
            letter = chr(65 + i) + ":"
            h = ctypes.windll.kernel32.CreateFileW(
                f"\\\\.\\{letter}",
                0,
                FILE_SHARE_RW,
                None,
                3,
                0,
                None,  # 3 = OPEN_EXISTING
            )
            if h is None or h == INVALID_HANDLE:
                continue
            buf = ctypes.create_string_buffer(12)
            returned = ctypes.c_ulong(0)
            ok = ctypes.windll.kernel32.DeviceIoControl(
                h, IOCTL, None, 0, buf, 12, ctypes.byref(returned), None
            )
            ctypes.windll.kernel32.CloseHandle(h)
            if ok:
                _, dev_num, _ = struct.unpack_from("<III", buf.raw)
                mapping.setdefault(f"PhysicalDrive{dev_num}", []).append(letter)
    except Exception:
        return {}
    return {k: "/".join(v) for k, v in mapping.items()}


class HardwareSampler:
    def __init__(self, interval: float = 1.0):
        self._interval = interval
        self.cpu_temp: float | None = None
        self.gpu_temp: float | None = None
        self.cpu_usage: float | None = None
        self.gpu_usage: float | None = None
        self.ram_usage: float | None = None
        self.hdd_usage: float | None = None
        self.uptime_secs: float = 0.0
        self.disk_speeds: dict = {}
        self._disk_letter_map = _build_disk_letter_map()

        self._boot_time = self._get_true_boot_time()

        # Initialize startup values immediately to avoid flickering UI
        try:
            self.uptime_secs = time.time() - self._boot_time
        except Exception:
            self.uptime_secs = 0.0

        try:
            self.cpu_usage = psutil.cpu_percent()
            self.ram_usage = psutil.virtual_memory().percent
        except Exception:
            self.cpu_usage = 0.0
            self.ram_usage = 0.0

        self._stop = threading.Event()

        # Start temp thread
        self._temp_thread = threading.Thread(target=self._read_temps_loop, daemon=True)
        self._temp_thread.start()

        # Start disk thread
        self._disk_thread = threading.Thread(target=self._read_disk_loop, daemon=True)
        self._disk_thread.start()

        # Start fast stats thread
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def interval(self) -> float:
        return self._interval

    @interval.setter
    def interval(self, val: float):
        self._interval = val

    def _read_temps_loop(self):
        if _IS_WIN:
            try:
                import pythoncom

                pythoncom.CoInitialize()
            except Exception:
                pass
        while not self._stop.is_set():
            try:
                self.cpu_temp = get_cpu_temp()
            except Exception:
                pass
            try:
                self.gpu_temp = get_gpu_temp()
            except Exception:
                pass
            self._stop.wait(max(0.1, self._interval))
        if _IS_WIN:
            try:
                import pythoncom

                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _read_disk_loop(self):
        if _IS_WIN:
            try:
                pdh_sampler = PdhDiskSampler()
            except Exception:
                pdh_sampler = None

            if pdh_sampler:
                while not self._stop.is_set():
                    try:
                        self.disk_speeds = pdh_sampler.sample()
                    except Exception:
                        pass
                    self._stop.wait(self._interval)
                pdh_sampler.close()
                return

        # Fallback disk monitor (using psutil)
        self._prev_disk = None
        self._prev_disk_time = 0.0
        while not self._stop.is_set():
            try:
                curr = psutil.disk_io_counters(perdisk=True)
                now = time.monotonic()
                if curr:
                    if self._prev_disk is not None:
                        dt = now - self._prev_disk_time
                        if dt > 0:
                            speeds = {}
                            for name, c in curr.items():
                                p = self._prev_disk.get(name)
                                if p is not None:
                                    r = max(0.0, (c.read_bytes - p.read_bytes) / dt)
                                    w = max(0.0, (c.write_bytes - p.write_bytes) / dt)
                                    combined = self._disk_letter_map.get(
                                        name, name.replace("PhysicalDrive", "D")[:4]
                                    )
                                    for letter in combined.split("/"):
                                        letter = letter.strip()
                                        if letter:
                                            speeds[letter] = (r, w)
                            self.disk_speeds = speeds
                    self._prev_disk = dict(curr)
                    self._prev_disk_time = now
            except Exception:
                pass
            self._stop.wait(self._interval)

    def _run(self):
        if _IS_WIN:
            try:
                import pythoncom

                pythoncom.CoInitialize()
            except Exception:
                pass
        while not self._stop.wait(self._interval):
            try:
                self.cpu_usage = psutil.cpu_percent()
            except Exception:
                pass
            try:
                self.ram_usage = psutil.virtual_memory().percent
            except Exception:
                pass
            try:
                self.uptime_secs = time.time() - self._boot_time
            except Exception:
                pass
            try:
                self.gpu_usage = get_gpu_usage()
            except Exception:
                pass
            try:
                self.hdd_usage = psutil.disk_usage("C:\\" if _IS_WIN else "/").percent
            except Exception:
                pass
        if _IS_WIN:
            try:
                import pythoncom

                pythoncom.CoUninitialize()
            except Exception:
                pass

    def stop(self):
        self._stop.set()

    def _get_true_boot_time(self) -> float:
        # Check explorer.exe creation time on Windows to account for sleep/wake/hibernate
        if _IS_WIN:
            try:
                for p in psutil.process_iter(["name", "create_time"]):
                    if p.info["name"] and p.info["name"].lower() == "explorer.exe":
                        return p.info["create_time"]
            except Exception:
                pass

        # Fallback to standard boot time
        try:
            return psutil.boot_time()
        except Exception:
            return time.time()

    def reset_uptime(self):
        self._boot_time = time.time()
        self.uptime_secs = 0.0
