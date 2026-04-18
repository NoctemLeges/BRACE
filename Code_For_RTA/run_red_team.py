import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code_For_RTA.offensive_agent.red_team_agent import RedTeamAgent


def main():
    parser = argparse.ArgumentParser(
        description=(
            "BRACE Red Team Agent: LLM-driven network scan -> CVE -> Metasploit -> reverse shell.\n\n"
            "Prerequisites:\n"
            "  - nmap installed on PATH\n"
            "  - msfrpcd running: msfrpcd -P <pass> -U msf -a 127.0.0.1 -p 55553 -S\n"
            "  - .env with OPENROUTER_API_KEY, MSF_RPC_PASS, RED_TEAM_ALLOWLIST (optional)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--target", required=True, help="IP/CIDR/host to attack (must match allowlist)")
    parser.add_argument("--lhost", required=True, help="Local IP for the reverse-shell listener")
    parser.add_argument("--lport", type=int, default=4444, help="Local port for the reverse-shell listener")
    args = parser.parse_args()

    agent = RedTeamAgent(lhost=args.lhost, lport=args.lport)
    final = agent.run(args.target)
    print()
    if final:
        print("\n=== Final report ===")
        print(final)


if __name__ == "__main__":
    main()
