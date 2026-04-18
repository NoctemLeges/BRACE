# tool_runner.py
import json
from pathlib import Path
import lmstudio as lms

# Import your module
import Demo.checkVulnVersions as dm  

def read_version_info(filename: str) -> list[str]:
    """
    Read version lines from a file.

    Args:
        filename: Path to a file with lines like "vendor:product:version".

    Returns:
        A list of version strings.
    """
    return dm.readVersionInfo(filename)

def check_vuln_versions(infos: list[str]) -> dict[str, int]:
    """
    Check vulnerabilities for each "vendor:product:version".

    Args:
        infos: List of product strings.

    Returns:
        Mapping product -> vulnerability count (ints).
    """
    # Convert OrderedDict to plain dict for JSON-serializability
    return dict(dm.checkVulnVersion(infos))

def latest_for_product(product: str) -> str:
    """
    Get latest version string for a single product.

    Args:
        product: "vendor:product:version"

    Returns:
        "vendor:product:latest_version"
    """
    return dm.updateToLatestVersion(product)

def update_file_to_latest(filename: str, vuln_counts: dict[str, int]) -> dict:
    """
    Compute latest versions and write them to filename (non-interactive).

    Args:
        filename: Destination file to write.
        vuln_counts: Mapping of product->vuln_count.

    Returns:
        Summary dict with 'written': True/False and 'lines_written'
    """
    #Making retrieveLatestVersion non-interactive:
    updated_lines: list[str] = []
    for product, n in vuln_counts.items():
        if n > 0:
            updated_lines.append(dm.updateToLatestVersion(product) + "\n")
        else:
            updated_lines.append(product + "\n")
    Path(filename).write_text("".join(updated_lines), encoding="utf-8")
    return {"written": True, "lines_written": len(updated_lines)}

def scan_and_update(filename: str, write_updates: bool = False) -> dict:
    """
    One-shot tool: read versions, check CVEs, optionally write latest versions.

    Args:
        filename: Path to VersionInfo.txt
        write_updates: If True, writes latest versions back to the file.

    Returns:
        {
          "summary": {product: vuln_count, ...},
          "latest": {product: latest_string, ...},
          "wrote": bool
        }
    """
    infos = dm.readVersionInfo(filename)
    counts = dict(dm.checkVulnVersion(infos))
    latest_map = {}
    for p, n in counts.items():
        latest_map[p] = dm.updateToLatestVersion(p) if n > 0 else p
    wrote = False
    if write_updates:
        lines = [latest_map[p] + "\n" for p in counts.keys()]
        Path(filename).write_text("".join(lines), encoding="utf-8")
        wrote = True
    return {"summary": counts, "latest": latest_map, "wrote": wrote}

# ---------------- LM Studio wiring ----------------

model = lms.llm("openai/gpt-oss-20b") 
system_prompt = (
    "You are a local assistant with tools for reading a VersionInfo file, "
    "checking NVD vulnerabilities, and updating to latest product versions. "
    "Prefer calling tools when the user asks you to scan, check, or update."
)

chat = lms.Chat(system_prompt)

# Register tools. They must have clear type hints + docstrings.
tools = [
    read_version_info,
    check_vuln_versions,
    latest_for_product,
    update_file_to_latest,
    scan_and_update,
]

def print_fragment(fragment, round_index=0):
    print(fragment.content, end="", flush=True)

if __name__ == "__main__":
    while True:
        try:
            user_input = input("User (blank to exit): ").strip()
        except EOFError:
            print()
            break
        if not user_input:
            break

        chat.add_user_message(user_input)
        print("Assistant: ", end="", flush=True)

        # Let the model choose and call tools
        model.act(
            chat,
            tools,
            on_message=chat.append,               
            on_prediction_fragment=print_fragment,  
        )
        print()
