# RetailPulse — Repository Structure and Developer Notes

This document describes the current functional-area layout on the `main` branch. The source tree is evolving; check the actual filenames before relying on older package/module names.

## Dataset source

The seven source CSV files are hosted in the [RetailPulse Hugging Face dataset repository](https://huggingface.co/datasets/RS2226/RetailPulse), not committed to GitHub. See [DATASETS.md](DATASETS.md) for the file manifest, retrieval instructions, access notes, and data-handling cautions.

Expected source files:

- `customer_master.csv`
- `inventory_snapshot.csv`
- `promotions.csv`
- `sales_transactions.csv`
- `sku_inventory_flags.csv`
- `sku_master.csv`
- `store_master.csv`

The repository page is publicly discoverable, but file downloads can require authentication if access gating is enabled. Never commit access tokens.

## Functional areas

- **F01 — Data Ingestion & Cleaning:** the canonical deployable package is `src/retailpulse/f01_data_pipeline/`. It downloads source CSVs from Hugging Face, cleans conservatively, writes timestamped Parquet outputs, and produces a JSON run report. The legacy folder `F01 - Data Ingestion & Cleaning/` retains diagnostic scripts and a compatibility entry point.
- **F02 — Customer Segmentation:** exploratory analysis, RFM/behavioural feature engineering, preprocessing, clustering, evaluation, and segment profiling.
- **F03 — Demand Forecasting:** project scope and documentation; verify that implementation files and dependencies exist before running a forecast.
- **F04 — Churn Prediction:** project scope and documentation; churn labels and model metrics require validation.
- **F05 — Inventory Optimization:** project scope and documentation; lead-time and stock-policy assumptions require confirmation.
- **F06 — Analytics Dashboard:** planned Streamlit interface; confirm implementation and deployment status before advertising a live demo.

Project acceptance criteria are defined in the project brief. They are targets until measured and documented from repeatable runs.

## Environment

From the repository root:

~~~powershell
uv sync
~~~

Use Python 3.11 or later. The project dependencies are declared in `pyproject.toml`.

## F01 — Inspect datasets

~~~powershell
uv run python -m retailpulse.f01_data_pipeline --help
uv run python -m retailpulse.f01_data_pipeline
~~~

The canonical pipeline retrieves the seven source CSVs directly from Hugging Face, processes sales in chunks, writes each run to a new output directory under `data/processed/`, and emits a JSON report under `reports/f01/`. Do not start the full pipeline automatically with Streamlit; use a separate batch job or worker. Set `HF_TOKEN` in deployment secrets if the dataset requires authentication.

## F01 — Container deployment

~~~bash
docker build -f Dockerfile.f01 -t retailpulse-f01 .
docker run --rm --env HF_TOKEN --mount type=bind,source="$(pwd)/data",target=/app/data --mount type=bind,source="$(pwd)/reports",target=/app/reports retailpulse-f01
~~~

Pass `HF_TOKEN` through the runtime environment or deployment secret store when required; never bake credentials into the image. The dataset is large, so use persistent storage for outputs that must survive container restarts. The old inspection and validation scripts remain useful for diagnostics but may expect the historical `data/raw` layout.

## F02 — Customer segmentation

The current folder includes scripts for EDA, feature engineering, preprocessing, clustering, evaluation, and segment profiling. Read the [F02 module README](src/retailpulse/F02%20-%20Customer%20Segmentation/readme.md), confirm each script's expected inputs and outputs, and run them in the appropriate dependency order.

## Data-quality cautions

- Do not remove duplicate-looking sales rows until transaction grain and business meaning are confirmed.
- Treat missing values according to field semantics; avoid blanket imputation.
- Validate join keys and referential integrity before combining tables.
- Use chronological holdouts for forecasting and avoid leakage from future data.
- Treat inactivity-derived churn labels as a proxy until the business definition is validated.
- Treat the default seven-day inventory lead time, if used, as an assumption rather than a confirmed supplier service level.

## Development standards

- Keep code modular and changes scoped to functional requirements.
- Do not commit source datasets, credentials, API keys, local machine paths, or generated model binaries.
- Add tests for transformations, feature logic, validation rules, and model evaluation as those components are implemented.
- Document the exact command, environment, dataset revision, and measured metrics for any reported result.
