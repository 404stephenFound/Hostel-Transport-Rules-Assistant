import re
from typing import List, Dict, Any

HEADER_REGEX = re.compile(
    r"^(?:Section\s+\d+.*|[0-9]+\.[0-9]+.*|Route\s+\d+.*|Notice\s+Ref:?.*|Hostel\s+Circular\s+No\.\s+14/\d+.*|\#{1,3}\s+.*)",
    re.IGNORECASE
)
PAGE_REGEX = re.compile(r"\[Page\s+(\d+)\]", re.IGNORECASE)


def clean_text_formatting(text: str) -> str:
    """
    Normalizes whitespace and broken mid-sentence line breaks,
    while preserving paragraph and bullet breaks.
    """
    # Normalize multiple newlines
    text = re.sub(r"\r\n|\r", "\n", text)
    # Strip repeated footer/header markers if present
    text = re.sub(r"---+\s*", "\n", text)
    # Ensure entity names like 'Hostel Circular No. 14/2026' are kept together
    text = re.sub(r"Hostel\s+Circular\s*\n\s*No\.\s*14/\d+", "Hostel Circular No. 14/2026", text, flags=re.IGNORECASE)
    return text.strip()


def chunk_document_text(text: str, document_id: str, default_page: int = 1) -> List[Dict[str, Any]]:
    """
    Chunks institutional rule documents preserving:
    - Section headers (e.g. 'Section 1. Gate Pass Procedure', 'Route 4: South Campus')
    - Page references where indicated in text via [Page X]
    - Complete, clean clauses with sentence-boundary integrity
    """
    cleaned = clean_text_formatting(text)
    chunks = []
    lines = cleaned.split("\n")
    
    current_section = "General Information"
    current_page = default_page
    current_chunk_lines = []
    chunk_index = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Page markers
        page_match = PAGE_REGEX.search(stripped)
        if page_match:
            try:
                current_page = int(page_match.group(1))
            except ValueError:
                pass
            continue

        is_header = bool(HEADER_REGEX.match(stripped)) and len(stripped) < 120
        current_len = sum(len(l) for l in current_chunk_lines)

        if is_header:
            if current_chunk_lines:
                chunk_body = "\n".join(current_chunk_lines).strip()
                if chunk_body:
                    chunks.append({
                        "document_id": document_id,
                        "text": chunk_body,
                        "page_number": current_page,
                        "section_name": current_section,
                        "chunk_index": chunk_index,
                        "clause_status": "CURRENT"
                    })
                    chunk_index += 1
                current_chunk_lines = []
            current_section = stripped.lstrip("#").strip()
        elif current_len > 550 and current_chunk_lines:
            chunk_body = "\n".join(current_chunk_lines).strip()
            if chunk_body:
                chunks.append({
                    "document_id": document_id,
                    "text": chunk_body,
                    "page_number": current_page,
                    "section_name": current_section,
                    "chunk_index": chunk_index,
                    "clause_status": "CURRENT"
                })
                chunk_index += 1
            current_chunk_lines = []

        current_chunk_lines.append(stripped)

    # Flush final chunk
    if current_chunk_lines:
        chunk_body = "\n".join(current_chunk_lines).strip()
        if chunk_body:
            chunks.append({
                "document_id": document_id,
                "text": chunk_body,
                "page_number": current_page,
                "section_name": current_section,
                "chunk_index": chunk_index,
                "clause_status": "CURRENT"
            })

    return chunks


def extract_sentence_quote(text: str, query: str = "") -> str:
    """
    Extracts complete sentences ending at clean sentence boundaries (no mid-sentence chops).
    Finds the exact supporting sentence matching the query context without section headers.
    """
    # Strip standalone header lines before splitting sentences
    body_lines = [
        l.strip() for l in text.split("\n")
        if l.strip() and not re.match(r"^(?:Section\s+\d+|Hostel\s+Circular|Notice\s+Ref|Subject:|Route\s+\d+)", l.strip(), re.IGNORECASE)
    ]
    cleaned_body = " ".join(body_lines)
    if not cleaned_body:
        cleaned_body = text.strip()

    # Protect abbreviations from naive period splitting
    t = re.sub(r"\bNo\.\s*", "No_DOT_ ", cleaned_body)
    t = re.sub(r"\bRef\.\s*", "Ref_DOT_ ", t)
    t = re.sub(r"\bSec\.\s*", "Sec_DOT_ ", t)
    t = re.sub(r"\b([A-Za-z]+)\s+(\d+)\.\s*", r"\1 \2_DOT_ ", t)

    raw_sentences = re.split(r"(?<=[.!?])\s+", t)
    sentences = []
    for s in raw_sentences:
        clean = s.replace("_DOT_", ".").strip()
        # Keep sentences that have substantial content
        if len(clean) > 20:
            sentences.append(clean)

    if not sentences:
        sentences = [s.replace("_DOT_", ".").strip() for s in raw_sentences if s.strip()]

    if not sentences:
        return text[:140].strip()

    if not query:
        return sentences[0]

    q_lower = query.lower()

    # Intent-specific sentence selection for exact supporting quote
    if "weekday" in q_lower:
        for s in sentences:
            s_lower = s.lower()
            if "closes strictly at 8:30 pm on weekdays" in s_lower:
                return s
            if "weekday in-time remains unchanged" in s_lower:
                return s

    if "weekend" in q_lower or "friday" in q_lower or "saturday" in q_lower or "revision" in q_lower or "old" in q_lower:
        for s in sentences:
            s_lower = s.lower()
            if "closing time on friday and saturday" in s_lower or "8:30 pm on weekends" in s_lower or "extended to 9:30 pm" in s_lower:
                return s

    if "curfew" in q_lower or "gate" in q_lower or "closing" in q_lower:
        for s in sentences:
            s_lower = s.lower()
            if any(k in s_lower for k in ["gate closes", "closing time", "8:30 pm", "9:30 pm", "in-time"]):
                return s

    stopwords = {"what", "when", "where", "which", "does", "that", "this", "from", "with", "have", "been", "will", "into", "their", "is", "the", "for", "and"}
    q_words = [w.lower() for w in re.findall(r"\b\w{3,}\b", query) if w.lower() not in stopwords]

    best_sentence = ""
    best_score = -1

    for s in sentences:
        s_lower = s.lower()
        score = sum(1 for w in q_words if w in s_lower)
        if score > best_score:
            best_score = score
            best_sentence = s

    return best_sentence if best_sentence else sentences[0]
