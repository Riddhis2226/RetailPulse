"""Train and track baseline K-Means customer segmentation with MLflow."""
import json
import os
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from retailpulse.config import (
    PROCESSED_DIR,
    MODELS_DIR,
    REPORTS_DIR,
    RANDOM_STATE,
)
from retailpulse.f02_customer_segmentation.preprocessing import FEATURES, prepare_features

EXPERIMENT_NAME = "RetailPulse-Customer-Segmentation"
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
MODEL_PATH = MODELS_DIR / "customer_kmeans.joblib"
ASSIGNMENTS_PATH = PROCESSED_DIR / "customer_segments.parquet"
PROFILE_PATH = REPORTS_DIR / "customer_segment_profiles.csv"
EVALUATION_PATH = REPORTS_DIR / "f02_clustering_evaluation.json"


def _validate_input(df: pd.DataFrame) -> None:
    required = {"cust_id", *FEATURES}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"customer_rfm.parquet is missing required columns: {missing}")
    if df.empty:
        raise ValueError("customer_rfm.parquet contains no customers.")
    if df["cust_id"].isna().any():
        raise ValueError("cust_id contains null values.")
    if df["cust_id"].duplicated().any():
        raise ValueError("Expected one RFM row per customer; duplicate cust_id values found.")
    for col in FEATURES:
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"{col} contains missing, non-numeric, or non-finite values.")
    if (pd.to_numeric(df["frequency_receipts"]) < 0).any():
        raise ValueError("frequency_receipts must be non-negative.")
    if (pd.to_numeric(df["monetary_value"]) < 0).any():
        raise ValueError("monetary_value must be non-negative.")


def main() -> None:
    source = PROCESSED_DIR / "customer_rfm.parquet"
    if not source.exists():
        raise FileNotFoundError(
            f"Input not found: {source}. Run the F02 feature-engineering step first."
        )

    for directory in (PROCESSED_DIR, MODELS_DIR, REPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(source)
    _validate_input(df)
    X, scaler = prepare_features(df)

    if len(X) != len(df):
        raise ValueError("prepare_features changed the row count; customer alignment is unsafe.")
    if not np.isfinite(X).all():
        raise ValueError("Preprocessed feature matrix contains non-finite values.")
    if len(np.unique(X, axis=0)) < 2:
        raise ValueError("At least two distinct customer feature rows are required.")
    if len(df) < 3:
        raise ValueError("At least three customers are required for silhouette evaluation.")

    # Keep the candidate range practical while ensuring k < number of customers.
    max_k = min(8, len(df) - 1)
    candidates = []
    best = None

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    with mlflow.start_run(run_name="baseline-kmeans-rfm") as run:
        mlflow.set_tags({
            "project": "RetailPulse",
            "module": "F02-Customer-Segmentation",
            "algorithm": "KMeans",
            "feature_source": source.name,
        })
        mlflow.log_params({
            "algorithm": "KMeans",
            "random_state": int(RANDOM_STATE),
            "n_init": 10,
            "min_k": 2,
            "max_k": max_k,
            "customer_count": int(len(df)),
            "feature_count": len(FEATURES),
            "features": ",".join(FEATURES),
            "preprocessing": "log1p frequency/monetary; StandardScaler",
            "silhouette_sample_size": min(5000, len(df)),
        })

        for k in range(2, max_k + 1):
            model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
            labels = model.fit_predict(X)
            try:
                sample_size = min(5000, len(X))
                if sample_size < len(X):
                    score = float(
                        silhouette_score(
                            X, labels, sample_size=sample_size,
                            random_state=RANDOM_STATE,
                        )
                    )
                else:
                    score = float(silhouette_score(X, labels))
            except ValueError as exc:
                candidates.append({
                    "k": k,
                    "silhouette_score": None,
                    "inertia": float(model.inertia_),
                    "evaluation_error": str(exc),
                })
                mlflow.log_metric(f"inertia_k_{k}", float(model.inertia_))
                continue

            candidate = {
                "k": int(k),
                "silhouette_score": score,
                "inertia": float(model.inertia_),
            }
            candidates.append(candidate)
            mlflow.log_metric(f"silhouette_k_{k}", score)
            mlflow.log_metric(f"inertia_k_{k}", float(model.inertia_))

            if best is None or score > best["score"]:
                best = {
                    "score": score,
                    "model": model,
                    "labels": labels,
                    "k": k,
                }

        if best is None:
            raise ValueError("No candidate model could be evaluated successfully.")

        model = best["model"]
        labels = best["labels"]
        selected_k = int(best["k"])
        selected_score = float(best["score"])

        result = df.copy()
        result["cluster_id"] = labels
        result.to_parquet(ASSIGNMENTS_PATH, index=False)

        profile = result.groupby("cluster_id").agg(
            customers=("cust_id", "count"),
            median_recency_days=("recency_days", "median"),
            median_frequency_receipts=("frequency_receipts", "median"),
            median_monetary_value=("monetary_value", "median"),
        ).reset_index()
        profile["customer_share_pct"] = (
            profile["customers"] / len(result) * 100
        ).round(2)
        profile.to_csv(PROFILE_PATH, index=False)

        report = {
            "experiment_name": EXPERIMENT_NAME,
            "mlflow_run_id": run.info.run_id,
            "customer_count": int(len(result)),
            "selected_k": selected_k,
            "silhouette_score": selected_score,
            "inertia": float(model.inertia_),
            "features": FEATURES,
            "candidates": candidates,
            "cluster_sizes": {
                str(int(cluster_id)): int(count)
                for cluster_id, count in result["cluster_id"].value_counts().sort_index().items()
            },
            "note": (
                "Cluster count is selected by silhouette score. Review segment meaning "
                "with business stakeholders before deployment."
            ),
        }
        EVALUATION_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

        mlflow.log_params({"selected_k": selected_k})
        mlflow.log_metrics({
            "selected_silhouette_score": selected_score,
            "selected_inertia": float(model.inertia_),
        })
        for cluster_id, count in result["cluster_id"].value_counts().items():
            mlflow.log_metric(f"cluster_{int(cluster_id)}_customers", int(count))

        # Save a reusable bundle with the exact scaler and feature order.
        joblib.dump(
            {
                "model": model,
                "scaler": scaler,
                "features": FEATURES,
                "preprocessing": {
                    "log1p_features": ["frequency_receipts", "monetary_value"],
                    "recency_sentinel": -1,
                },
                "selected_k": selected_k,
                "random_state": RANDOM_STATE,
            },
            MODEL_PATH,
        )

        # Log model and related artifacts to this MLflow run.
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="kmeans_model",
            input_example=X[: min(5, len(X))],
        )
        mlflow.log_artifact(str(MODEL_PATH), artifact_path="model_bundle")
        mlflow.log_artifact(str(ASSIGNMENTS_PATH), artifact_path="data")
        mlflow.log_artifact(str(PROFILE_PATH), artifact_path="reports")
        mlflow.log_artifact(str(EVALUATION_PATH), artifact_path="reports")

        print(json.dumps(report, indent=2))
        print(f"Saved assignments: {ASSIGNMENTS_PATH}")
        print(f"Saved model bundle: {MODEL_PATH}")
        print(f"MLflow run ID: {run.info.run_id}")
        print(f"MLflow UI: {TRACKING_URI}")


if __name__ == "__main__":
    main()
