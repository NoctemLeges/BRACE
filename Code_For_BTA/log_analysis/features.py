"""Extract a fixed-size numeric feature vector from an HTTPRequest."""
import math
from collections import Counter

import numpy as np

from .parser import HTTPRequest, url_decode


FEATURE_ORDER = [
    "uri_length",
    "query_length",
    "num_params",
    "max_param_value_length",
    "special_char_count",
    "digit_ratio",
    "non_ascii_count",
    "url_depth",
    "shannon_entropy",
    "method_id",
]

NUM_FEATURES = len(FEATURE_ORDER)

_METHOD_MAP = {"GET": 0, "POST": 1, "PUT": 2, "DELETE": 3}
_SPECIAL_CHARS = set(";'\"<>()%&|`\\=*+{}[]?!$#@~^")


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    total = len(s)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _digit_ratio(s: str) -> float:
    if not s:
        return 0.0
    digits = sum(1 for ch in s if ch.isdigit())
    alnums = sum(1 for ch in s if ch.isalnum())
    if alnums == 0:
        return 0.0
    return digits / alnums


def _params(query: str) -> list[tuple[str, str]]:
    if not query:
        return []
    out = []
    for pair in query.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
        else:
            k, v = pair, ""
        out.append((k, v))
    return out


def extract(req: HTTPRequest) -> np.ndarray:
    """Return a length-10 float32 vector. Order matches FEATURE_ORDER."""
    uri_decoded = url_decode(req.uri)
    query_decoded = url_decode(req.query)
    combined = uri_decoded + ("?" + query_decoded if query_decoded else "")

    params = _params(req.query)
    param_values = [v for _, v in params]
    max_pv_len = max((len(url_decode(v)) for v in param_values), default=0)

    special_count = sum(1 for ch in combined if ch in _SPECIAL_CHARS)
    non_ascii = sum(1 for ch in combined if ord(ch) > 127)
    url_depth = uri_decoded.count("/")
    entropy = _shannon_entropy(combined)
    method_id = _METHOD_MAP.get(req.method.upper(), 4)

    vec = np.array([
        len(uri_decoded),
        len(query_decoded),
        len(params),
        max_pv_len,
        special_count,
        _digit_ratio(combined),
        non_ascii,
        url_depth,
        entropy,
        method_id,
    ], dtype=np.float32)
    return vec


def batch_extract(reqs: list[HTTPRequest]) -> np.ndarray:
    """Stack feature vectors for a list of requests."""
    if not reqs:
        return np.zeros((0, NUM_FEATURES), dtype=np.float32)
    return np.vstack([extract(r) for r in reqs])


def top_contributors(x: np.ndarray, baseline_mean: np.ndarray,
                     baseline_std: np.ndarray, k: int = 3) -> list[dict]:
    """Return the k features with largest |z-score| vs the baseline.

    Used to annotate alerts with a human-readable "why this looked weird" hint.
    """
    std_safe = np.where(baseline_std > 1e-6, baseline_std, 1.0)
    z = (x - baseline_mean) / std_safe
    idx = np.argsort(-np.abs(z))[:k]
    return [
        {"feature": FEATURE_ORDER[i], "value": float(x[i]), "z": float(z[i])}
        for i in idx
    ]
