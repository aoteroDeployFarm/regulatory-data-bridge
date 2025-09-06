from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..schemas import AlertCreate, AlertOut
from ..db.session import get_db
from ..db.crud import create_alert, list_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("", response_model=list[AlertOut])
def get_alerts(active: bool | None = None, db: Session = Depends(get_db)):
    return list_alerts(db, active=active)

@router.post("", response_model=AlertOut)
def new_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    return create_alert(db, keyword=payload.keyword, jurisdiction=payload.jurisdiction, active=payload.active)
