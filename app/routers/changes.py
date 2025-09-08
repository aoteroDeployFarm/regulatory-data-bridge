# app/routers/changes.py
from fastapi import APIRouter, Query, Response
from typing import Optional, List
from datetime import date
import csv, io, os

from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine

router = APIRouter()

# -------------------------------
# Engine resolution (robust)
# -------------------------------
_ENGINE: Optional[Engine] = None

def _resolve_engine() -> Engine:
    # Try your project's get_engine first (no import-time crash)
    try:
        from app.db import get_engine as _ge  # type: ignore
        return _ge()
    except Exception:
        pass

    # Fallback: env or sqlite dev.db
    url = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)

def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _resolve_engine()
    return _ENGINE

def _rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    fieldnames = rows[0].keys() if rows else ["id","doc_id","change_type","fetched_at","title","url","source_id"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()

# -------------------------------
# /changes (JSON + optional md)
# -------------------------------
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
    Expects:
      - document_versions: id, doc_id, change_type, fetched_at, [jurisdiction], [diff_text]
      - documents: id, title, url, source_id, jurisdiction
    """
    eng = get_engine()
    params = {"jur": jurisdiction.upper(), "limit": limit}

    where = ["dv.jurisdiction = :jur"]
    if since:
        where.append("dv.fetched_at >= :since")
        params["since"] = f"{since} 00:00:00"

    def _exec(sql_parts_where: list[str], select_cols: Optional[list[str]] = None, grouped: bool = False):
        if grouped:
            sql = f"""
            SELECT d.source_id,
                   COUNT(*) AS count,
                   MIN(dv.fetched_at) AS first_seen,
                   MAX(dv.fetched_at) AS last_seen
            FROM document_versions dv
            JOIN documents d ON d.id = dv.doc_id
            WHERE {" AND ".join(sql_parts_where)}
            GROUP BY d.source_id
            ORDER BY last_seen DESC
            LIMIT :limit
            """
        else:
            sql = f"""
            SELECT {", ".join(select_cols or [
                "dv.id","dv.doc_id","dv.change_type","dv.fetched_at",
                "d.title","d.url","d.source_id"
            ])}
            FROM document_versions dv
            JOIN documents d ON d.id = dv.doc_id
            WHERE {" AND ".join(sql_parts_where)}
            ORDER BY dv.fetched_at DESC
            LIMIT :limit
            """
        with eng.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params)]

    try:
        if group_by == "source":
            rows = _exec(where, grouped=True)
        else:
            cols = ["dv.id","dv.doc_id","dv.change_type","dv.fetched_at","d.title","d.url","d.source_id"]
            if include and "diff" in include:
                cols.append("dv.diff_text")
            rows = _exec(where, select_cols=cols, grouped=False)
    except Exception as e:
        # Fallback if dv.jurisdiction doesn't exist; use documents.jurisdiction
        if "dv.jurisdiction" in str(e) or "no such column" in str(e):
            where_fallback = [w.replace("dv.jurisdiction", "d.jurisdiction") for w in where]
            if group_by == "source":
                rows = _exec(where_fallback, grouped=True)
            else:
                cols = ["dv.id","dv.doc_id","dv.change_type","dv.fetched_at","d.title","d.url","d.source_id"]
                if include and "diff" in include:
                    cols.append("dv.diff_text")
                rows = _exec(where_fallback, select_cols=cols, grouped=False)
        else:
            raise

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

# -------------------------------
# /changes/export.csv (CSV)
# -------------------------------
@router.get("/changes/export.csv")
def export_changes_csv(
    jurisdiction: str = Query(..., min_length=2, max_length=2),
    since: Optional[date] = Query(None),
    limit: int = Query(25000, ge=1, le=25000),
):
    eng = get_engine()
    params = {"jur": jurisdiction.upper(), "limit": limit}
    where = ["dv.jurisdiction = :jur"]
    if since:
        where.append("dv.fetched_at >= :since")
        params["since"] = f"{since} 00:00:00"

    def _exec(sql_parts_where: list[str]):
        sql = f"""
        SELECT dv.id, dv.doc_id, dv.change_type, dv.fetched_at, d.title, d.url, d.source_id
        FROM document_versions dv
        JOIN documents d ON d.id = dv.doc_id
        WHERE {" AND ".join(sql_parts_where)}
        ORDER BY dv.fetched_at DESC
        LIMIT :limit
        """
        with eng.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params)]

    try:
        rows = _exec(where)
    except Exception as e:
        if "dv.jurisdiction" in str(e) or "no such column" in str(e):
            where_fallback = [w.replace("dv.jurisdiction", "d.jurisdiction") for w in where]
            rows = _exec(where_fallback)
        else:
            raise

    return Response(content=_rows_to_csv(rows), media_type="text/csv")
