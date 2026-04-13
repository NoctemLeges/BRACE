import os
import sys
import re
import subprocess

DRY_RUN = "--dry-run" in sys.argv

LOG_FILE = os.path.expanduser("~/Projects/BRACE/update_scripts/logs/update_openssh.log")
OPENSSH_REPO = "https://github.com/openssh/openssh-portable.git"

if not DRY_RUN:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    open(LOG_FILE, 'w').close()


def shell(command):
    if DRY_RUN:
        print(f"  [DRY-RUN] Would execute: {command}")
        return
    os.system(f"{command} >> {LOG_FILE} 2>&1")


def get_latest_version_from_github():
    """Get the latest OpenSSH version from GitHub tags (format: V_X_Y_PZ)."""
    print("  Fetching latest version from GitHub...")
    result = subprocess.run(
        ["git", "ls-remote", "--tags", OPENSSH_REPO],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  [ERROR] git ls-remote failed: {result.stderr}")
        sys.exit(1)

    matches = re.findall(r'refs/tags/V_(\d+)_(\d+)_P(\d+)\s*$', result.stdout, re.MULTILINE)
    if not matches:
        print("  [ERROR] Could not find any release tags from GitHub")
        sys.exit(1)

    matches.sort(key=lambda m: (int(m[0]), int(m[1]), int(m[2])))
    major, minor, patch = matches[-1]
    return f"{major}.{minor}p{patch}"


def remove_old_openssh():
    print("1. -------------REMOVING OLD OPENSSH----------------------")
    shell("net stop sshd")
    print("[+] (1.1) Stopped sshd service")
    shell("taskkill /F /IM sshd.exe")
    shell("taskkill /F /IM ssh.exe")
    print("[+] (1.2) Killed running OpenSSH processes")
    shell("winget uninstall Microsoft.OpenSSH.Beta --silent")
    print("[+] (1.3) Uninstalled OpenSSH via winget")
    shell('powershell -Command "Remove-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0"')
    shell('powershell -Command "Remove-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0"')
    print("[+] (1.4) Removed Windows built-in OpenSSH capability")


def install_new_openssh():
    print("2. -------------INSTALLING NEW OPENSSH----------------------")
    shell("winget install Microsoft.OpenSSH.Beta --silent --accept-package-agreements --accept-source-agreements")
    print("[+] (2.1) Installed latest OpenSSH via winget")


def run_new_openssh():
    print("3. -------------RUNNING NEW OPENSSH----------------------")
    shell("net start sshd")
    print("[+] (3.1) Started sshd service")
    shell('sc config sshd start= auto')
    print("[+] (3.2) Set sshd to start automatically")
    shell("ssh -V")
    print("[+] (3.3) Printed OpenSSH version")


version = get_latest_version_from_github()
print(f"[+] Latest stable version on GitHub: OpenSSH_{version}")
remove_old_openssh()
install_new_openssh()
run_new_openssh()
