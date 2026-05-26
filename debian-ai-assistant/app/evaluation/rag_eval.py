"""
RAG evaluation.

Metrics
-------
- retrieval_precision     fraction of retrieved docs judged relevant
- retrieval_recall        fraction of relevant docs retrieved (requires gold set)
- mean_reciprocal_rank    MRR over the ranked document list
- context_utilisation     does the final answer actually use any retrieved text?
- groundedness_score      does every answer claim trace back to a retrieved doc?
- faithfulness_score      no contradictions between answer and docs
- answer_relevance        does the answer address the original question?
- latency_ms              end-to-end retrieval + generation time

All scores are floats in [0, 1] unless documented otherwise.
"""

from __future__ import annotations

import re
import time
from typing import Callable

from app.security.governance import write_evaluation_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lower-case, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _token_overlap(a: str, b: str) -> float:
    """Unigram F1 between two strings (quick groundedness proxy)."""
    tokens_a = set(_normalise(a).split())
    tokens_b = set(_normalise(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    precision = len(intersection) / len(tokens_a)
    recall = len(intersection) / len(tokens_b)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _doc_texts(documents: list[dict]) -> list[str]:
    """Extract the text field from each retrieved document dict."""
    texts = []
    for doc in documents:
        # Pinecone-style: text lives under metadata.text
        meta = doc.get("metadata", {})
        text = meta.get("text") or doc.get("text", "")
        if text:
            texts.append(str(text))
    return texts


# ---------------------------------------------------------------------------
# Individual metric functions
# ---------------------------------------------------------------------------

def retrieval_precision(
    documents: list[dict],
    relevance_fn: Callable[[dict], bool],
) -> float:
    """
    Fraction of retrieved documents that are relevant.

    ``relevance_fn`` receives a single document dict and returns True/False.
    If no documents were retrieved, returns 0.
    """
    if not documents:
        return 0.0
    hits = sum(1 for doc in documents if relevance_fn(doc))
    return hits / len(documents)


def retrieval_recall(
    documents: list[dict],
    gold_ids: list[str],
) -> float:
    """
    Fraction of known-relevant document IDs that were retrieved.

    ``gold_ids`` is the ground-truth set of document IDs that *should* be
    retrieved.  If the gold set is empty, returns 1.0 (nothing to recall).
    """
    if not gold_ids:
        return 1.0
    retrieved_ids = {doc.get("id") or doc.get("metadata", {}).get("id") for doc in documents}
    hits = sum(1 for gid in gold_ids if gid in retrieved_ids)
    return hits / len(gold_ids)


def mean_reciprocal_rank(
    documents: list[dict],
    relevance_fn: Callable[[dict], bool],
) -> float:
    """
    MRR over the ranked document list.

    Returns the reciprocal of the rank of the first relevant document.
    Returns 0 if no relevant document is found.
    """
    for rank, doc in enumerate(documents, start=1):
        if relevance_fn(doc):
            return 1.0 / rank
    return 0.0


def context_utilisation(
    answer: str,
    documents: list[dict],
    overlap_threshold: float = 0.15,
) -> float:
    """
    Fraction of retrieved documents that are reflected in the answer.

    Uses token-overlap F1 as a cheap lexical proxy.
    A document is "used" when its overlap with the answer exceeds
    ``overlap_threshold``.
    """
    if not documents or not answer:
        return 0.0
    doc_texts = _doc_texts(documents)
    if not doc_texts:
        return 0.0
    used = sum(
        1 for t in doc_texts if _token_overlap(answer, t) >= overlap_threshold
    )
    return used / len(doc_texts)


def groundedness_score(
    answer: str,
    documents: list[dict],
    claim_threshold: float = 0.20,
) -> float:
    """
    Mean max-overlap of each answer sentence against the retrieved docs.

    A high score means every claim in the answer has lexical support in at
    least one retrieved document.  This is a fast heuristic; replace the
    inner loop with an LLM-as-judge call for production-grade accuracy.
    """
    if not answer:
        return 0.0
    doc_texts = _doc_texts(documents)
    if not doc_texts:
        return 0.0

    sentences = [s.strip() for s in re.split(r"[.!?]", answer) if s.strip()]
    if not sentences:
        return 0.0

    scores = []
    for sentence in sentences:
        max_overlap = max(_token_overlap(sentence, dt) for dt in doc_texts)
        scores.append(max_overlap)

    return sum(scores) / len(scores)


def faithfulness_score(
    answer: str,
    documents: list[dict],
    contradiction_pairs: list[tuple[str, str]] | None = None,
) -> float:
    """
    Penalise the answer for each known contradiction with retrieved docs.

    ``contradiction_pairs`` is an optional list of (answer_phrase, conflicting_doc_phrase)
    tuples detected externally (e.g. by an LLM-as-judge step).

    Without an external contradiction detector this defaults to 1.0 when the
    answer has high overlap with docs, and applies a penalty for each supplied
    contradiction pair.
    """
    base = min(groundedness_score(answer, documents) + 0.2, 1.0)
    if not contradiction_pairs:
        return base

    penalty = 0.15 * len(contradiction_pairs)
    return max(0.0, base - penalty)


def answer_relevance(
    question: str,
    answer: str,
) -> float:
    """
    Token-overlap F1 between question and answer as a fast relevance proxy.

    In production replace with an embedding similarity or LLM-judge call.
    """
    return _token_overlap(question, answer)


# ---------------------------------------------------------------------------
# Timed retrieval wrapper
# ---------------------------------------------------------------------------

def timed_retrieve(
    retrieve_fn: Callable[..., dict],
    *args,
    **kwargs,
) -> tuple[dict, float]:
    """
    Call ``retrieve_fn(*args, **kwargs)`` and return (result, latency_ms).
    """
    t0 = time.perf_counter()
    result = retrieve_fn(*args, **kwargs)
    latency_ms = (time.perf_counter() - t0) * 1000
    return result, latency_ms


# ---------------------------------------------------------------------------
# High-level evaluator
# ---------------------------------------------------------------------------

def evaluate_rag(
    *,
    question: str,
    answer: str,
    rag_context: dict,
    relevance_fn: Callable[[dict], bool] | None = None,
    gold_ids: list[str] | None = None,
    contradiction_pairs: list[tuple[str, str]] | None = None,
    latency_ms: float | None = None,
    write_event: bool = True,
) -> dict:
    """
    Compute the full RAG metric suite and optionally persist to the eval log.

    Parameters
    ----------
    question:
        The original user question.
    answer:
        The assistant's final answer string.
    rag_context:
        The dict returned by ``retrieve_context()`` / ``search_rag()``.
        Expected keys: ``documents``, ``query``, ``optimized_query``.
    relevance_fn:
        Optional callable(doc) → bool.  Defaults to a simple keyword-overlap
        heuristic against ``question`` when not supplied.
    gold_ids:
        Optional list of document IDs that *should* have been retrieved
        (used for recall calculation).
    contradiction_pairs:
        Optional list of (answer_phrase, doc_phrase) contradictions detected
        by an external judge.
    latency_ms:
        End-to-end latency in milliseconds, if measured outside this call.
    write_event:
        Whether to persist the evaluation record to ``evaluation_events.jsonl``.

    Returns
    -------
    dict with keys: question, answer, num_docs_retrieved, retrieval_precision,
    retrieval_recall, mrr, context_utilisation, groundedness_score,
    faithfulness_score, answer_relevance, latency_ms, document_ids.
    """
    documents: list[dict] = rag_context.get("documents", [])

    # Default relevance function: any keyword from the question appears in doc text
    if relevance_fn is None:
        question_keywords = set(_normalise(question).split()) - {
            "a", "an", "the", "is", "are", "was", "were", "i", "my", "for",
            "of", "in", "to", "on", "at", "and", "or", "what", "how", "can",
        }

        def relevance_fn(doc: dict) -> bool:
            text = _normalise(
                doc.get("metadata", {}).get("text") or doc.get("text", "")
            )
            return bool(question_keywords & set(text.split()))

    precision = retrieval_precision(documents, relevance_fn)
    recall = retrieval_recall(documents, gold_ids or [])
    mrr = mean_reciprocal_rank(documents, relevance_fn)
    ctx_util = context_utilisation(answer, documents)
    ground = groundedness_score(answer, documents)
    faith = faithfulness_score(answer, documents, contradiction_pairs)
    ans_rel = answer_relevance(question, answer)

    doc_ids = [
        doc.get("id") or doc.get("metadata", {}).get("id", "unknown")
        for doc in documents
    ]

    result = {
        "question": question,
        "answer": answer,
        "num_docs_retrieved": len(documents),
        "document_ids": doc_ids,
        "retrieval_precision": round(precision, 4),
        "retrieval_recall": round(recall, 4),
        "mrr": round(mrr, 4),
        "context_utilisation": round(ctx_util, 4),
        "groundedness_score": round(ground, 4),
        "faithfulness_score": round(faith, 4),
        "answer_relevance": round(ans_rel, 4),
        "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
    }

    if write_event:
        write_evaluation_event({"rag_evaluation": result})

    return result


# ---------------------------------------------------------------------------
# Batch / suite runner
# ---------------------------------------------------------------------------

def run_rag_eval_suite(
    test_cases: list[dict],
    retrieve_fn: Callable[..., dict],
    generate_fn: Callable[[str, dict], str],
) -> dict:
    """
    Run a list of test cases through the full RAG + generation pipeline and
    return aggregated metrics.

    Each test case dict should contain:
      - ``question``    (str, required)
      - ``gold_ids``    (list[str], optional)
      - ``relevance_fn``(callable, optional)

    ``retrieve_fn(question) → rag_context`` should match the
    ``retrieve_context`` / ``search_rag`` signature.

    ``generate_fn(question, rag_context) → answer_str`` is your LLM call.

    Returns a dict with per-case results and macro-averaged metrics.
    """
    results = []

    for case in test_cases:
        question = case["question"]
        gold_ids = case.get("gold_ids")
        relevance_fn = case.get("relevance_fn")

        rag_context, latency_ms = timed_retrieve(retrieve_fn, question)
        answer = generate_fn(question, rag_context)

        metrics = evaluate_rag(
            question=question,
            answer=answer,
            rag_context=rag_context,
            relevance_fn=relevance_fn,
            gold_ids=gold_ids,
            latency_ms=latency_ms,
            write_event=True,
        )
        results.append(metrics)

    # Macro averages (exclude None latency values)
    numeric_keys = [
        "retrieval_precision", "retrieval_recall", "mrr",
        "context_utilisation", "groundedness_score", "faithfulness_score",
        "answer_relevance",
    ]
    averages: dict[str, float] = {}
    for key in numeric_keys:
        values = [r[key] for r in results if r.get(key) is not None]
        averages[key] = round(sum(values) / len(values), 4) if values else 0.0

    latencies = [r["latency_ms"] for r in results if r.get("latency_ms") is not None]
    averages["latency_ms"] = round(sum(latencies) / len(latencies), 2) if latencies else None

    suite_result = {
        "suite": "rag_eval_suite",
        "num_cases": len(test_cases),
        "macro_averages": averages,
        "per_case": results,
    }

    write_evaluation_event({"rag_suite_result": suite_result})
    return suite_result
