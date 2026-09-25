from __future__ import annotations

import logging
import pandas as pd
from core.config import load_settings
from core.utils import now_utc, write_csv, read_json
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from ingestion.cleaning import build_clean_dataframe
from retrieval.index import LocalEmbeddingIndex
from evaluation.metrics import evaluate_pipeline
from observability.quality import run_data_quality_checks, build_freshness_report
from observability.reporting import generate_corruption_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main() -> None:
    """Xay dung corruption -> evaluate -> repair -> compare flow."""
    s = load_settings()
    
    # 1. Load baseline metrics va clean dataset
    logger.info("1. Loading baseline metrics and clean data...")
    baseline_metrics = read_json(s.paths.baseline_metrics)
    df_clean = pd.read_json(s.paths.clean_json)
    
    # 2. Tao corrupted dataframe
    logger.info("2. Corrupting dataframe...")
    df_corrupted = corrupt_clean_dataframe(df_clean, s.paths.corruption_log)
    
    # 3. Save corrupted artifacts
    logger.info("3. Saving corrupted data...")
    write_csv(df_corrupted, s.paths.corrupted_clean_csv)
    df_corrupted.to_json(s.paths.corrupted_clean_json, orient="records")
    
    # 4. Rebuild index va evaluate (Corrupted)
    logger.info("4. Evaluating corrupted data...")
    corrupted_index = LocalEmbeddingIndex.build(df_corrupted, s, s.paths.corrupted_embeddings_json)
    corrupted_eval = evaluate_pipeline(
        s, corrupted_index, s.paths.eval_testset,
        s.paths.corrupted_metrics, s.paths.corrupted_answers
    )
    
    # 5. Run quality checks/freshness tren corrupted data
    logger.info("5. Running observability on corrupted data...")
    corrupted_quality = run_data_quality_checks(df_corrupted, s, "corrupted_quality_report.json")
    corrupted_freshness = build_freshness_report(df_corrupted, s, s.paths.quality_dir / "corrupted_freshness.json")
    
    # 6. Repair lai tu raw records
    logger.info("6. Repairing data from raw snapshot...")
    raw_records = load_raw_records(s.paths.raw_records_json)
    df_repaired = build_clean_dataframe(raw_records, now_utc())
    
    write_csv(df_repaired, s.paths.repaired_clean_csv)
    df_repaired.to_json(s.paths.repaired_clean_json, orient="records")
    
    # 7. Evaluate repaired dataset
    logger.info("7. Evaluating repaired data...")
    repaired_index = LocalEmbeddingIndex.build(df_repaired, s, s.paths.repaired_embeddings_json)
    repaired_eval = evaluate_pipeline(
        s, repaired_index, s.paths.eval_testset,
        s.paths.repaired_metrics, s.paths.repaired_answers
    )
    
    repaired_quality = run_data_quality_checks(df_repaired, s, "repaired_quality_report.json")
    repaired_freshness = build_freshness_report(df_repaired, s, s.paths.quality_dir / "repaired_freshness.json")
    
    # 8. Tao comparison report
    logger.info("8. Generating comparison report...")
    generate_corruption_report(
        s.paths.comparison_report,
        baseline_metrics,
        corrupted_eval.summary,
        repaired_eval.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness
    )
    
    # Print comparison table to console
    print("\n" + "="*50)
    print("COMPARISON REPORT")
    print(f"{'Metric':<20} | {'Baseline':<10} | {'Corrupted':<10} | {'Repaired':<10}")
    print("-" * 50)
    print(f"{'Hit Rate':<20} | {baseline_metrics.get('retrieval_hit_rate',0):<10.2%} | {corrupted_eval.summary.get('retrieval_hit_rate',0):<10.2%} | {repaired_eval.summary.get('retrieval_hit_rate',0):<10.2%}")
    print(f"{'Mean Token F1':<20} | {baseline_metrics.get('mean_token_f1',0):<10.2%} | {corrupted_eval.summary.get('mean_token_f1',0):<10.2%} | {repaired_eval.summary.get('mean_token_f1',0):<10.2%}")
    print(f"{'Quality Success':<20} | {'True':<10} | {str(corrupted_quality.get('success', False)):<10} | {str(repaired_quality.get('success', False)):<10}")
    print(f"{'Is Fresh':<20} | {'True':<10} | {str(corrupted_freshness.get('is_fresh', False)):<10} | {str(repaired_freshness.get('is_fresh', False)):<10}")
    print("="*50 + "\n")
    
if __name__ == "__main__":
    main()
