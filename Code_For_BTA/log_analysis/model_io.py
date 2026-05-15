"""Train, persist, and load the Isolation Forest model + threshold."""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from .features import FEATURE_ORDER


THRESHOLD_PERCENTILE = 1.0


@dataclass
class ModelBundle:
    model: IsolationForest
    threshold: float
    feature_order: list
    baseline_mean: np.ndarray
    baseline_std: np.ndarray
    meta: dict = field(default_factory=dict)


def train(X: np.ndarray, n_estimators: int = 200) -> ModelBundle:
    """Fit IsolationForest on benign-only features. Threshold = 1st percentile."""
    model = IsolationForest(
        n_estimators=n_estimators,
        contamination="auto",
        random_state=0,
        n_jobs=-1,
    )
    model.fit(X)
    scores = model.decision_function(X)
    threshold = float(np.percentile(scores, THRESHOLD_PERCENTILE))
    baseline_mean = X.mean(axis=0)
    baseline_std = X.std(axis=0)
    meta = {
        "train_n": int(X.shape[0]),
        "n_estimators": n_estimators,
        "threshold_percentile": THRESHOLD_PERCENTILE,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    return ModelBundle(
        model=model,
        threshold=threshold,
        feature_order=list(FEATURE_ORDER),
        baseline_mean=baseline_mean,
        baseline_std=baseline_std,
        meta=meta,
    )


def save(bundle: ModelBundle, model_path: str) -> str:
    """Persist the bundle to <model_path> and a sibling .meta.json."""
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump({
        "model": bundle.model,
        "threshold": bundle.threshold,
        "feature_order": bundle.feature_order,
        "baseline_mean": bundle.baseline_mean,
        "baseline_std": bundle.baseline_std,
        "meta": bundle.meta,
    }, model_path)
    meta_path = _meta_path(model_path)
    with open(meta_path, "w") as f:
        json.dump({
            "threshold": bundle.threshold,
            "feature_order": bundle.feature_order,
            "baseline_mean": bundle.baseline_mean.tolist(),
            "baseline_std": bundle.baseline_std.tolist(),
            **bundle.meta,
        }, f, indent=2)
    return meta_path


def load(model_path: str) -> ModelBundle:
    obj = joblib.load(model_path)
    return ModelBundle(
        model=obj["model"],
        threshold=float(obj["threshold"]),
        feature_order=list(obj["feature_order"]),
        baseline_mean=np.asarray(obj["baseline_mean"]),
        baseline_std=np.asarray(obj["baseline_std"]),
        meta=dict(obj.get("meta", {})),
    )


def _meta_path(model_path: str) -> str:
    base, _ = os.path.splitext(model_path)
    return base + ".meta.json"


def try_load(model_path: str) -> Optional[ModelBundle]:
    if not os.path.isfile(model_path):
        return None
    try:
        return load(model_path)
    except Exception:
        return None
