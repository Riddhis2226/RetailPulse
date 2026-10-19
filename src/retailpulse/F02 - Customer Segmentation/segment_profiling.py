"""Create interpretable customer segment profiles and log the profile artifact."""
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
    required = {
        "cust_id", "cluster_id", "recency_days",
        "frequency_receipts", "monetary_value",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Segment data is missing columns: {missing}")
    if df.empty:
        raise ValueError("Segment data contains no rows.")

    profile = df.groupby("cluster_id").agg(
        customers=("cust_id", "nunique"),
        median_recency_days=("recency_days", "median"),
        median_frequency=("frequency_receipts", "median"),
        median_monetary_value=("monetary_value", "median"),
    ).reset_index()
    profile["customer_share_pct"] = (
        profile["customers"] / profile["customers"].sum() * 100
    ).round(2)

    output = REPORTS_DIR / "customer_segment_profiles.csv"
    profile.to_csv(output, index=False)

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="segment-profiling"):
        mlflow.set_tags({"project": "RetailPulse", "module": "F02-Segment-Profiling"})
        mlflow.log_metric("profiled_cluster_count", int(profile["cluster_id"].nunique()))
        mlflow.log_metric("profiled_customer_count", int(profile["customers"].sum()))
        mlflow.log_artifact(str(output), artifact_path="profiles")
        print(profile.to_string(index=False))
        print(f"Saved segment profiles: {output}")


if __name__ == "__main__":
    main()
