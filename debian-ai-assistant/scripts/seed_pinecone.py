#!/usr/bin/env python3
"""
DeBian Pinecone Seeder
======================
Seeds the Pinecone index with:
  1. Built-in policy / FAQ / compensation documents
  2. Optional Kaggle DB delay dataset (if credentials available)

Usage
-----
  # Seed built-in docs only (no Kaggle creds needed):
  python scripts/seed_pinecone.py

  # Seed built-in docs + Kaggle dataset:
  KAGGLE_USERNAME=yourname KAGGLE_KEY=yourkey python scripts/seed_pinecone.py --kaggle

  # Dry-run (prints what would be upserted, no network calls):
  python scripts/seed_pinecone.py --dry-run

Kaggle Dataset
--------------
  Name : Deutsche Bahn – Actual and Planned Departure Times
  URL  : https://www.kaggle.com/datasets/nokkyu/deutsche-bahn-db-actual-and-planned-departure
  Size : ~150 MB (CSV, 2015–2023)

  Columns used:
    train_type, train_no, station_from, station_to,
    scheduled_departure, actual_departure, delay_minutes

Pinecone Setup
--------------
  1. Create account: https://app.pinecone.io
  2. Create index:
       Name      : debian-rag
       Dimension : 128
       Metric    : cosine
  3. Copy API key to .env:
       PINECONE_API_KEY=your_key_here
       PINECONE_INDEX_NAME=debian-rag
       PINECONE_DIMENSION=128
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import hashlib
import re
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import load_env
load_env()

from app.vector_db.pinecone_store import VectorStore, seed_default_documents


# ---------------------------------------------------------------------------
# Rich policy corpus (seeded regardless of Kaggle)
# ---------------------------------------------------------------------------

POLICY_DOCS = [
    {
        "id": "eu_reg_1371_compensation_en",
        "language": "en",
        "document_type": "passenger_rights",
        "region": "eu",
        "valid_from": "2009-12-03",
        "valid_to": "2099-12-31",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:32007R1371",
        "confidence_score": 0.99,
        "text": (
            "EU Regulation 1371/2007 on rail passengers' rights and obligations. "
            "Article 17: Passengers are entitled to compensation from the railway undertaking if they face a delay. "
            "The minimum compensation is 25% of the ticket price for a delay of 60 to 119 minutes, "
            "and 50% for a delay of 120 minutes or more. "
            "Compensation is not due when the passenger was informed before purchasing the ticket, "
            "or if the delay is caused by extraordinary circumstances. "
            "Claims must be submitted within one year of the delayed journey."
        ),
    },
    {
        "id": "eu_reg_1371_compensation_de",
        "language": "de",
        "document_type": "passenger_rights",
        "region": "eu",
        "valid_from": "2009-12-03",
        "valid_to": "2099-12-31",
        "source_url": "https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=celex:32007R1371",
        "confidence_score": 0.99,
        "text": (
            "EU-Verordnung 1371/2007 über die Rechte und Pflichten der Fahrgäste im Eisenbahnverkehr. "
            "Artikel 17: Bei Verspätung haben Fahrgäste Anspruch auf Entschädigung. "
            "Bei 60–119 Minuten Verspätung: 25 % des Fahrpreises. "
            "Bei 120 Minuten oder mehr: 50 % des Fahrpreises. "
            "Ansprüche müssen innerhalb eines Jahres nach der verspäteten Fahrt eingereicht werden."
        ),
    },
    {
        "id": "db_fahrgastrechte_antrag_de",
        "language": "de",
        "document_type": "claim_process",
        "region": "germany",
        "valid_from": "2024-01-01",
        "valid_to": "2099-12-31",
        "source_url": "https://www.bahn.de/service/informationen/fahrgastrechte",
        "confidence_score": 0.97,
        "text": (
            "Fahrgastrechte-Antrag bei der Deutschen Bahn. "
            "Schritt 1: Originale Fahrkarte aufbewahren und abstempeln lassen. "
            "Schritt 2: Fahrgastrechte-Formular ausfüllen (online unter bahn.de oder am Schalter). "
            "Schritt 3: Antrag innerhalb von 12 Monaten einreichen. "
            "Entschädigung: 25 % bei 60–119 Min. Verspätung, 50 % ab 120 Min. "
            "Erstattung per Banküberweisung oder als Gutschein möglich. "
            "IBAN für Banküberweisung angeben – nur die letzten 4 Ziffern werden im System angezeigt."
        ),
    },
    {
        "id": "db_delay_causes_en",
        "language": "en",
        "document_type": "operations",
        "region": "germany",
        "valid_from": "2024-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://delay-causes",
        "confidence_score": 0.91,
        "text": (
            "Common causes of DB train delays include: infrastructure defects on the track, "
            "signal failures, cascading delays from late arrivals on shared corridors, "
            "staff unavailability, weather events (ice, floods), and track works. "
            "ICE and IC services on high-speed lines tend to have higher punctuality than RE/RB regional trains. "
            "Delays above 60 minutes entitle the passenger to compensation under EU Regulation 1371/2007."
        ),
    },
    {
        "id": "db_occupancy_guidance_en",
        "language": "en",
        "document_type": "employee_sop",
        "region": "germany",
        "valid_from": "2024-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://occupancy-sop",
        "confidence_score": 0.94,
        "text": (
            "DB Internal SOP: Occupancy Monitoring. "
            "Trains with occupancy above 80% are classified as FULL. "
            "Trains between 50–80% are HIGH. Below 50% is LOW. "
            "When a train is full, employees should advise passengers to take the next available service "
            "or an alternative route. Employees and administrators can view occupancy via the DeBian dashboard. "
            "Customers are informed of general availability but do not see raw occupancy percentages."
        ),
    },
    {
        "id": "db_refund_iban_en",
        "language": "en",
        "document_type": "refund",
        "region": "germany",
        "valid_from": "2024-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://refund-iban",
        "confidence_score": 0.96,
        "text": (
            "Refund via bank account: The passenger provides an IBAN. "
            "For privacy, DeBian only displays the last 4 digits of the IBAN in all chat responses and receipts. "
            "The full IBAN is stored encrypted in the user profile and transmitted securely to the payment processor. "
            "Processing time: 5–10 business days. "
            "Alternatively, a voucher (Gutschein) valid for 3 years on all DB services can be issued immediately."
        ),
    },
    {
        "id": "db_booking_en",
        "language": "en",
        "document_type": "booking",
        "region": "germany",
        "valid_from": "2024-01-01",
        "valid_to": "2099-12-31",
        "source_url": "https://www.bahn.de",
        "confidence_score": 0.93,
        "text": (
            "DB ticket booking: Tickets can be purchased via the DB Navigator app, bahn.de, or at DB stations. "
            "Sparpreis tickets are available from 17.90 EUR for 2nd class, non-refundable. "
            "Flexpreis tickets are fully refundable. "
            "BahnCard 25 gives 25% discount, BahnCard 50 gives 50% discount. "
            "ICE connections between major cities run every hour. "
            "Seat reservation is 4.50 EUR extra and optional."
        ),
    },
    {
        "id": "db_station_services_en",
        "language": "en",
        "document_type": "station_faq",
        "region": "germany",
        "valid_from": "2024-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://station-services",
        "confidence_score": 0.90,
        "text": (
            "DB stations offer: DB Reisezentrum (travel center), lockers, lost property office, "
            "DB Lounge for 1st class passengers, Wi-Fi, DB Service Point. "
            "Frankfurt Hauptbahnhof, Berlin Hauptbahnhof, München Hauptbahnhof, Hamburg Hauptbahnhof, "
            "and Köln Hauptbahnhof are major interchange hubs. "
            "Accessibility: assistance can be arranged at db-barrierefrei.de or +49 30 65 21 28 88."
        ),
    },
    {
        "id": "db_role_access_en",
        "language": "en",
        "document_type": "internal_sop",
        "region": "germany",
        "valid_from": "2024-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://role-access",
        "confidence_score": 0.98,
        "text": (
            "DeBian Role-Based Access: "
            "Customer role – can check train delays, file compensation claims, add IBAN for refunds. "
            "Employee role – all customer permissions plus train occupancy status. "
            "Admin role – all employee permissions plus full analytics dashboard, fleet occupancy overview, "
            "revenue reports, delay statistics, and compensation trend analysis."
        ),
    },
]


# ---------------------------------------------------------------------------
# Kaggle dataset loader
# ---------------------------------------------------------------------------

def load_kaggle_docs(max_rows: int = 500) -> list[dict]:
    """
    Downloads and converts the DB delay Kaggle dataset into RAG documents.
    Requires: KAGGLE_USERNAME and KAGGLE_KEY env vars, kaggle pip package.
    """
    try:
        import kaggle  # noqa: F401
    except ImportError:
        print("  [kaggle] pip install kaggle  →  skipping Kaggle import.")
        return []

    import tempfile
    import csv

    dataset = "nokkyu/deutsche-bahn-db-actual-and-planned-departure"
    print(f"  [kaggle] Downloading dataset: {dataset}")
    with tempfile.TemporaryDirectory() as tmpdir:
        os.system(f"kaggle datasets download -d {dataset} -p {tmpdir} --unzip")
        csv_files = list(Path(tmpdir).glob("*.csv"))
        if not csv_files:
            print("  [kaggle] No CSV found after download.")
            return []

        csv_path = csv_files[0]
        print(f"  [kaggle] Loading {csv_path.name} …")
        docs = []
        with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                train_type = row.get("train_type", "")
                train_no   = row.get("train_no", "")
                origin     = row.get("station_from", "")
                dest       = row.get("station_to", "")
                delay      = row.get("delay_minutes", "0")
                sched      = row.get("scheduled_departure", "")

                try:
                    delay_min = int(float(delay))
                except (ValueError, TypeError):
                    delay_min = 0

                status = "on time" if delay_min < 5 else f"delayed {delay_min} min"
                text = (
                    f"{train_type} {train_no}: {origin} → {dest}. "
                    f"Scheduled: {sched}. Status: {status}. "
                    f"{'Delay compensation may apply.' if delay_min >= 60 else ''}"
                )
                doc_id = hashlib.md5(text.encode()).hexdigest()[:12]
                docs.append({
                    "id": f"kaggle_{doc_id}",
                    "language": "en",
                    "document_type": "delay_record",
                    "region": "germany",
                    "train_type": train_type,
                    "train_number": f"{train_type} {train_no}",
                    "origin": origin,
                    "destination": dest,
                    "delay_minutes": delay_min,
                    "source_url": f"kaggle://{dataset}",
                    "confidence_score": 0.85,
                    "text": text,
                })

        print(f"  [kaggle] Prepared {len(docs)} documents.")
        return docs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed DeBian Pinecone index")
    parser.add_argument("--kaggle", action="store_true", help="Also seed from Kaggle DB dataset")
    parser.add_argument("--dry-run", action="store_true", help="Print docs without upserting")
    parser.add_argument("--max-kaggle-rows", type=int, default=500)
    args = parser.parse_args()

    vs = VectorStore()
    print(f"\n[seed] Vector store mode: {vs.mode}")
    if vs.mode == "local":
        print("[seed] TIP: Set PINECONE_API_KEY in .env for cloud storage.")
    print(f"[seed] Upserting {len(POLICY_DOCS)} policy / FAQ documents …")

    if args.dry_run:
        for d in POLICY_DOCS:
            print(f"  DRY-RUN  id={d['id']}  type={d['document_type']}  lang={d['language']}")
    else:
        result = vs.upsert_documents(POLICY_DOCS)
        print(f"  ✓ {result}")

    # Built-in seed_default_documents (legacy)
    if not args.dry_run:
        legacy = seed_default_documents()
        print(f"  ✓ Legacy seed: {legacy}")

    if args.kaggle:
        print(f"\n[seed] Loading Kaggle dataset (max {args.max_kaggle_rows} rows) …")
        kaggle_docs = load_kaggle_docs(args.max_kaggle_rows)
        if kaggle_docs:
            if args.dry_run:
                for d in kaggle_docs[:5]:
                    print(f"  DRY-RUN  id={d['id']}  train={d.get('train_number')}  delay={d.get('delay_minutes')}min")
                print(f"  … and {len(kaggle_docs)-5} more.")
            else:
                result = vs.upsert_documents(kaggle_docs)
                print(f"  ✓ Kaggle: {result}")
        else:
            print("  [skipped] No Kaggle docs loaded.")
    else:
        print("\n[seed] Skipped Kaggle. Use --kaggle to include delay records.")

    print("\n[seed] ✅ Done.\n")
    print("Next steps:")
    print("  1. To use Pinecone cloud: set PINECONE_API_KEY in .env")
    print("  2. To seed Kaggle data:  python scripts/seed_pinecone.py --kaggle")
    print("     (requires: pip install kaggle  +  KAGGLE_USERNAME / KAGGLE_KEY in .env)")
    print("  3. Kaggle dataset URL:")
    print("     https://www.kaggle.com/datasets/nokkyu/deutsche-bahn-db-actual-and-planned-departure")


if __name__ == "__main__":
    main()
