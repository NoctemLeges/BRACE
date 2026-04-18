from arena.shared_state import BattlefieldState
from arena_openrouter.red_agent import RedAgent
from arena_openrouter.blue_agent import BlueAgent
from arena import display


def _sync_blue_metrics(state: BattlefieldState, round_num: int):
    """Pull Blue metrics from events into tracking lists for the scoreboard."""
    round_events = state.get_events_for_round(round_num)

    # Threats detected
    detect_events = [e for e in round_events if e["team"] == "BLUE" and e["action"] == "detect"]
    threats = sum(e.get("threats_found", 0) for e in detect_events)
    state.blue_threats_detected.append(threats)

    # Firewall rules
    fw_events = [e for e in round_events if e["team"] == "BLUE" and e["action"] == "firewall"]
    state.blue_firewall_rules.append(len(fw_events))

    # Validation
    val_events = [e for e in round_events if e["team"] == "BLUE" and e["action"] == "validate"]
    if val_events:
        state.blue_validations.append(val_events[-1])


def run_arena(version_file: str = "VersionInfo.txt", max_rounds: int = 3):
    state = BattlefieldState(version_file)
    red = RedAgent(state)
    blue = BlueAgent(state)

    display.print_banner()
    print(f"  Target file: {version_file}")
    print(f"  Output dir:  {state.output_dir}")
    print(f"  Initial versions: {state.get_current_versions()}")
    print()

    for round_num in range(1, max_rounds + 1):
        state.round_number = round_num
        display.print_round_header(round_num, max_rounds)

        # --- RED TEAM TURN ---
        display.print_team_header("RED")
        red.take_turn(round_num)
        display.print_team_footer("RED")

        # If red found 0 vulns, blue already won
        if state.red_scores and state.red_scores[-1] == 0:
            state.blue_patches.append(0)
            state.blue_threats_detected.append(0)
            state.blue_firewall_rules.append(0)
            display.print_blue_wins(round_num)
            break

        # --- BLUE TEAM TURN ---
        display.print_team_header("BLUE")
        blue.take_turn(round_num)
        display.print_team_footer("BLUE")

        # Sync metrics from events
        _sync_blue_metrics(state, round_num)

        # If blue didn't log patches this round, record 0
        if len(state.blue_patches) < round_num:
            state.blue_patches.append(0)

        # --- SCOREBOARD ---
        display.print_scoreboard(state)
        print(f"  Current versions: {state.get_current_versions()}")

    display.print_final_results(state)
