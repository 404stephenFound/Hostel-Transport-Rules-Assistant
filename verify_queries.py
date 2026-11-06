import json
from app.database import SessionLocal
import app.models
from app.api.chat import submit_chat_query
from app.schemas import ChatRequest

def run_deliverables_verification():
    db = SessionLocal()

    print("=" * 80)
    print("      DELIVERABLE: TEST QUERY EXECUTED 3 CONSECUTIVE TIMES")
    print("=" * 80)

    for run_i in range(1, 4):
        print(f"\n==================== [RUN {run_i}/3] ====================")
        req = ChatRequest(question="What is the hostel entry gate closing time on weekdays?")
        res = submit_chat_query(req, db=db)
        data = res.model_dump()

        print("--- FULL JSON OUTPUT ---")
        print(json.dumps(data, indent=2))

        print("\n--- RENDERED FRONTEND VIEW ---")
        print(f"Direct Answer:     {data['answer']}")
        print(f"Day Range:         {data['day_range']}")
        print(f"Applies To:        {data['applies_to']}")
        print(f"Effective Date:    {data['effective_date']}")
        if data['conflict']['exists']:
            print(f"Policy Notice:     {data['conflict']['notice']}")
        else:
            print(f"Policy Notice:     None (Neutral note: '{data['conflict'].get('notice')}')")
        print("Rule Summary:")
        for r in data['rule_summary']:
            print(f"  • {r}")
        print("Important Caveats:")
        for c in data['caveats']:
            print(f"  • {c}")
        print("Verified Sources Cited:")
        for s in data['sources']:
            print(f"  • [{s['status']}] {s['doc_title']} (Section: {s['section']}, Page {s['page']})")
            print(f"    Pub: {s['publication_date']} · Eff: {s['effective_from']}")
            print(f"    Quote: \"{s['quote']}\"")
        print(f"Escalation Office: {data['escalation_office']}")

    print("\n" + "=" * 80)
    print("      DELIVERABLE: ADDITIONAL REQUIRED TEST QUERIES")
    print("=" * 80)

    # 1. Weekend closing time
    print("\n--- [ADDITIONAL TEST 1: Weekend Closing Time] ---")
    req_weekend = ChatRequest(question="What is the hostel entry gate closing time on weekends?")
    res_weekend = submit_chat_query(req_weekend, db=db)
    data_weekend = res_weekend.model_dump()
    print(f"Answer:         {data_weekend['answer']}")
    print(f"Day Range:      {data_weekend['day_range']}")
    print(f"Applies To:     {data_weekend['applies_to']}")
    print(f"Effective Date: {data_weekend['effective_date']}")
    if data_weekend['conflict']['exists']:
        print(f"Policy Notice:  {data_weekend['conflict']['notice']}")
    print("Sources:")
    for s in data_weekend['sources']:
        print(f"  • [{s['status']}] {s['doc_title']} | Pub: {s['publication_date']} · Eff: {s['effective_from']}")
        print(f"    Quote: \"{s['quote']}\"")

    # 2. What changed recently
    print("\n--- [ADDITIONAL TEST 2: What Changed Recently] ---")
    req_changes = ChatRequest(question="What changed recently in the hostel rules?")
    res_changes = submit_chat_query(req_changes, db=db)
    data_changes = res_changes.model_dump()
    print(f"Answer:         {data_changes['answer']}")
    print(f"Day Range:      {data_changes['day_range']}")
    print(f"Applies To:     {data_changes['applies_to']}")
    if data_changes['conflict']['exists']:
        print(f"Policy Notice:  {data_changes['conflict']['notice']}")
    print("Rule Summary:")
    for r in data_changes['rule_summary']:
        print(f"  • {r}")
    print("Sources:")
    for s in data_changes['sources']:
        print(f"  • [{s['status']}] {s['doc_title']} | Pub: {s['publication_date']} · Eff: {s['effective_from']}")
        print(f"    Quote: \"{s['quote']}\"")

    # 3. No source (Refuse and escalate cleanly)
    print("\n--- [ADDITIONAL TEST 3: Out-of-Scope Query (Refuse & Escalate)] ---")
    req_unsupported = ChatRequest(question="Can day scholars book overnight hostel rooms for campus festivals?")
    res_unsupported = submit_chat_query(req_unsupported, db=db)
    data_unsupported = res_unsupported.model_dump()
    print(f"Answer:         {data_unsupported['answer']}")
    print(f"Sources Count:  {len(data_unsupported['sources'])}")
    print(f"Escalation:     {data_unsupported['escalation_office']}")

    db.close()

if __name__ == "__main__":
    run_deliverables_verification()
