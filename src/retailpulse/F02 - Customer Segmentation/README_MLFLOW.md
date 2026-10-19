# RetailPulse F02 — MLflow integration

## Prerequisites

Run these commands from the RetailPulse root directory with `.venv` activated:

```cmd
python -m pip install mlflow
```

Start the MLflow server in a separate terminal and leave it running:

```cmd
uvx mlflow server
```

The default tracking URL used by these scripts is `http://127.0.0.1:5000`.
Override it by setting `MLFLOW_TRACKING_URI` if needed.

## Run order

```cmd
set PYTHONPATH=src
python -m retailpulse.f02_customer_segmentation.eda
python -m retailpulse.f02_customer_segmentation.clustering
python -m retailpulse.f02_customer_segmentation.evaluation
python -m retailpulse.f02_customer_segmentation.segment_profiling
```

Run `clustering` only after `customer_rfm.parquet` exists. It creates the assignments,
model bundle, profile CSV, evaluation JSON, and the main MLflow training run.
The other scripts each create a separate MLflow run in the same experiment and log
their own reports.

## Tracked artifacts

- K-Means model
- Joblib bundle containing the model, fitted scaler, feature names, and preprocessing notes
- Customer assignments (Parquet)
- Cluster profile (CSV)
- Clustering evaluation report (JSON)
- RFM descriptive statistics, when EDA is run

## Notes

- `prepare_features` uses `log1p` on frequency and monetary value and fits a
  `StandardScaler`. `transform_features` applies the same transformation with an
  already-fitted scaler for future inference.
- The K-Means model logged through `mlflow.sklearn.log_model` operates on the
  transformed, scaled feature matrix. Use the joblib bundle and `transform_features`
  for new raw RFM rows.
- Silhouette score is a selection heuristic, not proof that clusters are meaningful.
  Validate cluster interpretations against business needs.
- MLflow tracking is not itself drift detection or production monitoring.
