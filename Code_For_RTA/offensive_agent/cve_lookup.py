import requests

NVD_CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0?virtualMatchString=cpe:2.3:*:"


def lookup_cves(vendor_product_version: str, max_results: int = 10) -> list[dict]:
    """Query NVD for CVEs matching 'vendor:product:version'.

    Returns a list of {cve_id, description, cvss} dicts, capped at max_results.
    """
    url = NVD_CVE_API + vendor_product_version.strip()
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    out: list[dict] = []
    for vuln in data.get("vulnerabilities", []):
        cve = vuln.get("cve", {})
        cve_id = cve.get("id")
        if not cve_id:
            continue

        description = ""
        for d in cve.get("descriptions", []):
            if d.get("lang") == "en":
                description = d.get("value", "")
                break

        metrics = cve.get("metrics", {})
        cvss = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            arr = metrics.get(key)
            if arr:
                cvss = arr[0].get("cvssData", {}).get("baseScore")
                break

        out.append({
            "cve_id": cve_id,
            "description": description[:240],
            "cvss": cvss,
        })
        if len(out) >= max_results:
            break
    return out
