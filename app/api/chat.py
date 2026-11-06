import json
import uuid
import time
import os
import datetime
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatSession, ChatMessage, AuditEvent
from app.schemas import ChatRequest, StructuredChatResponse
from app.rag.retriever import HybridRetriever
from app.rag.conflict_detector import analyze_retrieved_evidence
from app.llm.generator import RAGAnswerGenerator

router = APIRouter()
generator = RAGAnswerGenerator()

TRACES_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "request_traces.jsonl")


def log_request_trace_jsonl(record: dict):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(TRACES_FILE_PATH)), exist_ok=True)
        with open(TRACES_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as e:
        print(f"Warning: Failed to append to request_traces.jsonl: {e}")


@router.post("", response_model=StructuredChatResponse)
def submit_chat_query(req: ChatRequest, db: Session = Depends(get_db)) -> Any:
    start_time = time.time()

    # 1. Manage session
    session_id = req.session_id
    if not session_id:
        session = ChatSession(title=req.question[:60])
        db.add(session)
        db.flush()
        session_id = session.id
    else:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            session = ChatSession(id=session_id, title=req.question[:60])
            db.add(session)
            db.flush()

    # Save user message
    user_msg_id = str(uuid.uuid4())
    user_msg = ChatMessage(
        id=user_msg_id,
        session_id=session_id,
        role="user",
        content=req.question
    )
    db.add(user_msg)

    # 2. Hybrid Retrieval with Intent-Aware Clause Ranking
    retriever = HybridRetriever(db)
    retrieved_items = retriever.search(
        query=req.question,
        top_k=4,
        include_historical=req.include_historical
    )

    # 3. Analyze retrieved evidence for clause supersessions and conflicts
    chunks_with_docs = [(chunk, doc) for chunk, doc, _ in retrieved_items]
    analysis = analyze_retrieved_evidence(
        chunks_with_docs, 
        query=req.question, 
        today_date=req.today_date
    )

    # 4. Generate grounded structured response
    assistant_msg_id = str(uuid.uuid4())
    response = generator.generate_response(
        query=req.question,
        session_id=session_id,
        message_id=assistant_msg_id,
        retrieved_items=retrieved_items,
        analysis_metadata=analysis,
        today_date=req.today_date
    )

    latency_ms = round((time.time() - start_time) * 1000, 2)

    # 5. Format comprehensive debug trace object
    trace_record = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "query": req.question,
        "retrieved_chunk_ids_with_scores": [
            {
                "chunk_id": c.id,
                "doc_title": d.title,
                "section": c.section_name,
                "score": round(score, 3)
            }
            for c, d, score in retrieved_items
        ],
        "chosen_rule_clause": response.applies_to or "General institutional policy",
        "final_structured_output": response.model_dump(),
        "verification_result": {
            "status": "PASS" if not any("Fact-check" in c for c in response.caveats) else "FLAGGED",
            "reasons": response.caveats
        },
        "retry_count": 0,
        "latency_ms": latency_ms,
        "fallback_reason": None if response.sources else "unsupported_query_abstention"
    }

    # Log to JSON Lines file
    log_request_trace_jsonl(trace_record)

    # Save assistant message with full serialized JSON payload
    asst_msg = ChatMessage(
        id=assistant_msg_id,
        session_id=session_id,
        role="assistant",
        content=response.answer,
        structured_data=json.dumps(response.model_dump())
    )
    db.add(asst_msg)

    # Audit log entry with full debug trace JSON payload
    db.add(AuditEvent(
        action="QUERY_TRACE",
        target_type="CHAT",
        target_id=session_id,
        details=json.dumps(trace_record)
    ))

    db.commit()
    return response


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).order_by(ChatSession.created_at.desc()).limit(20).all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at} for s in sessions]


@router.get("/sessions/{session_id}")
def get_session_history(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "structured_data": json.loads(m.structured_data) if m.structured_data else None,
            "created_at": m.created_at
        }
        for m in messages
    ]
