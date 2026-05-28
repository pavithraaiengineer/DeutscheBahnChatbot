"""
LangSmith LLM-as-a-Judge Evaluation — DeBian RAG Pipeline
==========================================================

What this module does
---------------------
1. Creates (or syncs) a LangSmith Dataset called ``debian-rag-dataset``
   populated from the 20 canonical RAG test cases already defined in
   ``langsmith_rag_eval.py``.
2. Defines three LLM-as-a-Judge evaluators that mirror the templates you
   see in the LangSmith UI:
     - ``llm_correctness``   — does the answer semantically match a reference?
     - ``llm_faithfulness``  — is the answer grounded in the retrieved context?
     - ``llm_relevance``     — is the answer relevant to the question asked?
3. Runs ``langsmith.evaluate()`` which:
     a. Pulls every example from the dataset.
     b. Calls the *target function* (your live RAG + agent pipeline) for
        each example.
     c. Sends each (input, output, reference) triple to GPT-4o-mini for
        scoring.
     d. Uploads all scores as LangSmith feedback and links them to the
        experiment run visible in the LangSmith UI.

Setup — add to .env
-------------------
    LANGSMITH_API_KEY=lsv2_...
    LANGSMITH_PROJECT=DBchatbot          # already set in your .env
    LANGCHAIN_TRACING_V2=true
    OPENAI_API_KEY=sk-...                # already set — used by the judge LLM

Run
---
    python -m app.evaluation.langsmith_llm_judge_eval

View results
------------
    https://smith.langchain.com  →  DBchatbot  →  Datasets & Experiments
"""

from __future__ import annotations

import os
from typing import Any

from app.config import get_env

# ── Optional LangSmith imports (graceful degradation) ──────────────────────

def _require_langsmith():
    api_key = get_env("LANGSMITH_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "LANGSMITH_API_KEY is not set. Add it to your .env file.\n"
            "Get a key at https://smith.langchain.com → Settings → API Keys"
        )
    try:
        from langsmith import Client
        return Client(api_key=api_key), api_key
    except ImportError:
        raise ImportError(
            "langsmith package not installed.\n"
            "Run: pip install langsmith"
        )


# ── Dataset name & description ──────────────────────────────────────────────

DATASET_NAME = "debian-rag-dataset"
DATASET_DESCRIPTION = (
    "Canonical 20-case RAG evaluation dataset for the DeBian AI assistant. "
    "Covers customer / employee / admin roles, EN + DE languages, "
    "relevance checks and access-control (forbidden doc) checks."
)

# ── Examples imported from the existing eval module ─────────────────────────

def _build_examples() -> list[dict]:
    """Convert RAG_TEST_CASES into LangSmith example dicts."""
    from app.evaluation.langsmith_rag_eval import RAG_TEST_CASES

    examples = []
    for tc in RAG_TEST_CASES:
        examples.append(
            {
                # ---- inputs (what the agent receives) ----
                "inputs": {
                    "question":    tc.query,
                    "language":    tc.language,
                    "user_role":   tc.user_role,
                },
                # ---- reference outputs (ground-truth for the judge) ----
                "outputs": {
                    "expected_doc_ids":  tc.expected_doc_ids,
                    "forbidden_doc_ids": tc.forbidden_doc_ids,
                    "description":       tc.description,
                    # Human-readable reference answer used by the LLM judge.
                    # We phrase it as a policy statement so the judge has
                    # something concrete to compare against.
                    "reference_answer": (
                        f"The answer should address: {tc.description}. "
                        f"Relevant document IDs include: {tc.expected_doc_ids}. "
                        f"The response must NOT reveal documents: {tc.forbidden_doc_ids}."
                        if tc.expected_doc_ids
                        else (
                            f"No internal documents should be revealed. "
                            f"Forbidden document IDs: {tc.forbidden_doc_ids}."
                        )
                    ),
                },
                # ---- stable external ID so re-runs don't create duplicates ----
                "dataset_split": ["base"],
                "metadata": {
                    "test_case_id": tc.id,
                    "user_role":    tc.user_role,
                    "language":     tc.language,
                },
            }
        )
    return examples


# ── Dataset sync ─────────────────────────────────────────────────────────────

def sync_dataset(client) -> Any:
    """
    Create the dataset if it does not exist; add any missing examples.
    Returns the LangSmith Dataset object.
    """
    # Try to fetch existing dataset
    dataset = None
    for ds in client.list_datasets():
        if ds.name == DATASET_NAME:
            dataset = ds
            break

    if dataset is None:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description=DATASET_DESCRIPTION,
        )
        print(f"[Dataset] Created new dataset: '{DATASET_NAME}'  id={dataset.id}")
    else:
        print(f"[Dataset] Found existing dataset: '{DATASET_NAME}'  id={dataset.id}")

    # Fetch existing example IDs (by metadata.test_case_id) to avoid dupes
    existing_ids: set[str] = set()
    for ex in client.list_examples(dataset_id=dataset.id):
        tc_id = (ex.metadata or {}).get("test_case_id")
        if tc_id:
            existing_ids.add(tc_id)

    new_examples = [
        e for e in _build_examples()
        if e["metadata"]["test_case_id"] not in existing_ids
    ]

    if new_examples:
        client.create_examples(
            dataset_id=dataset.id,
            inputs=[e["inputs"] for e in new_examples],
            outputs=[e["outputs"] for e in new_examples],
            metadata=[e["metadata"] for e in new_examples],
        )
        print(f"[Dataset] Added {len(new_examples)} new example(s). "
              f"({len(existing_ids)} already present)")
    else:
        print(f"[Dataset] All {len(existing_ids)} examples already synced — nothing to add.")

    return dataset


# ── Target function (the system under test) ─────────────────────────────────

def _target(inputs: dict) -> dict:
    """
    Run the live DeBian RAG pipeline for a single dataset example.
    Returns a dict with ``answer`` and ``retrieved_doc_ids``.
    """
    from app.rag.retriever import search_rag
    from app.agents.debian_agent import DeBianAgent

    question  = inputs["question"]
    language  = inputs.get("language", "en")
    user_role = inputs.get("user_role", "customer")

    # 1. Retrieve documents
    rag_result    = search_rag(question, language=language, top_k=5, user_role=user_role)
    documents     = rag_result.get("documents", [])
    retrieved_ids = [
        doc.get("id") or doc.get("metadata", {}).get("id", "")
        for doc in documents
    ]

    # 2. Generate answer via the agent
    agent  = DeBianAgent()
    result = agent.respond(
        message=question,
        payload={"language": language},
        user_role=user_role,
    )
    answer = result.get("response", "")

    # Build context string for faithfulness judge
    context_texts = [
        doc.get("metadata", {}).get("text", "") or doc.get("text", "")
        for doc in documents
    ]
    context = "\n\n".join(filter(None, context_texts))

    return {
        "answer":            answer,
        "retrieved_doc_ids": retrieved_ids,
        "context":           context,
    }


# ── LLM-as-a-Judge evaluators ────────────────────────────────────────────────

def _make_openai_judge():
    """Return a lightweight OpenAI chat completion caller for the judge."""
    try:
        from openai import OpenAI
        return OpenAI(api_key=get_env("OPENAI_API_KEY", ""))
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")


def _judge_score(client_openai, system_prompt: str, user_prompt: str) -> float:
    """
    Ask the judge LLM to output ONLY a float between 0 and 1.
    Returns 0.0 on any error.
    """
    try:
        resp = client_openai.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=10,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        return max(0.0, min(1.0, float(raw)))
    except Exception:
        return 0.0


# ---- Correctness evaluator -------------------------------------------------

def eval_correctness(run, example) -> dict:
    """
    LLM judge: does the generated answer semantically match the reference?
    Mirrors the LangSmith 'Correctness' template.
    """
    openai = _make_openai_judge()

    answer    = (run.outputs or {}).get("answer", "")
    reference = (example.outputs or {}).get("reference_answer", "")

    system = (
        "You are a strict but fair evaluator. "
        "Score how well the ANSWER matches the REFERENCE on a scale 0.0–1.0. "
        "1.0 = fully correct and complete. 0.0 = wrong or contradicts the reference. "
        "Output ONLY the decimal number, nothing else."
    )
    user = f"REFERENCE:\n{reference}\n\nANSWER:\n{answer}"

    score = _judge_score(openai, system, user)
    return {"key": "llm_correctness", "score": score}


# ---- Faithfulness evaluator ------------------------------------------------

def eval_faithfulness(run, example) -> dict:
    """
    LLM judge: is the answer grounded in the retrieved context?
    Mirrors the LangSmith 'Hallucination' template (inverted: faithfulness = 1 - hallucination).
    """
    openai  = _make_openai_judge()
    outputs = run.outputs or {}
    answer  = outputs.get("answer", "")
    context = outputs.get("context", "")

    if not context:
        # No context retrieved — cannot assess faithfulness
        return {"key": "llm_faithfulness", "score": None}

    system = (
        "You are a factual-consistency checker. "
        "Score how faithfully the ANSWER is supported by the CONTEXT on a scale 0.0–1.0. "
        "1.0 = every claim in the answer is traceable to the context. "
        "0.0 = the answer contains facts that contradict or are absent from the context. "
        "Output ONLY the decimal number, nothing else."
    )
    user = f"CONTEXT:\n{context}\n\nANSWER:\n{answer}"

    score = _judge_score(openai, system, user)
    return {"key": "llm_faithfulness", "score": score}


# ---- Relevance evaluator ---------------------------------------------------

def eval_relevance(run, example) -> dict:
    """
    LLM judge: is the answer relevant to the original question?
    Mirrors the LangSmith 'User Satisfaction' / relevance template.
    """
    openai   = _make_openai_judge()
    question = (example.inputs or {}).get("question", "")
    answer   = (run.outputs or {}).get("answer", "")

    system = (
        "You are a relevance evaluator. "
        "Score how directly the ANSWER addresses the QUESTION on a scale 0.0–1.0. "
        "1.0 = answer fully and directly addresses the question. "
        "0.0 = answer is off-topic or does not address the question at all. "
        "Output ONLY the decimal number, nothing else."
    )
    user = f"QUESTION:\n{question}\n\nANSWER:\n{answer}"

    score = _judge_score(openai, system, user)
    return {"key": "llm_relevance", "score": score}


# ---- Access-control evaluator (rule-based, not LLM) -----------------------

def eval_access_control(run, example) -> dict:
    """
    Rule-based check: none of the forbidden document IDs appear in the
    retrieved set.  Score 1.0 = clean, 0.0 = at least one forbidden doc leaked.
    """
    retrieved = set((run.outputs or {}).get("retrieved_doc_ids", []))
    forbidden = set((example.outputs or {}).get("forbidden_doc_ids", []))
    leaked    = retrieved & forbidden
    score     = 0.0 if leaked else 1.0
    comment   = f"Leaked: {list(leaked)}" if leaked else "No forbidden docs leaked."
    return {"key": "access_control", "score": score, "comment": comment}


# ── Main runner ───────────────────────────────────────────────────────────────

def run_llm_judge_eval(experiment_prefix: str = "debian-llm-judge") -> dict:
    """
    Full pipeline:
      1. Sync the LangSmith dataset.
      2. Run langsmith.evaluate() with LLM-as-judge evaluators.
      3. Return the experiment summary URL.
    """
    client, _ = _require_langsmith()

    # Ensure tracing is enabled
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", get_env("LANGSMITH_PROJECT", "DBchatbot"))

    # 1. Sync dataset
    dataset = sync_dataset(client)

    # 2. Run evaluation
    print(f"\n[Evaluate] Starting experiment '{experiment_prefix}' …")
    try:
        from langsmith.evaluation import evaluate
    except ImportError:
        raise ImportError(
            "langsmith>=0.1.0 is required.\n"
            "Run: pip install 'langsmith>=0.1.0'"
        )

    results = evaluate(
        _target,
        data=DATASET_NAME,
        evaluators=[
            eval_correctness,
            eval_faithfulness,
            eval_relevance,
            eval_access_control,
        ],
        experiment_prefix=experiment_prefix,
        metadata={
            "project":     get_env("LANGSMITH_PROJECT", "DBchatbot"),
            "description": "LLM-as-a-judge evaluation of the DeBian RAG pipeline",
        },
        max_concurrency=2,   # keep OpenAI rate-limit pressure low
    )

    # 3. Summarise
    summary_url = (
        f"https://smith.langchain.com/o/default/datasets/{dataset.id}"
    )

    print(f"\n{'='*65}")
    print(f"  Experiment : {experiment_prefix}")
    print(f"  Dataset    : {DATASET_NAME}")
    num_examples = len(_build_examples())
    print(f"  Examples   : {num_examples}")
    print(f"  View       : {summary_url}")
    print(f"{'='*65}\n")

    return {
        "experiment_prefix": experiment_prefix,
        "dataset_name":      DATASET_NAME,
        "dataset_id":        str(dataset.id),
        "langsmith_url":     summary_url,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_llm_judge_eval()
