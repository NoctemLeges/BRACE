RED = "\x1b[38;2;255;060;060m"
BLUE = "\x1b[38;2;060;120;255m"
YELLOW = "\x1b[38;2;255;255;000m"
GREEN = "\x1b[38;2;000;225;000m"
CYAN = "\x1b[38;2;000;200;200m"
BOLD = "\x1b[1m"
RESET = "\x1b[0m"


def print_banner():
    banner = f"""{YELLOW}{BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    ██████  ██████   █████   ██████ ███████     ARENA         ║
║    ██   ██ ██   ██ ██   ██ ██      ██                        ║
║    ██████  ██████  ███████ ██      █████    Red vs Blue      ║
║    ██   ██ ██   ██ ██   ██ ██      ██                        ║
║    ██████  ██   ██ ██   ██  ██████ ███████                   ║
║                                                              ║
║           Autonomous Red Team vs Blue Team                   ║
╚══════════════════════════════════════════════════════════════╝
{RESET}"""
    print(banner)


def print_round_header(round_num: int, max_rounds: int):
    print(f"\n{YELLOW}{BOLD}{'═' * 60}")
    print(f"  ROUND {round_num} / {max_rounds}")
    print(f"{'═' * 60}{RESET}\n")


def print_team_header(team: str):
    if team == "RED":
        color = RED
        icon = "[!!]"
        action = "ATTACKING"
    else:
        color = BLUE
        icon = "[##]"
        action = "DEFENDING"
    print(f"\n{color}{BOLD}  {icon} {team} TEAM — {action} {'─' * 35}{RESET}\n")


def print_team_footer(team: str):
    color = RED if team == "RED" else BLUE
    print(f"\n{color}  {'─' * 55}{RESET}\n")


def print_scoreboard(state):
    print(f"\n{YELLOW}{BOLD}┌─────────┬──────────────┬──────────────┬──────────────┬──────────────┐")
    print(f"│  Round  │ Red (Vulns)  │ Blue (Patch) │ Blue (Detect)│ Exploit Win  │")
    print(f"├─────────┼──────────────┼──────────────┼──────────────┼──────────────┤")
    for i in range(len(state.red_scores)):
        r = state.red_scores[i]
        b = state.blue_patches[i] if i < len(state.blue_patches) else "-"
        d = state.blue_threats_detected[i] if i < len(state.blue_threats_detected) else "-"
        window = state.get_exploitation_window(i + 1)
        w = f"{window:.1f}s" if window >= 0 else "-"
        print(f"│    {i + 1}    │     {r:<8} │     {b:<8} │     {d:<8} │    {w:<9}│")
    print(f"└─────────┴──────────────┴──────────────┴──────────────┴──────────────┘{RESET}\n")


def print_blue_wins(round_num: int):
    print(f"\n{BLUE}{BOLD}{'═' * 60}")
    print(f"  BLUE TEAM WINS! No vulnerabilities found in round {round_num}.")
    print(f"{'═' * 60}{RESET}\n")


def print_final_results(state):
    total_vulns = sum(state.red_scores)
    total_patches = sum(state.blue_patches)
    total_detected = sum(state.blue_threats_detected) if state.blue_threats_detected else 0

    windows = [state.get_exploitation_window(i + 1) for i in range(len(state.red_scores))]
    valid_windows = [w for w in windows if w >= 0]
    avg_window = sum(valid_windows) / len(valid_windows) if valid_windows else 0

    print(f"\n{YELLOW}{BOLD}{'═' * 60}")
    print(f"  FINAL RESULTS")
    print(f"{'═' * 60}")
    print(f"  Total vulnerabilities found by Red:    {total_vulns}")
    print(f"  Total patches applied by Blue:         {total_patches}")
    print(f"  Total threats detected by Blue:        {total_detected}")
    print(f"  Avg exploitation window:               {avg_window:.1f}s")

    if state.blue_firewall_rules:
        total_fw = sum(state.blue_firewall_rules)
        print(f"  Firewall rule sets generated:          {total_fw}")

    if state.blue_validations:
        last = state.blue_validations[-1]
        print(f"  Final validation: {last.get('fixed', 0)} fixed, {last.get('remaining', 0)} remaining")

    print()
    # Check validation results (post-patch) rather than red's scan (pre-patch)
    if state.blue_validations and state.blue_validations[-1].get("remaining", 1) == 0:
        print(f"  {BLUE}BLUE TEAM WINS — all vulnerabilities patched!{YELLOW}")
    elif state.red_scores and state.red_scores[-1] == 0:
        print(f"  {BLUE}BLUE TEAM WINS — no vulnerabilities found!{YELLOW}")
    else:
        print(f"  {RED}RED TEAM WINS — vulnerabilities remain!{YELLOW}")
    print(f"{'═' * 60}{RESET}\n")


def red_fragment(fragment, round_index=0):
    print(f"{RED}{fragment.content}{RESET}", end="", flush=True)


def blue_fragment(fragment, round_index=0):
    print(f"{BLUE}{fragment.content}{RESET}", end="", flush=True)
