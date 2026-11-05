import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class Citation(BaseModel):
    document_id: str
    document_title: str
    category: str
    issuing_department: str
    publication_date: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    status: str
    page_number: Optional[int] = None
    section_name: Optional[str] = None
    quoted_snippet: str


class WarningDetail(BaseModel):
    warning_type: str  # "SUPERSEDED_SOURCE", "OUTDATED_NOTICE", "CONFLICTING_SOURCES", "UNDATED_SOURCE", "EXPIRED_SOURCE"
    message: str
    document_id: Optional[str] = None


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    session_id: Optional[str] = None
    include_historical: bool = False


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    direct_answer: str
    conditions_and_exceptions: Optional[str] = None
    citations: List[Citation] = []
    warnings: List[WarningDetail] = []
    escalation_office: Optional[str] = None
    full_response: str


class DocumentCreate(BaseModel):
    title: str
    category: str
    issuing_department: str
    publication_date: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    status: str = "current"
    supersedes_document_id: Optional[str] = None
    version: str = "1.0"
    content: str


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    category: str
    issuing_department: str
    publication_date: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    status: str
    supersedes_document_id: Optional[str] = None
    superseded_by_document_id: Optional[str] = None
    version: str
    page_count: int
    created_at: datetime.datetime


class FeedbackRequest(BaseModel):
    message_id: str
    rating: int  # 1 or -1
    issue_category: Optional[str] = None
    comment: Optional[str] = None


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    target_type: str
    target_id: Optional[str]
    details: Optional[str]
    timestamp: datetime.datetime
