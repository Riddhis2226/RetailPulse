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

- **F01 — Data Ingestion & Cleaning:** dataset inspection, Hugging Face retrieval checks, preparation pipeline, validation, relationship checks, duplicate and missing-value analysis, consistency checks, and quality reporting.
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
uv run python "src/retailpulse/F01 - Data Ingestion & Cleaning/01_inspect_datasets.py"
~~~

The inspection script reads sales data in 100,000-row chunks and writes reports under `reports/dataset_inspection/`. Review the generated reports for schema, missing values, duplicate counts, and data dimensions. The chunk-based duplicate check may not detect duplicates spanning different chunks.

## F01 — Verify Hugging Face access

~~~powershell
uv run python "src/retailpulse/F01 - Data Ingestion & Cleaning/02_verify_huggingface_dataset.py"
~~~

This verification script checks the customer master CSV. It does not by itself verify every source file.

## F01 — Run the preparation pipeline

~~~powershell
uv run python "src/retailpulse/F01 - Data Ingestion & Cleaning/03_pipeline.py"
~~~

Review the script configuration and expected outputs before processing the full dataset.

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
