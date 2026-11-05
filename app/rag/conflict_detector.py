import datetime
import re
from typing import List, Dict, Any, Tuple
from app.schemas import WarningDetail


def parse_date(date_str: str | None) -> datetime.date | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def analyze_retrieved_evidence(chunks_with_docs: List[Tuple[Any, Any]]) -> Dict[str, Any]:
    """
    Analyzes retrieved chunks and their parent documents for:
    1. Superseded documents being cited
    2. Undated documents
    3. Expired documents based on effective_until or status
    4. Date conflicts across multiple active documents
    """
    warnings: List[WarningDetail] = []
    today = datetime.date.today()
    
    seen_docs = {}
    for chunk, doc in chunks_with_docs:
        seen_docs[doc.id] = doc

    # 1. Superseded & Expired checks
    for doc_id, doc in seen_docs.items():
        if doc.status == "superseded" or doc.superseded_by_document_id:
            warnings.append(WarningDetail(
                warning_type="SUPERSEDED_SOURCE",
                message=f"'{doc.title}' has been marked as superseded. A newer policy or circular applies.",
                document_id=doc.id
            ))
        elif doc.status == "expired":
            warnings.append(WarningDetail(
                warning_type="EXPIRED_SOURCE",
                message=f"'{doc.title}' is an expired temporary notice.",
                document_id=doc.id
            ))
        elif doc.effective_until:
            eff_until = parse_date(doc.effective_until)
            if eff_until and eff_until < today:
                warnings.append(WarningDetail(
                    warning_type="EXPIRED_SOURCE",
                    message=f"'{doc.title}' was effective only until {doc.effective_until}.",
                    document_id=doc.id
                ))

        # Check if another retrieved document supersedes this document
        if doc.supersedes_document_id and doc.supersedes_document_id in seen_docs:
            older_doc = seen_docs[doc.supersedes_document_id]
            warnings.append(WarningDetail(
                warning_type="SUPERSEDED_SOURCE",
                message=f"'{older_doc.title}' has been superseded by '{doc.title}'.",
                document_id=older_doc.id
            ))

        # 2. Undated check
        if not doc.publication_date:
            warnings.append(WarningDetail(
                warning_type="UNDATED_SOURCE",
                message=f"'{doc.title}' is an undated source — freshness cannot be verified.",
                document_id=doc.id
            ))

    # 3. Conflict Detection across differing active documents
    # Detect timing / rule clashes (e.g. 8:30 PM vs 9:30 PM)
    time_regex = re.compile(r"(\b\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)\b|\b\d{1,2}:\d{2}\s*(?:hrs|hours)?\b)")
    extracted_times = {}

    for chunk, doc in chunks_with_docs:
        times = time_regex.findall(chunk.text)
        if times:
            extracted_times.setdefault(doc.id, set()).update(times)

    if len(extracted_times) > 1:
        doc_ids = list(extracted_times.keys())
        first_doc_id = doc_ids[0]
        for other_doc_id in doc_ids[1:]:
            doc_a = seen_docs[first_doc_id]
            doc_b = seen_docs[other_doc_id]
            if extracted_times[first_doc_id] != extracted_times[other_doc_id]:
                date_a = parse_date(doc_a.publication_date)
                date_b = parse_date(doc_b.publication_date)
                if date_a and date_b and date_a != date_b:
                    newer_doc = doc_a if date_a > date_b else doc_b
                    older_doc = doc_b if date_a > date_b else doc_a
                    warnings.append(WarningDetail(
                        warning_type="CONFLICTING_SOURCES",
                        message=(
                            f"Discrepancy detected between '{older_doc.title}' ({older_doc.publication_date}) and "
                            f"newer '{newer_doc.title}' ({newer_doc.publication_date}). "
                            f"The newer circular indicates updated timings."
                        ),
                        document_id=newer_doc.id
                    ))

    return {
        "warnings": warnings,
        "is_safe_to_answer": len(chunks_with_docs) > 0,
        "active_documents": list(seen_docs.values())
    }
