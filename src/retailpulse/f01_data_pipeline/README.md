# F01 — Deployable Data Ingestion & Cleaning

This is the canonical, platform-independent F01 entry point. It replaces the need to manually download CSVs into a machine-specific `data/raw` folder. The older scripts remain available for diagnostics and investigation; use this package for a reproducible full run.

## Source datasets

The seven CSVs are hosted in the [RetailPulse Hugging Face dataset](https://huggingface.co/datasets/RS2226/RetailPulse). Access may require an authorized Hugging Face account if gating is enabled. See the repository-level [DATASETS.md](../../../DATASETS.md).

## Run locally or in a deployment job

From the repository root, with project dependencies installed:

~~~bash
uv run python -m retailpulse.f01_data_pipeline --help
uv run python -m retailpulse.f01_data_pipeline
~~~

For a small test, set the chunk size lower or run against a small, authorized test dataset with the same expected filenames. A full run processes all seven source files and may take time and disk space; **do not run it automatically when a Streamlit app starts**.

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `HF_TOKEN` | Not set | Optional Hugging Face token; required if the dataset is gated for your account. Keep it in deployment secrets. |
| `RETAILPULSE_HF_REPO_ID` | `RS2226/RetailPulse` | Hugging Face dataset repo ID. |
| `RETAILPULSE_CHUNK_SIZE` | `100000` | Rows per sales CSV chunk; must be positive. |
| `RETAILPULSE_OUTPUT_DIR` | `data/processed` | Root for run-specific Parquet outputs. |
| `RETAILPULSE_REPORT_DIR` | `reports/f01` | Root for JSON run reports. |

CLI arguments `--repo-id`, `--chunk-size`, `--output-dir`, and `--report-dir` override the corresponding defaults. Hugging Face downloads use its managed local cache; the source CSVs are not copied into the repository.

## Output behavior

Every execution writes to a new timestamped subdirectory, e.g. `data/processed/run_.../`. The six smaller tables are written as individual Parquet files. Sales are read in chunks and written as multiple Parquet parts under `sales_transactions/`. A JSON report records row counts, missing values, invalid dates, text trimming, output paths, and runtime.

The pipeline does not drop rows, deduplicate transactions, impute missing values, or overwrite original source files. Invalid configured date values become null and are counted in the report. It preserves all input columns, including `observed_sales`, `is_stockout`, and `imputed_demand` if present. If a run fails, only that run's incomplete output directory is removed; earlier runs are not deleted.

## Deployment guidance

- Run this as an explicit batch job, scheduled worker, or one-off preprocessing step—not during Streamlit import/startup.
- Provide sufficient disk space for the downloaded cache plus Parquet outputs and intermediate files.
- Use persistent storage if downstream deployment expects outputs to survive container restarts. Ephemeral Streamlit Community Cloud storage should not be treated as a durable data store.
- Keep Hugging Face credentials in platform secrets. Never commit tokens or dataset files.
- Validate generated row counts and reports before consuming the output in F02–F06.

## Current limits

This module performs conservative whitespace/date cleaning and data retrieval. It is not a replacement for the separate referential-integrity, monetary, pricing, and business-rule validation scripts. Those checks must be run and reviewed separately before declaring the data production-ready.
