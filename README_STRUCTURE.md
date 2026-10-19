# RetailPulse refactored structure

This package groups implementation by functional requirement:

- `f01_data_pipeline`: ingestion, cleaning, validation, referential integrity, duplicate/missing-value analysis, consolidated reporting.
- `f02_customer_segmentation`: RFM aggregation, feature preprocessing, K-Means baseline and profiling.
- `f03_demand_forecasting`: daily demand aggregation, feature utilities, optional Prophet baseline and metrics. LSTM/hybrid are explicit placeholders and are not claimed as implemented.
- `f04_churn_prediction`: inactivity-based churn proxy and baseline classifier. This proxy is not observed churn; validate the label with business stakeholders.
- `f05_inventory_optimization`: demand inputs and baseline reorder recommendations. The default 7-day lead time is an assumption, not a known supplier SLA.
- `f06_dashboard`: Streamlit interface to available outputs.

## Install/update dependencies

From repository root (Windows PowerShell):

```powershell
uv pip install -e .
```

If you prefer adding dependencies through uv's project workflow:

```powershell
uv sync
```

## Run F01

Ensure the seven CSV files are in `data/raw` (or run the Hugging Face downloader):

```powershell
uv run python -m retailpulse.f01_data_pipeline.ingestion
uv run python -m retailpulse.f01_data_pipeline.pipeline
uv run python -m retailpulse.f01_data_pipeline.validation
uv run python -m retailpulse.f01_data_pipeline.relationship_checks
uv run python -m retailpulse.f01_data_pipeline.duplicate_analysis
uv run python -m retailpulse.f01_data_pipeline.missing_value_analysis
uv run python -m retailpulse.f01_data_pipeline.quality_report
```

## Run F02

```powershell
uv run python -m retailpulse.f02_customer_segmentation.feature_engineering
uv run python -m retailpulse.f02_customer_segmentation.eda
uv run python -m retailpulse.f02_customer_segmentation.clustering
uv run python -m retailpulse.f02_customer_segmentation.evaluation
uv run python -m retailpulse.f02_customer_segmentation.segment_profiling
```

## Run F03 (daily demand table can be large)

```powershell
uv run python -m retailpulse.f03_demand_forecasting.data_preparation
uv run python -m retailpulse.f03_demand_forecasting.prophet_model --sku-id YOUR_SKU_ID --horizon 30
```

Install optional Prophet dependency before running the model:

```powershell
uv add prophet
```

## Run F04

Requires F02 RFM features first:

```powershell
uv run python -m retailpulse.f04_churn_prediction.churn_labeling
uv run python -m retailpulse.f04_churn_prediction.feature_engineering
uv run python -m retailpulse.f04_churn_prediction.model_training
```

## Run F05

```powershell
uv run python -m retailpulse.f03_demand_forecasting.data_preparation
uv run python -m retailpulse.f05_inventory_optimization.demand_inputs
uv run python -m retailpulse.f05_inventory_optimization.reorder_policy
uv run python -m retailpulse.f05_inventory_optimization.optimization
uv run python -m retailpulse.f05_inventory_optimization.evaluation
```

## Run dashboard

```powershell
uv run streamlit run src/retailpulse/f06_dashboard/app.py
```

## Important cautions

- Back up your existing project before moving files.
- This is a structured starter implementation, not a claim that all functional requirements or target metrics have been achieved.
- Do not delete duplicate sales rows until the transaction grain has been confirmed.
- Missing `promo_id` values may mean no promotion, but this should be confirmed.
- Missing inventory-flag dates should not be imputed without understanding the flag semantics.
- Forecasting and churn evaluation must use leakage-safe chronological or otherwise appropriate holdouts before comparing against project targets.
