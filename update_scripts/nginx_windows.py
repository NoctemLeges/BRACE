import os
import sys
import re
import shutil
import subprocess
import zipfile
import urllib.request
from io import BytesIO

DRY_RUN = "--dry-run" in sys.argv

INSTALL_DIR = r"C:\nginx"
LOG_FILE = os.path.expanduser("~/Projects/BRACE/update_scripts/logs/update_nginx.log")
NGINX_REPO = "https://github.com/nginx/nginx.git"

if not DRY_RUN:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    open(LOG_FILE, 'w').close()


def shell(command):
    if DRY_RUN:
        print(f"  [DRY-RUN] Would execute: {command}")
        return
    os.system(f"{command} >> {LOG_FILE} 2>&1")


def run(args, **kwargs):
    if DRY_RUN:
        print(f"  [DRY-RUN] Would execute: {' '.join(args)}")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
    with open(LOG_FILE, 'a') as log:
        return subprocess.run(args, stdout=log, stderr=log, **kwargs)


def get_latest_version_from_github():
    """Get the latest nginx release version from GitHub tags (no clone needed)."""
    print("  Fetching latest version from GitHub...")
    result = subprocess.run(
        ["git", "ls-remote", "--tags", NGINX_REPO],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  [ERROR] git ls-remote failed: {result.stderr}")
        sys.exit(1)

    # Tags look like release-1.28.3
    versions = re.findall(r'release-(\d+\.\d+\.\d+)', result.stdout)
    if not versions:
        print("  [ERROR] Could not find any release tags from GitHub")
        sys.exit(1)
    versions.sort(key=lambda v: list(map(int, v.split('.'))))
    return versions[-1]


def remove_old_nginx():
    print("1. -------------REMOVING OLD NGINX----------------------")
    shell("taskkill /F /IM nginx.exe")
    print("[+] (1.1) Killed running Nginx process")
    if DRY_RUN:
        print(f"  [DRY-RUN] Would remove directory: {INSTALL_DIR}")
    else:
        if os.path.exists(INSTALL_DIR):
            shutil.rmtree(INSTALL_DIR)
    print("[+] (1.2) Removed the old Nginx directory")


def download_and_install_nginx(version):
    print("2. -------------DOWNLOADING NEW NGINX----------------------")
    zip_name = f"nginx-{version}.zip"
    url = f"https://nginx.org/download/{zip_name}"
    print(f"[+] (2.1) Downloading {url}")

    if DRY_RUN:
        print(f"  [DRY-RUN] Would download: {url}")
        print(f"  [DRY-RUN] Would extract to: {INSTALL_DIR}")
        print(f"[+] (2.2) Extracted to {INSTALL_DIR}")
        return

    data = urllib.request.urlopen(url).read()
    print(f"[+] (2.2) Downloaded {len(data)} bytes")

    print("3. -------------INSTALLING NEW NGINX----------------------")
    with zipfile.ZipFile(BytesIO(data)) as zf:
        # The zip contains a folder like nginx-1.26.1/ — extract then move
        zf.extractall(r"C:\\")
    extracted_dir = f"C:\\nginx-{version}"
    os.rename(extracted_dir, INSTALL_DIR)
    print(f"[+] (3.1) Extracted and installed to {INSTALL_DIR}")


def run_new_nginx():
    print("4. -------------RUNNING NEW NGINX----------------------")
    # Kill anything on port 80
    shell('for /f "tokens=5" %a in (\'netstat -ano ^| findstr :80 ^| findstr LISTENING\') do taskkill /F /PID %a')
    print("[+] (4.1) Killed any process running on port 80")

    nginx_exe = os.path.join(INSTALL_DIR, "nginx.exe")
    if DRY_RUN:
        print(f"  [DRY-RUN] Would start: {nginx_exe}")
        print(f"  [DRY-RUN] Would run: {nginx_exe} -v")
        print("[+] Latest nginx (dry-run) process started")
        return

    subprocess.Popen([nginx_exe], cwd=INSTALL_DIR)
    result = subprocess.run(
        [nginx_exe, "-v"],
        capture_output=True, text=True
    )
    version = result.stderr.strip()
    print(f"[+] Latest {version} process started")


version = get_latest_version_from_github()
print(f"[+] Latest stable version: nginx/{version}")
remove_old_nginx()
download_and_install_nginx(version)
run_new_nginx()
