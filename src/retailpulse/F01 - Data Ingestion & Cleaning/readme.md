# F01 — Data Ingestion & Cleaning

> **RetailPulse | Functional Requirement 01**

## Dataset

RetailPulse uses the project-owned Hugging Face dataset repository **[RS2226/RetailPulse](https://huggingface.co/datasets/RS2226/RetailPulse)**. The repository is currently marked **gated** on Hugging Face, so access may require permission from the dataset owner and authentication. The ingestion scripts reference seven CSV files:

| File | Intended data domain |
|---|---|
| `customer_master.csv` | Customer master records and customer attributes |
| `inventory_snapshot.csv` | Inventory snapshots |
| `promotions.csv` | Promotion records |
| `sales_transactions.csv` | Retail sales transactions (large file; the inspection script reads this file in 100,000-row chunks) |
| `sku_inventory_flags.csv` | SKU-level inventory flags |
| `sku_master.csv` | Product/SKU master records |
| `store_master.csv` | Store master records |

These descriptions are based on the filenames and repository scripts. Confirm the exact columns, data types, row counts, date coverage, and join keys by running the F01 dataset inspection; those figures should not be assumed from filenames alone.

**Retrieval:** The code uses `huggingface_hub.hf_hub_download` with dataset repository ID `RS2226/RetailPulse` and repository type `dataset`. Access the repository from the link above and authenticate with an authorized Hugging Face account if prompted. Do not commit access tokens or credentials.


## Dataset-quality Scope

F01 inspects dataset schemas, inferred data types, missing values, duplicate rows, relationships, monetary consistency, and pricing consistency. The inspection script states that missing values are reported but not imputed, and sales duplicate counts are computed within each chunk; duplicate rows spanning chunks may therefore be missed.


## Objective

Prepare retail source data for downstream analytics and machine-learning workflows. This module focuses on inspecting source files, validating data quality, cleaning inconsistent values, and checking relationships and business-rule consistency before analysis.

## Scope

- Inspect dataset schemas, dimensions, data types, and sample records.
- Verify the expected source dataset and its availability.
- Run the data preparation pipeline.
- Validate required fields and common data-quality conditions.
- Check referential integrity across related datasets.
- Investigate duplicate records and missing values.
- Check monetary and pricing consistency.
- Consolidate data-quality findings for review.

## Scripts

| Script | Purpose |
|---|---|
| `01_inspect_datasets.py` | Inspect available datasets and their structures. |
| `02_verify_huggingface_dataset.py` | Verify the referenced Hugging Face dataset. |
| `03_pipeline.py` | Run the main data-preparation pipeline. |
| `05_verify_pipeline.py` | Inspect or verify pipeline outputs. |
| `06_validate_f01.py` | Run F01 validation checks. |
| `07_validate_referential_integrity.py` | Check relationships between related records. |
| `08_check_monetary_consistency.py` | Review monetary-field consistency. |
| `09_check_pricing_consistency.py` | Review pricing-field consistency. |
| `analyze_duplicates.py` | Analyze potential duplicate records. |
| `analyze_missing_values.py` | Profile missing values. |
| `cleaning.py` | Data-cleaning utilities and logic. |
| `consolidate_quality_reports.py` | Consolidate available quality reports. |
| `upload_dataset.py` | Support dataset upload workflows. |
| `validate_data.py` | Run general data validation. |

## Getting Started

Run commands from the repository root. Install the project dependencies first using the instructions in the root README.

To inspect the source data:

```bash
uv run python "src/retailpulse/F01 - Data Ingestion & Cleaning/01_inspect_datasets.py"
```

To run the main pipeline:

```bash
uv run python "src/retailpulse/F01 - Data Ingestion & Cleaning/03_pipeline.py"
```

To run validation and data-quality analyses, execute the relevant scripts listed above. Check each script's configuration and console output before running it against the full dataset.

> **Note:** The exact input paths and generated output locations are determined by each script's configuration. Confirm them before running the pipeline.

## Data-quality Principles

- Preserve source data; write cleaned outputs separately where possible.
- Do not remove duplicate-looking rows until the transaction grain and business meaning are understood.
- Treat missing values according to field semantics rather than applying a blanket fill strategy.
- Validate join keys before combining tables.
- Record validation findings and investigate material anomalies before modeling.

## Expected Handoff

F01 should provide validated and documented data that downstream modules can use for customer segmentation, forecasting, churn analysis, and inventory planning. Actual output files and validation results should be confirmed from a successful run; this README does not imply that every check has passed.

## Current Status

Scripts for inspection, pipeline execution, cleaning, validation, and quality analysis are present in this folder. Run and verify them against the available data before treating the pipeline as production-ready.
