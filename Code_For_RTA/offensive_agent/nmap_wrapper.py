import shutil

try:
    import nmap as _nmap
except ImportError as e:
    _nmap = None
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None


def _require_nmap():
    if _nmap is None:
        raise RuntimeError(f"python-nmap not installed: {_IMPORT_ERROR}")
    if shutil.which("nmap") is None:
        raise RuntimeError("nmap binary not found on PATH. Install nmap (e.g., `brew install nmap`).")


def run_service_scan(target: str, ports: str = "1-10000", intensity: int = 5) -> list[dict]:
    """Run `nmap -sV` and return a flat list of discovered services.

    Each entry: {host, port, proto, state, service, product, version, extrainfo, cpe}.
    """
    _require_nmap()
    scanner = _nmap.PortScanner()
    args = f"-sV --version-intensity {intensity} -Pn --open -T4"
    scanner.scan(hosts=target, ports=ports, arguments=args)

    results: list[dict] = []
    for host in scanner.all_hosts():
        for proto in scanner[host].all_protocols():
            for port in sorted(scanner[host][proto].keys()):
                p = scanner[host][proto][port]
                cpe_list = p.get("cpe") or ""
                if isinstance(cpe_list, list):
                    cpe_list = ",".join(cpe_list)
                results.append({
                    "host": host,
                    "port": port,
                    "proto": proto,
                    "state": p.get("state", ""),
                    "service": p.get("name", ""),
                    "product": p.get("product", ""),
                    "version": p.get("version", ""),
                    "extrainfo": p.get("extrainfo", ""),
                    "cpe": cpe_list,
                })
    return results


def fingerprint_port(host: str, port: int) -> dict:
    """Deep version probe on a single port. Returns a single service dict or {} if closed."""
    results = run_service_scan(host, ports=str(port), intensity=9)
    for r in results:
        if r["port"] == port:
            return r
    return {}


def cpe_to_vendor_product_version(cpe: str) -> str | None:
    """Convert a CPE string like 'cpe:/a:apache:http_server:2.4.49' to 'apache:http_server:2.4.49'."""
    if not cpe:
        return None
    # Take first CPE if comma-separated
    first = cpe.split(",")[0].strip()
    parts = first.split(":")
    # cpe:/a:vendor:product:version  or  cpe:2.3:a:vendor:product:version:...
    if first.startswith("cpe:/"):
        if len(parts) >= 5:
            return f"{parts[2]}:{parts[3]}:{parts[4]}"
    elif first.startswith("cpe:2.3:"):
        if len(parts) >= 6:
            return f"{parts[3]}:{parts[4]}:{parts[5]}"
    return None
