import os
import sys
import re
import subprocess

DRY_RUN = "--dry-run" in sys.argv

LOG_FILE = os.path.expanduser("~/Projects/BRACE/update_scripts/logs/update_openssh.log")
CLONE_DIR = os.path.expanduser("~/Downloads/openssh")
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
    # Tags look like V_9_9_P2
    tags = re.findall(r'refs/tags/(V_\d+_\d+_P\d+)\s*$', result.stdout, re.MULTILINE)
    if not tags:
        print("  [ERROR] Could not find any release tags from GitHub")
        sys.exit(1)

    def tag_sort_key(tag):
        nums = re.findall(r'\d+', tag)
        return list(map(int, nums))

    tags.sort(key=tag_sort_key)
    latest_tag = tags[-1]
    # Convert V_9_9_P2 to 9.9p2
    match = re.match(r'V_(\d+)_(\d+)_P(\d+)', latest_tag)
    version = f"{match.group(1)}.{match.group(2)}p{match.group(3)}"
    return latest_tag, version


def remove_old_openssh():
    print("1. -------------REMOVING OLD OPENSSH----------------------")
    shell("sudo systemctl stop sshd")
    print("[+] (1.1) Stopped sshd service")
    shell("sudo rm -rf /usr/local/sbin/sshd /usr/local/bin/ssh /usr/local/bin/scp /usr/local/bin/sftp")
    print("[+] (1.2) Removed old OpenSSH binaries")


def download_new_openssh():
    print("2. -------------DOWNLOADING NEW OPENSSH----------------------")
    shell(f"rm -rf {CLONE_DIR}")
    print("[+] (2.1) Deleted the old repository")
    shell(f"mkdir -p {CLONE_DIR}")
    print("[+] (2.2) Made new repository folder")
    shell(f"cd {CLONE_DIR} && git clone {OPENSSH_REPO}")
    print("[+] (2.3) Cloned latest repo from GitHub")


def install_new_openssh(tag):
    print("3. -------------INSTALLING NEW OPENSSH----------------------")
    src_dir = os.path.join(CLONE_DIR, "openssh-portable")

    shell(f"cd {src_dir} && git checkout {tag}")
    print(f"[+] (3.1) Checked out tag {tag}")

    shell(f"cd {src_dir} && autoreconf")
    print("[+] (3.2) Running autoreconf...")

    if DRY_RUN:
        print(f"  [DRY-RUN] Would execute: ./configure in {src_dir}")
        print(f"  [DRY-RUN] Would execute: make in {src_dir}")
        print(f"  [DRY-RUN] Would execute: sudo make install in {src_dir}")
    else:
        with open(LOG_FILE, 'a') as log:
            subprocess.run(["./configure"], cwd=src_dir, stdout=log, stderr=log)
        print("[+] (3.3) Running configure...")

        with open(LOG_FILE, 'a') as log:
            subprocess.run(["make"], cwd=src_dir, stdout=log, stderr=log)
        print("[+] (3.4) Running make...")

        with open(LOG_FILE, 'a') as log:
            subprocess.run(["sudo", "make", "install"], cwd=src_dir, stdout=log, stderr=log)

    print("[+] (3.5) Running make install...")


def run_new_openssh():
    print("4. -------------RUNNING NEW OPENSSH----------------------")
    shell("sudo systemctl start sshd")
    print("[+] (4.1) Started sshd service")

    if DRY_RUN:
        print("  [DRY-RUN] Would execute: ssh -V")
        print("[+] Latest OpenSSH (dry-run) started")
        return

    result = subprocess.run(
        ["ssh", "-V"],
        capture_output=True, text=True
    )
    version = result.stderr.strip()
    print(f"[+] Latest {version} started")


tag, version = get_latest_version_from_github()
print(f"[+] Latest version: OpenSSH_{version} (tag: {tag})")
remove_old_openssh()
download_new_openssh()
install_new_openssh(tag)
run_new_openssh()
