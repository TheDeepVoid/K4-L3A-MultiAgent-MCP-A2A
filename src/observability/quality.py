from __future__ import annotations

from typing import Any
import json
from pathlib import Path

import great_expectations as gx
import pandas as pd
import great_expectations as gx
import great_expectations.expectations as gxe

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Tao bo data quality checks bang Great Expectations 1.x."""
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})
    
    suite = context.suites.add(gx.ExpectationSuite(name="papers_suite"))
    
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))
    
    validation_result = batch.validate(suite)
    
    res_dict = validation_result.to_json_dict()
    
    report_path = settings.paths.quality_dir / report_name
    write_json(report_path, res_dict)
    
    return res_dict


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report."""
    if df.empty:
        return {}
        
    latest_published = df["published"].max()
    oldest_published = df["published"].min()
    
    stale_mask = df["age_days"] > settings.freshness_threshold_days
    stale_rows = int(stale_mask.sum())
    total_rows = len(df)
    
    is_fresh = True
    if total_rows > 0:
        stale_ratio = stale_rows / total_rows
        is_fresh = stale_ratio <= 0.25
        
    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "is_fresh": is_fresh
    }
    
    write_json(report_path, payload)
    return payload
