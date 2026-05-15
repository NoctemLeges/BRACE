"""Compute detection metrics against a labeled test set."""
import json
import os

import numpy as np
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .model_io import ModelBundle


def evaluate(bundle: ModelBundle, X_benign: np.ndarray,
             X_anomalous: np.ndarray) -> dict:
    """Score both pools and report metrics.

    Convention: y=1 means anomaly. Higher decision_function = more normal,
    so we treat (-score) as the anomaly score for ROC-AUC.
    """
    X = np.vstack([X_benign, X_anomalous])
    y = np.concatenate([
        np.zeros(X_benign.shape[0], dtype=np.int32),
        np.ones(X_anomalous.shape[0], dtype=np.int32),
    ])
    scores = bundle.model.decision_function(X)
    preds = (scores < bundle.threshold).astype(np.int32)

    tn, fp, fn, tp = confusion_matrix(y, preds).ravel()
    metrics = {
        "n_benign": int(X_benign.shape[0]),
        "n_anomalous": int(X_anomalous.shape[0]),
        "threshold": float(bundle.threshold),
        "precision": float(precision_score(y, preds, zero_division=0)),
        "recall": float(recall_score(y, preds, zero_division=0)),
        "f1": float(f1_score(y, preds, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, -scores)),
        "confusion": {
            "tp": int(tp), "fp": int(fp),
            "tn": int(tn), "fn": int(fn),
        },
    }
    return metrics


def write_report(metrics: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)


def print_report(metrics: dict) -> None:
    print("=" * 60)
    print("HTTP-payload Isolation Forest evaluation")
    print("=" * 60)
    print(f"  Benign test:    {metrics['n_benign']}")
    print(f"  Anomalous test: {metrics['n_anomalous']}")
    print(f"  Threshold:      {metrics['threshold']:.6f}")
    print(f"  Precision:      {metrics['precision']:.4f}")
    print(f"  Recall:         {metrics['recall']:.4f}")
    print(f"  F1:             {metrics['f1']:.4f}")
    print(f"  ROC-AUC:        {metrics['roc_auc']:.4f}")
    c = metrics["confusion"]
    print(f"  Confusion:      TP={c['tp']}  FP={c['fp']}  TN={c['tn']}  FN={c['fn']}")
    print("=" * 60)
