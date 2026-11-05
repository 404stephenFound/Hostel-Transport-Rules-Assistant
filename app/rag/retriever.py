import math
import re
from typing import List, Tuple, Dict, Any
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk

STOPWORDS = {
    "what", "is", "the", "for", "and", "does", "of", "in", "on", "at", 
    "to", "a", "an", "do", "how", "when", "where", "which", "are", "can",
    "i", "my", "any", "this", "that", "there", "it", "with"
}


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"\b[A-Za-z0-9_./:-]{2,}\b", text)]


class HybridRetriever:
    """
    Hybrid Retriever combining:
    1. Filtered Content Token & Entity Match
    2. BM25 / TF-IDF Term Weighting
    3. Category & Domain affinity (Hostel vs Transport)
    4. Term Coverage threshold to prevent single-keyword hallucinations
    5. Document metadata filtering (excluding superseded by default)
    """

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query: str,
        top_k: int = 4,
        include_historical: bool = False
    ) -> List[Tuple[DocumentChunk, Document, float]]:
        raw_tokens = tokenize(query)
        # Content tokens (exclude stopwords)
        query_tokens = [t for t in raw_tokens if t not in STOPWORDS]
        if not query_tokens:
            return []

        # Filter documents based on status
        doc_query = self.db.query(Document)
        if not include_historical:
            doc_query = doc_query.filter(Document.status.in_(["current", "undated", "expired"]))

        documents = {doc.id: doc for doc in doc_query.all()}
        if not documents:
            return []

        chunks = self.db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(documents.keys())).all()
        if not chunks:
            return []

        total_chunks = len(chunks)

        # Compute document frequencies
        df: Dict[str, int] = {}
        for c in chunks:
            seen_in_chunk = set(tokenize(c.text))
            for t in seen_in_chunk:
                df[t] = df.get(t, 0) + 1

        # Domain intent detection
        is_hostel_query = any(k in query.lower() for k in ["hostel", "room", "mess", "curfew", "roll call", "leave", "warden", "gate pass"])
        is_transport_query = any(k in query.lower() for k in ["bus", "route", "stop", "pickup", "transport", "departure", "timings", "timetable"])

        scored_chunks: List[Tuple[DocumentChunk, Document, float]] = []

        for chunk in chunks:
            doc = documents.get(chunk.document_id)
            if not doc:
                continue

            chunk_tokens = tokenize(chunk.text)
            chunk_token_set = set(chunk_tokens)
            
            # Check content overlap
            matched_content_tokens = [qt for qt in query_tokens if qt in chunk_token_set]
            if not matched_content_tokens:
                continue

            # Term coverage: require at least 35% of query content terms unless exact phrase matches
            matched_ratio = len(matched_content_tokens) / len(query_tokens)
            lower_chunk = chunk.text.lower()
            lower_query = query.lower()
            has_phrase_match = any(
                phrase in lower_chunk for phrase in ["route 1", "route 2", "route 3", "route 4", "lakeview colony", "8:30 pm", "9:30 pm"]
                if phrase in lower_query
            )

            if matched_ratio < 0.35 and not has_phrase_match:
                continue

            # BM25-style relevance calculation
            score = 0.0
            for qt in matched_content_tokens:
                doc_freq = df.get(qt, 1)
                idf = math.log((total_chunks - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                tf = chunk_tokens.count(qt)
                score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * (len(chunk_tokens) / 80.0)))

            if has_phrase_match:
                score += 8.0

            # Boost matches in section names
            if chunk.section_name:
                sec_lower = chunk.section_name.lower()
                for qt in query_tokens:
                    if qt in sec_lower:
                        score += 3.0

            # Category affinity boost
            if is_hostel_query and "hostel" in doc.category.lower():
                score *= 2.0
            elif is_transport_query and "transport" in doc.category.lower():
                score *= 2.0

            # Freshness weighting: boost current over expired/undated
            if doc.status == "current":
                score *= 1.2
            elif doc.status == "superseded":
                score *= 0.6

            if score >= 1.5:
                scored_chunks.append((chunk, doc, score))

        scored_chunks.sort(key=lambda x: x[2], reverse=True)
        return scored_chunks[:top_k]
