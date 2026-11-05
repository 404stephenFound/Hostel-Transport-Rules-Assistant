# Project Architecture & File Rationale Log 📜

> **Project:** Hostel & Transport Rules Assistant  
> **Repository:** [https://github.com/404stephenFound/Hostel-Transport-Rules-Assistant](https://github.com/404stephenFound/Hostel-Transport-Rules-Assistant)  
> **Last Updated:** 2026-11-05 23:20 IST  
> **Maintainer:** Project Team  

---

## 📌 Purpose of this Document

This document is the **authoritative architecture and development log** for the repository. It explains:
1. **Why each folder and file was created** (the rationale and requirement it solves).
2. **What each component contains** (responsibilities, models, algorithms).
3. **How components interact** across the system.
4. **Chronological change history** tracking version increments.

---

## 📂 Complete Directory & File Manifest

```
Hostel-Transport-Rules-Assistant/
├── app/
│   ├── api/
│   │   ├── audit.py             # System telemetry & action auditing
│   │   ├── chat.py              # Student chat, conversation sessions & history
│   │   ├── documents.py         # Institutional notice upload, review & supersession
│   │   └── feedback.py          # Student answer quality rating & feedback logging
│   ├── llm/
│   │   ├── generator.py         # Grounded RAG synthesis engine (Answer + Conditions + Citations)
│   │   └── prompts.py           # System prompts, behavioural constraints & abstention templates
│   ├── rag/
│   │   ├── chunker.py           # Structural text parser preserving section titles & pages
│   │   ├── conflict_detector.py # Date conflict, supersession & freshness analyzer
│   │   └── retriever.py         # Hybrid BM25 keyword + domain-affinity retriever
│   ├── config.py                # Environment configuration & Pydantic settings
│   ├── database.py              # SQLite engine, session factory & dependency injection
│   ├── models.py                # SQLAlchemy relational database ORM definitions
│   ├── schemas.py               # Pydantic data validation schemas for API contracts
│   ├── seed.py                  # Institutional knowledge base seeder (Handbook, circulars, routes)
│   └── main.py                  # FastAPI application entrypoint, middleware & asset mounts
├── docs/
│   └── PROJECT_SPECIFICATION.md # Full 2,000+ line PRD, PID, Charter, Business Case & Schedule
├── static/
│   └── index.html               # Responsive Single-Page Web UI (Student Chat & Policy Admin Hub)
├── tests/
│   ├── test_api.py              # Unit & endpoint tests for FastAPI routers
│   ├── test_conflict_and_supersession.py # Tests for supersession, freshness & abstention
│   ├── test_rag.py              # Tests for semantic chunking & BM25 hybrid retrieval
│   └── test_realtime_dom.py     # Live Playwright browser DOM interaction test suite (Chrome)
├── pytest.ini                   # Pytest runner configuration
├── requirements.txt             # Minimal, production-only dependencies
├── run.py                       # Zero-config local application server launcher
├── PROJECT_LOG.md               # This document: Comprehensive file-by-file rationale log
└── README.md                    # Public GitHub repository overview & quickstart
```

---

## 🔍 Detailed Component Rationale & File Breakdown

### 1. Core Application Package (`app/`)

#### `app/config.py`
* **Why Created:** Centralizes all environment configuration, file storage paths, similarity thresholds, and model parameters into a typed Pydantic `BaseSettings` object.
* **What It Contains:** `Settings` class loading from `.env` or system defaults (`PROJECT_NAME`, `DATABASE_URL`, `UPLOAD_DIR`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K_RETRIEVAL`).
* **Interactions:** Imported by `app/database.py`, `app/main.py`, and `app/rag/retriever.py`.

#### `app/database.py`
* **Why Created:** Isolates database connection pooling, SQLAlchemy engine initialization, and FastAPI dependency injection.
* **What It Contains:** `engine`, `SessionLocal`, declarative `Base`, and the `get_db()` generator function.
* **Interactions:** Injected via `Depends(get_db)` into all API route controllers.

#### `app/models.py`
* **Why Created:** Defines the persistence schema matching PRD Sections 4.6 & 4.14.
* **What It Contains:**
  * `Document`: Stores title, department, publication date, effective dates, status (`current`, `superseded`, `expired`, `undated`, `draft`), and file hashes.
  * `DocumentChunk`: Text chunks with foreign keys to documents, section names, and page numbers.
  * `ChatSession` & `ChatMessage`: Conversation history and serialized JSON citations/warnings.
  * `Feedback`: Student quality ratings (+1 / -1) and issue tags.
  * `AuditEvent`: System audit trail logging all uploads, queries, and supersession links.

#### `app/schemas.py`
* **Why Created:** Enforces strict API request and response contracts using Pydantic v2.
* **What It Contains:** `ChatRequest`, `ChatResponse`, `Citation`, `WarningDetail`, `DocumentCreate`, `DocumentResponse`, `FeedbackRequest`, and `AuditEventResponse`.
* **Interactions:** Used by FastAPI router endpoints to validate request bodies and serialize JSON responses.

#### `app/seed.py`
* **Why Created:** Provides authentic baseline institutional documents so the system is immediately usable without requiring manual uploads first.
* **What It Contains:**
  1. *Hostel Student Handbook 2025-2026* (Curfew, roll call, mess timings, late entry ₹200 fines).
  2. *Hostel Circular No. 14/2026* (Explicitly supersedes weekend curfew from 8:30 PM to 9:30 PM).
  3. *College Transport Service Guide 2025-2026* (Routes 1, 2, 3, 4 with pickup points and departure times).
  4. *Transport Notice TR/EXAM/2024* (Expired temporary notice for freshness validation).
  5. *Hostel Gymnasium & Laundry Notice* (Undated memo for undated warning validation).
* **Interactions:** Automatically executed during `app/main.py` startup lifespan if database is empty.

#### `app/main.py`
* **Why Created:** Application factory configuring FastAPI, CORS, static file mounts, router inclusion, and lifespan initialization.
* **What It Contains:** `lifespan(app)` context manager, router inclusions for `/api/chat`, `/api/documents`, `/api/feedback`, and `/api/audit`, plus `/health` and root `/` serving `static/index.html`.

---

### 2. Retrieval-Augmented Generation Engine (`app/rag/`)

#### `app/rag/chunker.py`
* **Why Created:** Solves the problem of arbitrary text splitting by breaking documents strictly along section headers, numbered rules, timetable rows, and page markers (`[Page X]`).
* **What It Contains:** `chunk_document_text()` with structural regex matching (`Section \d+`, `Route \d+`, headings) to ensure entire policies and tables remain intact.

#### `app/rag/retriever.py`
* **Why Created:** Implements the hybrid search specified in PRD Section 4.4 FR-013.
* **What It Contains:**
  * Stopword-filtered content tokenization.
  * BM25 / TF-IDF term scoring.
  * Exact phrase match boosting (e.g. `"Route 4"`, `"Lakeview Colony"`, `"8:30 PM"`).
  * Category intent weighting (boosts Hostel docs for hostel queries, Transport docs for transit queries).
  * Minimum term-coverage threshold (requires $\ge 35\%$ query match to prevent single-word false matches).
  * Automatic exclusion of `superseded` notices unless explicitly requested.

#### `app/rag/conflict_detector.py`
* **Why Created:** Implements PRD Section 4.10 Date-Aware Source Ranking and Conflict Handling.
* **What It Contains:**
  * `analyze_retrieved_evidence()` function.
  * Detects when a cited source has been superseded by a newer notice (`SUPERSEDED_SOURCE`).
  * Flags expired notices past their `effective_until` date (`EXPIRED_SOURCE`).
  * Flags notices without a publication date (`UNDATED_SOURCE`).
  * Identifies discrepancies in timings across different documents (`CONFLICTING_SOURCES`).

---

### 3. LLM Orchestration & Policy Guardrails (`app/llm/`)

#### `app/llm/prompts.py`
* **Why Created:** Enforces institutional policy guardrails and zero-hallucination behaviour.
* **What It Contains:** `SYSTEM_PROMPT` mandating first-sentence direct answers, conditions checklist, strict grounding in evidence, and `ABSTENTION_MESSAGE` for unsupported queries.

#### `app/llm/generator.py`
* **Why Created:** Synthesizes the structured student response.
* **What It Contains:** `RAGAnswerGenerator` class that formats direct answers, extracts condition bullets, compiles traceable `Citation` objects, appends warning banners, and specifies the official escalation office.

---

### 4. API Endpoints (`app/api/`)

* **`app/api/chat.py`:** Handles `/api/chat`, manages session threads, executes retrieval and conflict analysis, logs queries, and returns formatted responses.
* **`app/api/documents.py`:** Provides admin document management: listing with filters, uploading new notices, manual supersession linking (`/{id}/supersede`), and archiving (`/{id}/deactivate`).
* **`app/api/feedback.py`:** Captures student feedback (+1 / -1) and comments for continuous evaluation.
* **`app/api/audit.py`:** Provides an immutable audit trail of all ingestion and query operations.

---

### 5. Frontend & UI (`static/index.html`)

* **Why Created:** Delivers a zero-setup, responsive web interface for both students and administrators without requiring Node.js/npm build steps.
* **What It Contains:**
  * **Student Chat View:** Conversational window, 5 quick-prompt suggestion chips, grounded response cards with direct answers, conditions, citation tags with dates, warning banners, escalation links, and feedback buttons.
  * **Policy Admin Hub:** Document table showing title, version, category, department, publication date, effective dates, status pills, and audit trail list.
  * **Upload Modal:** Form to add new institutional notices with date fields and live chunk indexing.

---

### 6. Documentation Package (`docs/`)

#### `docs/PROJECT_SPECIFICATION.md`
* **Why Created:** Preserves the foundational 2,000+ line institutional project specification pack.
* **What It Contains:**
  1. **Section 1 (Line 70):** Business Case & Problem Statement (Executive summary, stakeholder value, success measures).
  2. **Section 2 (Line 259):** Project Charter / PID (Vision, objectives, scope boundaries, deliverables, governance).
  3. **Section 3 (Line 526):** Project Plan & Schedule (Work breakdown structure, milestones, resource allocation).
  4. **Section 4 (Line 677):** Scope & Requirements / PRD (User personas, user stories, functional requirements FR-001 through FR-043, NFRs, metadata models, and evaluation strategy).
  5. **Section 5–9 (Line 1794+):** Build Order, Operational Policies, Change Log, Review Checklist, and Glossary.

---

### 7. Test Suite (`tests/`)

* **`tests/test_rag.py`:** 3 unit tests verifying section header preservation in chunks, hybrid BM25 curfew retrieval, and bus route stop lookups.
* **`tests/test_conflict_and_supersession.py`:** 4 unit tests verifying supersession detection (Circular 14/2026 vs Handbook), expired notices (`TR/EXAM/2024`), undated notices, and clean abstention on unanswerable questions.
* **`tests/test_api.py`:** 5 unit tests verifying `/health`, `/api/chat` grounded answers, `/api/documents` uploads, and `/api/feedback`.
* **`tests/test_realtime_dom.py`:** End-to-end browser DOM test using Playwright with real Google Chrome to verify page load, prompt clicks, assistant responses, transit queries, admin tab navigation, and audit trail rendering.

---

### 8. Project Configuration & Runners

* **`run.py`:** Simple launcher script executing `uvicorn app.main:app --reload` on port 8000.
* **`requirements.txt`:** Minimal, production-only dependencies: `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `pytest`, `pytest-asyncio`, `httpx`, `python-multipart`, and `playwright`.
* **`pytest.ini`:** Pytest settings setting `pythonpath = .` and `testpaths = tests`.
* **`.gitignore`:** Ignores virtual environments, SQLite databases, vector indexes, test artifacts, and caches.
* **`README.md`:** Repository landing page with architecture diagram, feature breakdown, API table, and quickstart commands.

---

## 📈 Change Log & Version Evolution

| Version | Date | Changes & Rationale | Status |
| :--- | :--- | :--- | :---: |
| **v1.0.0** | 2026-11-05 | Initialized clean repository; established database schema (`models.py`), hybrid retriever, conflict detector, RAG answer generator, and seeded institutional documents. | ✅ Completed |
| **v1.0.1** | 2026-11-05 | Built dual-mode Student Chat and Admin Hub web interface (`static/index.html`); created full unit test suite covering chunking, supersession, and API endpoints (12/12 passing). | ✅ Completed |
| **v1.1.0** | 2026-11-05 | Added automated real-time browser DOM test suite (`test_realtime_dom.py`) using Playwright with Google Chrome; verified UI interactions and DOM rendering; synchronized with GitHub. | ✅ Completed |
| **v1.1.1** | 2026-11-05 | Created `PROJECT_LOG.md` detailing file rationales, contents, and cross-component interactions; referenced `docs/PROJECT_SPECIFICATION.md` for Charter, PRD, and Plan. | ✅ Completed |

