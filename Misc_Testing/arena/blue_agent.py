import lmstudio as lms
from arena.shared_state import BattlefieldState
from arena.display import blue_fragment, BLUE, RESET
from arena.tools_blue import (
    set_state,
    blue_detect_threats,
    blue_scan_and_patch,
    blue_generate_firewall_rules,
    blue_validate_patches,
)

BLUE_SYSTEM_PROMPT = """You are a Blue Team defensive security agent. Your mission is to detect threats, patch vulnerabilities, harden defenses, and validate your fixes.

You have four tools:
1. blue_detect_threats - Detect Red Team activity by scanning for their CVE reports and exploit plans. Call this FIRST.
2. blue_scan_and_patch - Scan for vulnerabilities and patch all products to their latest versions.
3. blue_generate_firewall_rules - Generate iptables firewall rules to block attack vectors based on CVE data.
4. blue_validate_patches - Re-scan patched versions to verify vulnerabilities are actually fixed.

Each round, follow this order:
1. Call blue_detect_threats with "." to check what the Red Team found
2. Call blue_scan_and_patch with the target filename to patch vulnerabilities
3. Call blue_generate_firewall_rules with the filename to create network defenses
4. Call blue_validate_patches with the filename to verify fixes worked

Be thorough. Defend every attack vector."""


class BlueAgent:
    def __init__(self, state: BattlefieldState):
        self.state = state
        set_state(state)
        self.model = lms.llm("openai/gpt-oss-20b")
        self.chat = lms.Chat(BLUE_SYSTEM_PROMPT)
        self.tools = [
            blue_detect_threats,
            blue_scan_and_patch,
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
                on_message=self.chat.append,
                on_prediction_fragment=blue_fragment,
            )
        except lms.LMStudioPredictionError:
            print(f"\n{BLUE}[!] Tool call parse error, falling back to direct execution...{RESET}")
            self._fallback()
        print()

    def _fallback(self):
        """Direct tool execution when model.act() fails to parse tool calls."""
        print(f"{BLUE}[*] Detecting threats...{RESET}")
        threats = blue_detect_threats(".")
        print(f"{BLUE}{threats}{RESET}\n")

        print(f"{BLUE}[*] Scanning and patching...{RESET}")
        patches = blue_scan_and_patch(self.state.version_file)
        print(f"{BLUE}{patches}{RESET}\n")

        print(f"{BLUE}[*] Generating firewall rules...{RESET}")
        rules = blue_generate_firewall_rules(self.state.version_file)
        print(f"{BLUE}{rules}{RESET}\n")

        print(f"{BLUE}[*] Validating patches...{RESET}")
        validation = blue_validate_patches(self.state.version_file)
        print(f"{BLUE}{validation}{RESET}")
