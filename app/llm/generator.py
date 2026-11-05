import json
import re
from typing import List, Tuple, Dict, Any, Optional

from app.schemas import Citation, WarningDetail, ChatResponse
from app.models import Document, DocumentChunk
from app.llm.prompts import SYSTEM_PROMPT, ABSTENTION_MESSAGE


class RAGAnswerGenerator:
    """
    RAG Answer Generation Engine enforcing strict groundability:
    - Direct first-sentence response
    - Condition extraction
    - Traceable citations with publication/effective dates
    - Visible freshness/conflict warnings
    - Institutional office escalation
    """

    def generate_response(
        self,
        query: str,
        session_id: str,
        message_id: str,
        retrieved_items: List[Tuple[DocumentChunk, Document, float]],
        analysis_metadata: Dict[str, Any]
    ) -> ChatResponse:
        warnings: List[WarningDetail] = analysis_metadata.get("warnings", [])

        # 1. Abstention check: If no relevant evidence was found
        if not retrieved_items:
            return ChatResponse(
                session_id=session_id,
                message_id=message_id,
                direct_answer=ABSTENTION_MESSAGE,
                conditions_and_exceptions=None,
                citations=[],
                warnings=warnings,
                escalation_office="Hostel Administration / Transport Office",
                full_response=ABSTENTION_MESSAGE
            )

        # 2. Build citations list from top items
        citations: List[Citation] = []
        seen_chunk_ids = set()

        for chunk, doc, score in retrieved_items:
            if chunk.id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.id)

            snippet = chunk.text.strip().replace("\n", " ")
            if len(snippet) > 220:
                snippet = snippet[:220] + "..."

            citations.append(Citation(
                document_id=doc.id,
                document_title=doc.title,
                category=doc.category,
                issuing_department=doc.issuing_department,
                publication_date=doc.publication_date,
                effective_from=doc.effective_from,
                effective_until=doc.effective_until,
                status=doc.status,
                page_number=chunk.page_number,
                section_name=chunk.section_name,
                quoted_snippet=snippet
            ))

        # 3. Determine primary context and department
        primary_chunk, primary_doc, _ = retrieved_items[0]
        department = primary_doc.issuing_department
        escalation = (
            "Hostel Administration Office (Warden Desk / Ext. 102)"
            if "hostel" in department.lower() or "hostel" in query.lower()
            else "Transport Office (Fleet Coordinator / Ext. 204)"
        )

        # 4. Extract direct answer and conditions from top chunk
        text_lines = [l.strip() for l in primary_chunk.text.split("\n") if l.strip()]
        
        # Match question keywords to find the most relevant sentence for direct answer
        query_words = set(re.findall(r"\b\w{3,}\b", query.lower()))
        best_sentence = text_lines[0]
        best_overlap = 0

        sentences = re.split(r"(?<=[.!?])\s+", primary_chunk.text)
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            s_words = set(re.findall(r"\b\w{3,}\b", s_clean.lower()))
            overlap = len(query_words.intersection(s_words))
            if overlap > best_overlap:
                best_overlap = overlap
                best_sentence = s_clean

        direct_answer = best_sentence

        # Extract remaining points as conditions/exceptions
        condition_candidates = [
            s.strip() for s in sentences 
            if s.strip() and s.strip() != best_sentence and len(s.strip()) > 15
        ]
        conditions_text = "\n".join(f"• {c}" for c in condition_candidates[:3]) if condition_candidates else None

        # 5. Format full response according to PRD Section 4.9
        response_parts = [
            f"**Direct Answer:** {direct_answer}",
        ]

        if conditions_text:
            response_parts.append(f"\n**Conditions & Exceptions:**\n{conditions_text}")

        # Add Warnings if any
        if warnings:
            warning_bullets = "\n".join(f"⚠️ **{w.warning_type}:** {w.message}" for w in warnings)
            response_parts.append(f"\n**Important Notice / Freshness Warning:**\n{warning_bullets}")

        # Add Source Details
        source_bullets = []
        for c in citations[:2]:
            pub_info = f"Published: {c.publication_date}" if c.publication_date else "Undated Notice"
            eff_info = f" | Effective: {c.effective_from}" if c.effective_from else ""
            loc_info = f" (Section: {c.section_name}, Page {c.page_number})" if c.section_name else ""
            status_badge = f" [{c.status.upper()}]"
            source_bullets.append(f"• **{c.document_title}**{status_badge}: {pub_info}{eff_info}{loc_info}")

        response_parts.append("\n**Sources Cited:**\n" + "\n".join(source_bullets))
        response_parts.append(f"\n*For formal verification or special permissions, contact {escalation}.*")

        full_response = "\n".join(response_parts)

        return ChatResponse(
            session_id=session_id,
            message_id=message_id,
            direct_answer=direct_answer,
            conditions_and_exceptions=conditions_text,
            citations=citations,
            warnings=warnings,
            escalation_office=escalation,
            full_response=full_response
        )

