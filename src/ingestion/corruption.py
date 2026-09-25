from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from datetime import datetime, timedelta
from core.utils import write_json

def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate nhieu dang data corruption."""
    if df.empty:
        write_json(output_log_path, {"status": "empty_df"})
        return df
        
    df = df.copy()
    logs = []
    
    # 1. Drop mot so latest records (20%)
    num_to_drop = max(1, int(len(df) * 0.2))
    df = df.sort_values("published", ascending=False)
    dropped_ids = df.head(num_to_drop)["paper_id"].tolist()
    df = df.iloc[num_to_drop:].reset_index(drop=True)
    logs.append(f"Dropped {num_to_drop} latest records: {dropped_ids}")
    
    if not df.empty:
        # 2. Blank summary o mot so dong (dong 0)
        if len(df) > 0:
            df.at[0, "summary"] = ""
            df.at[0, "summary_chars"] = 0
            logs.append(f"Blanked summary for paper_id {df.at[0, 'paper_id']}")
            
        # 3. Inject noise vao text (dong 1)
        if len(df) > 1:
            noise = " %%%RÁC_VÔ_NGHĨA_123%%% "
            df.at[1, "summary"] = str(df.at[1, "summary"]) + noise
            df.at[1, "summary_chars"] = len(df.at[1, "summary"])
            logs.append(f"Injected noise to paper_id {df.at[1, 'paper_id']}")
            
        # 4. Lam title bi truncate < 8 ky tu (dong 2)
        if len(df) > 2:
            df.at[2, "title"] = str(df.at[2, "title"])[:7]
            logs.append(f"Truncated title for paper_id {df.at[2, 'paper_id']}")
            
        # 5. Lam published date cu di 365 ngay (dong 3)
        if len(df) > 3:
            try:
                pub_date = datetime.strptime(str(df.at[3, "published"]), "%Y-%m-%d")
                stale_date = pub_date - timedelta(days=365)
                df.at[3, "published"] = stale_date.strftime("%Y-%m-%d")
                df.at[3, "age_days"] = df.at[3, "age_days"] + 365
                logs.append(f"Made date stale for paper_id {df.at[3, 'paper_id']}")
            except Exception:
                pass
                
        # 6. Add duplicate rows (dong 4)
        if len(df) > 4:
            dup_row = df.iloc[4:5].copy()
            df = pd.concat([df, dup_row], ignore_index=True)
            logs.append(f"Duplicated paper_id {df.iloc[4]['paper_id']}")
            
        # 7. Rebuild `text_for_embedding`
        def rebuild_text(row):
            return f"Title: {row['title']}\nAuthors: {row['authors_joined']}\nPublished: {row['published']}\nCategories: {row['categories_joined']}\nSummary: {row['summary']}"
            
        df["text_for_embedding"] = df.apply(rebuild_text, axis=1)

    # 8. Ghi corruption log vao output_log_path
    write_json(output_log_path, {"logs": logs})
    return df
