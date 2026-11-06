import datetime
import hashlib
import json
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, AuditEvent
from app.rag.chunker import chunk_document_text


def seed_database(db: Session, force: bool = False):
    existing_docs = db.query(Document).count()
    if existing_docs > 0 and not force:
        return

    if force:
        db.query(DocumentChunk).delete()
        db.query(Document).delete()
        db.commit()

    docs_data = [
        {
            "title": "Hostel Student Handbook 2025-2026",
            "category": "Hostel Manual",
            "issuing_department": "Hostel Administration",
            "publication_date": "2025-07-20",
            "effective_from": "2025-08-01",
            "effective_until": None,
            "status": "PARTIALLY_SUPERSEDED",
            "superseded_sections": json.dumps(["Section 2: Weekend In-Time"]),
            "version": "1.0",
            "notes": "Comprehensive rulebook. Section 2 weekend curfew superseded by Circular No. 14/2026.",
            "content": """[Page 1]
Section 1. General Conduct and Hostel Discipline
All resident students must maintain high standards of discipline, decorum, and cleanliness within hostel premises. Ragging, alcohol consumption, smoking, and possession of unauthorized electrical heating appliances are strictly prohibited. Violations will lead to disciplinary hearing and possible expulsion.

Section 2. Curfew Timings and Roll Call
The main hostel entry gate closes strictly at 8:30 PM on weekdays (Monday through Thursday) and 8:30 PM on weekends. Every resident must be inside their respective block before the gate closes.
Mandatory daily roll call is taken by resident tutors at 9:30 PM sharp in each floor lounge. Unexcused absence during roll call is treated as unauthorized absence and escalated to parents.

[Page 2]
Section 3. Overnight Leave and Outstation Travel Procedures
Students intending to leave the campus overnight or visit local guardians must submit an online leave request via the hostel portal at least 24 hours in advance (before Thursday 5:00 PM for weekend leave).
Parental consent confirmation via registered SMS/email is mandatory before gate passes are approved by the Senior Warden. Students must sign the out-station register at the security desk before leaving and upon return.

Section 4. Late Entry Policy and Penalties
Returning to the hostel after 8:30 PM without a pre-approved late pass incurs an automatic fine of ₹200 for the first occurrence. Repeated late entries (more than twice in a semester) will result in notification to parents and disciplinary committee review.

[Page 3]
Section 5. Mess Timings and Dining Hall Rules
Mess meals are served at designated hours: Breakfast from 7:30 AM to 9:00 AM; Lunch from 12:30 PM to 2:00 PM; Evening Tea and Snacks from 4:45 PM to 5:45 PM; Dinner from 7:30 PM to 9:00 PM.
Food must not be carried outside the dining hall without written authorization from the hostel health clinic."""
        },
        {
            "title": "Hostel Circular No. 14/2026: Revision of Weekend In-Time",
            "category": "Hostel Circular",
            "issuing_department": "Hostel Administration",
            "publication_date": "2026-02-15",
            "effective_from": "2026-02-20",
            "effective_until": None,
            "status": "CURRENT",
            "superseded_sections": None,
            "version": "1.1",
            "notes": "Supersedes Section 2 weekend curfew timing stated in 2025 Handbook.",
            "content": """[Page 1]
Hostel Circular No. 14/2026
Subject: Extension of Weekend Curfew Hours for Hostel Residents

Following student representations and review by the Hostel Management Committee, the weekend in-time for all residential hostel blocks is hereby extended.
Effective from 20 February 2026, the hostel entry gate closing time on Friday and Saturday nights is revised to 9:30 PM (instead of 8:30 PM).
Weekday in-time remains unchanged at 8:30 PM (Sunday through Thursday).
Daily roll call on Friday and Saturday will be conducted at 10:00 PM.
All students must adhere to the biometric security verification at the main gate when entering."""
        },
        {
            "title": "College Transport Services & Route Schedule 2025-2026",
            "category": "Transport Timetable",
            "issuing_department": "Transport Office",
            "publication_date": "2025-08-01",
            "effective_from": "2025-08-05",
            "effective_until": "2026-06-30",
            "status": "CURRENT",
            "superseded_sections": None,
            "version": "2.0",
            "notes": "Official bus routes, morning pickup points, and departure schedules.",
            "content": """[Page 1]
Section 1. Bus Pass Guidelines and Identification
All students and staff commuting via college transport must carry their valid transport RFID pass. Spot checking is conducted by transport supervisors. Replacement passes for lost cards must be requested at the Transport Office (Ext. 204).

Section 2. Morning Bus Routes and Pickup Timings
Route 1 (North Line - Blue Bus):
• Central Railway Station (Main Gate): 7:00 AM
• City Plaza / Metro Station: 7:25 AM
• Green Avenue Junction: 7:45 AM
• College Campus Arrival: 8:15 AM

Route 2 (Metro Connector - Green Bus):
• Metro Pillar 140 Interchange: 7:15 AM
• Cyber Gateway / Tech Park: 7:40 AM
• College Campus Arrival: 8:20 AM

[Page 2]
Route 3 (West Suburbs - Yellow Bus):
• Outer Ring Road Junction: 6:50 AM
• Greenfield Cross / Market: 7:15 AM
• Shanti Nagar Bus Shelter: 7:35 AM
• College Campus Arrival: 8:10 AM

Route 4 (South Express - Red Bus):
• South Market Square: 7:10 AM
• Lakeview Colony Bus Stand: 7:35 AM
• Electronic City Overpass: 7:55 AM
• College Campus Arrival: 8:25 AM

Section 3. Evening Departure Schedules
On regular weekdays (Monday to Friday), all college buses depart from the Central Campus Bus Bay at 5:15 PM sharp (Route 2 departs at 5:30 PM).
On Saturdays with scheduled classes, buses depart at 1:30 PM from the main gate.
Only Route 1 and Route 2 operate on working Saturdays."""
        },
        {
            "title": "Transport Notice TR/EXAM/2024: Extended Night Services",
            "category": "Transport Notice",
            "issuing_department": "Transport Office",
            "publication_date": "2024-11-10",
            "effective_from": "2024-11-15",
            "effective_until": "2024-12-15",
            "status": "EXPIRED",
            "superseded_sections": None,
            "version": "1.0",
            "notes": "Temporary exam week transport schedule from 2024.",
            "content": """[Page 1]
Notice Ref: TR/EXAM/2024
Special Examination Extended Evening Bus Service
During the winter end-semester examinations from 15 November 2024 to 15 December 2024, an additional evening bus will depart campus at 8:00 PM serving all major transit hubs.
This service expires automatically on 15 December 2024."""
        },
        {
            "title": "Hostel Gymnasium and Laundry Timings",
            "category": "Hostel Notice",
            "issuing_department": "Hostel Administration",
            "publication_date": None,
            "effective_from": None,
            "effective_until": None,
            "status": "UNDATED",
            "superseded_sections": None,
            "version": "1.0",
            "notes": "Notice-board memo without official publication date.",
            "content": """[Page 1]
Notice to Hostel Residents: Recreation & Laundry Services
The student gymnasium located in Block C basement is open daily during:
• Morning Session: 6:00 AM to 8:30 AM
• Evening Session: 5:00 PM to 8:00 PM
Automated washing machines in the laundry room are operational from 8:00 AM to 9:00 PM. Residents must collect cleaned clothes within 30 minutes of cycle completion."""
        }
    ]

    created_docs = []
    for d in docs_data:
        content = d.pop("content")
        f_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        doc = Document(
            file_hash=f_hash,
            page_count=content.count("[Page") or 1,
            **d
        )
        db.add(doc)
        db.flush()
        created_docs.append(doc)

        chunks = chunk_document_text(content, doc.id)
        for c in chunks:
            # Set clause status
            clause_st = "CURRENT"
            if doc.status == "PARTIALLY_SUPERSEDED" and "Section 2" in c.get("section_name", ""):
                clause_st = "PARTIALLY_SUPERSEDED"
            elif doc.status == "EXPIRED":
                clause_st = "EXPIRED"
            elif doc.status == "UNDATED":
                clause_st = "UNDATED"

            c["clause_status"] = clause_st
            db.add(DocumentChunk(**c))

    # Link supersession
    handbook = next(doc for doc in created_docs if "Handbook" in doc.title)
    circular = next(doc for doc in created_docs if "Circular No. 14" in doc.title)
    circular.supersedes_document_id = handbook.id
    handbook.superseded_by_document_id = circular.id

    db.add(AuditEvent(
        action="SEED",
        target_type="KNOWLEDGE_BASE",
        target_id="SEED_V2",
        details="Seeded baseline corpus with clause-level supersession and day-range metadata."
    ))

    db.commit()
