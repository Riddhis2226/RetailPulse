# F01 — Data Ingestion & Cleaning

> **RetailPulse | Functional Requirement 01**

## Canonical deployable workflow

Use the package at `src/retailpulse/f01_data_pipeline/` for reproducible ingestion. It downloads the seven source CSVs from Hugging Face, conservatively cleans them, writes Parquet outputs to a new run directory, and generates a JSON report.

Dataset source: [RS2226/RetailPulse on Hugging Face](https://huggingface.co/datasets/RS2226/RetailPulse). Access may require authentication if gating is enabled. Full file manifest and access guidance: [DATASETS.md](../../../DATASETS.md).

### Install and run

From the repository root:

~~~bash
uv sync
uv run python -m retailpulse.f01_data_pipeline --help
uv run python -m retailpulse.f01_data_pipeline
~~~

A full run processes the seven source files (the dataset page reports approximately 805 MB total). Run it as an explicit batch job, not automatically during Streamlit startup. Provide sufficient memory and disk space for the Hugging Face cache and Parquet output.

If dataset access requires a token, set `HF_TOKEN` in your local environment or deployment secrets. Do not hard-code or commit tokens.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `HF_TOKEN` | unset | Authorized Hugging Face token, if required |
| `RETAILPULSE_HF_REPO_ID` | `RS2226/RetailPulse` | Dataset repository ID |
| `RETAILPULSE_CHUNK_SIZE` | `100000` | Sales rows processed per chunk |
| `RETAILPULSE_OUTPUT_DIR` | `data/processed` | Root for timestamped Parquet runs |
| `RETAILPULSE_REPORT_DIR` | `reports/f01` | Root for JSON reports |

CLI options `--repo-id`, `--chunk-size`, `--output-dir`, and `--report-dir` override these defaults.

## Source files

| File | Purpose |
|---|---|
| `customer_master.csv` | Customer master and attributes |
| `inventory_snapshot.csv` | Inventory snapshots |
| `promotions.csv` | Promotion records |
| `sales_transactions.csv` | Transaction-level sales, processed in chunks |
| `sku_inventory_flags.csv` | SKU inventory flags |
| `sku_master.csv` | Product/SKU master |
| `store_master.csv` | Store master |

These purpose descriptions are based on filenames and current scripts. Confirm schemas, keys, date coverage, and row counts using the generated report rather than assuming them.

## Output and data safety

Each run writes to a new directory such as `data/processed/run_...`; it does not overwrite earlier successful runs. Six smaller CSVs become Parquet files, while sales is split into Parquet parts. A JSON report records row counts, missing-value counts, invalid date counts, whitespace changes, output paths, and elapsed time.

- Original Hugging Face source files are not modified.
- Rows are not deleted and duplicate transactions are not automatically removed.
- Missing values are reported, not imputed.
- Invalid configured dates become null and are counted.
- Existing business columns—including `observed_sales`, `is_stockout`, and `imputed_demand` when present—are preserved.
- If a run fails, only that run's incomplete output directory is removed.
- The F01 ingestion workflow does not by itself certify referential integrity, pricing consistency, monetary consistency, or every business rule.

## Diagnostic and validation scripts

The legacy scripts remain in this folder for focused inspection and quality analysis:

- `01_inspect_datasets.py` — schema and data profiling.
- `02_verify_huggingface_dataset.py` — single-file download check.
- `05_verify_pipeline.py` — inspect locally generated outputs.
- `06_validate_f01.py` — F01 validation.
- `07_validate_referential_integrity.py` — relationship checks.
- `08_check_monetary_consistency.py` and `09_check_pricing_consistency.py` — monetary and pricing checks.
- `analyze_duplicates.py`, `analyze_missing_values.py`, `validate_data.py`, and `consolidate_quality_reports.py` — diagnostic reports.

Some legacy scripts expect the historical `data/raw` and `data/processed` layout. Review each script's input contract before using it with the timestamped output from the canonical pipeline. The canonical package is the supported deployable entry point.

## Deployment notes

- Use a separate batch job or worker for full ingestion.
- Do not load all 9.9M sales rows into memory at once.
- Streamlit Community Cloud storage is ephemeral; use persistent storage if later modules need the processed files across restarts.
- Keep the dataset in Hugging Face and outputs in an appropriate data store rather than committing CSV/Parquet files to GitHub.
