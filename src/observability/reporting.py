from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from core.utils import write_text

def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase."""
    md = f"""# Baseline Pipeline Report

## 1. Source Summary
- Total documents fetched: {source_summary.get('fetched', 0)}
- Clean documents saved: {source_summary.get('cleaned', 0)}

## 2. Data Quality & Freshness
- Quality Check Success: {quality.get('success', False)}
- Is Fresh: {freshness.get('is_fresh', False)}
- Stale Rows: {freshness.get('stale_rows', 0)} / {freshness.get('total_rows', 0)}

## 3. Evaluation Metrics
- Hit Rate: {metrics.get('retrieval_hit_rate', 0.0):.2%}
- Mean Token F1: {metrics.get('mean_token_f1', 0.0):.2%}
- Judge Accuracy: {metrics.get('judge_accuracy', 0.0):.2%}
- Mean Judge Score: {metrics.get('mean_judge_score', 0.0):.2f}/5
"""
    write_text(report_path, md)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Viet markdown report so sanh baseline/corrupted/repaired."""
    md = f"""# Data Corruption & Repair Report

| Metric | Baseline | Corrupted | Repaired |
|---|---|---|---|
| Hit Rate | {baseline_metrics.get('retrieval_hit_rate', 0):.2%} | {corrupted_metrics.get('retrieval_hit_rate', 0):.2%} | {repaired_metrics.get('retrieval_hit_rate', 0):.2%} |
| Mean Token F1 | {baseline_metrics.get('mean_token_f1', 0):.2%} | {corrupted_metrics.get('mean_token_f1', 0):.2%} | {repaired_metrics.get('mean_token_f1', 0):.2%} |
| Quality Success | N/A | {corrupted_quality.get('success', False)} | {repaired_quality.get('success', False)} |
| Is Fresh | N/A | {corrupted_freshness.get('is_fresh', False)} | {repaired_freshness.get('is_fresh', False)} |
"""
    write_text(report_path, md)
