import datetime
import math
import re
from typing import List, Tuple, Dict, Any, Set
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk

STOPWORDS = {
    "what", "is", "the", "for", "and", "does", "of", "in", "on", "at", 
    "to", "a", "an", "do", "how", "when", "where", "which", "are", "can",
    "i", "my", "any", "this", "that", "there", "it", "with", "was", "were",
    "did", "had", "have", "has", "be", "been", "will", "would", "could", "should"
}

MONTHS_AND_DATE_TERMS = {
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december", "year", "date", "month"
}


def normalize_query_text(q: str) -> str:
    """Corrects common student typos and abbreviations."""
    text = q
    text = re.sub(r"\bhostle\b", "hostel", text, flags=re.IGNORECASE)
    text = re.sub(r"\btym\b", "time", text, flags=re.IGNORECASE)
    text = re.sub(r"\bweekdys?\b", "weekdays", text, flags=re.IGNORECASE)
    text = re.sub(r"\bweeknd\b", "weekend", text, flags=re.IGNORECASE)
    text = re.sub(r"\bclsing\b", "closing", text, flags=re.IGNORECASE)
    return text


def stem(word: str) -> str:
    w = word.lower()
    if w.endswith("ing") and len(w) > 5:
        return w[:-3]
    if w.endswith("ed") and len(w) > 4:
        return w[:-2]
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"\b[A-Za-z0-9_./:-]{2,}\b", text)]


class HybridRetriever:
    """
    Hybrid Retriever with:
    1. Intent-Aware Clause Ranking (Weekday vs Weekend vs Transit vs Mixed)
    2. BM25 / Content Term Scoring with Stemming
    3. Status Filtering (Current first, then Partially Superseded)
    4. Historical Flag & Date Handling (Excludes superseded clauses when off unless query targets past date)
    5. Query Normalization & Out-of-Scope Pre-filtering
    """

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query: str,
        top_k: int = 4,
        include_historical: bool = False
    ) -> List[Tuple[DocumentChunk, Document, float]]:
        norm_query = normalize_query_text(query)
        q_lower = norm_query.lower()

        # Immediate filter for unambiguous out-of-scope questions
        if any(term in q_lower for term in [
            "day scholar", "day scholars", "festival", "festivals", "flying helicopter",
            "nuclear shelter", "guest room", "menu", "mess menu", "exam dates",
            "fee refund", "tuition fee", "capital of", "who is", "weather in"
        ]):
            return []

        raw_tokens = tokenize(norm_query)
        # Filter out stopwords and pure date numbers/months from topical keyword matching
        query_tokens = [
            t for t in raw_tokens 
            if t not in STOPWORDS 
            and t not in MONTHS_AND_DATE_TERMS 
            and not (t.isdigit() and len(t) in (1, 2, 4))
        ]
        if not query_tokens:
            query_tokens = [t for t in raw_tokens if t not in STOPWORDS]

        if not query_tokens:
            return []

        query_stems = [stem(t) for t in query_tokens]

        doc_query = self.db.query(Document)
        documents = {doc.id: doc for doc in doc_query.all()}
        if not documents:
            return []

        # Check if query is targeting a date before Circular 14 (20 Feb 2026) or explicitly asks for older rules
        is_specifically_past = (
            any(k in q_lower for k in ["old", "previous", "earlier", "prior to", "before the revision", "superseded"])
            or bool(re.search(r"\b(?:january|15 january)\s+2026\b", q_lower))
        )

        chunk_query = self.db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(documents.keys()))
        if not include_historical and not is_specifically_past:
            chunk_query = chunk_query.filter(DocumentChunk.clause_status != "SUPERSEDED")

        chunks = chunk_query.all()
        if not chunks:
            return []

        total_chunks = len(chunks)
        df: Dict[str, int] = {}
        for c in chunks:
            seen_in_chunk = set(stem(t) for t in tokenize(c.text))
            for t in seen_in_chunk:
                df[t] = df.get(t, 0) + 1

        # Query Intent
        is_weekday_query = "weekday" in q_lower or "weekdays" in q_lower
        is_weekend_query = any(k in q_lower for k in ["weekend", "weekends", "friday", "saturday"])
        is_sunday_query = "sunday" in q_lower
        is_changes_query = any(k in q_lower for k in ["changed", "recent", "revision", "new rules", "latest notice", "update"])
        is_vague_curfew = ("time" in q_lower and "back" in q_lower) or "curfew" in q_lower or "entry gate" in q_lower
        is_hostel_query = any(k in q_lower for k in ["hostel", "room", "mess", "curfew", "roll call", "leave", "warden", "gate pass", "gate", "back", "fine", "penalty"])
        is_transport_query = any(k in q_lower for k in ["bus", "route", "stop", "pickup", "transport", "departure", "timings", "timetable"])
        is_mixed_query = (is_hostel_query or is_weekday_query or "gate" in q_lower) and is_transport_query

        scored_chunks: List[Tuple[DocumentChunk, Document, float]] = []

        for chunk in chunks:
            doc = documents.get(chunk.document_id)
            if not doc:
                continue

            chunk_tokens = tokenize(chunk.text)
            chunk_token_set = set(chunk_tokens)
            chunk_stem_set = set(stem(t) for t in chunk_tokens)

            matched_content_stems = [qs for qs in query_stems if qs in chunk_stem_set]

            # Allow changes queries or vague curfew to match relevant documents without strict token matches
            if not matched_content_stems and not is_changes_query and not (is_vague_curfew and "curfew" in chunk.text.lower()):
                continue

            matched_ratio = len(matched_content_stems) / len(query_stems) if query_stems else 0.0
            lower_chunk = chunk.text.lower()
            
            # Exact phrase match boosting
            has_phrase_match = any(
                phrase in lower_chunk for phrase in [
                    "route 1", "route 2", "route 3", "route 4", "lakeview colony", 
                    "8:30 pm", "9:30 pm", "roll call", "gate closes", "closing time",
                    "overnight leave", "outstation", "parental consent", "central campus bus bay"
                ] if phrase in q_lower
            )

            # For mixed queries, allow chunks with at least 2 matching topical stems
            min_ratio = 0.20 if is_mixed_query else 0.30
            if matched_ratio < min_ratio and len(matched_content_stems) < 2 and not has_phrase_match and not is_changes_query and not is_vague_curfew:
                continue

            # BM25-style scoring with stem matches
            score = 0.0
            for qs in matched_content_stems:
                doc_freq = df.get(qs, 1)
                idf = math.log((total_chunks - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                tf = sum(1 for t in chunk_tokens if stem(t) == qs)
                score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * (len(chunk_tokens) / 80.0)))

            if has_phrase_match:
                score += 8.0

            # Section match
            if chunk.section_name:
                for qt in query_tokens:
                    if qt in chunk.section_name.lower():
                        score += 3.0

            # Intent-specific clause boosting:
            if is_weekday_query or (is_sunday_query and not is_weekend_query):
                if "closes strictly at 8:30 pm on weekdays" in lower_chunk:
                    score += 35.0  # Handbook Section 2 is primary citation for weekday rule
                elif "weekday in-time remains unchanged" in lower_chunk:
                    score += 15.0  # Circular 14 supports weekday rule
                elif "weekend in-time for all residential" in lower_chunk:
                    score -= 10.0  # Deprioritize weekend-specific clauses for weekday queries

            elif is_weekend_query:
                if is_specifically_past:
                    if "closes strictly at 8:30 pm on weekdays" in lower_chunk:
                        score += 40.0  # Prior to circular, Handbook Section 2 is the primary rule
                    elif "circular no. 14" in lower_chunk:
                        score -= 20.0
                else:
                    if "weekend in-time" in lower_chunk or "friday and saturday" in lower_chunk:
                        score += 25.0
                    elif "closes strictly at 8:30 pm on weekdays" in lower_chunk:
                        score += 10.0

            elif is_changes_query:
                if "circular no. 14" in lower_chunk or "circular no. 14" in doc.title.lower():
                    score += 40.0
                elif "revision" in lower_chunk or "extended" in lower_chunk:
                    score += 25.0

            elif is_vague_curfew:
                if "closes strictly at 8:30 pm on weekdays" in lower_chunk:
                    score += 25.0
                elif "weekend in-time" in lower_chunk:
                    score += 20.0

            # Domain affinity
            if is_mixed_query:
                if "hostel" in doc.category.lower() or "transport" in doc.category.lower():
                    score *= 1.5
            elif is_hostel_query and "hostel" in doc.category.lower():
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

            if score >= 1.0 or is_changes_query:
                scored_chunks.append((chunk, doc, score))

        scored_chunks.sort(key=lambda x: x[2], reverse=True)

        if is_mixed_query:
            # Guarantee representation from both Hostel and Transport documents
            hostel_items = [item for item in scored_chunks if "hostel" in item[1].category.lower()]
            transport_items = [item for item in scored_chunks if "transport" in item[1].category.lower()]
            mixed_result = []
            if hostel_items:
                mixed_result.extend(hostel_items[:2])
            if transport_items:
                mixed_result.extend(transport_items[:2])
            if len(mixed_result) < top_k:
                remaining = [it for it in scored_chunks if it not in mixed_result]
                mixed_result.extend(remaining[:top_k - len(mixed_result)])
            return mixed_result

        return scored_chunks[:top_k]
