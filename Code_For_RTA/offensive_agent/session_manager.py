import time

from Code_For_RTA.offensive_agent import metasploit_client


def wait_for_session(target_host: str, timeout: float = 30.0, poll_interval: float = 2.0) -> dict | None:
    """Poll msfrpc sessions for one matching target_host. Returns the session dict or None."""
    deadline = time.time() + timeout
    seen_ids: set = set()
    while time.time() < deadline:
        for s in metasploit_client.list_sessions():
            if s["id"] in seen_ids:
                continue
            seen_ids.add(s["id"])
            if target_host in str(s.get("target_host", "")) or target_host in str(s.get("tunnel_peer", "")):
                return s
        time.sleep(poll_interval)
    return None
