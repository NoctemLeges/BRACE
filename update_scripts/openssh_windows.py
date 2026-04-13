import os
import sys
import json
import shutil
import subprocess
import zipfile
import urllib.request
from io import BytesIO

DRY_RUN = "--dry-run" in sys.argv

INSTALL_DIR = r"C:\Program Files\OpenSSH"
LOG_FILE = os.path.expanduser("~/Projects/BRACE/update_scripts/logs/update_openssh.log")
RELEASES_API = "https://api.github.com/repos/PowerShell/Win32-OpenSSH/releases/latest"

if not DRY_RUN:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    open(LOG_FILE, 'w').close()


def shell(command):
    if DRY_RUN:
        print(f"  [DRY-RUN] Would execute: {command}")
        return
    os.system(f"{command} >> {LOG_FILE} 2>&1")


def get_latest_release():
    """Get the latest Win32-OpenSSH release from GitHub Releases API."""
    print("  Fetching latest release from GitHub...")
    req = urllib.request.Request(RELEASES_API, headers={"User-Agent": "BRACE-updater"})
    data = json.loads(urllib.request.urlopen(req).read().decode())
    tag = data["tag_name"]

    # Find the Win64 zip asset
    zip_url = None
    for asset in data["assets"]:
        if asset["name"] == "OpenSSH-Win64.zip":
            zip_url = asset["browser_download_url"]
            break

    if not zip_url:
        print("  [ERROR] Could not find OpenSSH-Win64.zip in release assets")
        sys.exit(1)

    return tag, zip_url


def remove_old_openssh():
    print("1. -------------REMOVING OLD OPENSSH----------------------")
    shell('net stop sshd')
    print("[+] (1.1) Stopped sshd service")
    shell("taskkill /F /IM sshd.exe")
    shell("taskkill /F /IM ssh.exe")
    print("[+] (1.2) Killed running OpenSSH processes")
    if DRY_RUN:
        print(f"  [DRY-RUN] Would remove directory: {INSTALL_DIR}")
    else:
        if os.path.exists(INSTALL_DIR):
            shutil.rmtree(INSTALL_DIR)
    print("[+] (1.3) Removed the old OpenSSH directory")


def download_and_install_openssh(zip_url):
    print("2. -------------DOWNLOADING NEW OPENSSH----------------------")
    print(f"[+] (2.1) Downloading {zip_url}")

    if DRY_RUN:
        print(f"  [DRY-RUN] Would download: {zip_url}")
        print(f"  [DRY-RUN] Would extract to: {INSTALL_DIR}")
        print(f"[+] (2.2) Extracted to {INSTALL_DIR}")
        return

    req = urllib.request.Request(zip_url, headers={"User-Agent": "BRACE-updater"})
    data = urllib.request.urlopen(req).read()
    print(f"[+] (2.2) Downloaded {len(data)} bytes")

    print("3. -------------INSTALLING NEW OPENSSH----------------------")
    with zipfile.ZipFile(BytesIO(data)) as zf:
        # The zip contains an OpenSSH-Win64/ folder
        zf.extractall(r"C:\Program Files")
    extracted_dir = r"C:\Program Files\OpenSSH-Win64"
    os.rename(extracted_dir, INSTALL_DIR)
    print(f"[+] (3.1) Extracted and installed to {INSTALL_DIR}")


def configure_and_run_openssh():
    print("4. -------------CONFIGURING AND RUNNING OPENSSH----------------------")
    install_script = os.path.join(INSTALL_DIR, "install-sshd.ps1")
    shell(f'powershell -ExecutionPolicy Bypass -File "{install_script}"')
    print("[+] (4.1) Installed sshd service")

    shell("net start sshd")
    print("[+] (4.2) Started sshd service")

    shell('sc config sshd start= auto')
    print("[+] (4.3) Set sshd to start automatically")

    ssh_exe = os.path.join(INSTALL_DIR, "ssh.exe")
    if DRY_RUN:
        print(f"  [DRY-RUN] Would run: {ssh_exe} -V")
        print("[+] Latest OpenSSH (dry-run) started")
        return

    result = subprocess.run(
        [ssh_exe, "-V"],
        capture_output=True, text=True
    )
    version = result.stderr.strip()
    print(f"[+] Latest {version} started")


tag, zip_url = get_latest_release()
print(f"[+] Latest release: {tag}")
print(f"[+] Download URL: {zip_url}")
remove_old_openssh()
download_and_install_openssh(zip_url)
configure_and_run_openssh()
