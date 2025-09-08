from fastapi import APIRouter, Query, Response
from typing import Optional, List, Dict
import csv, io, datetime
from app.services.documents import fetch_filtered_documents
from app.lib.filters import looks_like_real_doc

router = APIRouter()

CSV_HEADERS = ["id", "title", "url", "jurisdiction", "published_at"]

@router.get("/documents/export.csv")
def export_csv(
    jurisdiction: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    # Overfetch a bit, then filter & trim to limit
    rows: List[Dict] = []
    fetched = fetch_filtered_documents(jurisdiction, max(limit, 100))
    for d in fetched:
        if looks_like_real_doc(d):
            rows.append({
                "id": str(d.get("id") or ""),
                "title": (d.get("title") or "").strip(),
                "url": (d.get("url") or "").strip(),
                "jurisdiction": (d.get("jurisdiction") or "").strip(),
                "published_at": (d.get("published_at") or ""),
            })
            if len(rows) >= limit:
                break

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_HEADERS, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)

    return Response(content=buf.getvalue(), media_type="text/csv; charset=utf-8")
