
# RetailPulse

<div align="center">

### Retail Analytics · Customer Intelligence · Demand Planning

**A modular retail analytics and machine-learning project for exploring customer behaviour, forecasting product demand, identifying churn risk, and supporting inventory decisions.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Data-Pandas%20%7C%20NumPy-150458)](https://pandas.pydata.org/)
[![scikit-learn](https://img.shields.io/badge/ML-scikit--learn-orange)](https://scikit-learn.org/)
[![Hugging Face Dataset](https://img.shields.io/badge/Dataset-Hugging%20Face-yellow?logo=huggingface)](https://huggingface.co/datasets/RS2226/RetailPulse)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 1. Project Overview

RetailPulse is designed around an end-to-end retail analytics workflow: source-data inspection, customer-level feature engineering, predictive modelling, inventory recommendations, and interactive reporting.

The project requirements define six functional areas. The repository is being developed in stages, so the status labels below distinguish implemented starter code from planned components. Targets in the project brief are **acceptance criteria, not measured results**.

## 2. Functional Requirements and Status

| ID | Requirement | Intended scope / acceptance criteria | Repository status |
|---|---|---|---|
| **F01** | Data ingestion & cleaning | Retrieve the seven source CSVs from Hugging Face, clean conservatively, write Parquet outputs in chunks, and emit a JSON run report. | Canonical package and regression tests are present; full-dataset execution and deployment-resource needs must still be verified. |
| **F02** | Customer segmentation | RFM and behavioural features; K-Means/DBSCAN exploration; segment evaluation and business profiling. Target: 6–8 interpretable segments. | Starter scripts for feature engineering, clustering, evaluation, and profiling are present. Segment count and quality are not claimed. |
| **F03** | Demand forecasting | Daily demand preparation and 30-day forecasts; Prophet + LSTM/hybrid approach in the project brief. Target: MAPE ≤ 12%. | Requirements and module documentation exist; end-to-end forecasting and target performance remain unverified. |
| **F04** | Churn prediction | Identify at-risk customers with a clearly defined churn label and evaluated classifier. Targets: AUC-ROC ≥ 0.88 and precision@top 20% ≥ 0.75. | Module documentation exists; label validity, trained model, and metrics must be verified before reporting results. |
| **F05** | Inventory optimization | Forecast-informed reorder recommendations with explicit lead-time and safety-stock assumptions. | Module documentation exists; operational recommendations and impact are not claimed as validated. |
| **F06** | Interactive analytics dashboard | Streamlit views for sales, customers, forecasts, and inventory, including exportable insights and what-if analysis. | Planned; verify the dashboard implementation and deployment before presenting a live demo. |

### Project-wide non-functional targets

The project brief also sets goals for scalable processing, daily batch jobs under five minutes, reproducible experiment tracking, and data/model monitoring. These goals should be measured with repeatable tests before being described as achieved. Business-impact figures such as stockout reduction or revenue growth are aspirations from the brief, not current project results.

## 3. Source Data — Hugging Face

**The seven source CSV datasets are hosted in the RetailPulse Hugging Face dataset repository; they are not stored in this GitHub repository.**

**Dataset repository:** [RS2226/RetailPulse on Hugging Face](https://huggingface.co/datasets/RS2226/RetailPulse)  
**Dataset documentation:** [DATASETS.md](DATASETS.md)  
**Reported repository size in the dataset page:** approximately 805 MB (may change as files are updated).

| Source file | Intended data domain |
|---|---|
| **customer_master.csv** | Customer master records and customer attributes |
| **inventory_snapshot.csv** | Inventory snapshots |
| **promotions.csv** | Promotion records |
| **sales_transactions.csv** | Transaction-level sales; the inspection script reads this file in chunks |
| **sku_inventory_flags.csv** | SKU-level inventory flags |
| **sku_master.csv** | Product/SKU master records |
| **store_master.csv** | Store master records |

The Hugging Face repository page is publicly discoverable. **File access may still require a signed-in, authorized Hugging Face account if repository gating is enabled.** Check the dataset page for the current access status. The code uses Hugging Face Hub to retrieve source files. Never put access tokens or credentials in source control.

Schema details, exact row counts, date coverage, and join keys should be taken from the generated F01 inspection report rather than inferred from filenames.

## 4. Technology

| Layer | Technologies |
|---|---|
| Language and data processing | Python 3.11+, Pandas, NumPy, PyArrow, DuckDB |
| Machine learning | scikit-learn, PyTorch / Lightning |
| Forecasting and statistics | Prophet, statsmodels |
| Experiment tracking / tuning | MLflow, Optuna |
| Data access / configuration | Hugging Face Hub, SQLAlchemy, PostgreSQL driver, python-dotenv |
| Intended dashboard | Streamlit |

Some dependencies support planned or optional components and do not imply that every capability is already implemented. See [pyproject.toml](pyproject.toml) for declared dependencies.

## 5. Repository Layout

~~~text
RetailPulse/
├── src/retailpulse/
│   ├── F01 - Data Ingestion & Cleaning/  # legacy diagnostics / compatibility entry point
│   ├── f01_data_pipeline/                # canonical deployable F01 package
│   ├── F02 - Customer Segmentation/
│   ├── F03 - Demand Forecasting/       # documentation / planned work
│   ├── F04 - Churn Prediction/         # documentation / planned work
│   ├── F05 - Inventory Optimization/   # documentation / planned work
│   ├── __init__.py
│   └── config.py
├── data/
│   ├── raw/                            # local source files; not committed
│   └── processed/                      # local generated outputs
├── reports/                            # generated quality reports
├── pyproject.toml
├── requirements-f01.txt
├── Dockerfile.f01
├── .gitignore
├── DATASETS.md
├── README_STRUCTURE.md
├── README.md
└── LICENSE
~~~

The source tree is evolving. Run scripts by the paths present in your checkout; do not assume that proposed package names in older notes exist as importable modules.

## 6. Setup

Requirements: Python 3.11 or later, Git, and [uv](https://docs.astral.sh/uv/).

~~~bash
git clone https://github.com/Riddhis2226/RetailPulse.git
cd RetailPulse
uv sync
~~~

If you do not use uv, create a virtual environment and install the project using the dependency metadata in pyproject.toml.

## 7. Run Available Workflows

Run commands from the repository root.

### F01 — Inspect the seven source datasets

~~~bash
uv run python "src/retailpulse/F01 - Data Ingestion & Cleaning/01_inspect_datasets.py"
~~~

The inspection script retrieves the configured CSVs from Hugging Face and writes reports under reports/dataset_inspection/. It processes sales data in chunks of 100,000 rows. Missing values are reported, not automatically imputed; duplicate detection across chunk boundaries may be incomplete.

### F01 — Verify the customer master download

~~~bash
uv run python "src/retailpulse/F01 - Data Ingestion & Cleaning/02_verify_huggingface_dataset.py"
~~~

### F01 — Run the preparation pipeline

~~~bash
uv run python "src/retailpulse/F01 - Data Ingestion & Cleaning/03_pipeline.py"
~~~

Check the scripts and configuration for expected inputs and output locations before running the full pipeline.

### F02 — Customer segmentation

The folder contains starter scripts for EDA, feature engineering, preprocessing, clustering, evaluation, and segment profiling. Start with its [module README](src/retailpulse/F02%20-%20Customer%20Segmentation/readme.md) and run scripts in their required input/output order. Confirm generated artifacts and metrics from execution.

### F03–F06

Forecasting, churn prediction, inventory optimization, and dashboard work are described in their module documentation and the project requirements. Do not run the refactored module commands from earlier design notes unless those modules exist in your checked-out branch.

## 8. Evaluation and Responsible Interpretation

- Confirm data grain and business meaning before deleting duplicate-looking transactions.
- Treat missing promotion IDs according to verified field semantics; do not assume every missing value means “no promotion.”
- Validate primary and foreign keys before joining tables.
- Use time-ordered holdouts for demand forecasting and document the forecast horizon and evaluated scope.
- Treat inactivity-based churn labels as a proxy until they are validated against a business definition.
- Keep inventory lead time, service level, safety stock, and demand assumptions explicit and configurable.
- Report only measured model metrics, runtime, and business outcomes. Targets from the project brief must not be presented as achieved results without evidence.

## 9. Roadmap

- [ ] Run F01 against the complete Hugging Face source data and retain an inspection report.
- [ ] Validate F01 data-quality and referential-integrity checks.
- [ ] Reproduce F02 RFM features, clustering evaluation, and segment profiles.
- [ ] Implement and evaluate a leakage-safe forecasting baseline before any hybrid model.
- [ ] Define and validate churn labels; evaluate a baseline classifier.
- [ ] Implement and test configurable reorder recommendations.
- [ ] Build and test the Streamlit dashboard against generated outputs.
- [ ] Add automated tests, linting, and continuous integration.
- [ ] Record measured results and deployment/demo instructions.

## 10. Contributing

1. Keep changes scoped to a functional requirement where possible.
2. Document assumptions, reproducibility steps, and test results.
3. Use clear commit messages and review changes before merging.
4. Do not commit datasets, model binaries, credentials, API keys, or generated artifacts unnecessarily.

## License

The RetailPulse **code and documentation** are licensed under the [MIT License](LICENSE). Dataset terms and access conditions are governed by the Hugging Face dataset repository and any applicable source-data terms; the code license does not automatically grant rights to third-party data.

---

<div align="center">

**RetailPulse · From retail data to more informed decisions**

</div>
