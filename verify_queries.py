import json
from app.database import SessionLocal, engine, Base
import app.models
from app.api.chat import submit_chat_query
from app.schemas import ChatRequest

def run_5_test_queries():
    db = SessionLocal()
    
    test_cases = [
        {
            "id": 1,
            "name": "Weekday In-Time Query",
            "query": "What is the hostel entry gate closing time on weekdays?",
            "include_historical": False
        },
        {
            "id": 2,
            "name": "Weekend In-Time Query",
            "query": "What is the hostel entry gate closing time on weekends?",
            "include_historical": False
        },
        {
            "id": 3,
            "name": "Recent Policy Changes Query",
            "query": "What changed recently in the hostel rules?",
            "include_historical": False
        },
        {
            "id": 4,
            "name": "Superseded / Historical Rules Query",
            "query": "What were the old weekend curfew rules before the revision?",
            "include_historical": True
        },
        {
            "id": 5,
            "name": "Unsupported / Out-of-Scope Query (Refusal & Escalation)",
            "query": "Can day scholars book overnight hostel rooms for campus festivals?",
            "include_historical": False
        }
    ]

    results = []

    print("=" * 80)
    print("      5 TEST QUERIES VERIFICATION RUN")
    print("=" * 80)

    for tc in test_cases:
        req = ChatRequest(
            question=tc["query"],
            include_historical=tc["include_historical"]
        )
        res = submit_chat_query(req, db=db)

        tc_output = {
            "test_id": tc["id"],
            "title": tc["name"],
            "query": tc["query"],
            "include_historical": tc["include_historical"],
            "structured_output": {
                "answer": res.answer,
                "applies_to": res.applies_to,
                "effective_date": res.effective_date,
                "caveats": res.caveats,
                "rule_summary": res.rule_summary,
                "sources": [
                    {
                        "doc_title": s.doc_title,
                        "section": s.section,
                        "page": s.page,
                        "status": s.status,
                        "quote": s.quote
                    }
                    for s in res.sources
                ],
                "conflict": {
                    "exists": res.conflict.exists,
                    "resolved_rule": res.conflict.resolved_rule,
                    "older_rule": res.conflict.older_rule,
                    "notice": res.conflict.notice
                },
                "escalation_office": res.escalation_office
            }
        }
        results.append(tc_output)

        print(f"\n--- [TEST {tc['id']}: {tc['name']}] ---")
        print(f"QUERY: \"{tc['query']}\" (include_historical={tc['include_historical']})")
        print(f"DIRECT ANSWER: {res.answer}")
        print(f"APPLIES TO:    {res.applies_to}")
        print(f"EFFECTIVE:     {res.effective_date}")
        if res.conflict.exists:
            print(f"CONFLICT NOTICE: {res.conflict.notice}")
        if res.caveats:
            print(f"CAVEATS: {res.caveats}")
        print("RULE SUMMARY:")
        for r in res.rule_summary:
            print(f"  • {r}")
        print("CITATIONS:")
        for s in res.sources:
            print(f"  [{s.status}] {s.doc_title} • {s.section} (Page {s.page}): \"{s.quote}\"")
        print(f"ESCALATION: {res.escalation_office}")

    db.close()
    
    with open("test_artifacts/test_5_queries_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to test_artifacts/test_5_queries_results.json")

if __name__ == "__main__":
    run_5_test_queries()
