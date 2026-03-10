import time
import json
import requests

_cache: dict[str, dict] = {}
_TTL = 3600  # 1 hour


def cached_cve_lookup(product_string: str) -> dict:
    """Query NVD CVE API with caching to avoid redundant calls."""
    key = product_string.strip()
    now = time.time()

    if key in _cache and (now - _cache[key]["ts"]) < _TTL:
        return _cache[key]["data"]

    cve_api = "https://services.nvd.nist.gov/rest/json/cves/2.0?virtualMatchString=cpe:2.3:*:"
    url = cve_api + key
    response = requests.get(url)
    data = response.json()

    _cache[key] = {"ts": now, "data": data}
    return data


def cached_cpe_lookup(vendor: str, product: str) -> dict:
    """Query NVD CPE API with caching."""
    key = f"cpe:{vendor}:{product}"
    now = time.time()

    if key in _cache and (now - _cache[key]["ts"]) < _TTL:
        return _cache[key]["data"]

    cpe_api = "https://services.nvd.nist.gov/rest/json/cpes/2.0?cpeMatchString=cpe:2.3:a:"
    url = cpe_api + f"{vendor}:{product}"
    response = requests.get(url)
    data = response.json()

    _cache[key] = {"ts": now, "data": data}
    return data
