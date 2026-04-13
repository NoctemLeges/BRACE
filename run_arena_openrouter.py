import argparse
from arena_openrouter.orchestrator import run_arena


def main():
    parser = argparse.ArgumentParser(description="BRACE Arena (OpenRouter): Red Team vs Blue Team")
    parser.add_argument(
        "--file",
        default="VersionInfo2.txt",
        help="Path to the version info file (default: VersionInfo2.txt)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Number of rounds (default: 3)",
    )
    args = parser.parse_args()
    run_arena(version_file=args.file, max_rounds=args.rounds)


if __name__ == "__main__":
    main()
