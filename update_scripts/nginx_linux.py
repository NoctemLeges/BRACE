import os
import subprocess

LOG_FILE = os.path.expanduser("~/Projects/BRACE/update_scripts/logs/update_nginx.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
open(LOG_FILE, 'w').close()  # Create/clear log file

def shell(command):
    os.system(f"{command} >> {LOG_FILE} 2>&1")

def remove_old_nginx():
    print("1. -------------REMOVING OLD NGINX----------------------")
    shell("sudo pkill nginx")
    print("[+] (1.1) Killed running Nginx process")
    shell("sudo rm -rf /usr/local/nginx")
    print("[+] (1.2) Removed the old Nginx binary")

def download_new_nginx():
    print("2. -------------DOWNLOADING NEW NGINX----------------------")
    shell("rm -rf ~/Downloads/nginx")
    print("[+] (2.1) Deleted the old repository")
    shell("mkdir -p ~/Downloads/nginx")
    print("[+] (2.2) Made new repository folder")
    shell("cd ~/Downloads/nginx && git clone https://github.com/nginx/nginx.git")
    print("[+] (2.3) Cloned latest repo from Github")

def install_new_nginx():
    print("3. -------------INSTALLING NEW NGINX----------------------")
    nginx_dir = os.path.expanduser("~/Downloads/nginx/nginx/")

    print("[+] (3.1) Running auto/configure...")
    with open(LOG_FILE, 'a') as log:
        subprocess.run(["./auto/configure"], cwd=nginx_dir, stdout=log, stderr=log)

    print("[+] (3.2) Running make...")
    with open(LOG_FILE, 'a') as log:
        subprocess.run(["make"], cwd=nginx_dir, stdout=log, stderr=log)

    print("[+] (3.3) Running make install...")
    with open(LOG_FILE, 'a') as log:
        subprocess.run(["sudo", "make", "install"], cwd=nginx_dir, stdout=log, stderr=log)

def run_new_nginx():
    print("4. -------------RUNNING NEW NGINX----------------------")
    shell("sudo fuser -k 80/tcp")
    print("[+] (4.1) Killed any process running on port 80")
    shell("sudo /usr/local/nginx/sbin/nginx")
    version = subprocess.run(
        ["sudo", "/usr/local/nginx/sbin/nginx", "-v"],
        capture_output=True, text=True
    ).stderr.strip()
    print(f"[+] Latest {version} process started")

remove_old_nginx()
download_new_nginx()
install_new_nginx()
run_new_nginx()