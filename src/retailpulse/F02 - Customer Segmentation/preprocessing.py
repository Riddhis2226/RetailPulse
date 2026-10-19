"""Prepare RFM features for customer clustering."""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

FEATURES = ["recency_days", "frequency_receipts", "monetary_value"]
LOG1P_FEATURES = ["frequency_receipts", "monetary_value"]


def prepare_features(df: pd.DataFrame):
    """Return standardized RFM features and the fitted scaler.

    The same transformation order must be applied to future inference data:
    replace infinities with NaN, fill missing values with zero, log1p the
    non-negative frequency/monetary features, then apply StandardScaler.
    """
    missing = sorted(set(FEATURES).difference(df.columns))
    if missing:
        raise ValueError(f"Missing features: {missing}")

    work = df[FEATURES].copy()
    for column in FEATURES:
        work[column] = pd.to_numeric(work[column], errors="coerce")

    work = work.replace([np.inf, -np.inf], np.nan).fillna(0)
    for column in LOG1P_FEATURES:
        work[column] = np.log1p(work[column].clip(lower=0))

    scaler = StandardScaler()
    scaled = scaler.fit_transform(work)
    return scaled, scaler


def transform_features(df: pd.DataFrame, scaler: StandardScaler):
    """Transform new rows using an already-fitted scaler without refitting."""
    missing = sorted(set(FEATURES).difference(df.columns))
    if missing:
        raise ValueError(f"Missing features: {missing}")

    work = df[FEATURES].copy()
    for column in FEATURES:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.replace([np.inf, -np.inf], np.nan).fillna(0)

    for column in LOG1P_FEATURES:
        work[column] = np.log1p(work[column].clip(lower=0))

    return scaler.transform(work)
