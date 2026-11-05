from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditEvent
from app.schemas import AuditEventResponse

router = APIRouter()


@router.get("", response_model=List[AuditEventResponse])
def get_audit_trail(db: Session = Depends(get_db)):
    return db.query(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(50).all()
