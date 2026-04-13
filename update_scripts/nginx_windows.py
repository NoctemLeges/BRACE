import os
import sys
import re
import subprocess

DRY_RUN = "--dry-run" in sys.argv

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
    shell("winget uninstall nginxinc.nginx --silent")
    print("[+] (1.2) Uninstalled nginx via winget")


def install_new_nginx():
    print("2. -------------INSTALLING NEW NGINX----------------------")
    shell("winget install nginxinc.nginx --silent --accept-package-agreements --accept-source-agreements")
    print("[+] (2.1) Installed latest nginx via winget")


def run_new_nginx():
    print("3. -------------RUNNING NEW NGINX----------------------")
    shell('for /f "tokens=5" %a in (\'netstat -ano ^| findstr :80 ^| findstr LISTENING\') do taskkill /F /PID %a')
    print("[+] (3.1) Killed any process running on port 80")
    shell("nginx")
    print("[+] (3.2) Started nginx")
    shell("nginx -v")
    print("[+] (3.3) Printed nginx version")


version = get_latest_version_from_github()
print(f"[+] Latest stable version on GitHub: nginx/{version}")
remove_old_nginx()
install_new_nginx()
run_new_nginx()
