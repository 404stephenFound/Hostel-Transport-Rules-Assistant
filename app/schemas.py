import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SourceItem(BaseModel):
    doc_id: str
    doc_title: str
    section: Optional[str] = "General"
    page: Optional[int] = 1
    quote: str
    status: str
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None

    @property
    def document_title(self) -> str:
        return self.doc_title

    @property
    def section_name(self) -> Optional[str]:
        return self.section

    @property
    def page_number(self) -> Optional[int]:
        return self.page

    @property
    def exact_quote(self) -> str:
        return self.quote


class WarningDetail(BaseModel):
    warning_type: str
    message: str
    document_id: Optional[str] = None
    details: Optional[str] = None


class CitationItem(BaseModel):
    document_id: str
    document_title: str
    section_name: Optional[str] = "General"
    page_number: Optional[int] = 1
    exact_quote: str
    status: str


class ConflictInfo(BaseModel):
    exists: bool = False
    resolved_rule: Optional[str] = None
    older_rule: Optional[str] = None
    notice: Optional[str] = None


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    session_id: Optional[str] = None
    include_historical: bool = False


class StructuredChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    applies_to: Optional[str] = None
    effective_date: Optional[str] = None
    caveats: List[str] = []
    rule_summary: List[str] = []
    sources: List[SourceItem] = []
    conflict: ConflictInfo = ConflictInfo()
    escalation_office: str = "Hostel Administration Office (Warden Desk / Ext. 102)"
    full_response: str = ""

    @property
    def direct_answer(self) -> str:
        return self.answer

    @property
    def citations(self) -> List[SourceItem]:
        return self.sources


# Backward compatible alias
ChatResponse = StructuredChatResponse


class DocumentCreate(BaseModel):
    title: str
    category: str
    issuing_department: str
    publication_date: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    status: str = "CURRENT"
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
    superseded_sections: Optional[str] = None
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
