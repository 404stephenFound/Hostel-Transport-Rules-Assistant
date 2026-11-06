import hashlib
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, DocumentChunk, AuditEvent
from app.schemas import DocumentCreate, DocumentResponse
from app.rag.chunker import chunk_document_text

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Document)
    if category:
        query = query.filter(Document.category == str(category))
    if status:
        query = query.filter(Document.status == str(status))
    return query.order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("", response_model=DocumentResponse, status_code=201)
def create_and_index_document(doc_in: DocumentCreate, db: Session = Depends(get_db)):
    if not doc_in.publication_date:
        logger.warning("Ingestion Warning: Uploaded document '%s' is missing publication_date metadata.", doc_in.title)
    if not doc_in.effective_from:
        logger.warning("Ingestion Warning: Uploaded document '%s' is missing effective_from metadata.", doc_in.title)

    f_hash = hashlib.sha256(doc_in.content.encode("utf-8")).hexdigest()
    
    # Check duplicate
    existing = db.query(Document).filter(Document.file_hash == f_hash).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Duplicate document content. Identical to '{existing.title}'.")

    doc = Document(
        title=doc_in.title,
        category=doc_in.category,
        issuing_department=doc_in.issuing_department,
        publication_date=doc_in.publication_date,
        effective_from=doc_in.effective_from,
        effective_until=doc_in.effective_until,
        status=doc_in.status,
        supersedes_document_id=doc_in.supersedes_document_id,
        version=doc_in.version,
        file_hash=f_hash,
        page_count=doc_in.content.count("[Page") or 1
    )
    db.add(doc)
    db.flush()

    # If this document supersedes an older one, mark the older one
    if doc_in.supersedes_document_id:
        older = db.query(Document).filter(Document.id == doc_in.supersedes_document_id).first()
        if older:
            older.status = "superseded"
            older.superseded_by_document_id = doc.id

    # Chunk and store
    chunks = chunk_document_text(doc_in.content, doc.id)
    for c in chunks:
        db.add(DocumentChunk(**c))

    # Audit log
    db.add(AuditEvent(
        action="PUBLISH",
        target_type="DOCUMENT",
        target_id=doc.id,
        details=f"Created and indexed document '{doc.title}' with {len(chunks)} chunks."
    ))

    db.commit()
    db.refresh(doc)
    return doc


@router.post("/{document_id}/supersede")
def mark_document_superseded(
    document_id: str,
    replacement_id: str,
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Target document not found")

    replacement = db.query(Document).filter(Document.id == replacement_id).first()
    if not replacement:
        raise HTTPException(status_code=404, detail="Replacement document not found")

    doc.status = "superseded"
    doc.superseded_by_document_id = replacement.id
    replacement.supersedes_document_id = doc.id

    db.add(AuditEvent(
        action="SUPERSEDE",
        target_type="DOCUMENT",
        target_id=doc.id,
        details=f"Document '{doc.title}' marked superseded by '{replacement.title}'."
    ))

    db.commit()
    return {"status": "success", "message": f"'{doc.title}' is now marked superseded by '{replacement.title}'."}


@router.post("/{document_id}/deactivate")
def deactivate_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "inactive"
    db.add(AuditEvent(
        action="DEACTIVATE",
        target_type="DOCUMENT",
        target_id=doc.id,
        details=f"Document '{doc.title}' marked inactive."
    ))
    db.commit()
    return {"status": "success", "message": f"'{doc.title}' has been deactivated."}
