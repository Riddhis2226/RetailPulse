# F02 — Customer Segmentation

> **RetailPulse | Functional Requirement 02**

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


## Dataset Use in F02

- **Primary inputs:** customer master and sales transactions.
- **Potential supporting inputs:** SKU and store master data for grouping, joining, or descriptive profiles where required by the feature definitions.
- **Core output:** customer-level RFM features and interpretable cluster assignments.

The actual feature columns and observation window must be taken from the implementation and validated data. Confirm customer and transaction keys before aggregating or joining data. Avoid documenting a row count or final segment count until the pipeline has been run.


## Objective

Group customers by purchasing behaviour so retail teams can understand customer value, distinguish engagement patterns, and design more targeted retention and marketing strategies.

## Methodology

The planned baseline uses **RFM analysis**:

- **Recency (R):** how recently a customer made a purchase.
- **Frequency (F):** how often the customer purchased during the observation period.
- **Monetary (M):** the customer's total spend during that period.

RFM features can be prepared and scaled before applying clustering. K-Means is the baseline clustering approach in this folder; cluster evaluation and segment profiling help translate numerical groups into interpretable customer profiles.

## Scripts

| Script | Purpose |
|---|---|
| `eda.py` | Explore customer and purchasing patterns. |
| `feature_engineering.py` | Build customer-level RFM and related behavioural features. |
| `preprocessing.py` | Prepare features for downstream modeling. |
| `clustering.py` | Apply customer clustering. |
| `evaluation.py` | Evaluate clustering results. |
| `segment_profiling.py` | Summarize and interpret the resulting segments. |
| `README_MLFLOW.md` | Notes related to MLflow tracking. |

## Workflow

1. Complete F01 data preparation and inspect the validated data.
2. Generate customer-level features.
3. Review feature distributions and handle invalid or extreme values thoughtfully.
4. Preprocess numerical features for clustering.
5. Fit the clustering baseline.
6. Evaluate cluster separation and stability using suitable metrics.
7. Profile clusters using RFM summaries and describe their business meaning.

## Getting Started

Run commands from the repository root after installing project dependencies. Because this folder name contains spaces and a hyphen, run the scripts by file path:

```bash
uv run python "src/retailpulse/F02 - Customer Segmentation/eda.py"
uv run python "src/retailpulse/F02 - Customer Segmentation/feature_engineering.py"
uv run python "src/retailpulse/F02 - Customer Segmentation/preprocessing.py"
uv run python "src/retailpulse/F02 - Customer Segmentation/clustering.py"
uv run python "src/retailpulse/F02 - Customer Segmentation/evaluation.py"
uv run python "src/retailpulse/F02 - Customer Segmentation/segment_profiling.py"
```

Run the scripts in the order appropriate to their input/output dependencies. Confirm the expected input files and generated artifacts in each script before running the complete workflow.

## Interpretation Guidelines

- A cluster ID is not inherently a business segment; profile it before assigning a label.
- Select the number of clusters using evaluation results and business interpretability.
- Avoid using future information to construct features for a historical evaluation.
- Document the observation window and the reference date used to calculate recency.
- Do not claim a fixed number of meaningful segments until the model has been run and its results reviewed.

## Expected Handoff

F02 should produce customer-level RFM/behavioural features, cluster assignments, evaluation outputs, and segment profiles for use in downstream analysis and the dashboard.

## Current Status

The folder contains scripts for EDA, feature engineering, preprocessing, clustering, evaluation, and profiling. Confirm that the end-to-end workflow runs successfully and produces the expected artifacts before reporting final segment counts or model-quality results.
