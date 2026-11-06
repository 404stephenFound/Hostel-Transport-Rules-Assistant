import json
import re
import sys
import os

# Ensure root path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.api.chat import submit_chat_query
from app.schemas import ChatRequest

def run_all_tests():
    test_file = os.path.join(os.path.dirname(__file__), "test_queries.json")
    with open(test_file, "r", encoding="utf-8") as f:
        tests = json.load(f)

    db = SessionLocal()
    results = []
    total = len(tests)
    passed = 0

    print("=" * 80)
    print(f"RUNNING REGRESSION TEST SUITE: {total} CASES")
    print("=" * 80)

    try:
        for idx, tc in enumerate(tests, 1):
            tc_id = tc["id"]
            tc_name = tc.get("name", tc_id)
            query = tc["query"]
            include_hist = tc.get("include_historical", False)
            today_date = tc.get("today_date", None)
            should_refuse = tc.get("should_refuse", False)
            should_have_notice = tc.get("should_have_notice", False)
            expected_times = tc.get("expected_times", [])
            expected_days = tc.get("expected_days", [])
            expected_keywords = tc.get("expected_keywords", [])
            expected_doc = tc.get("expected_doc", None)

            req = ChatRequest(
                question=query,
                include_historical=include_hist,
                today_date=today_date
            )

            failures = []
            try:
                res = submit_chat_query(req, db=db)
                data = res.model_dump()
            except Exception as e:
                failures.append(f"Exception during query execution: {e}")
                results.append((tc_id, tc_name, False, failures))
                print(f"[{idx:02d}/{total}] FAIL: {tc_name} ({tc_id})")
                for f in failures:
                    print(f"      - {f}")
                continue

            answer = data.get("answer", "")
            direct_answer = data.get("direct_answer", "")
            sources = data.get("sources", [])
            citations = data.get("citations", [])
            conflict = data.get("conflict", {})
            warnings = data.get("warnings", [])

            # 1. Blank answer check
            if not answer.strip():
                failures.append("Blank answer returned")

            # 2. Refusal check
            if should_refuse:
                is_refused = (
                    "could not find this rule" in answer.lower()
                    or "couldn't verify this from the approved documents" in answer.lower()
                    or "escalate" in answer.lower()
                    or len(sources) == 0
                )
                if not is_refused:
                    failures.append("Expected refusal/escalation but got normal answer")
                if len(sources) > 0:
                    failures.append(f"Expected 0 sources on refusal, but got {len(sources)}")
                escalate_field = data.get("escalation_office", "")
                if not escalate_field:
                    failures.append("Missing escalation_office on refusal")
            else:
                # 3. Non-refusal checks
                # A. Check expected times
                for t in expected_times:
                    if t.lower() not in answer.lower() and not any(t.lower() in s.get("quote", "").lower() for s in sources):
                        failures.append(f"Expected time '{t}' not found in answer or sources")

                # B. Check expected days
                for d in expected_days:
                    if d.lower() not in answer.lower() and not any(d.lower() in s.get("quote", "").lower() for s in sources):
                        failures.append(f"Expected day '{d}' not found in answer or sources")

                # C. Check expected keywords
                for kw in expected_keywords:
                    if kw.lower() not in answer.lower() and not any(kw.lower() in s.get("quote", "").lower() for s in sources):
                        failures.append(f"Expected keyword '{kw}' not found in answer or sources")

                # D. Check expected document in sources
                if expected_doc:
                    found_doc = any(expected_doc.lower() in s.get("doc_title", "").lower() for s in sources)
                    if not found_doc:
                        failures.append(f"Expected source doc '{expected_doc}' not in sources")

                # E. Check notice relevance
                has_notice = conflict.get("exists", False) and bool(conflict.get("notice"))
                if should_have_notice and not has_notice:
                    failures.append("Expected policy update notice, but none was returned")
                elif not should_have_notice and has_notice:
                    failures.append(f"Unexpected policy update notice shown: '{conflict.get('notice')}'")

                # F. Check sources quotes and dates
                for s in sources:
                    quote = s.get("quote", "")
                    if not quote or not quote.strip():
                        failures.append(f"Empty quote found in source card '{s.get('doc_title')}'")
                    pub_date = s.get("publication_date")
                    doc_title = s.get("doc_title", "")
                    if "Handbook" in doc_title and (not pub_date or pub_date == "Undated"):
                        failures.append(f"Handbook source missing publication_date ('{pub_date}')")
                    if "Circular No. 14" in doc_title and (not pub_date or pub_date == "Undated"):
                        failures.append(f"Circular source missing publication_date ('{pub_date}')")

            is_passed = len(failures) == 0
            if is_passed:
                passed += 1
                print(f"[{idx:02d}/{total}] PASS: {tc_name}")
            else:
                print(f"[{idx:02d}/{total}] FAIL: {tc_name} ({tc_id})")
                for f in failures:
                    print(f"      - {f}")

            results.append((tc_id, tc_name, is_passed, failures))

    finally:
        db.close()

    print("=" * 80)
    print(f"SUMMARY: {passed}/{total} PASSED ({(passed/total)*100:.1f}%)")
    print("=" * 80)
    return passed, total, results

if __name__ == "__main__":
    passed, total, _ = run_all_tests()
    sys.exit(0 if passed == total else 1)
