import ipaddress
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code_For_LLM_Server.llm_config import RED_TEAM_ALLOWLIST

DEFAULT_ALLOWED_CIDRS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
]


def _load_allowed_networks() -> list[ipaddress._BaseNetwork]:
    cidrs = list(DEFAULT_ALLOWED_CIDRS)
    if RED_TEAM_ALLOWLIST:
        cidrs += [c.strip() for c in RED_TEAM_ALLOWLIST.split(",") if c.strip()]
    return [ipaddress.ip_network(c, strict=False) for c in cidrs]


_ALLOWED_NETWORKS = _load_allowed_networks()


def is_target_allowed(target: str) -> bool:
    """Return True if every host in target (IP, CIDR, or range like 192.168.1.1-10) is inside the allowlist."""
    try:
        if "-" in target and "/" not in target:
            base, _, tail = target.partition("-")
            start = ipaddress.ip_address(base.strip())
            if "." in tail:
                end = ipaddress.ip_address(tail.strip())
            else:
                octets = base.strip().split(".")
                octets[-1] = tail.strip()
                end = ipaddress.ip_address(".".join(octets))
            return all(
                any(ipaddress.ip_address(int(start) + i) in net for net in _ALLOWED_NETWORKS)
                for i in range(int(end) - int(start) + 1)
            )

        net = ipaddress.ip_network(target, strict=False)
        return any(net.subnet_of(allowed) for allowed in _ALLOWED_NETWORKS if net.version == allowed.version)
    except ValueError:
        return False


def require_allowed(target: str) -> str | None:
    """Return None if target is allowed, else a human-readable error string for the LLM."""
    if is_target_allowed(target):
        return None
    allowed = ", ".join(str(n) for n in _ALLOWED_NETWORKS)
    return (
        f"Error: target '{target}' is outside the authorized scope. "
        f"Allowed ranges: {allowed}. "
        f"Add extra CIDRs to RED_TEAM_ALLOWLIST env var if needed."
    )
