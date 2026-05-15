"""Load the HTTP-payloads anomaly dataset and produce feature matrices.

We use the HttpParamsDataset (Morzeux/HttpParamsDataset on GitHub) as a
publicly-mirrored substitute for the CSIC 2010 corpus. Each row is one HTTP
parameter payload with a benign/anomalous label and a fine-grained attack
category (sqli/xss/cmdi/path-traversal).

The original CSIC 2010 download URLs at csic.es / isi.csic.es have been dark
for years and there is no freely-accessible mirror of the raw files at time
of writing. HttpParamsDataset is the same task (URL-payload classification),
labelled, and downloads cleanly from GitHub.

File: payload_full.csv with columns payload,length,attack_type,label.
Source: https://raw.githubusercontent.com/Morzeux/HttpParamsDataset/master/payload_full.csv
"""
import csv
import hashlib
import os
import sys
from dataclasses import dataclass

import numpy as np

from .features import batch_extract
from .parser import HTTPRequest


DATASET_FILE = "payload_full.csv"
DATASET_URL = (
    "https://raw.githubusercontent.com/Morzeux/HttpParamsDataset/master/payload_full.csv"
)


@dataclass
class DatasetSplits:
    X_benign_train: np.ndarray
    X_benign_test: np.ndarray
    X_anomalous_test: np.ndarray
    counts: dict
    file_sha256: str


def ensure_present(dest_dir: str) -> None:
    path = os.path.join(dest_dir, DATASET_FILE)
    if not os.path.isfile(path):
        print(f"[!] Missing {DATASET_FILE} in {dest_dir}", file=sys.stderr)
        print(f"    Download once with:", file=sys.stderr)
        print(f"      mkdir -p {dest_dir} && "
              f"curl -sSL -o {path} '{DATASET_URL}'", file=sys.stderr)
        sys.exit(1)


def _payload_to_request(payload: str) -> HTTPRequest:
    """Wrap a parameter payload as a synthetic GET /search?q=<payload> request."""
    return HTTPRequest(
        method="GET",
        uri="/search",
        query="q=" + (payload or ""),
        body="",
        headers={},
    )


def _read_rows(path: str) -> tuple[list[dict], str]:
    with open(path, "rb") as f:
        data = f.read()
    sha = hashlib.sha256(data).hexdigest()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    reader = csv.DictReader(text.splitlines())
    rows = [r for r in reader if r.get("label") in ("norm", "anom")]
    return rows, sha


def load_dataset(dest_dir: str, train_ratio: float = 0.8,
                 seed: int = 0) -> DatasetSplits:
    ensure_present(dest_dir)
    rows, sha = _read_rows(os.path.join(dest_dir, DATASET_FILE))

    benign = [r for r in rows if r["label"] == "norm"]
    anom = [r for r in rows if r["label"] == "anom"]

    rng = np.random.default_rng(seed)
    idx = np.arange(len(benign))
    rng.shuffle(idx)
    split = int(len(idx) * train_ratio)
    train_idx = idx[:split]
    test_idx = idx[split:]

    benign_train = [_payload_to_request(benign[i]["payload"]) for i in train_idx]
    benign_test = [_payload_to_request(benign[i]["payload"]) for i in test_idx]
    anom_test = [_payload_to_request(r["payload"]) for r in anom]

    return DatasetSplits(
        X_benign_train=batch_extract(benign_train),
        X_benign_test=batch_extract(benign_test),
        X_anomalous_test=batch_extract(anom_test),
        counts={
            "benign_total": len(benign),
            "anomalous_total": len(anom),
            "benign_train": len(benign_train),
            "benign_test": len(benign_test),
            "anomalous_test": len(anom_test),
        },
        file_sha256=sha,
    )


def load_replay_rows(dest_dir: str) -> tuple[list[dict], list[dict]]:
    """Return (benign_rows, anomalous_rows) for the replay demo."""
    ensure_present(dest_dir)
    rows, _ = _read_rows(os.path.join(dest_dir, DATASET_FILE))
    benign = [r for r in rows if r["label"] == "norm"]
    anom = [r for r in rows if r["label"] == "anom"]
    return benign, anom
