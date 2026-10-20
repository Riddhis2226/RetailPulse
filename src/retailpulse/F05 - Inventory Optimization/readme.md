# F05 — Inventory Optimization

> **RetailPulse | Functional Requirement 05**

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


## Dataset Use in F05

- **Demand input:** forecasts or aggregated demand derived from `sales_transactions.csv` through F03.
- **Inventory input:** `inventory_snapshot.csv` and relevant fields from `sku_inventory_flags.csv`, after checking the meaning, timestamp, and coverage of those fields.
- **Product/store context:** `sku_master.csv` and `store_master.csv`, where valid keys are available.

The project notes use a 7-day supplier lead time as an initial assumption, not a verified SLA. Make lead time configurable and record it with each recommendation. Missing stock values should not automatically be treated as zero. The actual schema and availability of stock-on-hand, open orders, and supplier lead times must be confirmed from inspection outputs before calculating recommendations.


## Objective

Convert historical or forecast demand into practical replenishment recommendations that help reduce the risk of stockouts and excess inventory.

## Core Logic

A transparent baseline can estimate replenishment needs using:

- Recent or forecast average daily demand.
- Current available stock, where reliable inventory data exists.
- Supplier lead time.
- A documented safety-stock policy.
- A target coverage period or reorder point.

A common baseline formula is:

`Reorder Point = Expected Demand During Lead Time + Safety Stock`

A suggested order quantity can then be calculated from the target stock position, accounting for available stock and any known open purchase orders. The exact policy should reflect the fields available in the dataset and the business assumptions selected.

## Dependency on F03

F05 is designed to consume demand inputs or forecasts from F03. Forecasts should be aligned to the correct store, SKU, and date range before they are used for replenishment calculations.

If forecasts are unavailable, a clearly labelled historical-demand baseline may be used during development. Do not present a historical average as a model forecast.

## Lead-Time and Stockout Assumptions

The project structure notes a default **7-day lead time** as a starting assumption. It is not a verified supplier SLA. Make lead time configurable and replace the default with validated supplier or product-specific values when available.

Inventory recommendations also depend on the meaning and completeness of stock-on-hand, replenishment, and stockout fields. Missing inventory values should not be silently treated as zero.

## Intended Outputs

- Store and SKU identifiers.
- Demand estimate or forecast used.
- Lead-time demand and safety stock.
- Reorder point and recommended order quantity.
- Assumptions, input date, and recommendation rationale.

## Evaluation

Where actual inventory and replenishment outcomes are available, evaluate recommendations against stockouts, excess stock, service levels, and inventory holding costs. Without a reliable historical comparison, describe the output as a baseline recommendation rather than claiming a measured reduction in overstocking or stockouts.

The project brief mentions a 25–40% reduction target for overstock/understock. This remains a target until validated through a defined evaluation.

## Implementation Status

This folder currently contains its README placeholder; inventory optimization scripts are not present here yet. The logic described above is the intended implementation plan, not a claim that reorder recommendations are already generated.

## Completion Checklist

- [ ] Define the inventory and forecast input schemas.
- [ ] Implement demand-input preparation.
- [ ] Make lead time and safety stock configurable.
- [ ] Calculate reorder points and suggested order quantities.
- [ ] Handle missing or unreliable stock data explicitly.
- [ ] Validate recommendations against sample cases.
- [ ] Document assumptions and evaluation results.
