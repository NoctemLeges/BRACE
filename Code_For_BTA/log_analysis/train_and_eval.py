"""CLI: load CSIC, train Isolation Forest, evaluate on held-out test split."""
import argparse
import os
import sys

# Allow running as a script (python train_and_eval.py) or as a module
# (python -m Code_For_BTA.log_analysis.train_and_eval).
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from log_analysis.dataset import load_dataset
    from log_analysis.evaluate import evaluate, print_report, write_report
    from log_analysis.model_io import save, train
else:
    from .dataset import load_dataset
    from .evaluate import evaluate, print_report, write_report
    from .model_io import save, train


DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "iforest.joblib",
)
DEFAULT_REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "eval_report.json",
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Train and evaluate the CSIC 2010 anomaly detector.")
    ap.add_argument("--dataset-dir", required=True,
                    help="Directory containing normalTrafficTraining.txt, normalTrafficTest.txt, "
                         "anomalousTrafficTest.txt.")
    ap.add_argument("--model-out", default=DEFAULT_MODEL_PATH)
    ap.add_argument("--report-out", default=DEFAULT_REPORT_PATH)
    ap.add_argument("--n-estimators", type=int, default=200)
    args = ap.parse_args()

    print(f"[+] Loading dataset from {args.dataset_dir}")
    splits = load_dataset(args.dataset_dir)
    print(f"    benign_train={splits.counts['benign_train']}  "
          f"benign_test={splits.counts['benign_test']}  "
          f"anomalous_test={splits.counts['anomalous_test']}")

    print(f"[+] Training IsolationForest on {splits.X_benign_train.shape[0]} benign samples")
    bundle = train(splits.X_benign_train, n_estimators=args.n_estimators)
    bundle.meta["dataset_sha256"] = splits.file_sha256
    bundle.meta["dataset_counts"] = splits.counts
    print(f"    threshold = {bundle.threshold:.6f}")

    print(f"[+] Evaluating on held-out test split")
    metrics = evaluate(bundle, splits.X_benign_test, splits.X_anomalous_test)
    print_report(metrics)

    save(bundle, args.model_out)
    write_report(metrics, args.report_out)
    print(f"[+] Wrote model to {args.model_out}")
    print(f"[+] Wrote report to {args.report_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
