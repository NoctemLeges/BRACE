import subprocess
import requests
import os
import logging
import sys

# ---------- Logging Setup ----------
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "update_openvpn_linux.log")

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------- Pretty Terminal Output ----------
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'

def log_print(message, level="info"):
    if level == "info":
        print(f"{Colors.OKBLUE}[INFO]{Colors.END} {message}")
        logging.info(message)
    elif level == "success":
        print(f"{Colors.OKGREEN}[SUCCESS]{Colors.END} {message}")
        logging.info(message)
    elif level == "warning":
        print(f"{Colors.WARNING}[WARNING]{Colors.END} {message}")
        logging.warning(message)
    elif level == "error":
        print(f"{Colors.FAIL}[ERROR]{Colors.END} {message}")
        logging.error(message)

# ---------- Safe subprocess wrapper ----------
def run_cmd(cmd, cwd=None):
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        logging.debug(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        logging.error(e.stderr)
        log_print(f"Command failed: {' '.join(cmd)}", "error")
        log_print(e.stderr.strip(), "error")
        sys.exit(1)

# ---------- Install dependencies ----------
def install_dependencies():
    log_print("Installing dependencies...")
    packages = [
        "libnl-3-dev",
        "libnl-genl-3-dev",
        "pkg-config",
        "libcap-ng-dev",
        "liblz4-dev",
        "liblzo2-dev",
        "libpam0g-dev"
    ]

    run_cmd(["sudo", "apt", "update", "-y"])
    run_cmd(["sudo", "apt", "upgrade", "-y"])

    for pkg in packages:
        log_print(f"Installing {pkg}...")
        run_cmd(["sudo", "apt", "install", pkg, "-y"])

    log_print("Dependencies installed.", "success")

# ---------- Remove old OpenVPN ----------
def delete_old_openvpn():
    log_print("Removing old OpenVPN (if exists)...")
    try:
        run_cmd(["sudo", "rm", "/usr/local/sbin/openvpn"])
        log_print("Old OpenVPN removed.", "success")
    except SystemExit:
        log_print("No existing OpenVPN found or already removed.", "warning")

# ---------- Fetch latest release ----------
def get_new_openvpn():
    log_print("Fetching latest OpenVPN release info...")

    try:
        response = requests.get(
            "https://api.github.com/repos/OpenVPN/openvpn/releases/latest",
            timeout=10
        )
        response.raise_for_status()
        json_result = response.json()

        assets = requests.get(json_result['assets_url']).json()

        for asset in assets:
            if asset['name'].endswith(".tar.gz"):
                package_name = asset['name']
                download_url = asset['browser_download_url']
                break
        else:
            raise Exception("No suitable tar.gz asset found")

        log_print(f"Downloading {package_name}...")
        run_cmd(["wget", download_url])

        log_print(f"Downloaded {package_name}", "success")
        return package_name

    except Exception as e:
        log_print(f"Failed to fetch OpenVPN: {str(e)}", "error")
        sys.exit(1)

# ---------- Build & Install ----------
def install_new_openvpn(package_name):
    log_print("Starting OpenVPN installation...")

    install_dependencies()

    dir_name = package_name.replace(".tar.gz", "")

    log_print("Extracting package...")
    run_cmd(["tar", "-xvzf", package_name])

    log_print("Configuring build...")
    run_cmd(["./configure"], cwd=dir_name)

    log_print("Compiling...")
    run_cmd(["make", f"-j{os.cpu_count()}"], cwd=dir_name)

    log_print("Installing...")
    run_cmd(["sudo", "make", "install"], cwd=dir_name)

    log_print("OpenVPN installed successfully!", "success")

# ---------- Main ----------
if __name__ == "__main__":
    log_print("==== OpenVPN Auto Installer Started ====", "info")

    delete_old_openvpn()
    pkg = get_new_openvpn()
    install_new_openvpn(pkg)

    log_print("==== Completed Successfully ====", "success")