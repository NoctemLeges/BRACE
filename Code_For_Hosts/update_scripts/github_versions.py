"""
Fetch the latest stable versions of nginx, openssh, and openvpn from GitHub tags.

Replaces the NVD CPE API approach (updateToLatestVersion) with direct GitHub lookups
so the arena blue team patches to the actual latest release.
"""

import re
import subprocess
import sys

GITHUB_REPOS = {
    "nginx": "https://github.com/nginx/nginx.git",
    "openssh": "https://github.com/openssh/openssh-portable.git",
    "openvpn": "https://github.com/OpenVPN/openvpn.git",
}


def _git_tags(repo_url):
    """Fetch all tags from a GitHub repo via git ls-remote."""
    result = subprocess.run(
        ["git", "ls-remote", "--tags", repo_url],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-remote failed for {repo_url}: {result.stderr}")
    return result.stdout


def _latest_nginx():
    """Parse release-X.Y.Z tags, return latest version string."""
    tags = _git_tags(GITHUB_REPOS["nginx"])
    versions = re.findall(r'refs/tags/release-(\d+\.\d+\.\d+)\s*$', tags, re.MULTILINE)
    if not versions:
        raise RuntimeError("No nginx release tags found")
    versions.sort(key=lambda v: list(map(int, v.split('.'))))
    return versions[-1]


def _latest_openssh():
    """Parse V_X_Y_PZ tags, return version like 10.3p1."""
    tags = _git_tags(GITHUB_REPOS["openssh"])
    matches = re.findall(r'refs/tags/V_(\d+)_(\d+)_P(\d+)\s*$', tags, re.MULTILINE)
    if not matches:
        raise RuntimeError("No openssh release tags found")
    matches.sort(key=lambda m: (int(m[0]), int(m[1]), int(m[2])))
    major, minor, patch = matches[-1]
    return f"{major}.{minor}p{patch}"


def _latest_openvpn():
    """Parse vX.Y.Z tags (excluding alpha/beta/rc), return latest version."""
    tags = _git_tags(GITHUB_REPOS["openvpn"])
    # Only match stable releases: vX.Y.Z with no suffix
    versions = re.findall(r'refs/tags/v(\d+\.\d+\.\d+)\s*$', tags, re.MULTILINE)
    if not versions:
        raise RuntimeError("No openvpn stable release tags found")
    versions.sort(key=lambda v: list(map(int, v.split('.'))))
    return versions[-1]


_PRODUCT_MAP = {
    "nginx": ("f5", _latest_nginx),
    "openssh": ("openbsd", _latest_openssh),
    "openvpn": ("openvpn", _latest_openvpn),
}


def get_latest_from_github(product_string):
    """
    Drop-in replacement for updateToLatestVersion().

    Args:
        product_string: "vendor:product:version" (e.g. "f5:nginx:0.5.6")

    Returns:
        "vendor:product:latest_version" (e.g. "f5:nginx:1.29.8")
    """
    parts = product_string.split(":")
    product_name = parts[1]

    if product_name not in _PRODUCT_MAP:
        raise ValueError(f"Unknown product: {product_name}")

    vendor, fetch_fn = _PRODUCT_MAP[product_name]
    latest = fetch_fn()
    return f"{vendor}:{product_name}:{latest}"


if __name__ == "__main__":
    # Quick test
    for test in ["f5:nginx:0.5.6", "openbsd:openssh:7.7", "openvpn:openvpn:2.6.2"]:
        result = get_latest_from_github(test)
        print(f"  {test} -> {result}")
