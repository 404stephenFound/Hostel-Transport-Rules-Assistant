import re
from typing import List, Dict, Any

HEADER_REGEX = re.compile(
    r"^(?:Section\s+\d+.*|[0-9]+\.[0-9]+.*|Route\s+\d+.*|Notice\s+Ref:?.*|\#{1,3}\s+.*)",
    re.IGNORECASE
)
PAGE_REGEX = re.compile(r"\[Page\s+(\d+)\]", re.IGNORECASE)


def chunk_document_text(text: str, document_id: str, default_page: int = 1) -> List[Dict[str, Any]]:
    """
    Chunks institutional rule documents preserving:
    - Section headers (e.g. 'Section 1. Gate Pass Procedure', 'Route 4: South Campus')
    - Page references where indicated in text via [Page X]
    - Complete rule and policy sections together
    """
    chunks = []
    lines = text.split("\n")
    
    current_section = "General Information"
    current_page = default_page
    current_chunk_lines = []
    chunk_index = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for page markers
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
                        "chunk_index": chunk_index
                    })
                    chunk_index += 1
                current_chunk_lines = []
            current_section = stripped.lstrip("#").strip()
        elif current_len > 600 and current_chunk_lines:
            chunk_body = "\n".join(current_chunk_lines).strip()
            if chunk_body:
                chunks.append({
                    "document_id": document_id,
                    "text": chunk_body,
                    "page_number": current_page,
                    "section_name": current_section,
                    "chunk_index": chunk_index
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
                "chunk_index": chunk_index
            })

    return chunks
