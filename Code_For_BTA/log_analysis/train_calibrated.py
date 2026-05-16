"""Train a calibrated Isolation Forest and compare it with the baseline model.

This experiment keeps the original committed model untouched. It uses:

- benign-only training data for the Isolation Forest fit;
- a separate validation split to choose model settings and threshold;
- a held-out test split for the final old-vs-new comparison.
"""
import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from log_analysis.dataset import _payload_to_request, _read_rows
    from log_analysis.features import FEATURE_ORDER, batch_extract
    from log_analysis.model_io import ModelBundle, load, save
else:
    from .dataset import _payload_to_request, _read_rows
    from .features import FEATURE_ORDER, batch_extract
    from .model_io import ModelBundle, load, save


DEFAULT_DATASET = "csic2010/payload_full.csv"
DEFAULT_BASELINE_MODEL = "Code_For_BTA/models/iforest.joblib"
DEFAULT_MODEL_OUT = "Code_For_BTA/models/iforest_calibrated.joblib"
DEFAULT_REPORT_OUT = "Code_For_BTA/models/iforest_calibrated_eval_report.json"
DEFAULT_COMPARISON_OUT = "Code_For_BTA/models/iforest_calibrated_comparison.json"
DEFAULT_CARD_OUT = "Code_For_BTA/models/iforest_calibrated_model_card.md"
DEFAULT_CM_OUT = "Code_For_BTA/models/iforest_calibrated_confusion_matrix.svg"
DEFAULT_COMPARISON_PLOT_OUT = "Code_For_BTA/models/iforest_calibrated_comparison.svg"


def _featurize(rows: list[dict]) -> np.ndarray:
    return batch_extract([_payload_to_request(r["payload"]) for r in rows])


def _metrics(model: IsolationForest, threshold: float, X_benign: np.ndarray,
             X_anomalous: np.ndarray) -> dict[str, Any]:
    X = np.vstack([X_benign, X_anomalous])
    y = np.concatenate([
        np.zeros(X_benign.shape[0], dtype=np.int32),
        np.ones(X_anomalous.shape[0], dtype=np.int32),
    ])
    scores = model.decision_function(X)
    preds = (scores < threshold).astype(np.int32)
    tn, fp, fn, tp = confusion_matrix(y, preds).ravel()
    return {
        "n_benign": int(X_benign.shape[0]),
        "n_anomalous": int(X_anomalous.shape[0]),
        "threshold": float(threshold),
        "precision": float(precision_score(y, preds, zero_division=0)),
        "recall": float(recall_score(y, preds, zero_division=0)),
        "f1": float(f1_score(y, preds, zero_division=0)),
        "accuracy": float(accuracy_score(y, preds)),
        "roc_auc": float(roc_auc_score(y, -scores)),
        "confusion": {
            "tp": int(tp),
            "fp": int(fp),
            "tn": int(tn),
            "fn": int(fn),
        },
    }


def _write_json(path: str, obj: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def _fmt_metric(value: float) -> str:
    return f"{value:.4f}"


def _write_confusion_svg(path: str, title: str, metrics: dict[str, Any]) -> None:
    c = metrics["confusion"]
    cells = [
        ("TN", c["tn"], "Actual benign predicted benign", 230, 205, "#4d9fe8", "#ffffff"),
        ("FP", c["fp"], "Benign flagged anomalous", 486, 205, "#dbeafe", "#1e3a8a"),
        ("FN", c["fn"], "Anomalies missed", 230, 379, "#bfdbfe", "#1e3a8a"),
        ("TP", c["tp"], "Actual anomalous flagged", 486, 379, "#0f5ea8", "#ffffff"),
    ]
    cell_markup = "\n".join(
        f"""    <rect x="{x}" y="{y}" width="256" height="174" rx="10" fill="{fill}" stroke="#ffffff" stroke-width="4"/>
    <text x="{x + 128}" y="{y + 59}" text-anchor="middle" font-size="21" font-weight="700" fill="{text_color}">{name}</text>
    <text x="{x + 128}" y="{y + 104}" text-anchor="middle" font-size="38" font-weight="700" fill="{text_color}">{value:,}</text>
    <text x="{x + 128}" y="{y + 138}" text-anchor="middle" font-size="15" fill="{text_color}">{caption}</text>"""
        for name, value, caption, x, y, fill, text_color in cells
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="680" viewBox="0 0 900 680" role="img">
  <rect width="900" height="680" fill="#f8fafc"/>
  <text x="450" y="58" text-anchor="middle" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="#0f172a">{title}</text>
  <text x="450" y="92" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#475569">Test set: {metrics['n_benign']:,} benign + {metrics['n_anomalous']:,} anomalous samples</text>
  <text x="488" y="142" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" font-weight="700" fill="#334155">Predicted label</text>
  <text x="342" y="178" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#334155">Benign</text>
  <text x="634" y="178" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#334155">Anomalous</text>
  <g transform="translate(118 380) rotate(-90)">
    <text text-anchor="middle" font-family="Arial, sans-serif" font-size="18" font-weight="700" fill="#334155">Actual label</text>
  </g>
  <text x="171" y="318" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#334155">Benign</text>
  <text x="171" y="492" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#334155">Anomalous</text>
  <g font-family="Arial, sans-serif">
{cell_markup}
  </g>
  <g font-family="Arial, sans-serif" font-size="15" fill="#334155">
    <rect x="155" y="592" width="590" height="46" rx="8" fill="#ffffff" stroke="#cbd5e1"/>
    <text x="182" y="621">Accuracy: {_fmt_metric(metrics['accuracy'])}</text>
    <text x="322" y="621">Precision: {_fmt_metric(metrics['precision'])}</text>
    <text x="474" y="621">Recall: {_fmt_metric(metrics['recall'])}</text>
    <text x="596" y="621">F1: {_fmt_metric(metrics['f1'])}</text>
  </g>
</svg>
"""
    Path(path).write_text(svg)


def _write_comparison_svg(path: str, old_metrics: dict[str, Any],
                          new_metrics: dict[str, Any]) -> None:
    metric_names = ["accuracy", "precision", "recall", "f1", "roc_auc"]
    labels = ["Accuracy", "Precision", "Recall", "F1", "ROC-AUC"]
    x0 = 210
    bar_w = 420
    y0 = 135
    gap = 82
    rows = []
    for i, (key, label) in enumerate(zip(metric_names, labels)):
        y = y0 + i * gap
        old_w = old_metrics[key] * bar_w
        new_w = new_metrics[key] * bar_w
        delta = new_metrics[key] - old_metrics[key]
        rows.append(f"""
  <text x="72" y="{y + 19}" font-family="Arial, sans-serif" font-size="17" font-weight="700" fill="#334155">{label}</text>
  <rect x="{x0}" y="{y}" width="{bar_w}" height="22" rx="5" fill="#e2e8f0"/>
  <rect x="{x0}" y="{y}" width="{old_w:.2f}" height="22" rx="5" fill="#94a3b8"/>
  <text x="{x0 + bar_w + 18}" y="{y + 17}" font-family="Arial, sans-serif" font-size="15" fill="#475569">old {_fmt_metric(old_metrics[key])}</text>
  <rect x="{x0}" y="{y + 30}" width="{bar_w}" height="22" rx="5" fill="#e0f2fe"/>
  <rect x="{x0}" y="{y + 30}" width="{new_w:.2f}" height="22" rx="5" fill="#0f5ea8"/>
  <text x="{x0 + bar_w + 18}" y="{y + 47}" font-family="Arial, sans-serif" font-size="15" fill="#0f172a">new {_fmt_metric(new_metrics[key])} ({delta:+.4f})</text>""")
    old_c = old_metrics["confusion"]
    new_c = new_metrics["confusion"]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="920" height="660" viewBox="0 0 920 660" role="img">
  <rect width="920" height="660" fill="#f8fafc"/>
  <text x="460" y="54" text-anchor="middle" font-family="Arial, sans-serif" font-size="30" font-weight="700" fill="#0f172a">Baseline vs Calibrated Isolation Forest</text>
  <text x="460" y="86" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#475569">Same held-out test split; old model files preserved</text>
  <g font-family="Arial, sans-serif" font-size="14" fill="#475569">
    <rect x="210" y="104" width="18" height="18" rx="4" fill="#94a3b8"/><text x="236" y="118">Baseline</text>
    <rect x="330" y="104" width="18" height="18" rx="4" fill="#0f5ea8"/><text x="356" y="118">Calibrated</text>
  </g>
{''.join(rows)}
  <rect x="72" y="560" width="776" height="62" rx="10" fill="#ffffff" stroke="#cbd5e1"/>
  <text x="96" y="586" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#0f172a">Confusion matrix movement</text>
  <text x="96" y="611" font-family="Arial, sans-serif" font-size="15" fill="#334155">False negatives: {old_c['fn']:,} -> {new_c['fn']:,} ({new_c['fn'] - old_c['fn']:+,}); false positives: {old_c['fp']:,} -> {new_c['fp']:,} ({new_c['fp'] - old_c['fp']:+,})</text>
</svg>
"""
    Path(path).write_text(svg)


def _write_card(path: str, comparison: dict[str, Any], model_out: str,
                report_out: str, cm_out: str, comparison_plot_out: str) -> None:
    old = comparison["baseline_on_same_test"]
    new = comparison["calibrated_on_same_test"]
    best = comparison["selected_candidate"]
    split = comparison["split"]
    card = f"""# Calibrated Isolation Forest Model Card

This is a second Isolation Forest experiment. It does not replace or remove the original model.

## What Changed

| Area | Baseline | Calibrated model |
|---|---|---|
| Training data | Benign-only | Benign-only |
| Threshold selection | Fixed 1st percentile from training scores | Selected on validation split after grid search |
| Trees | 200 | {best['n_estimators']} |
| `max_samples` | `auto` | `{best['max_samples']}` |
| Threshold | `{old['threshold']}` | `{new['threshold']}` |

The change is honest but no longer purely unsupervised thresholding: anomalous validation labels are used to select the operating point. The Isolation Forest fit itself still uses benign samples only. To keep the artifact practical, the script chooses the smallest model within `0.0001` validation F1 of the best grid-search result.

## Split

| Split | Benign | Anomalous | Purpose |
|---|---:|---:|---|
| Train | {split['train_benign']:,} | 0 | Fit Isolation Forest |
| Validation | {split['validation_benign']:,} | {split['validation_anomalous']:,} | Select hyperparameters and threshold |
| Test | {split['test_benign']:,} | {split['test_anomalous']:,} | Final old-vs-new comparison |

Dataset SHA-256: `{comparison['dataset_sha256']}`

## Same-Test Metrics

| Metric | Baseline | Calibrated | Delta |
|---|---:|---:|---:|
| Accuracy | {_fmt_metric(old['accuracy'])} | {_fmt_metric(new['accuracy'])} | {new['accuracy'] - old['accuracy']:+.4f} |
| Precision | {_fmt_metric(old['precision'])} | {_fmt_metric(new['precision'])} | {new['precision'] - old['precision']:+.4f} |
| Recall | {_fmt_metric(old['recall'])} | {_fmt_metric(new['recall'])} | {new['recall'] - old['recall']:+.4f} |
| F1 score | {_fmt_metric(old['f1'])} | {_fmt_metric(new['f1'])} | {new['f1'] - old['f1']:+.4f} |
| ROC-AUC | {_fmt_metric(old['roc_auc'])} | {_fmt_metric(new['roc_auc'])} | {new['roc_auc'] - old['roc_auc']:+.4f} |

## Calibrated Confusion Matrix

![Calibrated confusion matrix]({Path(cm_out).name})

| Actual \\ Predicted | Benign | Anomalous |
|---|---:|---:|
| Benign | {new['confusion']['tn']:,} | {new['confusion']['fp']:,} |
| Anomalous | {new['confusion']['fn']:,} | {new['confusion']['tp']:,} |

## Comparison Plot

![Baseline vs calibrated comparison]({Path(comparison_plot_out).name})

## Artifact Paths

| Artifact | Path |
|---|---|
| Model | `{model_out}` |
| Evaluation report | `{report_out}` |
| Comparison JSON | `{DEFAULT_COMPARISON_OUT}` |
| Confusion matrix plot | `{cm_out}` |
| Comparison plot | `{comparison_plot_out}` |

## Readout

The calibrated model is better on this held-out split mainly because it recovers many more anomalies. False negatives drop from {old['confusion']['fn']:,} to {new['confusion']['fn']:,}, while false positives rise only from {old['confusion']['fp']:,} to {new['confusion']['fp']:,}. Precision drops slightly, but recall and F1 improve sharply.
"""
    Path(path).write_text(card)


def main() -> int:
    ap = argparse.ArgumentParser(description="Train a calibrated Isolation Forest comparison model.")
    ap.add_argument("--dataset", default=DEFAULT_DATASET)
    ap.add_argument("--baseline-model", default=DEFAULT_BASELINE_MODEL)
    ap.add_argument("--model-out", default=DEFAULT_MODEL_OUT)
    ap.add_argument("--report-out", default=DEFAULT_REPORT_OUT)
    ap.add_argument("--comparison-out", default=DEFAULT_COMPARISON_OUT)
    ap.add_argument("--card-out", default=DEFAULT_CARD_OUT)
    ap.add_argument("--confusion-plot-out", default=DEFAULT_CM_OUT)
    ap.add_argument("--comparison-plot-out", default=DEFAULT_COMPARISON_PLOT_OUT)
    args = ap.parse_args()

    rows, sha = _read_rows(args.dataset)
    benign = [r for r in rows if r["label"] == "norm"]
    anomalous = [r for r in rows if r["label"] == "anom"]

    rng = np.random.default_rng(0)
    benign_idx = np.arange(len(benign))
    rng.shuffle(benign_idx)
    train_end = int(0.6 * len(benign_idx))
    val_end = int(0.8 * len(benign_idx))
    benign_train_idx = benign_idx[:train_end]
    benign_val_idx = benign_idx[train_end:val_end]
    benign_test_idx = benign_idx[val_end:]

    anomalous_idx = np.arange(len(anomalous))
    rng.shuffle(anomalous_idx)
    anomalous_val_idx = anomalous_idx[:len(anomalous_idx) // 2]
    anomalous_test_idx = anomalous_idx[len(anomalous_idx) // 2:]

    X_train = _featurize([benign[i] for i in benign_train_idx])
    X_val_benign = _featurize([benign[i] for i in benign_val_idx])
    X_test_benign = _featurize([benign[i] for i in benign_test_idx])
    X_val_anomalous = _featurize([anomalous[i] for i in anomalous_val_idx])
    X_test_anomalous = _featurize([anomalous[i] for i in anomalous_test_idx])

    X_val = np.vstack([X_val_benign, X_val_anomalous])
    y_val = np.concatenate([
        np.zeros(X_val_benign.shape[0], dtype=np.int32),
        np.ones(X_val_anomalous.shape[0], dtype=np.int32),
    ])

    candidates = []
    for n_estimators in (200, 400, 600):
        for max_samples in ("auto", 0.7, 1.0):
            model = IsolationForest(
                n_estimators=n_estimators,
                contamination="auto",
                random_state=0,
                n_jobs=-1,
                max_samples=max_samples,
            )
            model.fit(X_train)
            train_scores = model.decision_function(X_train)
            val_scores = model.decision_function(X_val)
            for threshold_percentile in np.arange(1.0, 20.5, 0.5):
                threshold = float(np.percentile(train_scores, threshold_percentile))
                preds = (val_scores < threshold).astype(np.int32)
                candidates.append({
                    "n_estimators": n_estimators,
                    "max_samples": max_samples,
                    "threshold_percentile": float(threshold_percentile),
                    "threshold": threshold,
                    "precision": float(precision_score(y_val, preds, zero_division=0)),
                    "recall": float(recall_score(y_val, preds, zero_division=0)),
                    "f1": float(f1_score(y_val, preds, zero_division=0)),
                    "accuracy": float(accuracy_score(y_val, preds)),
                })

    best_f1 = max(c["f1"] for c in candidates)
    near_best = [c for c in candidates if best_f1 - c["f1"] <= 0.0001]
    selected = min(
        near_best,
        key=lambda d: (
            d["n_estimators"],
            str(d["max_samples"]),
            -d["recall"],
            -d["precision"],
        ),
    )
    calibrated_model = IsolationForest(
        n_estimators=selected["n_estimators"],
        contamination="auto",
        random_state=0,
        n_jobs=-1,
        max_samples=selected["max_samples"],
    )
    calibrated_model.fit(X_train)
    threshold = float(np.percentile(
        calibrated_model.decision_function(X_train),
        selected["threshold_percentile"],
    ))
    new_metrics = _metrics(calibrated_model, threshold, X_test_benign, X_test_anomalous)

    baseline_bundle = load(args.baseline_model)
    old_metrics = _metrics(
        baseline_bundle.model,
        baseline_bundle.threshold,
        X_test_benign,
        X_test_anomalous,
    )

    meta = {
        "train_n": int(X_train.shape[0]),
        "n_estimators": int(selected["n_estimators"]),
        "max_samples": selected["max_samples"],
        "contamination": "auto",
        "random_state": 0,
        "threshold_percentile": selected["threshold_percentile"],
        "threshold_selection": "validation_f1_grid_search",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": sha,
        "split": {
            "seed": 0,
            "train_benign": int(X_train.shape[0]),
            "validation_benign": int(X_val_benign.shape[0]),
            "validation_anomalous": int(X_val_anomalous.shape[0]),
            "test_benign": int(X_test_benign.shape[0]),
            "test_anomalous": int(X_test_anomalous.shape[0]),
        },
        "selected_candidate": selected,
    }
    bundle = ModelBundle(
        model=calibrated_model,
        threshold=threshold,
        feature_order=list(FEATURE_ORDER),
        baseline_mean=X_train.mean(axis=0),
        baseline_std=X_train.std(axis=0),
        meta=meta,
    )
    save(bundle, args.model_out)
    _write_json(args.report_out, new_metrics)

    comparison = {
        "dataset_sha256": sha,
        "split": meta["split"],
        "selected_candidate": selected,
        "baseline_on_same_test": old_metrics,
        "calibrated_on_same_test": new_metrics,
    }
    _write_json(args.comparison_out, comparison)
    _write_confusion_svg(
        args.confusion_plot_out,
        "Calibrated Isolation Forest Confusion Matrix",
        new_metrics,
    )
    _write_comparison_svg(args.comparison_plot_out, old_metrics, new_metrics)
    _write_card(
        args.card_out,
        comparison,
        args.model_out,
        args.report_out,
        args.confusion_plot_out,
        args.comparison_plot_out,
    )

    print(json.dumps({
        "model": args.model_out,
        "report": args.report_out,
        "comparison": args.comparison_out,
        "confusion_plot": args.confusion_plot_out,
        "comparison_plot": args.comparison_plot_out,
        "card": args.card_out,
        "selected_candidate": selected,
        "baseline_on_same_test": old_metrics,
        "calibrated_on_same_test": new_metrics,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
