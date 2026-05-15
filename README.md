# BRACE

### *Agentic AI in Conflict: Emergent Dynamics of Red–Blue Co-Evolution*

**Authors:** Satadru Roy, Akash Kundu, Debajit Kanungo, Rishika Goswami
**Mentor:** Aritra Saha
**Repository:** https://github.com/NoctemLeges/BRACE

---

## What BRACE Is

BRACE is a research framework that turns a classical security exercise — a red team attacking a network while a blue team defends it — into a **closed adversarial loop between two autonomous LLM agents**. The attacker probes a simulated enterprise network for vulnerable software; the defender scans the same network, reasons about what is exposed, and patches it. Both sides speak to the same reasoning engine through a shared LLM server, and every "serious" action passes through a human-in-the-loop *Operational Admin* before it touches a host.

The thesis of the accompanying paper is that when you let a generative red agent and a deterministic-leaning blue agent share an environment and iterate against each other, you get **co-evolution**: the red agent is rewarded for bypassing blue heuristics, the blue agent is rewarded for covering newly discovered attack patterns, and together they harden the environment in a way that mirrors generative-adversarial training for cybersecurity. This is the idea the literature is starting to call *agentic purple teaming* — the BRACE project is one concrete, reproducible instantiation of it.

BRACE is deliberately built around three design commitments:

1. **Agentic, not scripted.** Neither team follows a fixed playbook. Each agent is given a system prompt, a set of Python tools exposed as OpenAI-format function schemas, and the freedom to decide what to call next. The red agent can choose to skip a CVE it doesn't trust; the blue agent can choose to ignore a host it deems patched.
2. **Deterministic where it matters.** LLMs are probabilistic — version matching, CPE resolution, and exploit validation cannot be. BRACE pushes all version-to-CVE mapping through the NVD CPE Match API (not through model inference) and validates exploits by observing real Metasploit session objects, not by trusting a model's self-report.
3. **Safe by construction.** The red agent is bounded by an allowlist (RFC1918 + explicit CIDRs). The blue agent cannot dispatch an update command without an Operational Admin approval. No live exploit can land on a target outside the lab scope.

---

## The Story So Far

BRACE has evolved through two distinct phases, both captured in [BRACE_Documentation.pdf](BRACE_Documentation.pdf) and [BRACE_Documentation_Part2.pdf](BRACE_Documentation_Part2.pdf).

### Phase 1 — The Paper-Plan MVP (June 2025 – November 2025)

The first question the team had to answer was: *"How do we simulate a network cheaply enough to iterate quickly?"* The answer was to drop the network entirely and represent each host as a plain text file of `vendor:product:version` lines. A Blue agent could parse those lines, query NVD, and "patch" by rewriting the file. A Red agent could read the same file, look up CVEs, and generate `msfvenom` command strings — a **payload plan**, not a payload.

That MVP gave the team a tight feedback loop to solve the hard problems:

- **Vulnerability lookup correctness.** Early tests revealed a nasty trap in the NVD API: querying `openvpn:2.6.12` directly returned zero CVEs, even though CVE-2025-2704 covers the range 2.6.1–2.6.13. The fix was a two-step CPE-driven pipeline — first resolve the exact version to the nearest matching CPE via `/cpematch/2.0`, then query `/cves/2.0?cpeName=<cpe>` for the actual vulnerabilities. This pipeline is now the foundation of all blue-side intelligence.
- **Service selection.** OpenSSH, OpenVPN, and Nginx were chosen as the canonical target set — representing remote access, secure tunneling, and web serving — because they have rich CVE histories, clean CPE entries, and straightforward install paths. DNS and DHCP were considered and dropped for CPE inconsistency.
- **Severity-aware prioritization.** The vulnerability counter was converted from a plain `dict` to an `OrderedDict`, and CVE entries are now stored with CVSS metadata so the blue agent can prioritize critical patches first.
- **Literature grounding.** The design draws deliberately on Google's **Big Sleep** and DeepMind's **CodeMender**, on **XBOW** (which topped HackerOne through LLM-guided attacks verified by deterministic canaries), on **PatchLM**, and on **DARPA's AI Cyber Challenge** — all of which validate that LLMs can execute the full detect–analyze–patch cycle when paired with deterministic verification.

This is the phase most of the code in this repository is built around, and it is fully runnable today.

### Phase 2 — The Distributed Testbed (January 2026 – ongoing)

Phase 2 is the jump from a single-process simulation to an architecture that resembles a real enterprise network. It is in progress, and the five-way decomposition of the codebase you see today reflects it:

```
                    ┌─────────────────────┐
                    │   OpenRouter (API)  │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │       LLM Server          │
                 │  (RTA context │ BTA ctx)  │
                 └──────┬───────────┬────────┘
                        │           │
                ┌───────┴─────┐   ┌─┴──────────────┐
                │ Red Team    │   │ Blue Team      │
                │ Agent (RTA) │   │ Agent (BTA)    │◄──► Operational
                │ — external  │   │ — internal     │     Admin (OA)
                └───────┬─────┘   └──────┬─────────┘
                        │                │
                        │        ┌───────┴────────┐
                        │        │    Router      │
                        │        └──┬──────────┬──┘
                        │           │          │
                        ▼        ┌──┴──┐    ┌──┴──┐
                    (external)   │ SW1 │    │ SW2 │
                                 │H1 H2│    │ H4  │
                                 │ H3  │    │ H5  │
                                 │ SSH │    │ H6  │
                                 └─────┘    │NGINX│
                                            └─────┘
```

The key architectural commitments of Phase 2 are:

- **Decoupled reasoning.** The LLM Server is a separate service that holds *independent conversation contexts* for the Red and Blue agents. They share the environment, but their internal state is isolated.
- **Multi-subnet topology.** Two switches, two subnets, a router between them, and a BTA positioned on both sides with dual NICs so it can bridge internal traffic. The RTA is deliberately positioned *outside* the subnets so it must earn its access.
- **Authorization as a first-class citizen.** Every serious action (dispatching a patch, firing an exploit) routes through an Operational Admin. The research question here is *granularity* — which actions are safe to automate, and which require a human to press Y?
- **Hardened telemetry.** Each host runs a lightweight extractor that ships `vendor:product:version` data to the BTA. The extractor itself must not become an attack surface — this is an explicit constraint, not an afterthought.

---

## Repository Layout

The codebase is partitioned into **five functional categories** that mirror the Phase 2 architecture. The four that matter for the operational loop are below; the fifth (Operational Admin) is currently implemented as a CLI `input()` stand-in inside the BTA server and will be lifted into its own component.

```
BRACE/
├── Code_For_LLM_Server/     # Reasoning gateway (WIP)
├── Code_For_RTA/            # Red Team Agent (WIP — live-fire branch)
├── Code_For_BTA/            # Blue Team Agent (operational)
├── Code_For_Hosts/          # Host-side agents: extractors + updaters (operational)
│
├── Misc_Testing/            # Phase-1 arena harnesses (paper-plan Red vs Blue)
├── BRACE_Documentation.pdf  # Meeting minutes, Part 1 (Phase 1)
├── BRACE_Documentation_Part2.pdf   # Meeting minutes, Part 2 (Phase 2)
└── VersionInfo.txt          # Sample host telemetry
```

### [Code_For_LLM_Server/](Code_For_LLM_Server/) — the reasoning hub *(WIP)*

The LLM Server is the piece that makes BRACE "agentic" rather than scripted. Both the RTA and the BTA are clients of it; neither talks to a model directly.

Today, this folder contains the scaffolding — a shared [llm_client.py](Code_For_LLM_Server/llm_client.py) that wraps OpenRouter with:

- A `Chat` object that tracks a single agent's conversation history.
- An `LLMClient.act(chat, tools)` method that runs a full tool-calling loop: send messages → execute any tool calls the model makes → append results → repeat until the model stops calling tools.
- A `function_to_tool_schema(func)` utility that introspects a Python function's type hints and Google-style docstring and produces a valid OpenAI function schema automatically. This is why every tool in the project is "just a Python function" — the schema is generated, not hand-written.
- Retry logic for 429s, structured tool-result appending, and configurable model selection via [llm_config.py](Code_For_LLM_Server/llm_config.py) (default: `openai/gpt-oss-120b`).

What is **still to come** and is actively WIP:

- Promoting this from an in-process library to a **networked service** with its own HTTP endpoint, so the RTA and BTA (which will live on different machines/subnets) can call it remotely.
- **Context isolation** as a server-side guarantee: today the two agents just instantiate separate `Chat` objects; in the target architecture the server is responsible for keeping their contexts separate, auditable, and replayable.
- **Request logging + replay** so experiments are reproducible across runs.
- Moving the reasoning away from local GPT-OSS and onto a hybrid OpenRouter-backed GPT-OSS deployment (the 48 GB workstation cannot host 7–14 B parameter models with any headroom — this transition is happening now).

When you see a file in `Code_For_LLM_Server/` imported from an agent module, treat it as the stand-in for what will become a dedicated server process.

### [Code_For_RTA/](Code_For_RTA/) — the Red Team Agent *(WIP)*

The RTA has two generations of code in this folder, representing the two project phases.

**Phase 1: [`payload_generation/`](Code_For_RTA/payload_generation/)** — the paper-plan agent. It reads a version file, queries NVD, and asks an LLM to emit a JSON list of `msfvenom` commands. Nothing is executed against a live host. This is what the paper calls the "payload plan" stage.

**Phase 2: [`offensive_agent/`](Code_For_RTA/offensive_agent/)** — the live-fire agent *(WIP)*. This is the branch the project is currently building out. It replaces paper plans with the real kill chain, driven by an LLM making function calls:

| Tool | What it does |
|---|---|
| `red_nmap_scan(target, ports)` | `nmap -sV` sweep. Returns structured `{host, port, service, product, version, cpe}` dicts. Allowlist-gated. |
| `red_fingerprint_service(host, port)` | Intensity-9 version probe on one port. Normalizes CPE to `vendor:product:version`. |
| `red_cve_lookup(vendor_product_version)` | NVD CVE lookup. Returns `[{cve_id, description, cvss}]`. |
| `red_search_metasploit_modules(query)` | Searches the MSF module DB via `msfrpcd`. Returns `[{path, rank, disclosure_date, name}]`. |
| `red_run_exploit(module, rhost, rport, payload, lhost, lport, extras)` | Loads a module, configures it, fires it, and waits 30 s for a session. |
| `red_list_sessions()` | Enumerates open MSF sessions. |
| `red_execute_in_session(session_id, command)` | Runs a command in a shell/meterpreter session and reads the output. |
| `red_full_attack_chain(target, lhost, lport)` | Convenience wrapper: scan → CVE → module-search in one shot. Does not auto-exploit. |

The agent is driven by [`red_team_agent.py`](Code_For_RTA/offensive_agent/red_team_agent.py) with a system prompt that encodes the kill-chain order, payload-selection heuristics (Linux x64 vs Windows x64 vs generic *nix), and hard stopping conditions (once a session opens, run 1–2 ID commands and report — no persistence, no pivoting, no exfil). Full walkthrough in [metasploit.md](metasploit.md).

What is **WIP**:

- Wiring the RTA into the arena so the BTA can *react* to real exploit activity rather than only to the contents of a text file.
- Persistent session handling and OA approval on the *run_exploit* boundary (currently the allowlist alone gates exploitation).
- Graceful degradation when `msfrpcd` is down (today tools return an error string and the LLM stops — fine for a prototype, not fine for an unattended arena round).

### [Code_For_BTA/](Code_For_BTA/) — the Blue Team Agent

This is the most mature piece of the system. The BTA runs as a TCP server ([`BTA_SERVER.py`](Code_For_BTA/BTA_SERVER.py)) that hosts connect to, upload their version file to, and receive remediation instructions from.

The defensive pipeline in [`checkVulnVersions.py`](Code_For_BTA/checkVulnVersions.py) is the deterministic core described in the paper:

1. `readVersionInfo(file)` parses `vendor:product:version` lines.
2. `checkVulnVersion(infos)` queries the NVD CVE 2.0 API with each product and returns an `OrderedDict` of vulnerability counts per product.
3. `updateToLatestVersion(product)` resolves the newest CPE via the CPE API (this is where the work on nearest-version-not-exceeding heuristics lives).
4. `retrieveLatestVersion(...)` builds the updated product list and — in the paper-plan variant — rewrites the file.

In the server variant, the handshake is:

```
host  ──"Hello from client"──▶ BTA
host  ──VersionInfo.txt─────▶ BTA
                              BTA runs checkVulnVersion(...)
                              BTA asks Operational Admin (stdin) for approval
host  ◀─────update list────── BTA
host  runs Code_For_Hosts/update_scripts/<product>_linux.py
```

The Operational Admin prompt is currently a per-host admin terminal window owned by `ClientPrinter` in [BTA_SERVER.py:69-151](Code_For_BTA/BTA_SERVER.py#L69-L151) (with a stdin fallback for headless environments); in the target architecture this becomes a dedicated authorization service. The BTA server is multi-client by construction — see the "Recent Updates" section below for the threading model.

#### [Code_For_BTA/log_analysis/](Code_For_BTA/log_analysis/) — ML-based HTTP log anomaly detection (MVP)

The CVE pipeline above tells BTA what is vulnerable *in principle*. The log-analysis package gives BTA a second sense organ that observes what is happening *on the wire*: hosts ship their service logs to BTA, BTA scores each request with a pre-trained anomaly model, and flagged requests land in BTA's event log alongside the existing CVE findings.

**Design decisions** (the full plan is in the project's plan history):

- **BTA is not a network gateway** — it is a TCP server on `:65432`. A sniffer on BTA's NIC would see only traffic addressed to BTA itself. The system therefore reads **logs shipped by hosts**, not packets captured on the wire. This mirrors the Splunk-forwarder / Splunk-server pattern.
- **Unsupervised anomaly detection on URL-payload features.** A `sklearn.ensemble.IsolationForest` is trained on benign HTTP requests only, and a threshold is fixed at the 1st-percentile decision-function score on the training data. Anomalous traffic is never seen during training.
- **No RTA dependency for development or evaluation.** The MVP is self-validating against a labeled academic dataset; it does not require a running adversary to demonstrate detection.

**Training data.** The original target was the **CSIC 2010 HTTP dataset** (Spanish National Research Council), but its original csic.es / isi.csic.es URLs are dark and there is no freely-accessible mirror of the raw files. The MVP substitutes the publicly-mirrored [**HttpParamsDataset**](https://github.com/Morzeux/HttpParamsDataset) (Morzeux on GitHub) — 31,067 labeled HTTP parameter payloads spanning benign, SQL injection, XSS, command injection, and path traversal. Same task, freely downloadable. The local cache path is still named `csic2010/` for continuity.

**Feature set.** Ten numeric features extracted from each parsed HTTP request — `uri_length`, `query_length`, `num_params`, `max_param_value_length`, `special_char_count`, `digit_ratio`, `non_ascii_count`, `url_depth`, `shannon_entropy`, `method_id`. The set is from the URL-anomaly-detection literature (Kruegel & Vigna's PAYL/Anagram lineage, ECML/PKDD HTTP challenge baselines). Each alert ships back the three features with the largest |z-score| versus the training baseline, so the operator gets a "*why* this looked weird" explanation.

**Architecture.**

```
+----------------- Host (nginx server) ----------------------+
| /var/log/nginx/access.log                                  |
|       │                                                    |
| host_client.py --mode log-upload (NEW):                    |
|   every N seconds: read new lines since last byte offset,  |
|   open TCP :65432, send "LOG_UPLOAD <host_id>" greeting,   |
|   send batch as one length-prefixed message                |
+-----------------│------------------------------------------+
                  │
                  ▼
+----------------- BTA host ---------------------------------+
| BTA_SERVER.py (extended):                                  |
|   handle_client dispatches on greeting:                    |
|     "Hello..."         → existing version-upload flow      |
|     "LOG_UPLOAD <id>"  → handle_log_upload():              |
|        ├─ append raw batch to logs/raw/<host>_access.log   |
|        ├─ for each line: parse → features → score          |
|        │    if score < threshold:                          |
|        │       append logs/bta_events.jsonl                |
|        │       printer.log("[ANOMALY ...]")                |
|        └─ reply OK lines=N parsed=M alerts=K               |
+------------------------------------------------------------+
```

The model is loaded once at BTA startup. Detection is inline in the existing per-client thread — no extra process, no raw-socket privileges, no new port.

**Package layout** (new files under [Code_For_BTA/log_analysis/](Code_For_BTA/log_analysis/)):

| File | Responsibility |
|---|---|
| [parser.py](Code_For_BTA/log_analysis/parser.py) | `HTTPRequest` dataclass; `parse_nginx_line` (Common/Combined Log Format) and `parse_csic_record` |
| [features.py](Code_For_BTA/log_analysis/features.py) | 10-feature extractor, `FEATURE_ORDER`, `top_contributors` |
| [dataset.py](Code_For_BTA/log_analysis/dataset.py) | HttpParamsDataset loader; produces `(X_benign_train, X_benign_test, X_anomalous_test)` splits |
| [model_io.py](Code_For_BTA/log_analysis/model_io.py) | `train` / `save` / `load` for the IsolationForest bundle |
| [evaluate.py](Code_For_BTA/log_analysis/evaluate.py) | Precision / recall / F1 / ROC-AUC against the labeled test split |
| [train_and_eval.py](Code_For_BTA/log_analysis/train_and_eval.py) | CLI: load dataset → train → evaluate → persist artifacts |
| [detector.py](Code_For_BTA/log_analysis/detector.py) | `HTTPDetector.score_line` / `score_batch` runtime used by BTA_SERVER |
| [replay.py](Code_For_BTA/log_analysis/replay.py) | End-to-end demo: synthesizes nginx log lines from labeled payloads, ships them via the live `LOG_UPLOAD` protocol |

The trained model and its metadata live under [Code_For_BTA/models/](Code_For_BTA/models/) (`iforest.joblib`, `iforest.meta.json`, `eval_report.json`) and are committed to the repository so a fresh checkout does not need to retrain. Alerts are appended to [Code_For_BTA/logs/bta_events.jsonl](Code_For_BTA/logs/) in `{team: "BLUE", action: "detect", ...}` shape — deliberately mirroring `BattlefieldState.log_event` from the Phase-1 arena so a future tail-watcher can replay alerts into the arena scoreboard.

**Performance (held-out test split, 3,861 benign + 11,763 anomalous):**

| Metric | Value |
|---|---|
| Precision | 0.9965 |
| Recall | 0.9186 |
| F1 | 0.9559 |
| ROC-AUC | 0.9955 |

10,805 true positives, 38 false positives, 3,823 true negatives, 958 false negatives.

**Known limitation.** The current training data has `uri="/search"` for every record — it is a parameter-payload dataset, not a full-request dataset. The model therefore catches anomalies *in the query string* very well, but URL-path attacks (e.g., raw path traversal like `GET /../../../../etc/passwd`) score just inside the threshold on real nginx logs because that URI shape is out of training distribution. The fix in v2 is to augment training with varied benign URI paths, or to recompute the threshold against locally-captured real-nginx benign traffic without retraining the model itself.

**Files modified by this work:**

- [Code_For_BTA/BTA_SERVER.py](Code_For_BTA/BTA_SERVER.py) — model loaded at startup, `LOG_UPLOAD` greeting dispatch added, `handle_log_upload` scores each line and emits JSONL + admin-terminal alerts. Existing version-upload flow is untouched (greeting-string dispatch is backward-compatible).
- [Code_For_Hosts/host_client.py](Code_For_Hosts/host_client.py) — new `--mode log-upload` with byte-offset state tracking so the host only ships new bytes each interval. Default mode (`--mode versions`) preserves the existing CVE flow.
- [requirements.txt](requirements.txt) — added `scikit-learn>=1.5`, `joblib>=1.4`.

### [Code_For_Hosts/](Code_For_Hosts/) — the host-side agents

Each simulated host in the testbed runs two things:

- **A version extractor.** Platform-specific scripts that inventory the installed software. On Linux this is [`extract_version_linux.sh`](Code_For_Hosts/extract_version_scripts/extract_version_linux.sh), which detects OpenVPN, OpenSSH, and Nginx binaries and emits a `vendor:product:version` line for each. On Windows it is [`extract_version_windows.bat`](Code_For_Hosts/extract_version_scripts/extract_version_windows.bat).
- **A client + update executor.** [`host_client.py`](Code_For_Hosts/host_client.py) is the agent that connects to the BTA, ships the version file, receives the update list, and dispatches the appropriate update script. The update scripts in [`update_scripts/`](Code_For_Hosts/update_scripts/) are deliberately opinionated — they fetch the latest release from upstream (OpenVPN GitHub releases, OpenSSH tags, Nginx releases), compile from source when needed, and write to system paths.

Upstream-version lookup uses [`github_versions.py`](Code_For_Hosts/update_scripts/github_versions.py), which queries `git ls-remote --tags` for each project and parses release patterns. This replaces the earlier NVD-CPE-based "latest version" resolution, which could lag behind upstream by months.

---

## The Adversarial Loop in Practice

For Phase 1 (paper-plan arena, fully functional today):

```
┌────────────────── ROUND n ──────────────────┐
│                                              │
│   RED:   read arena_versions.txt             │
│          → NVD CVE lookup per product        │
│          → LLM generates msfvenom plan       │
│          → emit CVE report + payload plan    │
│                                              │
│   BLUE:  read arena_versions.txt             │
│          → NVD CPE latest-version lookup     │
│          → rewrite arena_versions.txt        │
│                                              │
│   SCORE: { red_vulns_found, blue_patches }   │
└──────────────────────────────────────────────┘
              ↓ repeat until Blue = 0 vulns
```

For Phase 2 (distributed testbed, WIP):

```
Host  →  BTA gateway  →  LLM Server  →  "this host is vulnerable to CVE-X"
BTA   →  Operational Admin  →  "approve update?"  →  Host runs update script
RTA   →  LLM Server + msfrpcd  →  live scan  →  CVE  →  exploit  →  session
BTA   ←  detects exploit activity on router  →  triggers patch ahead of RTA
```

The research payoff is the comparison between rounds: does the BTA learn to patch services the RTA hasn't reached yet? Does the RTA learn to target services the BTA is slow to update? Those are the dynamics the paper is about.

---

## Related Work & Intellectual Lineage

BRACE stands on a lot of 2024–2025 work. The pieces that shaped the design directly:

- **Big Sleep** (Google DeepMind / Project Zero, 2025) — autonomous LLM bug-finding in real open-source projects (FFmpeg, ImageMagick). Validated that generative reasoning can surface real CVEs.
- **XBOW** (Black Hat USA 2025) — autonomous bug-bounty agent that confirmed 1,000+ valid vulnerabilities on HackerOne by pairing LLM-guided attacks with deterministic canary verification. BRACE copies XBOW's "generative reasoning + deterministic validation" pattern verbatim.
- **CodeMender** (DeepMind) and **PatchLM** (2025) — autonomous patch agents. Grounded the blue side of the project.
- **DARPA AIxCC** (2025) — large-scale AI vulnerability discovery and repair against 54 M LOC; 43/54 synthetic and 18 real bugs patched. Demonstrated that the full detect→patch cycle is tractable.
- **Vul-RAG** (arXiv 2406.11147) and **Li et al. (2025)** (arXiv 2504.13474v1) — on retrieval-augmented and context-aware LLM vulnerability detection. Motivated BRACE's CPE-driven retrieval over pure-LLM reasoning.
- **Lasso Security's Agentic Purple Teaming report (2025)** — the conceptual framing for the continuous red↔blue feedback loop BRACE implements.

---

## Setup

### Prerequisites

- Python 3.12+
- An **OpenRouter** API key (or local LM Studio with `openai/gpt-oss-20b` loaded — the Phase 1 arena supports both)
- For the live-fire RTA only: `nmap` on PATH and Metasploit Framework (`msfrpcd`)

### Install

```bash
git clone https://github.com/NoctemLeges/BRACE.git
cd BRACE
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment

Copy `.env.example` (or create `.env`) with:

```
OPENROUTER_API_KEY=sk-or-...

# Live-fire RTA only
MSF_RPC_HOST=127.0.0.1
MSF_RPC_PORT=55553
MSF_RPC_USER=msf
MSF_RPC_PASS=your_msfrpcd_password
MSF_RPC_SSL=true
RED_TEAM_ALLOWLIST=       # extra CIDRs beyond RFC1918, comma-separated
```

---

## Running

### Phase 1 — the paper-plan arena

```bash
python Misc_Testing/run_arena.py --file VersionInfo.txt --rounds 3
```

What happens:

1. `VersionInfo.txt` is copied to `arena_versions.txt` (the original is preserved).
2. In each round, Red scans the file for CVEs and emits a payload plan; Blue rescans the file and patches vulnerable versions to the latest release.
3. A scoreboard prints after each round. The arena ends when Blue reaches zero vulnerabilities or the round cap is hit.

### Phase 2 — the distributed testbed

**BTA server** (on the defender machine):

```bash
python Code_For_BTA/BTA_SERVER.py
```

**Host client** (on each simulated host; update `SERVER_IP` in [host_client.py](Code_For_Hosts/host_client.py) first):

```bash
python Code_For_Hosts/host_client.py
```

**Live-fire RTA** *(WIP — requires Metasploit)*:

```bash
# Terminal 1: start msfrpcd
msfrpcd -P your_msfrpcd_password -U msf -a 127.0.0.1 -p 55553 -S

# Terminal 2: run the agent
python Code_For_RTA/run_red_team.py \
    --target 127.0.0.1 \
    --lhost  127.0.0.1 \
    --lport  4444
```

See [metasploit.md](metasploit.md) for the full end-to-end walkthrough (including a vulnerable Apache 2.4.49 Docker target for testing CVE-2021-41773).

### HTTP log anomaly detection

The trained model is committed to the repository (`Code_For_BTA/models/iforest.joblib`), so a fresh checkout can run inference without retraining or downloading the dataset.

```bash
# (optional) retrain — only needed if you change features or the dataset.
# Requires payload_full.csv in ./csic2010/:
mkdir -p csic2010 && curl -sSL \
    -o csic2010/payload_full.csv \
    https://raw.githubusercontent.com/Morzeux/HttpParamsDataset/master/payload_full.csv
python -m Code_For_BTA.log_analysis.train_and_eval --dataset-dir ./csic2010

# Start the BTA server. It loads iforest.joblib automatically; if the model
# is missing, log analysis is disabled and the existing CVE flow is unchanged.
python Code_For_BTA/BTA_SERVER.py

# Live end-to-end demo: synthesize nginx log lines from labeled payloads and
# ship them through the running BTA on :65432.
python -m Code_For_BTA.log_analysis.replay \
    --dataset-dir ./csic2010 --bta-host 127.0.0.1 --total 1000

# Real host log shipping (run on each nginx host):
python Code_For_Hosts/host_client.py --mode log-upload \
    --log-path /var/log/nginx/access.log \
    --bta-host <BTA_IP> \
    --host-id $(hostname) \
    --interval 10
```

Alerts are appended to `Code_For_BTA/logs/bta_events.jsonl` (one JSON object per line, includes `score`, `threshold`, `method`, `uri`, `query`, and `top_contributors` z-scores) and printed live to the per-host admin terminal.

---

## Safety

This project builds tools that can execute live exploits and dispatch privileged update scripts. The guardrails that exist today:

- **Target allowlist.** The RTA cannot scan or exploit any target outside RFC1918 (`10/8`, `172.16/12`, `192.168/16`, `127/8`) plus whatever CIDRs you add to `RED_TEAM_ALLOWLIST`. Out-of-scope targets return a plain error string to the LLM, which halts the agent.
- **Operational Admin approval.** The BTA will not dispatch an update command without explicit human confirmation on stdin.
- **No post-exploitation.** Once a session opens, the RTA system prompt instructs the model to run 1–2 identification commands and stop. No persistence, no lateral movement, no data exfil.
- **Deterministic verification.** Exploits are only considered successful when `msfrpcd` reports a matching session object — not when the model claims success.

This is still a research prototype. **Do not point any of this at infrastructure you do not own or do not have written authorization to test.**

---

## Recent Updates

### 15 May 2026

Two pieces of work landed on this date.

#### 1. BTA multi-client threading (commit [`b2c7536`](https://github.com/NoctemLeges/BRACE/commit/b2c7536))

**Problem.** The original BTA server was single-threaded and prompted the Operational Admin via a bare `input()` on stdin. As soon as a second host connected while the first was still waiting on approval, two issues surfaced: the second connection blocked on accept until the first one finished, and even if both were served, both admin prompts would compete for the same stdin with no way to tell which host the admin was approving. In a real testbed with N hosts arriving at staggered intervals, this design did not scale past one.

**Fix.** [`BTA_SERVER.py`](Code_For_BTA/BTA_SERVER.py) now:

- **Spawns a daemon thread per accepted connection** ([L322-L325](Code_For_BTA/BTA_SERVER.py#L322-L325)) — the accept loop never blocks on a single client's work. Hosts can connect simultaneously and are served concurrently.
- **Gives each client its own admin terminal window** via the new `ClientPrinter` class ([L93-L174](Code_For_BTA/BTA_SERVER.py#L93-L174)). On construction, `ClientPrinter` opens a localhost listen socket, spawns a terminal emulator (`gnome-terminal` / `konsole` / `xfce4-terminal` / `xterm` on Linux, `CREATE_NEW_CONSOLE` on Windows), and hands the spawned terminal the listen-socket port via the new [`admin_prompt_worker.py`](Code_For_BTA/admin_prompt_worker.py) helper script. The worker connects back, and from then on `printer.log(msg)` / `printer.prompt(msg)` are JSON-framed IPC calls to that one terminal — the operator gets a dedicated window per host, with all log lines and approval prompts for that host visible together.
- **Falls back cleanly when no terminal emulator is available** (CI, headless servers, etc.). The `ClientPrinter` constructor sets `self.fallback = True` and downgrades `log` to the server's stdout and `prompt` to the server's stdin, so the headless run path still works for single-client testing.

The wire protocol with hosts is unchanged — the multithreading fix is purely server-side. Existing host clients keep working without modification.

#### 2. ML-based HTTP log anomaly detection MVP (this conversation)

Added the [`Code_For_BTA/log_analysis/`](Code_For_BTA/log_analysis/) package described in the BTA section above. End-to-end:

- New `LOG_UPLOAD <host_id>` greeting on `:65432` lets hosts ship log batches alongside the existing version-upload protocol — both modes coexist on the same port, dispatched by greeting-string prefix.
- An unsupervised `IsolationForest` is trained offline on the [HttpParamsDataset](https://github.com/Morzeux/HttpParamsDataset) (a public substitute for the CSIC 2010 dataset, whose original csic.es mirrors are dark) and persisted as [`Code_For_BTA/models/iforest.joblib`](Code_For_BTA/models/iforest.joblib). The trained artifacts are committed to the repository so a fresh checkout does not need to retrain.
- BTA scores each incoming nginx log line inline and writes anomalies to `Code_For_BTA/logs/bta_events.jsonl` in `{team: "BLUE", action: "detect", ...}` shape, mirroring the Phase-1 arena's event schema.
- Held-out evaluation: **F1 = 0.9559**, **ROC-AUC = 0.9955** (3,861 benign + 11,763 anomalous test records).
- End-to-end replay demo via [`replay.py`](Code_For_BTA/log_analysis/replay.py) ships labeled records through the live BTA pipeline as if a real host had sent them; alerts include `top_contributors` z-scores so the operator sees *why* each URL was flagged.
- The host log shipper is `host_client.py --mode log-upload` with byte-offset state tracking — only new bytes are sent each interval.

Detailed design in [`Code_For_BTA/log_analysis/`](Code_For_BTA/log_analysis/) (see also the "log_analysis" subsection under `Code_For_BTA/` above for architecture, dataset rationale, features, and the known URL-path-attack limitation).

---

## Roadmap

| Status | Item |
|---|---|
| Done | Phase 1 paper-plan arena (Red + Blue against text-file hosts) |
| Done | CPE-driven two-step NVD lookup with nearest-version heuristic |
| Done | Host extractor + updater scripts (Linux, Windows) for OpenSSH, OpenVPN, Nginx |
| Done | BTA server + host client socket protocol |
| Done | BTA multi-client threading + per-host admin terminal (15 May 2026) |
| Done | ML-based HTTP log anomaly detection MVP — IsolationForest, F1=0.96 (15 May 2026) |
| Done | Live-fire RTA tool surface (nmap + NVD + msfrpcd) |
| WIP | Networked LLM Server with isolated per-agent contexts |
| WIP | Operational Admin as a dedicated authorization service |
| WIP | Two-subnet router testbed with BTA dual-homed across both subnets |
| WIP | RTA wired into the arena (Blue reacts to real exploit activity) |
| WIP | Log-analysis v2: augment training with varied URI paths so URL-path attacks fall in-distribution |
| Planned | Second log source: `auth.log` for sshd brute-force / failed-login detection |
| Planned | Streaming `tail -f` log shipping (replace 10–30 s batch interval) |
| Planned | Rate-limit / block-IP detector (rule-based, with optional ML upgrade) |
| Planned | Co-evolution metrics: round-over-round detection delta and patch lead time |

---

## Citing / Reading the Paper

The research paper (in IEEE conference format) is titled *"Agentic AI in Conflict: Emergent Dynamics of Red–Blue Co-Evolution"*. The meeting minutes and progress log that document the full design journey — including every dead end — are in [BRACE_Documentation.pdf](BRACE_Documentation.pdf) (Phase 1) and [BRACE_Documentation_Part2.pdf](BRACE_Documentation_Part2.pdf) (Phase 2).

If you use BRACE or its ideas, please cite the paper and link back to this repository.
