import json
import uuid
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


@router.post("", response_model=StructuredChatResponse)
def submit_chat_query(req: ChatRequest, db: Session = Depends(get_db)) -> Any:
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
    analysis = analyze_retrieved_evidence(chunks_with_docs, query=req.question)

    # 4. Generate grounded structured response
    assistant_msg_id = str(uuid.uuid4())
    response = generator.generate_response(
        query=req.question,
        session_id=session_id,
        message_id=assistant_msg_id,
        retrieved_items=retrieved_items,
        analysis_metadata=analysis
    )

    # Save assistant message with full serialized JSON payload
    asst_msg = ChatMessage(
        id=assistant_msg_id,
        session_id=session_id,
        role="assistant",
        content=response.answer,
        structured_data=json.dumps(response.model_dump())
    )
    db.add(asst_msg)

    # Audit log
    db.add(AuditEvent(
        action="QUERY",
        target_type="CHAT",
        target_id=session_id,
        details=f"Query: '{req.question[:100]}', Retrieved: {len(retrieved_items)} chunks, Conflict: {response.conflict.exists}"
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
    return {
        "session_id": session.id,
        "title": session.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "structured_data": json.loads(m.structured_data) if m.structured_data else None,
                "created_at": m.created_at
            }
            for m in messages
        ]
    }
