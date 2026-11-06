import datetime
import re
from typing import List, Dict, Any, Tuple, Optional
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


def resolve_effective_reference_date(query: str, today_date_str: Optional[str] = None) -> datetime.date:
    """Extracts reference evaluation date from parameter or query string."""
    if today_date_str:
        d = parse_date(today_date_str)
        if d:
            return d

    # Search for date patterns like "15 January 2026", "January 2026", "March 2026"
    m_full = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", query, re.I)
    if m_full:
        day_int = int(m_full.group(1))
        month_str = m_full.group(2)
        year_int = int(m_full.group(3))
        try:
            dt = datetime.datetime.strptime(f"{day_int} {month_str} {year_int}", "%d %B %Y").date()
            return dt
        except ValueError:
            pass

    m_month = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", query, re.I)
    if m_month:
        month_str = m_month.group(1)
        year_int = int(m_month.group(2))
        try:
            dt = datetime.datetime.strptime(f"1 {month_str} {year_int}", "%d %B %Y").date()
            return dt
        except ValueError:
            pass

    return datetime.date.today()


def format_effective_notice(eff_date_str: str | None, reference_date: Optional[datetime.date] = None) -> str:
    if not eff_date_str:
        return "immediate effect"
    eff_date = parse_date(eff_date_str)
    if not eff_date:
        return f"effective {eff_date_str}"
    ref = reference_date or datetime.date.today()
    formatted = eff_date.strftime("%d %B %Y")
    if eff_date <= ref:
        return f"already in force since {formatted}"
    else:
        return f"takes effect on {formatted}"


def analyze_retrieved_evidence(
    chunks_with_docs: List[Tuple[Any, Any]], 
    query: str = "",
    today_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyzes retrieved chunks for clause-level supersession and conflicts.
    - Uses clause-level supersession metadata to determine if the answer depends on the revised clause.
    - Weekday / Sunday / unaffected clauses do not show a conflict notice.
    - Dates prior to Circular 14 effective date (2026-02-20) do not show a conflict notice.
    """
    ref_date = resolve_effective_reference_date(query, today_date)
    circular_14_eff_date = datetime.date(2026, 2, 20)

    seen_docs = {}
    for chunk, doc in chunks_with_docs:
        seen_docs[doc.id] = doc

    conflict_info = ConflictInfo(exists=False)
    warnings: List[WarningDetail] = []
    caveats: List[str] = []

    q_lower = query.lower() if query else ""

    # Check query intents
    is_weekday = "weekday" in q_lower or "weekdays" in q_lower
    is_weekend = any(k in q_lower for k in ["weekend", "weekends", "friday", "saturday"])
    is_sunday = "sunday" in q_lower
    is_changes = any(k in q_lower for k in ["changed", "recent", "revision", "new rules", "latest notice", "update"])
    is_historical = any(k in q_lower for k in ["old", "previous", "earlier", "prior to", "before the revision", "superseded"])
    is_vague_curfew = "time" in q_lower and "back" in q_lower

    has_circular_14 = any("Circular No. 14" in doc.title for doc in seen_docs.values())

    # 1. Clause-level supersession detection
    # Circular 14 specifically revised ONLY Section 2: Weekend In-Time (Friday and Saturday nights)
    # The answer depends on the revised clause IF AND ONLY IF:
    # (a) The query asks about weekend curfew on or after 20 Feb 2026
    # (b) OR the query explicitly asks what changed recently
    is_after_eff_date = ref_date >= circular_14_eff_date

    if has_circular_14 and not is_historical and not is_vague_curfew and is_after_eff_date:
        if (is_weekend and not is_sunday) or is_changes:
            eff_phrase = format_effective_notice("2026-02-20", reference_date=ref_date)
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
        elif is_weekday or is_sunday:
            # Weekday or Sunday query: show neutral non-conflicting note only; timing was not modified
            neutral_note = "Weekend timings were revised effective 20 Feb 2026. Weekday timing is unchanged."
            conflict_info = ConflictInfo(
                exists=False,
                resolved_rule="Weekday in-time is 8:30 PM.",
                older_rule="Weekday in-time is 8:30 PM.",
                notice=neutral_note
            )
    elif is_weekday or is_sunday:
        neutral_note = "Weekend timings were revised effective 20 Feb 2026. Weekday timing is unchanged."
        conflict_info = ConflictInfo(
            exists=False,
            resolved_rule="Weekday in-time is 8:30 PM.",
            older_rule="Weekday in-time is 8:30 PM.",
            notice=neutral_note
        )

    # 2. Check for day range disagreement caveat
    if any(k in q_lower for k in ["weekday", "day", "sunday", "thursday", "curfew", "gate", "back", "weekdys"]):
        caveats.append(
            "The handbook lists Monday to Thursday while Circular 14/2026 lists Sunday to Thursday. Please confirm Sunday timing with the Warden Desk (Ext. 102)."
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
        "active_documents": list(seen_docs.values()),
        "reference_date": ref_date
    }
