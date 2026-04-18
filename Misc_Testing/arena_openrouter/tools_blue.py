import json
import glob
import platform
import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Demo.checkVulnVersions import (
    readVersionInfo,
    checkVulnVersion,
)
from update_scripts.github_versions import get_latest_from_github
from llm_client import LLMClient, Chat

_state = None


def set_state(state):
    global _state
    _state = state


def blue_detect_threats(working_dir: str) -> str:
    """
    Detect Red Team activity by reading their output artifacts (CVE reports and payload plans).

    Args:
        working_dir: Directory to scan for Red Team artifacts like arena_cve_round*.json and arena_payload_plan_round*.json.

    Returns:
        A threat briefing summarizing what the Red Team discovered and planned.
    """
    search_dir = _state.output_dir if _state else working_dir
    cve_files = sorted(glob.glob(os.path.join(search_dir, "cve_round*.json")))
    plan_files = sorted(glob.glob(os.path.join(search_dir, "payload_plan_round*.json")))

    if not cve_files and not plan_files:
        return "No Red Team artifacts detected. No known threats."

    briefing_parts = []

    for cve_file in cve_files:
        try:
            with open(cve_file) as f:
                data = json.load(f)
            for product, info in data.items():
                cves = info.get("CVEs", [])
                if cves:
                    cve_ids = [c["CVE_ID"] for c in cves[:5]]
                    briefing_parts.append(
                        f"  THREAT: {product} has {len(cves)} CVEs: {', '.join(cve_ids)}"
                    )
        except (json.JSONDecodeError, KeyError):
            continue

    for plan_file in plan_files:
        try:
            with open(plan_file) as f:
                content = f.read()
            plan_data = json.loads(content)
            if isinstance(plan_data, list):
                for entry in plan_data:
                    target = entry.get("target", "unknown")
                    payload = entry.get("payload", "unknown")
                    briefing_parts.append(
                        f"  EXPLOIT PLANNED: {target} using {payload}"
                    )
        except (json.JSONDecodeError, KeyError):
            continue

    if not briefing_parts:
        return "Red Team artifacts found but no actionable threats extracted."

    if _state is not None:
        _state.log_event("BLUE", "detect", {"threats_found": len(briefing_parts)})

    return f"Threat briefing ({len(briefing_parts)} threats detected):\n" + "\n".join(briefing_parts)


def blue_scan_and_patch(filename: str) -> str:
    """
    Scan a version file for vulnerabilities, then patch all vulnerable products to their latest versions.

    Args:
        filename: Path to a file with lines like "vendor:product:version".

    Returns:
        A summary of all patches applied.
    """
    infos = readVersionInfo(filename)
    vuln_counts = dict(checkVulnVersion(infos))

    patches = {}
    updated_lines = []
    for product, count in vuln_counts.items():
        if count > 0:
            new_version = get_latest_from_github(product)
            patches[product] = new_version
            updated_lines.append(new_version + "\n")
        else:
            updated_lines.append(product + "\n")

    Path(filename).write_text("".join(updated_lines))

    if _state is not None:
        _state.blue_patches.append(len(patches))
        _state.log_event("BLUE", "patch", {"patches": patches})

    if not patches:
        return "No vulnerabilities found. Nothing to patch."

    lines = [f"  {old} -> {new}" for old, new in patches.items()]
    return f"Applied {len(patches)} patches:\n" + "\n".join(lines)


def blue_generate_firewall_rules(filename: str) -> str:
    """
    Generate firewall rules to block known attack vectors based on CVE data. Uses AI to reason about which ports and protocols to block.

    Args:
        filename: Path to the version info file to analyze for firewall rule generation.

    Returns:
        Generated iptables/nftables firewall rules to mitigate detected threats.
    """
    search_dir = _state.output_dir if _state else "."
    cve_files = sorted(glob.glob(os.path.join(search_dir, "cve_round*.json")))
    cve_context = ""
    for cve_file in cve_files:
        try:
            with open(cve_file) as f:
                data = json.load(f)
            cve_context += json.dumps(data, indent=2)
        except (json.JSONDecodeError, KeyError):
            continue

    if not cve_context:
        infos = readVersionInfo(filename)
        cve_context = f"Software inventory: {', '.join(i.strip() for i in infos)}"

    prompt = f"""You are a Blue Team network defender. Based on the following CVE data and software inventory, generate iptables firewall rules to block known attack vectors.

Rules should:
- Block inbound traffic to vulnerable service ports
- Allow only necessary outbound connections
- Include comments explaining which CVE each rule mitigates
- Be valid iptables syntax ready to execute

CVE Data:
{cve_context}

Return ONLY the firewall rules, one per line."""

    model = LLMClient()
    chat = Chat("You generate iptables firewall rules. Return only valid firewall rules.")
    chat.add_user_message(prompt)
    rules = model.respond(chat).strip()

    if _state is not None:
        _state.log_event("BLUE", "firewall", {"rules": rules})

    return f"Generated firewall rules:\n{rules}"


def blue_validate_patches(filename: str) -> str:
    """
    Validate that applied patches actually resolved vulnerabilities by re-scanning the patched versions.

    Args:
        filename: Path to the patched version info file.

    Returns:
        Validation report showing which patches succeeded and which failed.
    """
    infos = readVersionInfo(filename)
    vuln_counts = dict(checkVulnVersion(infos))

    remaining = {p: c for p, c in vuln_counts.items() if c > 0}
    fixed = {p: c for p, c in vuln_counts.items() if c == 0}

    report_lines = []
    for product in fixed:
        report_lines.append(f"  [OK] {product}: patch verified, 0 vulnerabilities")
    for product, count in remaining.items():
        report_lines.append(f"  [!!] {product}: still has {count} vulnerabilities after patching")

    if _state is not None:
        _state.log_event("BLUE", "validate", {
            "fixed": len(fixed),
            "remaining": len(remaining),
        })

    status = "ALL CLEAR" if not remaining else f"{len(remaining)} PRODUCTS STILL VULNERABLE"
    return f"Patch validation — {status}:\n" + "\n".join(report_lines)


def blue_patch_nginx(dry_run: bool = True) -> str:
    """
    Patch nginx to the latest version using the OS-appropriate update script. Removes the old nginx, downloads the latest from GitHub, installs, and starts it.

    Args:
        dry_run: If True, simulates the update without making changes. If False, actually patches nginx.

    Returns:
        The output from the update script showing each step performed.
    """
    system = platform.system().lower()
    project_root = os.path.join(os.path.dirname(__file__), "..")

    if system == "windows":
        script = os.path.join(project_root, "update_scripts", "nginx_windows.py")
    else:
        script = os.path.join(project_root, "update_scripts", "nginx_linux.py")

    if not os.path.exists(script):
        return f"Error: update script not found at {script}"

    cmd = [sys.executable, script]
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[WARNING] Script exited with code {result.returncode}"
    except subprocess.TimeoutExpired:
        output = "Error: update script timed out after 300 seconds"
    except Exception as e:
        output = f"Error running update script: {e}"

    if _state is not None:
        _state.log_event("BLUE", "patch_nginx", {
            "dry_run": dry_run,
            "script": script,
        })

    mode = "DRY-RUN" if dry_run else "LIVE"
    return f"Nginx patch ({mode}):\n{output}"


def blue_patch_openssh(dry_run: bool = True) -> str:
    """
    Patch openssh to the latest version using the OS-appropriate update script. Removes the old openssh, downloads the latest from GitHub, installs, and starts it.

    Args:
        dry_run: If True, simulates the update without making changes. If False, actually patches openssh.

    Returns:
        The output from the update script showing each step performed.
    """
    system = platform.system().lower()
    project_root = os.path.join(os.path.dirname(__file__), "..")

    if system == "windows":
        script = os.path.join(project_root, "update_scripts", "openssh_windows.py")
    else:
        script = os.path.join(project_root, "update_scripts", "openssh_linux.py")

    if not os.path.exists(script):
        return f"Error: update script not found at {script}"

    cmd = [sys.executable, script]
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[WARNING] Script exited with code {result.returncode}"
    except subprocess.TimeoutExpired:
        output = "Error: update script timed out after 300 seconds"
    except Exception as e:
        output = f"Error running update script: {e}"

    if _state is not None:
        _state.log_event("BLUE", "patch_openssh", {
            "dry_run": dry_run,
            "script": script,
        })

    mode = "DRY-RUN" if dry_run else "LIVE"
    return f"OpenSSH patch ({mode}):\n{output}"
