import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.seed import seed_database
from app.main import health_check
from app.api.chat import submit_chat_query, list_sessions
from app.api.documents import list_documents, create_and_index_document
from app.api.feedback import submit_feedback
from app.schemas import ChatRequest, DocumentCreate, FeedbackRequest

# In-memory test DB
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture
def test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    seed_database(db)
    yield db
    db.close()
    Base.metadata.drop_all(bind=test_engine)


def test_health_check_endpoint():
    res = health_check()
    assert res["status"] == "healthy"
    assert "Hostel & Transport" in res["service"]


def test_student_chat_query_endpoint(test_db):
    req = ChatRequest(question="What time does the hostel main gate close on weekdays?")
    res = submit_chat_query(req, db=test_db)
    
    assert res.session_id is not None
    assert "8:30 PM" in res.answer
    assert res.applies_to is not None
    assert "Weekdays" in res.applies_to
    assert len(res.sources) >= 1
    assert res.sources[0].doc_title is not None
    assert "Hostel" in res.escalation_office
    # Ensure day range caveat is attached
    assert any("discrepancy" in c.lower() or "sunday" in c.lower() for c in res.caveats)


def test_student_chat_unsupported_abstains_endpoint(test_db):
    req = ChatRequest(question="What is the secret password for the underground nuclear shelter?")
    res = submit_chat_query(req, db=test_db)
    
    assert "I could not find this rule" in res.answer
    assert len(res.sources) == 0


def test_document_listing_and_creation_endpoints(test_db):
    # Test listing seeded documents
    docs = list_documents(db=test_db)
    assert len(docs) >= 4
    handbook = next(d for d in docs if "Handbook" in d.title)
    assert handbook.status == "PARTIALLY_SUPERSEDED"
    assert handbook.superseded_sections is not None

    # Test creating a new document
    new_doc_data = DocumentCreate(
        title="Circular No. 20/2026: Campus Library Extended Hours",
        category="Hostel Notice",
        issuing_department="Hostel Administration",
        publication_date="2026-03-01",
        effective_from="2026-03-05",
        status="current",
        content="[Page 1]\nLibrary study hall remains open until 11:00 PM for all hostel residents."
    )
    created = create_and_index_document(new_doc_data, db=test_db)
    assert created.id is not None
    assert created.title == new_doc_data.title

    # Verify updated list count
    updated_docs = list_documents(db=test_db)
    assert len(updated_docs) == len(docs) + 1


def test_feedback_endpoint(test_db):
    chat_req = ChatRequest(question="When does Route 1 bus leave campus?")
    chat_res = submit_chat_query(chat_req, db=test_db)

    fb_req = FeedbackRequest(
        message_id=chat_res.message_id,
        rating=1,
        issue_category="Accurate & timely",
        comment="Provided exact departure time from Central Campus."
    )
    fb_res = submit_feedback(fb_req, db=test_db)
    assert fb_res["status"] == "success"
