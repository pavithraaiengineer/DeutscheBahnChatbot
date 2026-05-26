"""
DeBian – Role-Based RAG Documents
===================================
Documents are tagged with an `access_role` metadata field that enforces
who can retrieve them:

    access_role = "customer"   → visible to customer, employee, admin
    access_role = "employee"   → visible to employee and admin only
    access_role = "admin"      → visible to admin only

The role hierarchy mirrors app/auth.py:
    ROLE_HIERARCHY = {"admin": 3, "employee": 2, "customer": 1}

Usage
-----
    from rag_role_based_docs import ROLE_BASED_DOCS
    # Seed all docs (access control is enforced at retrieval time)
    VectorStore().upsert_documents(ROLE_BASED_DOCS)

Retrieval (enforced in retriever.py / pinecone_store.py):
    # Only pass docs whose access_role level <= caller's role level
    filtered = [d for d in matches if role_level(user_role) >= role_level(d["access_role"])]

Document categories
-------------------
  EMPLOYEE-ONLY  – Occupancy data, internal SOPs, escalation procedures
  ADMIN-ONLY     – Analytics, fraud signals, financial thresholds, SLA reports
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Role level map (mirrors app/auth.py ROLE_HIERARCHY)
# ---------------------------------------------------------------------------
ROLE_HIERARCHY: dict[str, int] = {
    "customer": 1,
    "employee": 2,
    "admin": 3,
}


def is_accessible(user_role: str, doc_access_role: str) -> bool:
    """Return True if the user's role level meets or exceeds the document's required role."""
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(doc_access_role, 99)


# ---------------------------------------------------------------------------
# Schema
# {
#   "id": str,
#   "language": "en" | "de",
#   "document_type": str,
#   "category": str,
#   "region": "germany" | "eu",
#   "valid_from": "YYYY-MM-DD",
#   "valid_to":   "YYYY-MM-DD",
#   "source_url": str,
#   "confidence_score": float,
#   "access_role": "customer" | "employee" | "admin",   ← NEW field
#   "text": str,
# }
# ---------------------------------------------------------------------------

ROLE_BASED_DOCS: list[dict] = [

    # =========================================================================
    # ACCESS: employee + admin  (NOT customer)
    # Category: OCCUPANCY – real-time train capacity data
    # =========================================================================

    {
        "id": "occupancy_status_sop_en",
        "language": "en",
        "document_type": "internal_sop",
        "category": "OCCUPANCY",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/occupancy-status",
        "confidence_score": 0.97,
        "access_role": "employee",          # employee + admin only
        "text": (
            "Document ID: OCCUPANCY-SOP-001. Title: Train Occupancy Status – Internal Reference. "
            "Access: DeBian employees and administrators only. Not to be shared verbatim with customers. "
            "Purpose: This SOP defines how staff query and interpret real-time occupancy data. "
            "Data source: DB Regio live capacity feed, refreshed every 90 seconds. "
            "Occupancy codes: "
            "  GREEN  – fewer than 40% of seats occupied; freely communicate to customer. "
            "  YELLOW – 40–70% occupied; advise customer to board early or use an adjacent car. "
            "  RED    – more than 70% occupied; do NOT guarantee seating; suggest later service. "
            "  BLOCKED – car excluded from sale (technical defect, VIP reservation, or maintenance). "
            "Staff must never quote raw occupancy percentages to customers – use the colour-coded "
            "descriptions above. If the feed is unavailable (HTTP 503 or timeout > 5 s), "
            "respond with: 'Occupancy data is temporarily unavailable; please check at the platform.' "
            "Escalation: If RED occupancy persists for 3+ consecutive trains on the same corridor, "
            "flag to the capacity management team via Slack #capacity-alerts."
        ),
    },

    {
        "id": "occupancy_status_sop_de",
        "language": "de",
        "document_type": "internal_sop",
        "category": "OCCUPANCY",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/auslastungsstatus",
        "confidence_score": 0.97,
        "access_role": "employee",
        "text": (
            "Dokument-ID: OCCUPANCY-SOP-001-DE. Titel: Zugauslastungsstatus – Interne Referenz. "
            "Zugriff: Nur für DeBian-Mitarbeiter und Administratoren. Nicht wörtlich an Kunden weitergeben. "
            "Zweck: Diese SOP beschreibt, wie Mitarbeiter Echtzeit-Auslastungsdaten abrufen und interpretieren. "
            "Datenquelle: DB Regio Live-Kapazitätsfeed, Aktualisierung alle 90 Sekunden. "
            "Auslastungscodes: "
            "  GRÜN   – weniger als 40 % der Sitze belegt; kann offen an Kunden kommuniziert werden. "
            "  GELB   – 40–70 % belegt; Empfehlung: früh einsteigen oder Nachbarwagen nutzen. "
            "  ROT    – mehr als 70 % belegt; Sitzplatzgarantie NICHT zusagen; alternativen Zug empfehlen. "
            "  GESPERRT – Wagen aus dem Verkauf genommen (techn. Defekt, VIP-Reservierung oder Wartung). "
            "Mitarbeiter dürfen Kunden keine konkreten Prozentzahlen nennen – nur die obigen Farbbeschreibungen verwenden. "
            "Wenn der Feed nicht verfügbar ist (HTTP 503 oder Timeout > 5 s), antworten: "
            "'Auslastungsdaten sind vorübergehend nicht verfügbar; bitte am Bahnsteig prüfen.' "
            "Eskalation: Wenn ROT auf derselben Strecke 3+ aufeinanderfolgende Züge betrifft, "
            "Kapazitätsmanagement-Team per Slack #kapazitaet-alerts informieren."
        ),
    },

    {
        "id": "escalation_human_agent_sop_en",
        "language": "en",
        "document_type": "internal_sop",
        "category": "ESCALATION",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/escalation-procedures",
        "confidence_score": 0.98,
        "access_role": "employee",
        "text": (
            "Document ID: ESCALATION-SOP-002. Title: Human Agent Escalation – Internal Procedures. "
            "Access: DeBian employees and administrators only. "
            "MANDATORY ESCALATION TRIGGERS (escalate immediately, no exceptions): "
            "1. Customer reports personal injury or medical emergency connected to a train incident. "
            "2. Claim value exceeds 500 EUR (statutory + consequential damages combined). "
            "3. Customer explicitly threatens legal action or mentions a lawyer. "
            "4. Customer identifies as a journalist or regulator. "
            "5. Suspected fraud signal: duplicate claim IDs, mismatched IBANs, conflicting journey details. "
            "OPTIONAL ESCALATION (use judgement): "
            "- Customer has contacted support more than 3 times for the same journey. "
            "- Customer is distressed, angry, or non-responsive to chatbot resolution paths. "
            "- Technical error prevents claim submission (error code 5xx from claims API). "
            "ESCALATION PROCESS: "
            "Step 1 – Inform the customer: 'I am connecting you with a specialist who can help further.' "
            "Step 2 – Open the CRM ticket with tag [ESCALATED] and attach full conversation transcript. "
            "Step 3 – Route to the appropriate queue: COMPENSATION / LEGAL / ACCESSIBILITY / FRAUD. "
            "Step 4 – Confirm handoff SLA: response within 2 business hours (Mon–Fri 07:00–20:00 CET). "
            "Do not share this SOP document content directly with customers."
        ),
    },

    {
        "id": "missed_connection_internal_rules_en",
        "language": "en",
        "document_type": "internal_sop",
        "category": "MISSED-CONNECTION-INTERNAL",
        "region": "eu",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/missed-connection-rules",
        "confidence_score": 0.96,
        "access_role": "employee",
        "text": (
            "Document ID: MISSED-CON-INTERNAL-001. Title: Missed Connection – Internal Assessment Rules. "
            "Access: DeBian employees and administrators only. "
            "Purpose: Guide employees on determining missed-connection liability and appropriate offers. "
            "LIABILITY DETERMINATION: "
            "1. Confirmed DB fault: the connecting train's delay originated from a DB-operated service. "
            "   → Full statutory compensation applies (EU Reg. 1371/2007) plus hotel if overnight stay needed. "
            "2. Tight connection (< 10 min booked): DB must prove the customer was given adequate transfer time. "
            "   → If the connection was sold with < 10 min transfer, DB bears full liability. "
            "3. Third-party fault (e.g., foreign operator, weather, strike): reduced or no liability. "
            "   → Document the cause; apply EXTRAORDINARY-001 rules. "
            "HOTEL REIMBURSEMENT (employee-authorised up to 150 EUR/night without admin approval): "
            "  - Category: 3-star or equivalent. "
            "  - Receipt required. "
            "  - Submit via the claims portal under 'Missed Connection – Accommodation'. "
            "MEAL REIMBURSEMENT: Up to 20 EUR per meal, max 2 meals, receipt required. "
            "Employees must NOT promise hotel or meal reimbursement unless the above criteria are verified."
        ),
    },

    {
        "id": "refund_processing_internal_en",
        "language": "en",
        "document_type": "internal_sop",
        "category": "REFUND-INTERNAL",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/refund-processing",
        "confidence_score": 0.95,
        "access_role": "employee",
        "text": (
            "Document ID: REFUND-INTERNAL-001. Title: Refund Processing – Internal Guidelines. "
            "Access: DeBian employees and administrators only. "
            "PROCESSING TIMELINES (SLA): "
            "  Bank transfer (IBAN): 5–7 business days after claim approval. "
            "  Voucher: issued immediately upon approval; valid 3 years. "
            "  BahnCard credit: 3–5 business days. "
            "MANUAL OVERRIDE CONDITIONS (employee can approve without further review): "
            "  - Claim value ≤ 50 EUR AND journey is confirmed in the booking system. "
            "  - Customer is a verified BahnCard 100 holder. "
            "  - Repeat claim for the same confirmed delayed journey (duplicate auto-merged). "
            "HOLDS & BLOCKS: "
            "  - Place a HOLD if the customer's IBAN has failed a previous bank transfer. "
            "  - Place a FRAUD BLOCK if the fraud scoring model returns > 0.75 probability. "
            "    Fraud-blocked claims must be reviewed by a senior agent before any payout. "
            "AUDIT: All manual overrides are logged to audit_log.jsonl with the employee's user_id. "
            "Do not share processing timelines or fraud thresholds with customers."
        ),
    },

    # =========================================================================
    # ACCESS: admin only (NOT employee, NOT customer)
    # Category: ANALYTICS – system performance and business intelligence
    # =========================================================================

    {
        "id": "analytics_dashboard_sop_en",
        "language": "en",
        "document_type": "admin_sop",
        "category": "ANALYTICS",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://admin/analytics-dashboard",
        "confidence_score": 0.99,
        "access_role": "admin",             # admin only
        "text": (
            "Document ID: ANALYTICS-ADMIN-001. Title: Analytics Dashboard – Administrator Guide. "
            "Access: DeBian administrators only. CONFIDENTIAL. "
            "Dashboard URL: internal://admin/dashboard (requires admin JWT). "
            "KEY METRICS: "
            "  - Daily Active Users (DAU): total unique sessions per calendar day. "
            "  - Resolution Rate: percentage of conversations resolved without human escalation. Target: ≥ 85%. "
            "  - Mean Time to Resolution (MTTR): average minutes from first user message to claim closed. Target: < 4 min. "
            "  - Escalation Rate: percentage of sessions that triggered a human agent. Alert if > 15%. "
            "  - Compensation Payout Volume: total EUR disbursed per day/week/month. "
            "  - Fraud Block Rate: percentage of claims flagged by the fraud model. "
            "ALERT THRESHOLDS (auto-paged to #admin-alerts Slack): "
            "  Escalation Rate > 20% for > 30 minutes. "
            "  Fraud Block Rate > 5% in any 1-hour window. "
            "  Payout volume exceeds 10,000 EUR in a single hour. "
            "  API error rate (5xx) > 2% over 5 minutes. "
            "REPORT SCHEDULE: "
            "  Daily summary: 08:00 CET → admin@bahn.de. "
            "  Weekly PDF report: Mondays 07:00 CET. "
            "  Monthly board pack: 1st of each month, 06:00 CET. "
            "Access to this document is restricted to administrators. Employees should request analytics "
            "summaries through their team lead."
        ),
    },

    {
        "id": "fraud_detection_thresholds_en",
        "language": "en",
        "document_type": "admin_sop",
        "category": "FRAUD",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://admin/fraud-thresholds",
        "confidence_score": 0.99,
        "access_role": "admin",
        "text": (
            "Document ID: FRAUD-ADMIN-001. Title: Fraud Detection Thresholds & Model Parameters. "
            "Access: DeBian administrators only. STRICTLY CONFIDENTIAL – do not share with employees or customers. "
            "FRAUD MODEL: XGBoost binary classifier, retrained weekly on claims data. "
            "FEATURE WEIGHTS (top signals, descending importance): "
            "  1. IBAN change within 48 h of a new claim submission. "
            "  2. Journey date outside the valid ticket window by > 1 day. "
            "  3. Claim submitted for a train with 0 reported delays in the DB feed. "
            "  4. More than 3 claims by the same customer_id in a 30-day rolling window. "
            "  5. IP address geo-mismatch with the registered account country by > 500 km. "
            "THRESHOLD TABLE: "
            "  Score 0.00–0.49: auto-approve (no fraud flag). "
            "  Score 0.50–0.74: soft flag – employee review required before payout. "
            "  Score 0.75–0.89: hard block – senior agent + second pair of eyes required. "
            "  Score 0.90–1.00: auto-reject + case opened in FRAUD_REVIEW queue. "
            "MODEL PERFORMANCE (last calibration 2026-04-01): "
            "  Precision: 0.91 | Recall: 0.87 | F1: 0.89 | AUC-ROC: 0.96. "
            "RETRAINING SCHEDULE: every Monday 02:00 CET (automated pipeline, Databricks). "
            "ADMIN OVERRIDE: Administrator can manually override a fraud block via the admin portal. "
            "All overrides are audited and must include a written justification."
        ),
    },

    {
        "id": "financial_sla_thresholds_en",
        "language": "en",
        "document_type": "admin_sop",
        "category": "FINANCIAL-SLA",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://admin/financial-sla",
        "confidence_score": 0.98,
        "access_role": "admin",
        "text": (
            "Document ID: FINANCIAL-SLA-ADMIN-001. Title: Financial Approval Thresholds & SLA Commitments. "
            "Access: DeBian administrators only. CONFIDENTIAL. "
            "PURPOSE: Define monetary limits at each approval level and contractual SLA commitments. "
            "APPROVAL TIERS: "
            "  Automated (no human review): ≤ 50 EUR, verified journey, no fraud flag. "
            "  Employee approval: 51–250 EUR, verified journey, fraud score < 0.50. "
            "  Admin approval: 251–500 EUR, or any claim with a fraud score 0.50–0.74. "
            "  Legal review (legal@bahn.de): > 500 EUR, or any claim citing consequential damages. "
            "PAYMENT SLA COMMITMENTS (contractual, as per DB Passenger Charter 2026): "
            "  Bank transfer: ≤ 7 business days from claim approval. "
            "  Voucher: ≤ 24 hours from approval (email delivery). "
            "SLA BREACH PROTOCOL: "
            "  If SLA is breached, automatically add a 10 EUR goodwill top-up to the payout. "
            "  Breaches exceeding 10 business days must be reported to the compliance team. "
            "BUDGET CAPS (monthly, reset on the 1st): "
            "  Automated payouts: 200,000 EUR. Alert admin if 80% consumed by the 20th. "
            "  Goodwill top-ups: 10,000 EUR. Suspend if exceeded; admin manual approval required. "
            "This document is for administrator use only. Do not expose these thresholds to employees."
        ),
    },

    {
        "id": "system_configuration_admin_en",
        "language": "en",
        "document_type": "admin_sop",
        "category": "SYSTEM-CONFIG",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://admin/system-config",
        "confidence_score": 0.99,
        "access_role": "admin",
        "text": (
            "Document ID: SYSCONFIG-ADMIN-001. Title: System Configuration & Infrastructure Reference. "
            "Access: DeBian administrators only. HIGHLY CONFIDENTIAL. "
            "ARCHITECTURE SUMMARY: "
            "  Frontend: Streamlit (port 8501). "
            "  Backend API: FastAPI (port 8080), deployed on GKE. "
            "  Vector DB: Pinecone index 'debian-rag' (dimension 128, cosine metric). "
            "  Auth: HMAC-SHA256 token, secret stored in GCP Secret Manager as 'debian-auth-secret'. "
            "  Session store: Google Firestore (collection: debian_sessions). "
            "  Fraud model: Databricks MLflow registry, model alias 'fraud-prod'. "
            "  Analytics pipeline: Databricks Delta Lake (bronze/silver/gold layers). "
            "ENVIRONMENT VARIABLES (production): "
            "  AUTH_SECRET      – rotate every 90 days; last rotated 2026-03-01. "
            "  PINECONE_API_KEY – stored in GCP Secret Manager as 'pinecone-api-key'. "
            "  OPENAI_API_KEY   – stored in GCP Secret Manager as 'openai-api-key'. "
            "  DATABRICKS_TOKEN – stored in GCP Secret Manager as 'databricks-token'. "
            "MAINTENANCE WINDOWS: Tuesdays 01:00–03:00 CET (planned). "
            "DISASTER RECOVERY: RTO 4 hours, RPO 1 hour. Runbook: internal://admin/dr-runbook. "
            "LOGGING: All admin actions logged to audit_log.jsonl and forwarded to GCP Cloud Logging. "
            "This document must not leave the admin channel. Rotation of secrets must be logged."
        ),
    },

    {
        "id": "fleet_occupancy_overview_admin_en",
        "language": "en",
        "document_type": "admin_sop",
        "category": "FLEET-OCCUPANCY",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://admin/fleet-occupancy",
        "confidence_score": 0.97,
        "access_role": "admin",
        "text": (
            "Document ID: FLEET-ADMIN-001. Title: Full Fleet Occupancy Overview – Administrator Access. "
            "Access: DeBian administrators only. "
            "This document provides administrators with the complete fleet occupancy dataset, "
            "including suppressed figures not available to employees. "
            "FULL OCCUPANCY DATA FIELDS (admin-only): "
            "  - Exact seat occupancy percentage per car (e.g., 83.4% in car 7 of ICE 1234). "
            "  - Reservation-vs-walk-in ratio per service. "
            "  - First-class vs. second-class split per train. "
            "  - Revenue yield per occupied seat (linked to pricing model). "
            "  - Unannounced capacity reductions (fleet technical faults pending repair). "
            "FLEET HEALTH THRESHOLDS: "
            "  < 60% fleet average: no action needed. "
            "  60–75%: consider activating additional rolling stock (contact operations). "
            "  > 75%: escalate to capacity management; consider temporary price cap override. "
            "SENSITIVE INFORMATION: Unannounced capacity reductions are commercially sensitive. "
            "Do not share with employees or customers until the public communications team "
            "issues a service bulletin. "
            "Report cadence: updated every 5 minutes from DB Regio live feed. "
            "Admin dashboard widget: 'Fleet Health' (top-right panel)."
        ),
    },

    {
        "id": "user_management_admin_en",
        "language": "en",
        "document_type": "admin_sop",
        "category": "USER-MANAGEMENT",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://admin/user-management",
        "confidence_score": 0.98,
        "access_role": "admin",
        "text": (
            "Document ID: USERMGMT-ADMIN-001. Title: User & Role Management – Administrator Procedures. "
            "Access: DeBian administrators only. "
            "ROLE ASSIGNMENT RULES: "
            "  - Only administrators can assign or promote a user to 'employee' or 'admin'. "
            "  - New registrations default to 'customer' role. "
            "  - Role promotion requires written approval from a second administrator (four-eyes principle). "
            "  - Admin role must be approved by the Head of Operations. "
            "ACCOUNT LIFECYCLE: "
            "  - Inactive accounts (> 365 days no login): auto-suspend, flagged for admin review. "
            "  - Suspended accounts: access disabled but data retained for 90 days per GDPR. "
            "  - Deletion requests (GDPR Article 17): must be completed within 30 days. "
            "    Use the admin portal: Settings > User Management > Delete User (permanent). "
            "AUDIT REQUIREMENTS: "
            "  - All role changes logged to audit_log.jsonl with: timestamp, admin_user_id, target_user_id, old_role, new_role. "
            "  - Quarterly access review: administrators must certify that all employee/admin accounts are still valid. "
            "EMERGENCY LOCKOUT: "
            "  If a compromised admin account is suspected, use the emergency lockout API: "
            "    POST /admin/lockout/{user_id} with a valid second admin token. "
            "  Immediately rotate AUTH_SECRET and notify the security team."
        ),
    },
]


# ---------------------------------------------------------------------------
# Helper: filter docs by caller role at retrieval time
# ---------------------------------------------------------------------------

def filter_by_role(documents: list[dict], user_role: str) -> list[dict]:
    """
    Return only documents that the given user_role is allowed to see.

    Args:
        documents: list of RAG document dicts (must include 'access_role' key).
        user_role: the authenticated user's role string ('customer', 'employee', 'admin').

    Returns:
        Filtered list containing only accessible documents.
    """
    return [
        doc for doc in documents
        if is_accessible(user_role, doc.get("access_role", "admin"))
    ]


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Total role-based RAG documents: {len(ROLE_BASED_DOCS)}\n")

    for role in ("customer", "employee", "admin"):
        visible = filter_by_role(ROLE_BASED_DOCS, role)
        print(f"  [{role.upper():8s}] can access {len(visible)}/{len(ROLE_BASED_DOCS)} documents:")
        for doc in visible:
            print(f"             - {doc['id']}  (access_role={doc['access_role']})")
        print()
