import os
import sys
import shutil
import subprocess

def build():
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(workspace_dir, "dist")
    root_dist = os.path.join(os.path.dirname(workspace_dir), "dist")
    os.makedirs(dist_dir, exist_ok=True)
    os.makedirs(root_dist, exist_ok=True)

    # Determine next executable version
    version = 1
    while (os.path.exists(os.path.join(dist_dir, f"NetMonitor_v{version}.exe")) or
           os.path.exists(os.path.join(root_dist, f"NetMonitor_v{version}.exe"))):
        version += 1

    exe_name = f"NetMonitor_v{version}.exe"
    print(f"[*] Building versioned executable: {exe_name}...")

    qss_data = f"{os.path.join(workspace_dir, 'style.qss')};."

    cmd = [
        "pyinstaller",
        "--name", f"NetMonitor_v{version}",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--add-data", qss_data,
        "--hidden-import", "pyqtgraph",
        "--hidden-import", "psutil",
        "--hidden-import", "PyQt5.QtCore",
        "--hidden-import", "PyQt5.QtWidgets",
        "--hidden-import", "PyQt5.QtGui",
        "--hidden-import", "wmi",
        "--hidden-import", "winreg",
        os.path.join(workspace_dir, "main.py")
    ]

    print(f"[*] Executing command: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=workspace_dir)

    if res.returncode == 0:
        built_exe = os.path.join(dist_dir, exe_name)
        target_exe = os.path.join(root_dist, exe_name)
        if os.path.exists(built_exe):
            shutil.copy2(built_exe, target_exe)
            print(f"[+] Build SUCCESS! Output executable: {built_exe}")
            print(f"[+] Synced to workspace root: {target_exe}")
            return built_exe
        else:
            print(f"[-] Executable not found at {built_exe}")
            return None
    else:
        print(f"[-] PyInstaller failed with code: {res.returncode}")
        return None

if __name__ == "__main__":
    build()
