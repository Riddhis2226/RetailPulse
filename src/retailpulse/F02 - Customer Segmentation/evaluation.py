"""Evaluate saved customer segmentation assignments and track results in MLflow."""
import json
import os

import mlflow
import pandas as pd

from retailpulse.config import PROCESSED_DIR, REPORTS_DIR

EXPERIMENT_NAME = "RetailPulse-Customer-Segmentation"
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")


def main():
    source = PROCESSED_DIR / "customer_segments.parquet"
    if not source.exists():
        raise FileNotFoundError(f"Run clustering.py first: {source}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(source)
    required = {"cust_id", "cluster_id"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Segment assignments are missing columns: {missing}")
    if df.empty:
        raise ValueError("Segment assignments contain no rows.")
    if df["cluster_id"].isna().any():
        raise ValueError("cluster_id contains null values.")

    sizes = df["cluster_id"].value_counts().sort_index().to_dict()
    report = {
        "customer_count": int(len(df)),
        "cluster_count": int(df["cluster_id"].nunique()),
        "cluster_sizes": {str(k): int(v) for k, v in sizes.items()},
        "cluster_share_pct": {
            str(k): round(int(v) / len(df) * 100, 2) for k, v in sizes.items()
        },
    }
    output = REPORTS_DIR / "f02_segment_size_report.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="segment-size-evaluation"):
        mlflow.set_tags({"project": "RetailPulse", "module": "F02-Evaluation"})
        mlflow.log_metrics({
            "customer_count": report["customer_count"],
            "cluster_count": report["cluster_count"],
        })
        for cluster_id, count in sizes.items():
            mlflow.log_metric(f"cluster_{cluster_id}_customers", int(count))
            mlflow.log_metric(
                f"cluster_{cluster_id}_share_pct",
                report["cluster_share_pct"][str(cluster_id)],
            )
        mlflow.log_artifact(str(output), artifact_path="evaluation")
        print(json.dumps(report, indent=2))
        print(f"Saved evaluation report: {output}")


if __name__ == "__main__":
    main()
