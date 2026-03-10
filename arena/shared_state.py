import os
import shutil
import time
from datetime import datetime
from pathlib import Path


class BattlefieldState:
    def __init__(self, version_file: str):
        self.original_file = version_file

        # Create timestamped output directory: arena_output/2026-03-06_14-30-15/
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.output_dir = os.path.join("arena_output", ts)
        os.makedirs(self.output_dir, exist_ok=True)

        self.version_file = os.path.join(self.output_dir, "arena_versions.txt")
        shutil.copy2(version_file, self.version_file)

        self.round_number = 0
        self.events: list[dict] = []
        self.red_scores: list[int] = []
        self.blue_patches: list[int] = []
        self.blue_threats_detected: list[int] = []
        self.blue_firewall_rules: list[int] = []
        self.blue_validations: list[dict] = []

        # Exploitation window tracking
        self._red_scan_times: list[float] = []
        self._blue_patch_times: list[float] = []

    def artifact_path(self, filename: str) -> str:
        """Get the full path for an artifact inside the output directory."""
        return os.path.join(self.output_dir, filename)

    def log_event(self, team: str, action: str, details: dict):
        self.events.append({
            "round": self.round_number,
            "team": team,
            "action": action,
            "timestamp": time.time(),
            **details,
        })

        # Track exploitation windows
        if team == "RED" and action == "scan":
            self._red_scan_times.append(time.time())
        elif team == "BLUE" and action == "patch":
            self._blue_patch_times.append(time.time())

    def get_events_for_round(self, round_num: int) -> list[dict]:
        return [e for e in self.events if e["round"] == round_num]

    def get_current_versions(self) -> list[str]:
        return Path(self.version_file).read_text().strip().splitlines()

    def get_exploitation_window(self, round_num: int) -> float:
        """Seconds between Red finding vulns and Blue patching them."""
        red_events = [
            e for e in self.events
            if e["round"] == round_num and e["team"] == "RED" and e["action"] == "scan"
        ]
        blue_events = [
            e for e in self.events
            if e["round"] == round_num and e["team"] == "BLUE" and e["action"] == "patch"
        ]
        if red_events and blue_events:
            return blue_events[-1]["timestamp"] - red_events[0]["timestamp"]
        return -1
