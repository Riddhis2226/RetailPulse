# F05 — Inventory Optimization

> **RetailPulse | Functional Requirement 05**

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
