import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import time
import subprocess
import threading
import uvicorn
from playwright.sync_api import sync_playwright

CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
if not os.path.exists(CHROME_PATH):
    CHROME_PATH = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"

SERVER_PORT = 8001
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"


class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.server = None
        self.daemon = True

    def run(self):
        from app.main import app
        config = uvicorn.Config(app, host="127.0.0.1", port=SERVER_PORT, log_level="warning")
        self.server = uvicorn.Server(config)
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True


def run_dom_tests():
    print("=" * 70)
    print("   REAL-TIME BROWSER & DOM INTERACTION TEST SUITE")
    print("=" * 70)
    print(f"1. Starting local FastAPI application on {BASE_URL}...")
    server_thread = ServerThread()
    server_thread.start()
    time.sleep(3.0)  # Wait for uvicorn to initialize and seed database

    artifacts_dir = os.path.join(PROJECT_ROOT, "test_artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    print(f"2. Launching browser instance using {os.path.basename(CHROME_PATH)}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True
        )
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        print(f"3. Navigating to {BASE_URL}...")
        page.goto(BASE_URL, wait_until="networkidle")

        # Step A: Verify initial DOM structure
        page_title = page.title()
        print(f"   [DOM CHECK] Page Title: '{page_title}'")
        assert "Hostel & Transport" in page_title

        header_text = page.locator("header h1").text_content()
        print(f"   [DOM CHECK] Header H1: '{header_text}'")
        assert "Hostel & Transport Rules Assistant" in header_text

        # Verify quick prompts chips exist
        chips = page.locator("#quick-prompts button")
        chip_count = chips.count()
        print(f"   [DOM CHECK] Quick Prompt Chips rendered: {chip_count}")
        assert chip_count >= 5

        page.screenshot(path=os.path.join(artifacts_dir, "01_initial_load.png"))

        # Step B: Click quick prompt and test Real-Time Chat DOM
        first_chip = page.locator("button:has-text('Weekday Hostel Curfew')")
        print("4. Clicking quick prompt chip 'Weekday Hostel Curfew'...")
        first_chip.click()

        # Wait for assistant response to render in DOM
        print("   Waiting for assistant response bubble and citations to render in DOM...")
        page.wait_for_selector("#messages-container .bg-white.border.border-slate-200.rounded-tl-sm", timeout=8000)

        # Inspect Assistant Response DOM elements
        direct_answer_el = page.locator("#messages-container div.font-medium.text-slate-900.leading-relaxed")
        direct_answer_text = direct_answer_el.first.text_content()
        print(f"   [DOM VERIFIED] Direct Answer: '{direct_answer_text[:80]}...'")
        assert "8:30 PM" in direct_answer_text or "9:30 PM" in direct_answer_text

        # Inspect Citation Card
        citation_card = page.locator("#messages-container .citation-card").first
        citation_title = citation_card.locator("span.font-bold.text-slate-800").text_content()
        print(f"   [DOM VERIFIED] Cited Document: '{citation_title}'")
        assert "Hostel" in citation_title

        # Inspect Escalation Section
        escalation_el = page.locator("#messages-container div.mt-3.text-\\[11px\\].text-slate-500").first
        escalation_text = escalation_el.text_content()
        print(f"   [DOM VERIFIED] Escalation Route: '{escalation_text.strip()}'")
        assert "Hostel Administration" in escalation_text

        page.screenshot(path=os.path.join(artifacts_dir, "02_chat_response.png"))

        # Step C: Ask a Bus Route Query
        print("5. Submitting custom input query: 'Which bus goes to Lakeview Colony and what is the morning time?'...")
        user_input = page.locator("#user-input")
        user_input.fill("Which bus goes to Lakeview Colony and what is the morning time?")
        page.locator("#send-btn").click()

        # Wait for second response bubble
        second_bubble = page.locator("#messages-container .bg-white.border.border-slate-200.rounded-tl-sm").nth(1)
        second_bubble.wait_for(state="visible", timeout=8000)
        route_response = second_bubble.locator("div.font-medium.text-slate-900.leading-relaxed").text_content()
        print(f"   [DOM VERIFIED] Transit Route Answer: '{route_response[:80]}...'")
        assert "Route 4" in route_response or "7:35 AM" in route_response or "Lakeview Colony" in route_response

        page.screenshot(path=os.path.join(artifacts_dir, "03_transit_query.png"))

        # Step D: Test Tab Switching to Admin Policy Hub
        print("6. Switching to 'Policy Admin Hub' tab...")
        page.locator("#tab-admin-btn").click()
        page.wait_for_selector("#admin-view:not(.hidden)", timeout=4000)
        # Wait for async documents load to populate table rows
        page.wait_for_selector("#docs-table-body tr td.font-semibold", timeout=6000)

        # Verify documents table rows
        rows = page.locator("#docs-table-body tr")
        row_count = rows.count()
        print(f"   [DOM VERIFIED] Policy Repository Table Rows: {row_count}")
        assert row_count >= 5

        # Check badges in table
        table_html = page.locator("#docs-table-body").inner_html().lower()
        assert "hostel student handbook 2025-2026" in table_html
        assert "circular no. 14/2026" in table_html
        assert "route schedule" in table_html
        assert "current" in table_html
        assert "partially_superseded" in table_html or "superseded" in table_html
        assert "expired" in table_html
        assert "undated" in table_html

        page.screenshot(path=os.path.join(artifacts_dir, "04_admin_hub.png"))

        # Step E: Verify System Audit Trail DOM
        audit_items = page.locator("#audit-log-list div")
        audit_count = audit_items.count()
        print(f"   [DOM VERIFIED] Audit Trail Entries: {audit_count}")
        assert audit_count >= 1

        print("7. All Real-Time DOM & Browser Verification Checks Passed Successfully!")
        browser.close()

    server_thread.stop()
    print("=" * 70)


if __name__ == "__main__":
    run_dom_tests()
