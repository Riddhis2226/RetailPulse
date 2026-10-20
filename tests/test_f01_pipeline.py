from __future__ import annotations

import pandas as pd

from retailpulse.f01_data_pipeline.pipeline import clean_dataframe


def test_cleaning_preserves_rows_columns_and_business_fields() -> None:
    source = pd.DataFrame(
        {
            "customer_id": [" C001 ", "C002"],
            "date": ["2025-01-01", "not-a-date"],
            "observed_sales": [12.0, 0.0],
            "is_stockout": [False, True],
            "imputed_demand": [12.0, 8.0],
        }
    )

    cleaned, stats = clean_dataframe(source, "sales_transactions.csv")

    assert len(cleaned) == len(source)
    assert list(cleaned.columns) == list(source.columns)
    assert cleaned["customer_id"].tolist() == ["C001", "C002"]
    assert cleaned["observed_sales"].tolist() == [12.0, 0.0]
    assert cleaned["is_stockout"].tolist() == [False, True]
    assert cleaned["imputed_demand"].tolist() == [12.0, 8.0]
    assert pd.isna(cleaned.loc[1, "date"])
    assert stats["invalid_dates"] == 1
    assert stats["trimmed_text_cells"] == 1


def test_cleaning_does_not_mutate_source_dataframe() -> None:
    source = pd.DataFrame({"customer_id": [" C001 "]})
    before = source.copy(deep=True)

    cleaned, _ = clean_dataframe(source, "customer_master.csv")

    pd.testing.assert_frame_equal(source, before)
    assert cleaned.loc[0, "customer_id"] == "C001"


def test_unknown_dataset_name_is_conservatively_cleaned() -> None:
    source = pd.DataFrame({"label": [" value ", None]})

    cleaned, stats = clean_dataframe(source, "unknown.csv")

    assert cleaned["label"].iloc[0] == "value"
    assert pd.isna(cleaned["label"].iloc[1])
    assert stats["invalid_dates"] == 0
