<div align="center">

# RetailPulse
### Retail Analytics • Customer Intelligence • Demand Planning

**An evolving retail analytics and machine-learning project for turning transactional data into customer, demand, and inventory insights.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Machine Learning](https://img.shields.io/badge/Machine%20Learning-scikit--learn-orange)](https://scikit-learn.org/)
[![Data Analysis](https://img.shields.io/badge/Data%20Analysis-Pandas%20%7C%20NumPy-150458)](https://pandas.pydata.org/)
[![Experiment Tracking](https://img.shields.io/badge/Experiment%20Tracking-MLflow-0194E2)](https://mlflow.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Overview

**RetailPulse** is a modular retail analytics project organized around six functional areas: data ingestion and quality, customer segmentation, demand forecasting, churn analysis, inventory optimization, and an analytics dashboard.

The goal is to build a repeatable analytical workflow that starts with raw retail data and progresses toward interpretable customer and operational insights. The repository currently contains data-quality and customer-segmentation code, alongside developing or planned components. Not every planned capability or performance target has been implemented or validated yet.

## Project Objectives

- Build a repeatable ingestion, cleaning, and data-quality validation workflow.
- Derive customer-level **Recency, Frequency, and Monetary (RFM)** features.
- Explore customer groups with K-Means clustering and segment profiling.
- Develop time-series demand forecasts and evaluate forecast error.
- Establish a baseline churn-risk workflow with transparent label assumptions.
- Produce baseline reorder recommendations from demand inputs and lead-time assumptions.
- Bring analytical outputs together in an interactive dashboard as that component is developed.

## Functional Areas

| ID | Functional area | Scope |
|---|---|---|
| **F01** | Data ingestion & cleaning | Dataset inspection, ingestion, cleaning, missing-value and duplicate analysis, validation, referential-integrity checks, and quality reporting. |
| **F02** | Customer segmentation | RFM feature engineering, preprocessing, exploratory analysis, K-Means clustering, evaluation, and segment profiling. |
| **F03** | Demand forecasting | Daily demand preparation, forecasting utilities, an optional Prophet baseline, and forecast metrics. LSTM/hybrid forecasting remains a placeholder unless separately implemented and validated. |
| **F04** | Churn prediction | Inactivity-based churn proxy, feature engineering, and a baseline classifier. The proxy is not equivalent to observed churn and needs business validation. |
| **F05** | Inventory optimization | Demand inputs and baseline reorder recommendations. The default seven-day lead time is an assumption, not a confirmed supplier service level. |
| **F06** | Analytics dashboard | Intended Streamlit interface for available outputs; confirm the current implementation and run path before treating it as deployment-ready. |

> **Implementation status:** This repository is under active development. The functional-area descriptions include project scope and starter components; they are not a claim that every module, acceptance criterion, or target metric is complete.

## Technology Stack

- **Language:** Python 3.11+
- **Data processing:** Pandas, NumPy, PyArrow, DuckDB
- **Machine learning:** scikit-learn, PyTorch / Lightning
- **Forecasting and statistics:** Prophet, statsmodels
- **Experiment tracking and optimization:** MLflow, Optuna
- **Database connectivity:** SQLAlchemy, psycopg2
- **Dataset access and configuration:** Hugging Face Hub, python-dotenv
- **Planned / interface layer:** Streamlit

Dependencies are defined in [pyproject.toml](pyproject.toml). Some packages are for optional or evolving components and may not be required for every workflow.

## Repository Structure

The repository is organized by functional requirement. The current source tree uses functional-area directory names under `src/retailpulse/`.

```text
RetailPulse/
├── data/
│   ├── raw/                   # Place source datasets here; do not commit sensitive data
│   └── processed/             # Generated/cleaned data outputs
├── src/
│   └── retailpulse/
│       ├── F01 - Data Ingestion & Cleaning/
│       ├── F02 - Customer Segmentation/
│       ├── F03 - Demand Forecasting/
│       ├── F04 - Churn Prediction/
│       ├── F05 - Inventory Optimization/
│       ├── __init__.py
│       └── config.py
├── pyproject.toml
├── README.md
└── README_STRUCTURE.md
```

The checked-in tree may evolve as modules are refactored. Consult [README_STRUCTURE.md](README_STRUCTURE.md) for the current developer notes and workflow guidance.

## Getting Started

### 1. Prerequisites

- Python **3.11 or later**
- Git
- [uv](https://docs.astral.sh/uv/) for dependency and project management

### 2. Clone the repository

```bash
git clone https://github.com/Riddhis2226/RetailPulse.git
cd RetailPulse
```

### 3. Install dependencies

Using the project workflow:

```bash
uv sync
```

Alternatively, install the local package in editable mode:

```bash
uv pip install -e .
```

If dependency resolution fails on your environment, check the Python version and the package versions declared in `pyproject.toml`.

### 4. Prepare the dataset

The documented F01 workflow expects **seven CSV files** in `data/raw`, or use the repository's Hugging Face dataset downloader where appropriate. Review the dataset verification and ingestion scripts before running the pipeline, and check the expected filenames and schema in the code.

Do not commit private, licensed, or otherwise restricted datasets to the repository. Keep credentials and local configuration out of version control.

## Running the Workflows

The current source tree contains functional-area folders with spaces in their names, while `README_STRUCTURE.md` documents a proposed/refactored module layout using names such as `f01_data_pipeline`. These layouts are not interchangeable. **Use the paths and commands that match the version of the code checked out in your branch.** The commands below are the workflow documented in `README_STRUCTURE.md` and may require the refactored layout to be present.

### F01 — Data ingestion and quality

For the refactored module layout:

```powershell
uv run python -m retailpulse.f01_data_pipeline.ingestion
uv run python -m retailpulse.f01_data_pipeline.pipeline
uv run python -m retailpulse.f01_data_pipeline.validation
uv run python -m retailpulse.f01_data_pipeline.relationship_checks
uv run python -m retailpulse.f01_data_pipeline.duplicate_analysis
uv run python -m retailpulse.f01_data_pipeline.missing_value_analysis
uv run python -m retailpulse.f01_data_pipeline.quality_report
```

### F02 — Customer segmentation

```powershell
uv run python -m retailpulse.f02_customer_segmentation.feature_engineering
uv run python -m retailpulse.f02_customer_segmentation.eda
uv run python -m retailpulse.f02_customer_segmentation.clustering
uv run python -m retailpulse.f02_customer_segmentation.evaluation
uv run python -m retailpulse.f02_customer_segmentation.segment_profiling
```

### F03 — Demand forecasting

Prepare the daily demand table first. It may be large.

```powershell
uv run python -m retailpulse.f03_demand_forecasting.data_preparation
uv run python -m retailpulse.f03_demand_forecasting.prophet_model --sku-id YOUR_SKU_ID --horizon 30
```

### F04 — Churn analysis

Generate the required RFM features before running the churn workflow.

```powershell
uv run python -m retailpulse.f04_churn_prediction.churn_labeling
uv run python -m retailpulse.f04_churn_prediction.feature_engineering
uv run python -m retailpulse.f04_churn_prediction.model_training
```

### F05 — Inventory optimization

```powershell
uv run python -m retailpulse.f03_demand_forecasting.data_preparation
uv run python -m retailpulse.f05_inventory_optimization.demand_inputs
uv run python -m retailpulse.f05_inventory_optimization.reorder_policy
uv run python -m retailpulse.f05_inventory_optimization.optimization
uv run python -m retailpulse.f05_inventory_optimization.evaluation
```

### F06 — Dashboard

The developer notes document this intended command for the refactored layout:

```powershell
uv run streamlit run src/retailpulse/f06_dashboard/app.py
```

Run it only when that module exists in your checkout. The dashboard path is not present in every version of the current repository tree.

## Evaluation and Responsible Interpretation

Retail analytics outputs are useful only when the assumptions and evaluation method are explicit.

- **Data quality:** inspect missing values, duplicates, schema consistency, and relationships before transformation.
- **Duplicate transactions:** do not delete repeated-looking sales rows until the transaction grain and business rules are confirmed.
- **Missing promotion IDs:** confirm whether a missing value means “no promotion” before imputing it.
- **Inventory flags:** do not impute missing dates until the meaning of the flag is understood.
- **Forecasting:** use chronological holdouts for time-series evaluation and report the metric, horizon, and SKU/category scope.
- **Churn:** treat inactivity-derived labels as a proxy until stakeholders validate the definition against actual churn behavior.
- **Inventory:** document lead time, service-level, safety-stock, and demand assumptions before operational use.
- **Performance targets:** metrics such as forecast MAPE or churn AUC are goals to test, not results to claim without measured evidence.

## Current Limitations

- Some functional areas are starter implementations or documented next steps.
- LSTM/hybrid forecasting should not be described as implemented until its code and evaluation are available.
- The inactivity-based churn proxy is not observed customer churn.
- Inventory recommendations depend on assumed lead time and other inputs.
- The refactored commands in `README_STRUCTURE.md` may not match all directories in the current source tree.
- No production deployment or achievement of acceptance metrics is asserted by this README.

## Roadmap

- [ ] Align the on-disk package layout and documented commands.
- [ ] Complete reproducible F01 data-quality reporting.
- [ ] Validate RFM features and document cluster-selection criteria.
- [ ] Add leakage-safe forecasting benchmarks and evaluation reports.
- [ ] Validate the churn definition and evaluate the baseline classifier.
- [ ] Make inventory assumptions configurable and test reorder policies.
- [ ] Implement and verify the Streamlit dashboard against available outputs.
- [ ] Add automated tests and continuous integration.
- [ ] Document reproducible sample outputs and measured results.

## Contributing

Contributions and issue reports are welcome.

1. Open an issue describing the proposed change or problem.
2. Keep changes scoped to a functional area where possible.
3. Document assumptions and how the change was tested.
4. Avoid committing datasets, secrets, credentials, or generated artifacts.

## License

RetailPulse is licensed under the [MIT License](LICENSE). See the `LICENSE` file for the complete terms.

---

<div align="center">

**RetailPulse** · Building toward more reliable, interpretable retail decisions.

</div>
