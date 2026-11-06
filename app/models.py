import datetime
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)  # "Hostel Manual", "Hostel Circular", "Transport Timetable", "Transport Notice"
    issuing_department = Column(String(100), nullable=False)  # "Hostel Administration", "Transport Office"
    publication_date = Column(String(50), nullable=True)  # YYYY-MM-DD
    effective_from = Column(String(50), nullable=True)
    effective_until = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="CURRENT")  # "CURRENT", "PARTIALLY_SUPERSEDED", "SUPERSEDED", "EXPIRED", "UNDATED", "DRAFT"
    supersedes_document_id = Column(String(36), nullable=True)
    superseded_by_document_id = Column(String(36), nullable=True)
    superseded_sections = Column(Text, nullable=True)  # JSON-serialized list of superseded section names
    version = Column(String(50), default="1.0")
    file_hash = Column(String(64), nullable=True)
    storage_uri = Column(String(255), nullable=True)
    page_count = Column(Integer, default=1)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    page_number = Column(Integer, default=1)
    section_name = Column(String(150), nullable=True)
    chunk_index = Column(Integer, default=0)
    clause_status = Column(String(50), default="CURRENT")  # "CURRENT", "SUPERSEDED", "HISTORICAL"
    superseded_by_clause = Column(String(255), nullable=True)

    document = relationship("Document", back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), default="New Conversation")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)     # Direct answer text or summary
    structured_data = Column(Text, nullable=True) # Full structured JSON payload
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), nullable=False)
    rating = Column(Integer, nullable=False)  # 1 for positive, -1 for negative
    issue_category = Column(String(100), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
