from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Feedback, AuditEvent
from app.schemas import FeedbackRequest

router = APIRouter()


@router.post("")
def submit_feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    fb = Feedback(
        message_id=req.message_id,
        rating=req.rating,
        issue_category=req.issue_category,
        comment=req.comment
    )
    db.add(fb)
    db.add(AuditEvent(
        action="FEEDBACK",
        target_type="CHAT_MESSAGE",
        target_id=req.message_id,
        details=f"Rating: {req.rating}, Category: {req.issue_category}"
    ))
    db.commit()
    return {"status": "success", "message": "Feedback recorded"}
