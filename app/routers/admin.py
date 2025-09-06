from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..services.ingest import run_ingest_once
from ..services.alerts import notify

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/ingest")
def ingest(db: Session = Depends(get_db)):
    run_ingest_once(db)
    return {"ok": True}

@router.post("/alerts/test")
def alerts_test(to: str, db: Session = Depends(get_db)):
    notify(db, to_addr=to)
    return {"ok": True, "sent_to": to}
