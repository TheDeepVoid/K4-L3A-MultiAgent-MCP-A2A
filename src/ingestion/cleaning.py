from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord
from core.utils import compact_join, normalize_whitespace, write_csv, write_json


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed."""
    
    rows = []
    for r in records:
        # Normalize
        title = normalize_whitespace(r.title)
        summary = normalize_whitespace(r.summary)
        authors_joined = compact_join(r.authors)
        categories_joined = compact_join(r.categories)
        
        # Parse date and calculate age_days
        try:
            # Convert published string to datetime
            pub_date = datetime.strptime(r.published, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            # Ensure run_date has timezone info
            if run_date.tzinfo is None:
                run_date = run_date.replace(tzinfo=timezone.utc)
            age_days = (run_date - pub_date).days
        except Exception:
            age_days = 0
            
        summary_chars = len(summary)
        
        text_for_embedding = f"Title: {title}\nAuthors: {authors_joined}\nPublished: {r.published}\nCategories: {categories_joined}\nSummary: {summary}"
        
        rows.append({
            "paper_id": r.paper_id,
            "title": title,
            "summary": summary,
            "authors": r.authors,
            "categories": r.categories,
            "primary_category": r.primary_category,
            "published": r.published,
            "updated": r.updated,
            "abs_url": r.abs_url,
            "pdf_url": r.pdf_url,
            "comment": r.comment,
            "authors_joined": authors_joined,
            "categories_joined": categories_joined,
            "age_days": age_days,
            "summary_chars": summary_chars,
            "text_for_embedding": text_for_embedding
        })
        
    df = pd.DataFrame(rows)
    
    if df.empty:
        return df
        
    # Filter out bad rows
    df = df[df["title"].str.len() > 0]
    df = df[df["summary"].str.len() > 0]
    df = df[df["paper_id"].str.len() > 0]
    
    # Drop duplicates
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    
    # Sort
    df = df.sort_values(by="published", ascending=False).reset_index(drop=True)
    
    return df
