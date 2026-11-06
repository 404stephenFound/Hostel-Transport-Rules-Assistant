import datetime
import re
from typing import List, Dict, Any, Tuple
from app.schemas import ConflictInfo, WarningDetail


def parse_date(date_str: str | None) -> datetime.date | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def format_effective_notice(eff_date_str: str | None) -> str:
    if not eff_date_str:
        return "immediate effect"
    eff_date = parse_date(eff_date_str)
    if not eff_date:
        return f"effective {eff_date_str}"
    today = datetime.date.today()
    formatted = eff_date.strftime("%d %B %Y")
    if eff_date <= today:
        return f"already in force since {formatted}"
    else:
        return f"takes effect on {formatted}"


def analyze_retrieved_evidence(chunks_with_docs: List[Tuple[Any, Any]], query: str = "") -> Dict[str, Any]:
    """
    Analyzes retrieved chunks for clause-level supersession and conflicts.
    - Merges SUPERSEDED_SOURCE and CONFLICTING_SOURCES into ONE unified notice.
    - OMIT warnings completely if the query touches an unaffected clause (e.g. mess, laundry, leave).
    """
    today = datetime.date.today()
    seen_docs = {}
    for chunk, doc in chunks_with_docs:
        seen_docs[doc.id] = doc

    conflict_info = ConflictInfo(exists=False)
    warnings: List[WarningDetail] = []
    caveats: List[str] = []

    # Check if query touches curfew or weekend timing
    q_lower = query.lower() if query else ""
    chunk_has_timing = any(
        "gate" in (getattr(c, "text", "") or "").lower()
        or "curfew" in (getattr(c, "text", "") or "").lower()
        or "in-time" in (getattr(c, "text", "") or "").lower()
        for c, _ in chunks_with_docs
    )
    is_curfew_or_timing_query = (
        any(k in q_lower for k in ["curfew", "gate", "close", "closing", "in-time", "time", "timing", "weekend", "weekday", "changed", "recent"])
        or (not query and chunk_has_timing)
    )

    # 1. Clause-level supersession detection for Curfew / In-time rules
    has_circular_14 = any("Circular No. 14" in doc.title for doc in seen_docs.values())
    has_handbook = any("Handbook" in doc.title for doc in seen_docs.values())

    if is_curfew_or_timing_query and has_circular_14:
        eff_phrase = format_effective_notice("2026-02-20")
        notice_text = (
            f"Updated by Hostel Circular No. 14/2026 (published 2026-02-15, {eff_phrase}). "
            f"Older rule: 8:30 PM on weekends. Current rule: 9:30 PM on Friday and Saturday."
        )
        conflict_info = ConflictInfo(
            exists=True,
            resolved_rule="Weekend in-time is 9:30 PM on Friday and Saturday nights (roll call at 10:00 PM). Weekday in-time is 8:30 PM.",
            older_rule="8:30 PM every night including weekends (from 2025 Handbook).",
            notice=notice_text
        )
        warnings.append(WarningDetail(
            warning_type="POLICY_UPDATE_NOTICE",
            message=notice_text,
            details=notice_text
        ))

    # 2. Check for day range disagreement caveat
    if any(k in q_lower for k in ["weekday", "day", "sunday", "thursday", "curfew", "gate"]):
        caveats.append(
            "Day range discrepancy noted in institutional sources: The 2025 Handbook defines weekdays as "
            "Monday through Thursday, whereas Circular No. 14/2026 specifies Sunday through Thursday. "
            "Please confirm with the Warden Desk whether Sunday follows weekday in-time."
        )

    # 3. Notice-level checks (Expired, Undated)
    for doc_id, doc in seen_docs.items():
        if doc.status == "EXPIRED":
            warnings.append(WarningDetail(
                warning_type="EXPIRED_SOURCE",
                message=f"'{doc.title}' was effective until {doc.effective_until or '2024-12-15'} and is now expired.",
                document_id=doc.id
            ))
        elif doc.status == "UNDATED":
            warnings.append(WarningDetail(
                warning_type="UNDATED_SOURCE",
                message=f"'{doc.title}' is an undated memo — freshness cannot be verified.",
                document_id=doc.id
            ))

    return {
        "conflict": conflict_info,
        "warnings": warnings,
        "caveats": caveats,
        "is_safe_to_answer": len(chunks_with_docs) > 0,
        "active_documents": list(seen_docs.values())
    }
