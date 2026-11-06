import json
from typing import List, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditEvent
from app.schemas import AuditEventResponse

router = APIRouter()


@router.get("", response_model=List[AuditEventResponse])
def get_audit_trail(db: Session = Depends(get_db)):
    return db.query(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(50).all()


@router.get("/traces")
def get_request_traces(db: Session = Depends(get_db)):
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.action == "QUERY_TRACE")
        .order_by(AuditEvent.timestamp.desc())
        .limit(30)
        .all()
    )
    traces = []
    for ev in events:
        try:
            parsed = json.loads(ev.details)
            parsed["audit_id"] = ev.id
            traces.append(parsed)
        except Exception:
            traces.append({
                "audit_id": ev.id,
                "timestamp": ev.timestamp.isoformat(),
                "query": "Unparseable trace",
                "details": ev.details
            })
    return traces
