from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import date
import html
import json
from pathlib import Path
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, write_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict[str, Any]) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord."""
    records = []
    items = payload.get("message", {}).get("items", [])
    for item in items:
        paper_id = item.get("DOI", "")
        if not paper_id:
            continue
            
        title_list = item.get("title", [])
        title = title_list[0] if title_list else ""
        if not title:
            continue
            
        abstract = item.get("abstract", "")
        # Loai bo HTML tags khoi abstract
        if abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()
        
        author_list = item.get("author", [])
        authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in author_list]
        
        categories = item.get("subject", [])
        primary_category = categories[0] if categories else ""
        
        # Parse published date
        published = ""
        published_info = item.get("published", {}).get("date-parts", [])
        if published_info and published_info[0]:
            parts = published_info[0]
            if len(parts) >= 3:
                published = f"{parts[0]}-{parts[1]:02d}-{parts[2]:02d}"
            elif len(parts) == 2:
                published = f"{parts[0]}-{parts[1]:02d}-01"
            elif len(parts) == 1:
                published = f"{parts[0]}-01-01"
                
        # Parse updated/created date
        updated = ""
        created_info = item.get("created", {}).get("date-time", "")
        if created_info:
            updated = created_info.split("T")[0]
        else:
            updated = published
            
        abs_url = item.get("URL", "")
        
        # Parse PDF URL if available
        pdf_url = ""
        link_list = item.get("link", [])
        for link in link_list:
            if link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL", "")
                break
                
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=abstract,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=""
            )
        )
        
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API, luu raw response, parse thanh records."""
    # Kiem tra xem co nen dung file backup khong
    if not settings.refresh_source and settings.paths.raw_api_response.exists():
        logger.info(f"Loading raw response from {settings.paths.raw_api_response}")
        with open(settings.paths.raw_api_response, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        logger.info("Fetching from Crossref API...")
        url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
            "select": "DOI,title,abstract,author,subject,published,created,URL,link"
        }
        
        payload = {}
        for attempt in range(3):
            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code in (429, 503):
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                payload = response.json()
                break
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)
                
        if not payload:
            logger.warning("Failed to fetch from API, falling back to local file if exists.")
            if settings.paths.raw_api_response.exists():
                with open(settings.paths.raw_api_response, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            else:
                return []
                
        settings.paths.raw_api_response.parent.mkdir(parents=True, exist_ok=True)
        with open(settings.paths.raw_api_response, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            
    records = parse_crossref_payload(payload)
    
    settings.paths.raw_records_json.parent.mkdir(parents=True, exist_ok=True)
    records_dict = [vars(r) for r in records]
    with open(settings.paths.raw_records_json, "w", encoding="utf-8") as f:
        json.dump(records_dict, f, indent=2)
        
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [PaperRecord(**item) for item in data]
