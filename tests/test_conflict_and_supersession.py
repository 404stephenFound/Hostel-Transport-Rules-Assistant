import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.seed import seed_database
from app.rag.retriever import HybridRetriever
from app.rag.conflict_detector import analyze_retrieved_evidence
from app.llm.generator import RAGAnswerGenerator


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    seed_database(db)
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_superseded_and_conflict_detection(test_db):
    retriever = HybridRetriever(test_db)
    # Search for weekend curfew which is present in both Handbook (8:30 PM) and Circular 14/2026 (9:30 PM)
    results = retriever.search("What is the hostel gate closing time on weekends?", top_k=4, include_historical=True)
    chunks_with_docs = [(c, d) for c, d, _ in results]

    analysis = analyze_retrieved_evidence(chunks_with_docs)
    warnings = analysis["warnings"]
    warning_types = [w.warning_type for w in warnings]

    # Should detect conflict between circular and handbook
    assert "CONFLICTING_SOURCES" in warning_types or "SUPERSEDED_SOURCE" in warning_types


def test_expired_notice_detection(test_db):
    retriever = HybridRetriever(test_db)
    results = retriever.search("Extended evening bus service during winter exams 2024", top_k=2, include_historical=True)
    chunks_with_docs = [(c, d) for c, d, _ in results]

    analysis = analyze_retrieved_evidence(chunks_with_docs)
    warning_types = [w.warning_type for w in analysis["warnings"]]
    assert "EXPIRED_SOURCE" in warning_types


def test_undated_notice_detection(test_db):
    retriever = HybridRetriever(test_db)
    results = retriever.search("Gymnasium morning and evening hours", top_k=2)
    chunks_with_docs = [(c, d) for c, d, _ in results]

    analysis = analyze_retrieved_evidence(chunks_with_docs)
    warning_types = [w.warning_type for w in analysis["warnings"]]
    assert "UNDATED_SOURCE" in warning_types


def test_abstention_on_unsupported_query(test_db):
    generator = RAGAnswerGenerator()
    retriever = HybridRetriever(test_db)
    
    # Query completely absent from institutional documents
    results = retriever.search("What is the parking fee for personal flying helicopters?", top_k=3)
    chunks_with_docs = [(c, d) for c, d, _ in results]
    analysis = analyze_retrieved_evidence(chunks_with_docs)

    res = generator.generate_response(
        query="What is the parking fee for personal flying helicopters?",
        session_id="test-session",
        message_id="test-msg",
        retrieved_items=results,
        analysis_metadata=analysis
    )

    assert "I could not find this rule" in res.direct_answer
    assert len(res.citations) == 0

