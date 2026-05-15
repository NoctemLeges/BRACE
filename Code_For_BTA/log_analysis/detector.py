"""Server-side runtime: score nginx log lines against a pre-trained model."""
import time
from typing import Optional

import numpy as np

from .features import extract, top_contributors
from .model_io import ModelBundle, load
from .parser import parse_nginx_line


class HTTPDetector:
    """Wraps a trained IsolationForest and scores nginx access lines."""

    def __init__(self, bundle: ModelBundle):
        self.bundle = bundle

    @classmethod
    def from_path(cls, model_path: str) -> "HTTPDetector":
        return cls(load(model_path))

    def score_line(self, line: str, host_id: str = "") -> Optional[dict]:
        """Return an alert dict if the line is anomalous, else None.

        A line that fails to parse is silently dropped (returns None).
        """
        req = parse_nginx_line(line)
        if req is None:
            return None
        x = extract(req)
        score = float(self.bundle.model.decision_function(x.reshape(1, -1))[0])
        if score >= self.bundle.threshold:
            return None
        return {
            "type": "anomaly",
            "ts": time.time(),
            "host": host_id,
            "score": score,
            "threshold": self.bundle.threshold,
            "method": req.method,
            "uri": req.uri,
            "query": req.query,
            "top_contributors": top_contributors(
                x, self.bundle.baseline_mean, self.bundle.baseline_std, k=3,
            ),
        }

    def score_batch(self, lines: list[str], host_id: str = "") -> tuple[list[dict], int]:
        """Score a list of nginx log lines, return (alerts, total_parsed)."""
        if not lines:
            return [], 0
        reqs = [parse_nginx_line(ln) for ln in lines]
        keep_idx = [i for i, r in enumerate(reqs) if r is not None]
        if not keep_idx:
            return [], 0
        X = np.vstack([extract(reqs[i]) for i in keep_idx])
        scores = self.bundle.model.decision_function(X)
        alerts = []
        for j, i in enumerate(keep_idx):
            s = float(scores[j])
            if s >= self.bundle.threshold:
                continue
            r = reqs[i]
            alerts.append({
                "type": "anomaly",
                "ts": time.time(),
                "host": host_id,
                "score": s,
                "threshold": self.bundle.threshold,
                "method": r.method,
                "uri": r.uri,
                "query": r.query,
                "top_contributors": top_contributors(
                    X[j], self.bundle.baseline_mean, self.bundle.baseline_std, k=3,
                ),
            })
        return alerts, len(keep_idx)
