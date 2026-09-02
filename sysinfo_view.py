"""
sysinfo_view.py
Rich, modern System Information (msinfo32) tab for net-widget.
Displays deep OS, Motherboard, BIOS, CPU, Dual GPU, Storage, Network, and Memory specs.
"""

import os
import platform
import subprocess
import json
import time
import psutil
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QFrame,
    QGridLayout,
    QApplication,
    QProgressBar,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QCursor

# Color constants
CYAN = "#00ffb4"
PURPLE = "#a78bfa"
BLUE = "#38bdf8"
EMERALD = "#34d399"
GOLD = "#fbbf24"
ROSE = "#fb7185"
DIM = "rgba(255, 255, 255, 0.70)"
DIMMER = "rgba(255, 255, 255, 0.40)"
BORDER = "rgba(255, 255, 255, 0.08)"
BG_CARD = "rgba(255, 255, 255, 0.03)"


def _divider():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(
        "border-top: 1px solid rgba(255, 255, 255, 0.08); max-height: 1px; background: transparent;"
    )
    return f


class SysInfoCollectorWorker(QThread):
    """Background worker that queries WMI / CIM for deep msinfo32 specs."""
    data_ready = pyqtSignal(dict)

    def run(self):
        info = {
            "summary": {},
            "gpus": [],
            "disks": [],
            "logical_disks": [],
            "network": [],
            "env": {},
        }

        # 1. Instant native gathering
        try:
            vm = psutil.virtual_memory()
            sw = psutil.swap_memory()

            info["summary"]["OS Name"] = f"{platform.system()} {platform.release()}"
            info["summary"]["Version"] = platform.version()
            info["summary"]["System Name"] = platform.node()
            info["summary"]["System Type"] = f"{platform.machine()} PC"
            info["summary"]["Processor"] = platform.processor()
            info["summary"]["Total Physical Memory"] = f"{vm.total / (1024**3):.2f} GB"
            info["summary"]["Available Physical Memory"] = f"{vm.available / (1024**3):.2f} GB"
            info["summary"]["Total Virtual Memory"] = f"{(vm.total + sw.total) / (1024**3):.2f} GB"
            info["summary"]["Available Virtual Memory"] = f"{(vm.available + sw.free) / (1024**3):.2f} GB"
            info["summary"]["User Name"] = os.environ.get("USERNAME", "User")
            info["summary"]["User Domain"] = os.environ.get("USERDOMAIN", platform.node())
            info["summary"]["Windows Directory"] = os.environ.get("WINDIR", "C:\\Windows")
            info["summary"]["System Directory"] = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32")
            info["summary"]["Logical Processors"] = str(psutil.cpu_count(logical=True) or 0)
            info["summary"]["Physical Cores"] = str(psutil.cpu_count(logical=False) or 0)
            info["summary"]["Time Zone"] = time.tzname[0] if time.tzname else "Local Time"

            # Logical disks
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    info["logical_disks"].append({
                        "DeviceID": part.device,
                        "MountPoint": part.mountpoint,
                        "FileSystem": part.fstype,
                        "TotalGB": usage.total / (1024**3),
                        "FreeGB": usage.free / (1024**3),
                        "UsedGB": usage.used / (1024**3),
                        "Percent": usage.percent,
                    })
                except Exception:
                    pass
        except Exception:
            pass

        # 2. Deep CIM Query
        ps_cmd = """
$os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, Manufacturer, WindowsDirectory, SystemDirectory, BootDevice, TotalVisibleMemorySize, FreePhysicalMemory, TotalVirtualMemorySize, FreeVirtualMemory, LocalDateTime, OSArchitecture
$cs = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, SystemType, SystemSKUNumber, UserName, TotalPhysicalMemory, NumberOfProcessors, Domain
$bb = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product, Version, SerialNumber
$bios = Get-CimInstance Win32_BIOS | Select-Object Manufacturer, SMBIOSBIOSVersion, ReleaseDate, SMBIOSMajorVersion, SMBIOSMinorVersion, BIOSVersion
$cpu = Get-CimInstance Win32_Processor | Select-Object Name, MaxClockSpeed, NumberOfCores, NumberOfLogicalProcessors, SocketDesignation, Architecture
$gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM, CurrentHorizontalResolution, CurrentVerticalResolution, CurrentRefreshRate, VideoProcessor)
$disks = @(Get-CimInstance Win32_DiskDrive | Select-Object Model, Size, MediaType, InterfaceType, Partitions)
$net = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" | Select-Object Description, MACAddress, IPAddress, DefaultIPGateway, DNSServerSearchOrder)

[PSCustomObject]@{
    OS = $os
    ComputerSystem = $cs
    BaseBoard = $bb
    BIOS = $bios
    CPU = $cpu
    GPUs = $gpus
    Disks = $disks
    Network = $net
} | ConvertTo-Json -Depth 5 -Compress
"""
        try:
            p = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                creationflags=0x08000000,
            )
            if p.returncode == 0:
                cdata = json.loads(p.stdout)
                cos = cdata.get("OS") or {}
                ccs = cdata.get("ComputerSystem") or {}
                cbb = cdata.get("BaseBoard") or {}
                cbios = cdata.get("BIOS") or {}
                ccpu = cdata.get("CPU") or {}

                if cos.get("Caption"):
                    info["summary"]["OS Name"] = cos["Caption"]
                if cos.get("Version"):
                    build = cos.get("BuildNumber", "")
                    info["summary"]["Version"] = f"{cos['Version']} Build {build}"
                if cos.get("Manufacturer"):
                    info["summary"]["OS Manufacturer"] = cos["Manufacturer"]
                if cos.get("OSArchitecture"):
                    info["summary"]["OS Architecture"] = cos["OSArchitecture"]
                if ccs.get("Manufacturer"):
                    info["summary"]["System Manufacturer"] = ccs["Manufacturer"]
                if ccs.get("Model"):
                    info["summary"]["System Model"] = ccs["Model"]
                if ccs.get("SystemType"):
                    info["summary"]["System Type"] = ccs["SystemType"]
                if ccs.get("SystemSKUNumber"):
                    info["summary"]["System SKU"] = ccs["SystemSKUNumber"]
                if ccpu.get("Name"):
                    mhz = f", {ccpu.get('MaxClockSpeed')} MHz" if ccpu.get("MaxClockSpeed") else ""
                    cores = f", {ccpu.get('NumberOfCores')} Cores" if ccpu.get("NumberOfCores") else ""
                    threads = f", {ccpu.get('NumberOfLogicalProcessors')} Threads" if ccpu.get("NumberOfLogicalProcessors") else ""
                    info["summary"]["Processor"] = f"{ccpu['Name'].strip()}{mhz}{cores}{threads}"
                if cbios.get("Manufacturer"):
                    b_ver = cbios.get("SMBIOSBIOSVersion", "")
                    b_date = cbios.get("ReleaseDate", "")[:10] if cbios.get("ReleaseDate") else ""
                    info["summary"]["BIOS Version/Date"] = f"{cbios['Manufacturer']} {b_ver}, {b_date}"
                if cbios.get("SMBIOSMajorVersion"):
                    info["summary"]["SMBIOS Version"] = f"{cbios['SMBIOSMajorVersion']}.{cbios.get('SMBIOSMinorVersion', '0')}"
                if cbb.get("Manufacturer"):
                    info["summary"]["BaseBoard Manufacturer"] = cbb["Manufacturer"]
                if cbb.get("Product"):
                    info["summary"]["BaseBoard Product"] = cbb["Product"]
                if cbb.get("Version"):
                    info["summary"]["BaseBoard Version"] = cbb["Version"]
                if cos.get("BootDevice"):
                    info["summary"]["Boot Device"] = cos["BootDevice"]

                # GPUs
                cgpus = cdata.get("GPUs") or []
                if isinstance(cgpus, dict):
                    cgpus = [cgpus]
                for g in cgpus:
                    ram_str = "N/A"
                    if g.get("AdapterRAM"):
                        ram_mb = int(g["AdapterRAM"]) / (1024**2)
                        ram_str = f"{ram_mb / 1024:.1f} GB" if ram_mb >= 1024 else f"{ram_mb:.0f} MB"
                    res_str = "N/A"
                    if g.get("CurrentHorizontalResolution"):
                        res_str = f"{g['CurrentHorizontalResolution']} x {g['CurrentVerticalResolution']} @ {g.get('CurrentRefreshRate', 60)}Hz"
                    info["gpus"].append({
                        "Name": g.get("Name", "Graphics Device"),
                        "Driver Version": g.get("DriverVersion", "N/A"),
                        "Video Memory": ram_str,
                        "Resolution": res_str,
                        "Video Processor": g.get("VideoProcessor", "N/A"),
                    })

                # Disks
                cdisks = cdata.get("Disks") or []
                if isinstance(cdisks, dict):
                    cdisks = [cdisks]
                for d in cdisks:
                    sz_str = "N/A"
                    if d.get("Size"):
                        sz_gb = int(d["Size"]) / (1024**3)
                        sz_str = f"{sz_gb:.1f} GB" if sz_gb < 1000 else f"{sz_gb / 1024:.2f} TB"
                    info["disks"].append({
                        "Model": d.get("Model", "Hard Disk Drive"),
                        "Size": sz_str,
                        "MediaType": d.get("MediaType", "Fixed hard disk media"),
                        "Interface": d.get("InterfaceType", "N/A"),
                        "Partitions": str(d.get("Partitions", "N/A")),
                    })

                # Network
                cnets = cdata.get("Network") or []
                if isinstance(cnets, dict):
                    cnets = [cnets]
                for n in cnets:
                    ips = n.get("IPAddress") or []
                    if isinstance(ips, str):
                        ips = [ips]
                    gws = n.get("DefaultIPGateway") or []
                    if isinstance(gws, str):
                        gws = [gws]
                    dns = n.get("DNSServerSearchOrder") or []
                    if isinstance(dns, str):
                        dns = [dns]
                    info["network"].append({
                        "Adapter": n.get("Description", "Network Adapter"),
                        "MAC Address": n.get("MACAddress", "N/A"),
                        "IPv4 Address": ips[0] if ips else "N/A",
                        "IPv6 Address": ips[1] if len(ips) > 1 else "N/A",
                        "Default Gateway": gws[0] if gws else "N/A",
                        "DNS Servers": ", ".join(dns[:2]) if dns else "N/A",
                    })
        except Exception:
            pass

        self.data_ready.emit(info)


class SysInfoView(QWidget):
    """
    Main System Information view matching msinfo32 with interactive tabs,
    live searching/filtering, copy report, and instant refresh.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._current_category = "summary"
        self._search_query = ""
        self._info_data = {}
        self._worker = None

        self._build_ui()
        self.refresh_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 8, 14, 14)
        root.setSpacing(8)

        # ── Top Action & Search Bar ──────────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        # Search box (Find what...)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 Find what in System Information...")
        self._search_input.setStyleSheet(
            "QLineEdit {"
            "  background: rgba(255, 255, 255, 0.05);"
            "  color: #00ffb4;"
            "  border: 1px solid rgba(255, 255, 255, 0.12);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 11px;"
            "}"
            "QLineEdit:focus {"
            "  border: 1px solid #00ffb4;"
            "  background: rgba(0, 255, 180, 0.05);"
            "}"
        )
        self._search_input.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self._search_input, 1)

        # Refresh button
        self._refresh_btn = QPushButton("🔄 Refresh")
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setStyleSheet(self._btn_style(CYAN))
        self._refresh_btn.clicked.connect(self.refresh_data)
        top_bar.addWidget(self._refresh_btn)

        # Copy Info button
        self._copy_btn = QPushButton("📋 Copy")
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.setStyleSheet(self._btn_style(PURPLE))
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        top_bar.addWidget(self._copy_btn)

        # Open msinfo32 button
        self._msinfo_btn = QPushButton("⚡ msinfo32")
        self._msinfo_btn.setToolTip("Open Windows System Information (msinfo32)")
        self._msinfo_btn.setCursor(Qt.PointingHandCursor)
        self._msinfo_btn.setStyleSheet(self._btn_style(GOLD))
        self._msinfo_btn.clicked.connect(self._open_native_msinfo32)
        top_bar.addWidget(self._msinfo_btn)

        root.addLayout(top_bar)

        # ── Category Navigation Tabs ─────────────────────────────────────────
        cat_bar = QHBoxLayout()
        cat_bar.setSpacing(4)

        self._cat_btns = {}
        categories = [
            ("summary", "📋 Summary", CYAN),
            ("gpus", "🎮 GPUs & Display", PURPLE),
            ("disks", "💾 Storage", EMERALD),
            ("network", "🌐 Network", BLUE),
        ]

        for cat_id, label, color in categories:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(cat_id == self._current_category)
            btn.setStyleSheet(self._cat_btn_style(color, cat_id == self._current_category))
            btn.clicked.connect(lambda _, c=cat_id: self._set_category(c))
            self._cat_btns[cat_id] = (btn, color)
            cat_bar.addWidget(btn)

        root.addLayout(cat_bar)
        root.addWidget(_divider())

        # ── Scrollable Content Area ──────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical {"
            "  background: rgba(255,255,255,0.03);"
            "  width: 6px;"
            "  border-radius: 3px;"
            "  margin: 0px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(0, 255, 180, 0.3);"
            "  border-radius: 3px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            "  background: rgba(0, 255, 180, 0.6);"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )

        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(2, 2, 6, 2)
        self._content_layout.setSpacing(6)

        self._scroll.setWidget(self._content_widget)
        root.addWidget(self._scroll, 1)

    def _btn_style(self, color: str) -> str:
        return (
            "QPushButton {"
            "  background: rgba(255, 255, 255, 0.04);"
            f"  color: {color};"
            "  border: 1px solid rgba(255, 255, 255, 0.12);"
            "  border-radius: 4px;"
            "  padding: 4px 8px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            f"  background: rgba(255, 255, 255, 0.10);"
            f"  border: 1px solid {color};"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(0, 0, 0, 0.3);"
            "}"
        )

    def _cat_btn_style(self, color: str, active: bool) -> str:
        if active:
            return (
                "QPushButton {"
                f"  background: rgba(255, 255, 255, 0.08);"
                f"  color: {color};"
                f"  border: 1px solid {color};"
                "  border-radius: 4px;"
                "  padding: 5px 10px;"
                "  font-size: 11px;"
                "  font-weight: bold;"
                "}"
            )
        else:
            return (
                "QPushButton {"
                "  background: rgba(255, 255, 255, 0.02);"
                "  color: rgba(255, 255, 255, 0.65);"
                "  border: 1px solid rgba(255, 255, 255, 0.06);"
                "  border-radius: 4px;"
                "  padding: 5px 10px;"
                "  font-size: 11px;"
                "  font-weight: normal;"
                "}"
                "QPushButton:hover {"
                f"  color: {color};"
                "  background: rgba(255, 255, 255, 0.05);"
                "  border: 1px solid rgba(255, 255, 255, 0.15);"
                "}"
            )

    def _set_category(self, cat_id: str):
        self._current_category = cat_id
        for cid, (btn, col) in self._cat_btns.items():
            btn.setChecked(cid == cat_id)
            btn.setStyleSheet(self._cat_btn_style(col, cid == cat_id))
        self._render_current_view()

    def _on_search_changed(self, text: str):
        self._search_query = text.strip().lower()
        self._render_current_view()

    def refresh_data(self):
        self._refresh_btn.setText("⏳ Loading...")
        self._refresh_btn.setEnabled(False)

        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()

        self._worker = SysInfoCollectorWorker()
        self._worker.data_ready.connect(self._on_data_loaded)
        self._worker.start()

    def _on_data_loaded(self, data: dict):
        self._info_data = data
        self._refresh_btn.setText("🔄 Refresh")
        self._refresh_btn.setEnabled(True)
        self._render_current_view()

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render_current_view(self):
        self._clear_content()

        if not self._info_data:
            lbl = QLabel("Gathering system information...")
            lbl.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px; margin: 20px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._content_layout.addWidget(lbl)
            return

        if self._current_category == "summary":
            self._render_summary()
        elif self._current_category == "gpus":
            self._render_gpus()
        elif self._current_category == "disks":
            self._render_disks()
        elif self._current_category == "network":
            self._render_network()

    def _render_summary(self):
        summary = self._info_data.get("summary", {})
        q = self._search_query

        # Key Hero Cards row (OS, CPU, Motherboard, RAM)
        if not q:
            cards_row = QHBoxLayout()
            cards_row.setSpacing(6)

            os_short = summary.get("OS Name", "Windows").replace("Microsoft ", "")
            cards_row.addWidget(self._make_hero_card("OS", os_short, CYAN))

            mb = summary.get("BaseBoard Product", summary.get("System Model", "Motherboard"))
            cards_row.addWidget(self._make_hero_card("MOTHERBOARD", mb, PURPLE))

            cpu = summary.get("Processor", "Processor").split(",")[0]
            if len(cpu) > 22:
                cpu = cpu[:20] + "…"
            cards_row.addWidget(self._make_hero_card("CPU", cpu, BLUE))

            ram = summary.get("Total Physical Memory", "RAM")
            cards_row.addWidget(self._make_hero_card("RAM", ram, GOLD))

            c_widget = QWidget()
            c_widget.setLayout(cards_row)
            self._content_layout.addWidget(c_widget)
            self._content_layout.addWidget(_divider())

        # Detail Table rows
        count = 0
        for item, val in summary.items():
            s_item = str(item)
            s_val = str(val)
            if q and q not in s_item.lower() and q not in s_val.lower():
                continue
            row = self._make_table_row(s_item, s_val, count % 2 == 0)
            self._content_layout.addWidget(row)
            count += 1

        if count == 0 and q:
            self._add_empty_search_label()

    def _render_gpus(self):
        gpus = self._info_data.get("gpus", [])
        q = self._search_query
        count = 0

        for idx, g in enumerate(gpus):
            name = g.get("Name", "GPU")
            driver = g.get("Driver Version", "N/A")
            vram = g.get("Video Memory", "N/A")
            res = g.get("Resolution", "N/A")
            proc = g.get("Video Processor", "N/A")

            # Check search
            all_text = f"{name} {driver} {vram} {res} {proc}".lower()
            if q and q not in all_text:
                continue

            card = QWidget()
            card.setStyleSheet(
                "QWidget {"
                "  background: rgba(255, 255, 255, 0.03);"
                "  border: 1px solid rgba(167, 139, 250, 0.25);"
                "  border-radius: 6px;"
                "}"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(10, 8, 10, 8)
            c_lay.setSpacing(4)

            # Header row
            h_lay = QHBoxLayout()
            icon = "⚡" if "NVIDIA" in name.upper() or "RTX" in name.upper() else "◈"
            title = QLabel(f"{icon} {name}")
            title.setStyleSheet("color: #a78bfa; font-size: 13px; font-weight: bold; border: none;")
            h_lay.addWidget(title)
            h_lay.addStretch()

            vram_badge = QLabel(f"VRAM: {vram}")
            vram_badge.setStyleSheet(
                "color: #00ffb4; font-size: 11px; font-weight: bold; background: rgba(0, 255, 180, 0.1);"
                " padding: 2px 6px; border-radius: 3px; border: 1px solid rgba(0, 255, 180, 0.3);"
            )
            h_lay.addWidget(vram_badge)
            c_lay.addLayout(h_lay)
            c_lay.addWidget(_divider())

            # Specs
            c_lay.addWidget(self._make_prop_line("Driver Version", driver, CYAN))
            c_lay.addWidget(self._make_prop_line("Current Resolution", res, GOLD))
            c_lay.addWidget(self._make_prop_line("Video Processor", proc, BLUE))

            self._content_layout.addWidget(card)
            count += 1

        if count == 0 and q:
            self._add_empty_search_label()

    def _render_disks(self):
        q = self._search_query
        count = 0

        # 1. Logical Drives / Volumes
        logical = self._info_data.get("logical_disks", [])
        if logical:
            sec_lbl = QLabel("LOGICAL VOLUMES & PARTITIONS")
            sec_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold; letter-spacing: 1px; margin-top: 4px;")
            self._content_layout.addWidget(sec_lbl)

            for l in logical:
                dev = l.get("DeviceID", "Drive")
                fs = l.get("FileSystem", "")
                tot = l.get("TotalGB", 0.0)
                free = l.get("FreeGB", 0.0)
                used = l.get("UsedGB", 0.0)
                pct = l.get("Percent", 0.0)

                all_text = f"{dev} {fs} {tot} {free}".lower()
                if q and q not in all_text:
                    continue

                card = QWidget()
                card.setStyleSheet(
                    "QWidget {"
                    "  background: rgba(255, 255, 255, 0.03);"
                    "  border: 1px solid rgba(52, 211, 153, 0.20);"
                    "  border-radius: 6px;"
                    "}"
                )
                c_lay = QVBoxLayout(card)
                c_lay.setContentsMargins(10, 8, 10, 8)
                c_lay.setSpacing(4)

                h_lay = QHBoxLayout()
                lbl_d = QLabel(f"🖴 {dev} ({fs})")
                lbl_d.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; border: none;")
                h_lay.addWidget(lbl_d)
                h_lay.addStretch()

                lbl_space = QLabel(f"{free:.1f} GB free of {tot:.1f} GB ({pct:.0f}% used)")
                lbl_space.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px; border: none;")
                h_lay.addWidget(lbl_space)
                c_lay.addLayout(h_lay)

                # Usage bar
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(int(pct))
                bar.setTextVisible(False)
                bar.setFixedHeight(5)
                bar_col = "#34d399" if pct < 70 else ("#fbbf24" if pct < 88 else "#fb7185")
                bar.setStyleSheet(
                    "QProgressBar {"
                    "  background: rgba(255, 255, 255, 0.08);"
                    "  border-radius: 2px;"
                    "  border: none;"
                    "}"
                    f"QProgressBar::chunk {{ background: {bar_col}; border-radius: 2px; }}"
                )
                c_lay.addWidget(bar)

                self._content_layout.addWidget(card)
                count += 1

        # 2. Physical Drives
        disks = self._info_data.get("disks", [])
        if disks:
            self._content_layout.addSpacing(6)
            sec_lbl2 = QLabel("PHYSICAL STORAGE DISKS")
            sec_lbl2.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
            self._content_layout.addWidget(sec_lbl2)

            for d in disks:
                model = d.get("Model", "Hard Drive")
                size = d.get("Size", "N/A")
                media = d.get("MediaType", "Fixed hard disk")
                if not media:
                    media = "Removable / Storage"
                iface = d.get("Interface", "N/A")
                parts = d.get("Partitions", "N/A")

                all_text = f"{model} {size} {media} {iface}".lower()
                if q and q not in all_text:
                    continue

                card = QWidget()
                card.setStyleSheet(
                    "QWidget {"
                    "  background: rgba(255, 255, 255, 0.03);"
                    "  border: 1px solid rgba(56, 189, 248, 0.20);"
                    "  border-radius: 6px;"
                    "}"
                )
                c_lay = QVBoxLayout(card)
                c_lay.setContentsMargins(10, 8, 10, 8)
                c_lay.setSpacing(3)

                h_lay = QHBoxLayout()
                icon = "⚡" if "NVME" in model.upper() or "S60" in model.upper() else "🖴"
                lbl_m = QLabel(f"{icon} {model}")
                lbl_m.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: bold; border: none;")
                h_lay.addWidget(lbl_m)
                h_lay.addStretch()

                sz_lbl = QLabel(size)
                sz_lbl.setStyleSheet("color: #00ffb4; font-size: 11px; font-weight: bold; border: none;")
                h_lay.addWidget(sz_lbl)
                c_lay.addLayout(h_lay)

                c_lay.addWidget(self._make_prop_line("Media Type", media, DIM))
                c_lay.addWidget(self._make_prop_line("Interface / Partitions", f"{iface} ({parts} Partitions)", DIM))

                self._content_layout.addWidget(card)
                count += 1

        if count == 0 and q:
            self._add_empty_search_label()

    def _render_network(self):
        nets = self._info_data.get("network", [])
        q = self._search_query
        count = 0

        for n in nets:
            adapter = n.get("Adapter", "Network Adapter")
            mac = n.get("MAC Address", "N/A")
            ip4 = n.get("IPv4 Address", "N/A")
            ip6 = n.get("IPv6 Address", "N/A")
            gw = n.get("Default Gateway", "N/A")
            dns = n.get("DNS Servers", "N/A")

            all_text = f"{adapter} {mac} {ip4} {gw} {dns}".lower()
            if q and q not in all_text:
                continue

            card = QWidget()
            card.setStyleSheet(
                "QWidget {"
                "  background: rgba(255, 255, 255, 0.03);"
                "  border: 1px solid rgba(56, 189, 248, 0.20);"
                "  border-radius: 6px;"
                "}"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(10, 8, 10, 8)
            c_lay.setSpacing(3)

            h_lay = QHBoxLayout()
            icon = "📡" if "WIRELESS" in adapter.upper() or "WI-FI" in adapter.upper() else "🌐"
            title = QLabel(f"{icon} {adapter}")
            title.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: bold; border: none;")
            h_lay.addWidget(title)
            h_lay.addStretch()

            ip_badge = QLabel(f"IPv4: {ip4}")
            ip_badge.setStyleSheet(
                "color: #00ffb4; font-size: 11px; font-weight: bold; background: rgba(0, 255, 180, 0.1);"
                " padding: 2px 6px; border-radius: 3px; border: 1px solid rgba(0, 255, 180, 0.3);"
            )
            h_lay.addWidget(ip_badge)
            c_lay.addLayout(h_lay)
            c_lay.addWidget(_divider())

            c_lay.addWidget(self._make_prop_line("MAC Address", mac, CYAN))
            c_lay.addWidget(self._make_prop_line("Default Gateway", gw, GOLD))
            c_lay.addWidget(self._make_prop_line("DNS Servers", dns, PURPLE))
            if ip6 != "N/A":
                c_lay.addWidget(self._make_prop_line("IPv6 Address", ip6, DIM))

            self._content_layout.addWidget(card)
            count += 1

        if count == 0 and q:
            self._add_empty_search_label()

    def _make_hero_card(self, label: str, val: str, color: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet(
            "QWidget {"
            "  background: rgba(255, 255, 255, 0.04);"
            f"  border: 1px solid {color}33;"
            "  border-radius: 5px;"
            "}"
        )
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: bold; border: none;")
        lay.addWidget(lbl)

        v_lbl = QLabel(val)
        v_lbl.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold; border: none;")
        v_lbl.setWordWrap(False)
        lay.addWidget(v_lbl)
        return w

    def _make_table_row(self, item: str, val: str, is_even: bool) -> QWidget:
        row = QWidget()
        bg = "rgba(255, 255, 255, 0.02)" if is_even else "transparent"
        row.setStyleSheet(f"QWidget {{ background: {bg}; border-radius: 3px; }}")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(10)

        item_lbl = QLabel(item)
        item_lbl.setFixedWidth(160)
        item_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-size: 11px; border: none;")

        val_lbl = QLabel(val)
        val_lbl.setStyleSheet("color: #ffffff; font-size: 11px; border: none;")
        val_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)

        lay.addWidget(item_lbl)
        lay.addWidget(val_lbl, 1)
        return row

    def _make_prop_line(self, name: str, val: str, color: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(8)

        n_lbl = QLabel(name)
        n_lbl.setFixedWidth(140)
        n_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.50); font-size: 11px; border: none;")

        v_lbl = QLabel(val)
        v_lbl.setStyleSheet(f"color: {color}; font-size: 11px; border: none;")
        v_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)

        lay.addWidget(n_lbl)
        lay.addWidget(v_lbl, 1)
        return w

    def _add_empty_search_label(self):
        lbl = QLabel(f"No results found matching '{self._search_query}'")
        lbl.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 12px; margin: 20px;")
        lbl.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(lbl)

    def _copy_to_clipboard(self):
        lines = ["# System Information (msinfo32)", ""]
        summary = self._info_data.get("summary", {})
        if summary:
            lines.append("## System Summary")
            for k, v in summary.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")

        gpus = self._info_data.get("gpus", [])
        if gpus:
            lines.append("## Display & GPUs")
            for g in gpus:
                lines.append(f"- **{g.get('Name')}**: VRAM {g.get('Video Memory')}, Driver {g.get('Driver Version')}, Res {g.get('Resolution')}")
            lines.append("")

        disks = self._info_data.get("disks", [])
        if disks:
            lines.append("## Physical Disks")
            for d in disks:
                lines.append(f"- **{d.get('Model')}**: Size {d.get('Size')}, {d.get('MediaType')}")
            lines.append("")

        logical = self._info_data.get("logical_disks", [])
        if logical:
            lines.append("## Logical Volumes")
            for l in logical:
                lines.append(f"- **{l.get('DeviceID')}**: Free {l.get('FreeGB', 0):.1f} GB / Total {l.get('TotalGB', 0):.1f} GB ({l.get('Percent', 0):.0f}% used)")
            lines.append("")

        nets = self._info_data.get("network", [])
        if nets:
            lines.append("## Network Adapters")
            for n in nets:
                lines.append(f"- **{n.get('Adapter')}**: IPv4 {n.get('IPv4 Address')}, MAC {n.get('MAC Address')}, Gateway {n.get('Default Gateway')}")

        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        self._copy_btn.setText("✓ Copied!")
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._copy_btn.setText("📋 Copy"))

    def _open_native_msinfo32(self):
        try:
            subprocess.Popen(["msinfo32.exe"], creationflags=0x08000000)
        except Exception as e:
            print("Failed to open msinfo32:", e)
