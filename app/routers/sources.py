from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..schemas import SourceCreate, SourceOut
from ..db.session import get_db
from ..db import crud

router = APIRouter(prefix="/sources", tags=["sources"])

@router.get("", response_model=list[SourceOut])
def list_sources(active: bool | None = None, db: Session = Depends(get_db)):
    return crud.list_sources(db, active=active)

@router.post("", response_model=SourceOut)
def upsert_source(payload: SourceCreate, db: Session = Depends(get_db)):
    src = crud.upsert_source(
        db,
        name=payload.name,
        url=payload.url,
        jurisdiction=payload.jurisdiction,
        type_=payload.type,
        active=payload.active,
    )
    return src
