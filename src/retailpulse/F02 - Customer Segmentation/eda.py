"""Generate descriptive statistics for customer RFM features and log the artifact."""
import os

import mlflow
import pandas as pd

from retailpulse.config import PROCESSED_DIR, REPORTS_DIR
from retailpulse.f02_customer_segmentation.preprocessing import FEATURES

EXPERIMENT_NAME = "RetailPulse-Customer-Segmentation"
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")


def main():
    path = PROCESSED_DIR / "customer_rfm.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Generate customer_rfm.parquet first: {path}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(path)
    missing = sorted(set(FEATURES).difference(df.columns))
    if missing:
        raise ValueError(f"RFM dataset is missing columns: {missing}")

    summary = df[FEATURES].describe(percentiles=[0.25, 0.5, 0.75]).T
    output = REPORTS_DIR / "f02_rfm_descriptive_statistics.csv"
    summary.to_csv(output)

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="rfm-eda-summary"):
        mlflow.set_tags({"project": "RetailPulse", "module": "F02-EDA"})
        mlflow.log_metrics({
            "eda_customer_count": int(len(df)),
            "eda_feature_count": int(len(FEATURES)),
        })
        mlflow.log_artifact(str(output), artifact_path="eda")
        print(summary)
        print(f"Saved EDA report: {output}")


if __name__ == "__main__":
    main()
