# RetailPulse Source Datasets

## Source of truth

The seven source CSVs used by RetailPulse are hosted outside GitHub in the Hugging Face dataset repository:

**[RS2226/RetailPulse — Hugging Face Datasets](https://huggingface.co/datasets/RS2226/RetailPulse)**

The dataset page shown on Hugging Face reports a total repository size of approximately **805 MB**. File size and contents may change as the dataset is updated. Source CSVs are intentionally not checked into this GitHub repository.

> **Access note:** The dataset repository page is publicly discoverable. If Hugging Face access gating is enabled, downloading the files requires signing in and having access to the repository. Check the current dataset page before troubleshooting a download. Do not place a Hugging Face access token in source code, notebooks, screenshots, or commits.

## Seven source files

| File | Intended domain | Primary use in RetailPulse |
|---|---|---|
| `customer_master.csv` | Customer master and customer attributes | Customer-level features and segmentation |
| `inventory_snapshot.csv` | Inventory snapshots | Inventory position and replenishment analysis |
| `promotions.csv` | Promotion records | Promotion context and sales analysis |
| `sales_transactions.csv` | Retail transaction/line-item records | RFM features, daily demand, churn features, and sales analysis |
| `sku_inventory_flags.csv` | SKU-level inventory flags | Inventory status and stock-related analysis |
| `sku_master.csv` | Product/SKU master records | Product attributes and SKU-level grouping |
| `store_master.csv` | Store master records | Store attributes and store-level reporting |

These descriptions are based on the filenames and current project workflow. They are not a substitute for schema inspection. Use F01 reports to confirm columns, inferred types, row counts, date coverage, missingness, and relationship keys before building joins or model features.

## Download one file with Python

The project declares `huggingface-hub` as a dependency. Once your account has access to the dataset, retrieve an individual CSV using the repository ID and exact filename:

~~~python
from huggingface_hub import hf_hub_download
import pandas as pd

REPO_ID = "RS2226/RetailPulse"

csv_path = hf_hub_download(
    repo_id=REPO_ID,
    repo_type="dataset",
    filename="customer_master.csv",
)

customers = pd.read_csv(csv_path)
print(customers.shape)
print(customers.head())
~~~

If authentication is required, sign in with the Hugging Face CLI using the supported command for your installed version, or use the Hugging Face Hub login flow. Keep credentials in your local environment; do not hard-code tokens.

## Run the F01 inspection

From the GitHub repository root, run:

~~~bash
uv run python "src/retailpulse/F01 - Data Ingestion & Cleaning/01_inspect_datasets.py"
~~~

The inspection script lists all seven expected CSVs, retrieves them from Hugging Face, and writes a JSON report and text summary under `reports/dataset_inspection/`. The sales file is read in chunks of 100,000 rows to limit memory use.

### Important interpretation notes

- Missing values are reported; the inspection script does not automatically impute them.
- Sales duplicate counts are calculated within each chunk. Identical records split across chunk boundaries may not be counted as duplicates by that check.
- Do not delete repeated-looking sales rows until transaction grain and business meaning are established.
- Do not assume a missing promotion ID means “no promotion” without confirming the data definition.
- Do not impute missing inventory-flag dates until the meaning of the flags is understood.
- Use verified join keys and validate relationships before merging the tables.
- Do not document exact dataset dimensions or date ranges until an inspection report has been generated and reviewed.

## Licensing and data handling

The GitHub repository's MIT License applies to the RetailPulse code and documentation. It does not automatically grant rights to third-party source data. Review the dataset card and applicable data terms on Hugging Face before redistributing the CSVs or derived data. Do not commit the 805 MB source dataset to GitHub; use the Hugging Face repository as the source location.
