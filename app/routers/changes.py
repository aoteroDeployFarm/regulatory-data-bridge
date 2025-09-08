# app/routers/changes.py
from fastapi import APIRouter, Query, Response
from typing import Optional, List
from datetime import date
import csv, io
from sqlalchemy import text

# Adjust this import to your project if needed
from app.db import get_engine

router = APIRouter()

def _rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    fieldnames = rows[0].keys() if rows else ["id","doc_id","change_type","fetched_at","title","url","source_id"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()

@router.get("/changes")
def list_changes(
    jurisdiction: str = Query(..., min_length=2, max_length=2, description="State code, e.g. CO"),
    since: Optional[date] = Query(None, description="YYYY-MM-DD"),
    group_by: Optional[str] = Query(None, pattern="^(source)$"),
    format: Optional[str] = Query(None, pattern="^(md)$"),
    include: Optional[List[str]] = Query(None, description="e.g. include=diff"),
    limit: int = Query(500, ge=1, le=25000),
):
    """
    Read recent changes from document_versions joined to documents.
    Columns expected on document_versions: id, doc_id, change_type, fetched_at, (optional) diff_text, jurisdiction
    Columns expected on documents: id, title, url, source_id, jurisdiction
    """
    engine = get_engine()
    params = {"jur": jurisdiction.upper(), "limit": limit}
    where = ["dv.jurisdiction = :jur"]
    if since:
        where.append("dv.fetched_at >= :since")
        params["since"] = f"{since} 00:00:00"

    if group_by == "source":
        sql = f"""
        SELECT d.source_id,
               COUNT(*) AS count,
               MIN(dv.fetched_at) AS first_seen,
               MAX(dv.fetched_at) AS last_seen
        FROM document_versions dv
        JOIN documents d ON d.id = dv.doc_id
        WHERE {" AND ".join(where)}
        GROUP BY d.source_id
        ORDER BY last_seen DESC
        LIMIT :limit
        """
    else:
        select_cols = [
            "dv.id", "dv.doc_id", "dv.change_type", "dv.fetched_at",
            "d.title", "d.url", "d.source_id"
        ]
        if include and "diff" in include:
            select_cols.append("dv.diff_text")
        sql = f"""
        SELECT {", ".join(select_cols)}
        FROM document_versions dv
        JOIN documents d ON d.id = dv.doc_id
        WHERE {" AND ".join(where)}
        ORDER BY dv.fetched_at DESC
        LIMIT :limit
        """

    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(text(sql), params)]

    if format == "md":
        lines = ["# Recent Changes\n"]
        if group_by == "source":
            for r in rows:
                lines.append(f"- **Source {r['source_id']}** — {r['count']} changes (last: {r['last_seen']})")
        else:
            for r in rows:
                lines.append(f"- **{r.get('title') or ''}** — {r['change_type']} — {r['fetched_at']}  \n{r.get('url') or ''}")
                if 'diff_text' in r and r.get('diff_text'):
                    snippet = (r['diff_text'][:2000]) if r['diff_text'] else ""
                    lines.append(f"```diff\n{snippet}\n```")
        return {"markdown": "\n".join(lines)}

    return rows

@router.get("/changes/export.csv")
def export_changes_csv(
    jurisdiction: str = Query(..., min_length=2, max_length=2),
    since: Optional[date] = Query(None),
    limit: int = Query(25000, ge=1, le=25000),
):
    engine = get_engine()
    params = {"jur": jurisdiction.upper(), "limit": limit}
    where = ["dv.jurisdiction = :jur"]
    if since:
        where.append("dv.fetched_at >= :since")
        params["since"] = f"{since} 00:00:00"

    sql = f"""
    SELECT dv.id, dv.doc_id, dv.change_type, dv.fetched_at, d.title, d.url, d.source_id
    FROM document_versions dv
    JOIN documents d ON d.id = dv.doc_id
    WHERE {" AND ".join(where)}
    ORDER BY dv.fetched_at DESC
    LIMIT :limit
    """

    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(text(sql), params)]

    csv_text = _rows_to_csv(rows)
    return Response(content=csv_text, media_type="text/csv")
