"""
seed_pinecone_patch.py
======================
Apply this patch to scripts/seed_pinecone.py to include the new synthetic
compensation / offer / escalation / helpline RAG documents.

Two changes only:

1. Import COMPENSATION_DOCS at the top of the file (after the existing imports).
2. Extend POLICY_DOCS with COMPENSATION_DOCS before the seeding loop.

HOW TO APPLY
------------
Either copy-paste the two snippets into seed_pinecone.py, or run:

    python seed_pinecone_patch.py

This script modifies scripts/seed_pinecone.py in-place (makes a .bak first).
"""

from __future__ import annotations
import shutil
import sys
from pathlib import Path

TARGET = Path(__file__).parent.parent / "scripts" / "seed_pinecone.py"
COMP_FILE = Path(__file__).parent / "rag_compensation_docs.py"


def apply_patch(target: Path) -> None:
    if not target.exists():
        print(f"[patch] ERROR: {target} not found – run from the project root.")
        sys.exit(1)

    src = target.read_text(encoding="utf-8")

    IMPORT_ANCHOR = "from app.vector_db.pinecone_store import VectorStore, seed_default_documents"
    IMPORT_INJECT = (
        "from app.vector_db.pinecone_store import VectorStore, seed_default_documents\n"
        "\n"
        "# NEW: synthetic compensation / offer / escalation / helpline RAG docs\n"
        "from rag_compensation_docs import COMPENSATION_DOCS\n"
    )

    EXTEND_ANCHOR = '    {\n        "id": "eu_reg_1371_compensation_en",'
    EXTEND_INJECT = (
        "# Extend with new synthetic compensation & offer documents\n"
        "POLICY_DOCS.extend(COMPENSATION_DOCS)\n\n\n"
        '    {\n        "id": "eu_reg_1371_compensation_en",'
    )

    if IMPORT_ANCHOR not in src:
        print("[patch] ERROR: import anchor not found – has seed_pinecone.py changed?")
        sys.exit(1)

    if "COMPENSATION_DOCS" in src:
        print("[patch] Already patched – nothing to do.")
        return

    # Back up
    bak = target.with_suffix(".py.bak")
    shutil.copy(target, bak)
    print(f"[patch] Backup written to {bak}")

    src = src.replace(IMPORT_ANCHOR, IMPORT_INJECT, 1)
    src = src.replace(EXTEND_ANCHOR, EXTEND_INJECT, 1)

    target.write_text(src, encoding="utf-8")
    print(f"[patch] ✅ {target} patched successfully.")
    print(f"[patch]    {len(COMPENSATION_DOCS_PREVIEW)} compensation documents added to POLICY_DOCS.")


# Just for the info message
try:
    import importlib.util, os, sys
    spec = importlib.util.spec_from_file_location("rag_compensation_docs", COMP_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    COMPENSATION_DOCS_PREVIEW = mod.COMPENSATION_DOCS
except Exception:
    COMPENSATION_DOCS_PREVIEW = []


if __name__ == "__main__":
    apply_patch(TARGET)
