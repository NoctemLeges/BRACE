# BRACE - Autonomous Red Team vs Blue Team Security Arena

BRACE is an AI-driven vulnerability assessment and response framework. It pits an autonomous **Red Team agent** (attacker) against an autonomous **Blue Team agent** (defender) in a turn-based arena, both powered by a local LLM via LM Studio.

- **Red Team**: Scans software for CVEs, generates exploit payload plans using msfvenom
- **Blue Team**: Detects vulnerabilities and patches software to the latest secure versions
- Both agents use function calling to autonomously decide which tools to invoke

## Prerequisites

- Python 3.12+
- [LM Studio](https://lmstudio.ai/) installed and running
- Internet connection (for NVD API queries)

## Setting Up LM Studio

### Option A: GUI (recommended for first time)

1. **Download and install** LM Studio from [lmstudio.ai](https://lmstudio.ai/)
2. **Download the model**: Open LM Studio, go to the search/discover tab, and download `gpt-oss-20b` (search for "openai/gpt-oss-20b")
3. **Load the model**: Go to the Developer tab and load `openai/gpt-oss-20b`
4. **Start the server**: Click "Start Server". By default it runs on `http://localhost:1234`

### Option B: CLI (headless / after first setup)

Once LM Studio is installed and the model is downloaded, you can use the `lms` CLI:

```bash
# Start the LM Studio server in the background
lms server start

# Load the model
lms load openai/gpt-oss-20b

# Verify it's running
lms status
lms ls  # lists loaded models
```

To stop later:
```bash
lms server stop
```

> **Note**: The `lms` CLI is bundled with LM Studio. If `lms` is not in your PATH, you can find it in the LM Studio installation directory, or add it via LM Studio settings > "Enable CLI".

## Installation

```bash
# Clone the repository
git clone https://github.com/NoctemLeges/BRACE.git
cd BRACE

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Arena

Make sure LM Studio is running with `gpt-oss-20b` loaded, then:

```bash
python run_arena.py
```

### Options

```bash
python run_arena.py --file VersionInfo2.txt --rounds 3
```

| Flag | Default | Description |
|------|---------|-------------|
| `--file` | `VersionInfo2.txt` | Path to the version info file to scan |
| `--rounds` | `3` | Number of attack/defend rounds |

### What Happens

1. The original version file is copied to `arena_versions.txt` (your file is preserved)
2. Each round:
   - **Red Team** reads the file, scans for CVEs via the NVD API, generates a CVE report, and creates msfvenom payload plans (not executed)
   - **Blue Team** reads the file, checks for vulnerabilities, looks up latest versions, and patches the file
3. A scoreboard is displayed after each round showing vulnerabilities found vs patches applied
4. The arena ends when Blue patches everything (0 vulns) or max rounds are reached

### Example Output

```
╔══════════════════════════════════════════════════════════════╗
║    BRACE ARENA — Red vs Blue                                 ║
╚══════════════════════════════════════════════════════════════╝

═══════════════════ ROUND 1 / 3 ═══════════════════

  [!!] RED TEAM — ATTACKING ───────────────────────
  Scanning openvpn:openvpn:2.6.2 ... found 15 CVEs
  Payload plan generated for 3 products
  ─────────────────────────────────────────────────

  [##] BLUE TEAM — DEFENDING ──────────────────────
  Patching openvpn:openvpn:2.6.2 -> openvpn:openvpn:2.6.12
  Applied 3 patches
  ─────────────────────────────────────────────────

┌─────────┬───────────────┬───────────────┐
│  Round  │  Red (Vulns)  │ Blue (Patches)│
│    1    │      15       │      3        │
└─────────┴───────────────┴───────────────┘
```

## Version Info File Format

Each line follows the format `vendor:product:version`:

```
openvpn:openvpn:2.6.2
f5:nginx:0.5.6
openbsd:openssh:7.7
```

You can create your own version files or use `extractVersion.sh` to pull versions from a live system using nmap/systemctl.

## Project Structure

```
BRACE/
├── arena/                    # Red vs Blue arena system
│   ├── shared_state.py       # Battlefield state (event log, scores)
│   ├── display.py            # ANSI-colored terminal output
│   ├── tools_red.py          # Red team tools (scan, CVE JSON, payload plan)
│   ├── tools_blue.py         # Blue team tools (scan, patch, report)
│   ├── red_agent.py          # Red team agent (LLM + function calling)
│   ├── blue_agent.py         # Blue team agent (LLM + function calling)
│   └── orchestrator.py       # Turn-based game loop
├── Demo/                     # Core vulnerability checking module
│   └── checkVulnVersions.py  # NVD API functions (readVersionInfo, checkVulnVersion, etc.)
├── payload_generation/       # Payload generation module
│   ├── checkVulnVersions.py  # Extended with generateCVEJson
│   ├── generate_payload.py   # Gemini-based payload planning
│   └── msfvenom.info         # msfvenom reference data
├── run_arena.py              # Arena entry point
├── gpt_oss_tool.py           # Standalone LM Studio chat agent
├── function_calling.py       # Mistral-7B function calling demo
├── VersionInfo2.txt          # Sample version data
├── extractVersion.sh         # Extract versions from live systems
└── requirements.txt          # Python dependencies
```

## Other Tools

### Standalone Chat Agent

Interactive chat with function calling (no arena, just a single agent):

```bash
python gpt_oss_tool.py
```

### Mistral-7B Function Calling

Requires a GPU with enough VRAM to run Mistral-7B-Instruct:

```bash
python function_calling.py
```

## API Notes

- **NVD API**: The arena queries the [NVD CVE API](https://nvd.nist.gov/developers/vulnerabilities) and [CPE API](https://nvd.nist.gov/developers/products). Without an API key, requests are rate-limited to ~5 per 30 seconds. The arena handles this naturally since the LLM takes time between tool calls.
- **LM Studio**: Uses the `lmstudio` Python SDK which connects to the local server. No API key needed.
