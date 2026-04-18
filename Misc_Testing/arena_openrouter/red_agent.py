from arena.shared_state import BattlefieldState
from arena.display import RED, RESET
from arena_openrouter.tools_red import (
    set_state,
    set_round,
    red_scan_and_report,
    red_generate_exploits,
)
from llm_client import LLMClient, Chat

RED_SYSTEM_PROMPT = """You are a Red Team penetration testing agent. Your mission is to find vulnerabilities in software and generate exploit payload plans.

You have two tools:
1. red_scan_and_report - Scans a version file against the NVD CVE database and reports all vulnerabilities found.
2. red_generate_exploits - Generates CVE JSON and msfvenom payload plans for the vulnerable software (does NOT execute).

Each round:
1. First call red_scan_and_report with the target filename
2. Then call red_generate_exploits with the same filename to create exploit plans

Always call both tools in order."""


class RedAgent:
    def __init__(self, state: BattlefieldState):
        self.state = state
        set_state(state)
        self.model = LLMClient()
        self.chat = Chat(RED_SYSTEM_PROMPT)
        self.tools = [
            red_scan_and_report,
            red_generate_exploits,
        ]

    def take_turn(self, round_num: int):
        set_round(round_num)
        instruction = (
            f"Round {round_num}: Scan '{self.state.version_file}' for vulnerabilities, "
            f"then generate exploit payload plans."
        )
        self.chat.add_user_message(instruction)

        try:
            self.model.act(
                self.chat,
                self.tools,
                on_content=lambda c: print(f"{RED}{c}{RESET}", end="", flush=True),
            )
        except Exception as e:
            print(f"\n{RED}[!] Error: {e}, falling back to direct execution...{RESET}")
            self._fallback(round_num)
        print()

    def _fallback(self, round_num: int):
        """Direct tool execution when model.act() fails."""
        print(f"{RED}[*] Scanning vulnerabilities...{RESET}")
        result = red_scan_and_report(self.state.version_file)
        print(f"{RED}{result}{RESET}")

        print(f"{RED}[*] Generating exploit plans...{RESET}")
        plan = red_generate_exploits(self.state.version_file)
        print(f"{RED}{plan}{RESET}")
