import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.seed import seed_database
from app.rag.chunker import chunk_document_text
from app.rag.retriever import HybridRetriever


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


def test_chunk_document_text():
    sample_text = """[Page 1]
Section 1. Gate Pass Procedure
Students must apply for a gate pass 24 hours prior to travel.
Section 2. Return Timings
Gate closes at 8:30 PM on weekdays."""
    chunks = chunk_document_text(sample_text, "doc-test-1")
    assert len(chunks) >= 2
    assert chunks[0]["page_number"] == 1
    assert "Gate Pass Procedure" in chunks[0]["section_name"]
    assert "Return Timings" in chunks[1]["section_name"]


def test_hybrid_retriever_hostel_curfew(test_db):
    retriever = HybridRetriever(test_db)
    results = retriever.search("What time does the hostel main gate close on weekdays?", top_k=3)
    assert len(results) > 0
    top_chunk, top_doc, score = results[0]
    assert "8:30 PM" in top_chunk.text
    assert "Hostel" in top_doc.title


def test_hybrid_retriever_bus_route(test_db):
    retriever = HybridRetriever(test_db)
    results = retriever.search("Which bus goes to Lakeview Colony and what is the morning time?", top_k=3)
    assert len(results) > 0
    top_chunk, top_doc, score = results[0]
    assert "Route 4" in top_chunk.text or "Lakeview Colony" in top_chunk.text
    assert "Transport" in top_doc.title

