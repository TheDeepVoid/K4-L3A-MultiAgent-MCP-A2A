from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
import pandas as pd
from core.utils import write_json, first_sentence

def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao bo evaluation set tu cleaned dataframe."""
    if df.empty:
        write_json(output_path, [])
        return []

    # Lay 3 bai bao dai dien de sinh cau hoi
    sample_df = df.head(3)
    
    test_set = []
    eval_id = 1
    
    # 10 cau hoi thuoc 4 dang khac nhau
    question_plan = [
        ("summary", "What is the summary of the paper '{title}'?", lambda r: first_sentence(r["summary"])),
        ("summary", "What is the summary of the paper '{title}'?", lambda r: first_sentence(r["summary"])),
        ("summary", "What is the summary of the paper '{title}'?", lambda r: first_sentence(r["summary"])),
        ("authors", "Who are the authors of the paper '{title}'?", lambda r: r["authors_joined"]),
        ("authors", "Who are the authors of the paper '{title}'?", lambda r: r["authors_joined"]),
        ("authors", "Who are the authors of the paper '{title}'?", lambda r: r["authors_joined"]),
        ("date", "When was the paper '{title}' published?", lambda r: str(r["published"])),
        ("date", "When was the paper '{title}' published?", lambda r: str(r["published"])),
        ("categories", "What are the categories of the paper '{title}'?", lambda r: r["categories_joined"]),
        ("categories", "What are the categories of the paper '{title}'?", lambda r: r["categories_joined"])
    ]
    
    for i, (q_type, q_template, get_gt) in enumerate(question_plan):
        # Quay vong cac bai bao dai dien
        row = sample_df.iloc[i % len(sample_df)]
        
        test_set.append({
            "id": f"eval_{eval_id:03d}",
            "question_type": q_type,
            "question": q_template.format(title=row["title"]),
            "ground_truth": get_gt(row),
            "ground_truth_doc_ids": [row["paper_id"]]
        })
        eval_id += 1
        
    write_json(output_path, test_set)
    return test_set
