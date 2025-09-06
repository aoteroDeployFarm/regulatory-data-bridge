from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..schemas import DocumentOut
from ..db.session import get_db
from ..db.crud import search_documents

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("", response_model=list[DocumentOut])
def list_documents(
    q: str | None = None,
    jurisdiction: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return search_documents(
        db,
        q=q,
        jurisdiction=jurisdiction,
        date_from=date_from,
        date_to=date_to,
        limit=min(limit, 200),
        offset=offset,
    )
