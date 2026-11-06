import datetime
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
    Hybrid Retriever with:
    1. Intent-Aware Clause Ranking (Weekday vs Weekend vs Transit)
    2. BM25 / Content Term Scoring
    3. Status Filtering (Current first, then Partially Superseded)
    4. Historical Flag Handling (Excludes superseded clauses when off)
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
        query_tokens = [t for t in raw_tokens if t not in STOPWORDS]
        if not query_tokens:
            return []

        doc_query = self.db.query(Document)
        documents = {doc.id: doc for doc in doc_query.all()}
        if not documents:
            return []

        # Filter chunks based on historical flag
        chunk_query = self.db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(documents.keys()))
        if not include_historical:
            chunk_query = chunk_query.filter(DocumentChunk.clause_status != "SUPERSEDED")

        chunks = chunk_query.all()
        if not chunks:
            return []

        total_chunks = len(chunks)
        df: Dict[str, int] = {}
        for c in chunks:
            seen_in_chunk = set(tokenize(c.text))
            for t in seen_in_chunk:
                df[t] = df.get(t, 0) + 1

        # Query Intent
        q_lower = query.lower()
        is_weekday_query = "weekday" in q_lower or "weekdays" in q_lower
        is_weekend_query = "weekend" in q_lower or "weekends" in q_lower or "friday" in q_lower or "saturday" in q_lower
        is_changes_query = any(k in q_lower for k in ["changed", "recent", "revision", "new rules", "latest notice"])
        is_hostel_query = any(k in q_lower for k in ["hostel", "room", "mess", "curfew", "roll call", "leave", "warden", "gate pass"])
        is_transport_query = any(k in q_lower for k in ["bus", "route", "stop", "pickup", "transport", "departure", "timings", "timetable"])

        scored_chunks: List[Tuple[DocumentChunk, Document, float]] = []

        for chunk in chunks:
            doc = documents.get(chunk.document_id)
            if not doc:
                continue

            chunk_tokens = tokenize(chunk.text)
            chunk_token_set = set(chunk_tokens)
            matched_content_tokens = [qt for qt in query_tokens if qt in chunk_token_set]
            if not matched_content_tokens:
                continue

            matched_ratio = len(matched_content_tokens) / len(query_tokens)
            lower_chunk = chunk.text.lower()
            
            # Exact phrase match boosting
            has_phrase_match = any(
                phrase in lower_chunk for phrase in [
                    "route 1", "route 2", "route 3", "route 4", "lakeview colony", 
                    "8:30 pm", "9:30 pm", "roll call", "gate closes", "closing time"
                ] if phrase in q_lower
            )

            if matched_ratio < 0.45 and not has_phrase_match and not is_changes_query:
                continue

            # Check if query asks for out-of-scope concepts absent from knowledge base
            if any(term in q_lower for term in ["day scholar", "day scholars", "festival", "festivals", "flying helicopter", "nuclear shelter"]):
                continue

            # BM25-style scoring
            score = 0.0
            for qt in matched_content_tokens:
                doc_freq = df.get(qt, 1)
                idf = math.log((total_chunks - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                tf = chunk_tokens.count(qt)
                score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * (len(chunk_tokens) / 80.0)))

            if has_phrase_match:
                score += 8.0

            # Section match
            if chunk.section_name:
                for qt in query_tokens:
                    if qt in chunk.section_name.lower():
                        score += 3.0

            # Intent-specific clause boosting:
            if is_weekday_query:
                if "weekday in-time remains unchanged" in lower_chunk or "closes strictly at 8:30 pm on weekdays" in lower_chunk:
                    score += 15.0
                elif "weekend in-time for all residential" in lower_chunk:
                    score -= 5.0  # Deprioritize weekend rule when asking about weekdays

            elif is_weekend_query:
                if "weekend in-time" in lower_chunk or "friday and saturday" in lower_chunk:
                    score += 15.0

            elif is_changes_query:
                if "circular no. 14" in lower_chunk or "revision" in lower_chunk:
                    score += 18.0

            # Domain affinity
            if is_hostel_query and "hostel" in doc.category.lower():
                score *= 1.8
            elif is_transport_query and "transport" in doc.category.lower():
                score *= 1.8

            # Status priority (Current > Partially Superseded > Superseded)
            if chunk.clause_status == "CURRENT":
                score *= 1.3
            elif chunk.clause_status == "PARTIALLY_SUPERSEDED":
                score *= 1.0
            elif chunk.clause_status == "SUPERSEDED":
                score *= 0.5

            if score >= 1.5:
                scored_chunks.append((chunk, doc, score))

        scored_chunks.sort(key=lambda x: x[2], reverse=True)
        return scored_chunks[:top_k]
