# F03 — Demand Forecasting

> **RetailPulse | Functional Requirement 03**

## Objective

Estimate future product demand from historical retail sales to support replenishment planning, inventory decisions, and forward-looking business analysis.

## Forecasting Design

The project specification calls for daily demand forecasting at the **store–SKU level**, with a 30-day forecast horizon as the target use case.

A reliable workflow should:

1. Aggregate sales into a consistent daily time series for each store and SKU.
2. Validate date coverage, missing dates, invalid quantities, and unusual spikes.
3. Create time-based training and validation windows.
4. Establish a simple baseline before testing more complex models.
5. Fit and evaluate a forecasting model.
6. Generate forecasts with dates and product/store identifiers.
7. Save forecasts and evaluation metrics for F05 and the dashboard.

Prophet is identified as a candidate baseline in the project plan. An LSTM or hybrid Prophet–LSTM model is an extension, not a result to claim until it has been implemented, trained, and evaluated.

## Suggested Evaluation

Use a chronological holdout so the evaluation reflects forecasting into the future. Report metrics such as:

- **MAE:** average absolute forecast error.
- **RMSE:** penalizes larger errors more heavily.
- **MAPE or WAPE:** percentage-based error, with care around zero or very small actual demand.

The project brief lists a target of **MAPE ≤ 12%**. This is a target, not a measured result; report the actual score only after running evaluation on a defined holdout.

## Intended Inputs and Outputs

**Inputs**
- Historical sales with a transaction date, product/SKU identifier, store identifier, and a usable demand or quantity measure.
- Optional calendar or promotion features, if their availability and semantics are validated.

**Outputs**
- Daily historical demand series.
- Forecast dates and predicted demand by store and SKU.
- Evaluation metrics and model metadata.

Stockouts can suppress observed sales, so observed sales should not automatically be treated as true unconstrained demand. Any imputation or stockout correction needs a documented method.

## Implementation Status

This folder currently contains its README placeholder; forecasting scripts are not present here yet. The workflow above documents the intended module and does not claim that a forecasting model has been trained or that forecasts are currently generated.

## Completion Checklist

- [ ] Implement daily store–SKU demand aggregation.
- [ ] Validate date continuity and demand values.
- [ ] Add a naïve or seasonal baseline.
- [ ] Implement and evaluate a Prophet baseline.
- [ ] Save forecast outputs in a documented format.
- [ ] Add chronological backtesting and metric reporting.
- [ ] Consider LSTM/hybrid forecasting only after the baseline is reliable.
- [ ] Document the model, forecast horizon, data window, and actual evaluation results.
