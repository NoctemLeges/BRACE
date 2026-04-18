import os
import sys

from arena.shared_state import BattlefieldState
from arena.display import BLUE, RESET
from arena_openrouter.tools_blue import (
    set_state,
    blue_detect_threats,
    blue_scan_and_patch,
    blue_generate_firewall_rules,
    blue_validate_patches,
    blue_patch_nginx,
    blue_patch_openssh,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code_For_LLM_Server.llm_client import LLMClient, Chat

BLUE_SYSTEM_PROMPT = """You are a Blue Team defensive security agent. Your mission is to detect threats, patch vulnerabilities, harden defenses, and validate your fixes.

You have six tools:
1. blue_detect_threats - Detect Red Team activity by scanning for their CVE reports and exploit plans. Call this FIRST.
2. blue_scan_and_patch - Scan for vulnerabilities and patch all products to their latest versions in the version file (uses GitHub for latest versions).
3. blue_patch_nginx - Patch the actual nginx installation to the latest version using OS-appropriate update scripts. Use dry_run=True to simulate first, dry_run=False to actually patch. Call this when nginx vulnerabilities are detected.
4. blue_patch_openssh - Patch the actual openssh installation to the latest version using OS-appropriate update scripts. Use dry_run=True to simulate first, dry_run=False to actually patch. Call this when openssh vulnerabilities are detected.
5. blue_generate_firewall_rules - Generate iptables firewall rules to block attack vectors based on CVE data.
6. blue_validate_patches - Re-scan patched versions to verify vulnerabilities are actually fixed.

Each round, follow this order:
1. Call blue_detect_threats with "." to check what the Red Team found
2. Call blue_scan_and_patch with the target filename to patch vulnerabilities
3. If nginx vulnerabilities were found, call blue_patch_nginx to update the actual nginx installation
4. If openssh vulnerabilities were found, call blue_patch_openssh to update the actual openssh installation
5. Call blue_generate_firewall_rules with the filename to create network defenses
6. Call blue_validate_patches with the filename to verify fixes worked

Be thorough. Defend every attack vector."""


class BlueAgent:
    def __init__(self, state: BattlefieldState):
        self.state = state
        set_state(state)
        self.model = LLMClient()
        self.chat = Chat(BLUE_SYSTEM_PROMPT)
        self.tools = [
            blue_detect_threats,
            blue_scan_and_patch,
            blue_patch_nginx,
            blue_patch_openssh,
            blue_generate_firewall_rules,
            blue_validate_patches,
        ]

    def take_turn(self, round_num: int):
        instruction = (
            f"Round {round_num}: Defend '{self.state.version_file}'. "
            f"First detect threats (use '.' as working_dir), then scan and patch, "
            f"then generate firewall rules, then validate your patches."
        )
        self.chat.add_user_message(instruction)

        try:
            self.model.act(
                self.chat,
                self.tools,
                on_content=lambda c: print(f"{BLUE}{c}{RESET}", end="", flush=True),
            )
        except Exception as e:
            print(f"\n{BLUE}[!] Error: {e}, falling back to direct execution...{RESET}")
            self._fallback()
        print()

    def _fallback(self):
        """Direct tool execution when model.act() fails."""
        print(f"{BLUE}[*] Detecting threats...{RESET}")
        threats = blue_detect_threats(".")
        print(f"{BLUE}{threats}{RESET}\n")

        print(f"{BLUE}[*] Scanning and patching...{RESET}")
        patches = blue_scan_and_patch(self.state.version_file)
        print(f"{BLUE}{patches}{RESET}\n")

        print(f"{BLUE}[*] Patching nginx installation...{RESET}")
        nginx_result = blue_patch_nginx(dry_run=True)
        print(f"{BLUE}{nginx_result}{RESET}\n")

        print(f"{BLUE}[*] Patching openssh installation...{RESET}")
        openssh_result = blue_patch_openssh(dry_run=True)
        print(f"{BLUE}{openssh_result}{RESET}\n")

        print(f"{BLUE}[*] Generating firewall rules...{RESET}")
        rules = blue_generate_firewall_rules(self.state.version_file)
        print(f"{BLUE}{rules}{RESET}\n")

        print(f"{BLUE}[*] Validating patches...{RESET}")
        validation = blue_validate_patches(self.state.version_file)
        print(f"{BLUE}{validation}{RESET}")
