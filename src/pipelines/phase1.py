from __future__ import annotations

import logging
from core.config import load_settings
from core.utils import now_utc, write_csv
from ingestion.crossref import fetch_source_records
from ingestion.cleaning import build_clean_dataframe
from retrieval.index import LocalEmbeddingIndex
from evaluation.testset import build_test_set
from evaluation.metrics import evaluate_pipeline
from observability.quality import run_data_quality_checks, build_freshness_report
from observability.reporting import generate_phase1_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main() -> None:
    """Xay dung baseline pipeline end-to-end."""
    # 1. Load settings
    logger.info("1. Loading settings...")
    s = load_settings()
    
    # 2. Load hoac fetch raw records
    logger.info("2. Fetching records...")
    records = fetch_source_records(s)
    
    # 3. Clean data
    logger.info("3. Cleaning data...")
    df = build_clean_dataframe(records, now_utc())
    
    # 4. Save clean CSV/JSON
    logger.info("4. Saving clean data...")
    write_csv(df, s.paths.clean_csv)
    df.to_json(s.paths.clean_json, orient="records")
    
    # 5. Build Chroma index
    logger.info("5. Building Chroma index...")
    index = LocalEmbeddingIndex.build(df, s, s.paths.embeddings_json)
    
    # 6. Tao hoac load evaluation set
    logger.info("6. Building test set...")
    build_test_set(df, s.paths.eval_testset)
    
    # 7. Evaluate
    logger.info("7. Evaluating pipeline...")
    eval_bundle = evaluate_pipeline(
        s, 
        index, 
        s.paths.eval_testset,
        s.paths.baseline_metrics,
        s.paths.baseline_answers
    )
    
    # 8. Run quality checks va freshness report
    logger.info("8. Running quality checks...")
    quality_res = run_data_quality_checks(df, s, "baseline_quality_report.json")
    freshness_res = build_freshness_report(df, s, s.paths.freshness_report)
    
    # 9. Tao markdown report
    logger.info("9. Generating phase 1 report...")
    source_summary = {"fetched": len(records), "cleaned": len(df)}
    generate_phase1_report(
        s.paths.baseline_report,
        source_summary,
        eval_bundle.summary,
        quality_res,
        freshness_res
    )
    
    logger.info("Phase 1 pipeline completed successfully!")

if __name__ == "__main__":
    main()
