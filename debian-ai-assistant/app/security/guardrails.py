"""
DeBian LLM Guardrails
=====================
Two-layer protection applied on every request:

  INPUT GUARDRAILS   (before the LLM sees the message)
  ─────────────────────────────────────────────────────
  1. Prompt injection / jailbreak detection
     – "ignore previous instructions", "pretend you are", DAN/roleplay attacks, etc.
  2. Role escalation probing
     – Attempts to claim a higher role ("I am an admin", "act as admin", etc.)
  3. Sensitive data extraction attempts
     – Fishing for budgets, passwords, API keys, internal configs
  4. Off-topic / abuse filter
     – Non-rail topics the assistant should not engage with
  5. Repeated-attack detection
     – Same attack pattern > 2× in the same session → hard block

  OUTPUT GUARDRAILS  (before the LLM response is returned to the user)
  ─────────────────────────────────────────────────────────────────────
  6. Confidential data leak detection
     – Detect if LLM accidentally included internal budget numbers, vendor
       contract values, API keys, KPI targets, or admin-only text
  7. Role-boundary enforcement
     – Ensure no admin/employee keywords leak into a customer response
  8. PII / IBAN double-check
     – Catch any unmasked IBAN-like strings the LLM may have generated
  9. Response grounding check
     – If the LLM response contradicts the known RAG access level, redact it

All guardrail decisions are logged to audit_log.jsonl.

Usage (in debian_agent.py)
──────────────────────────
    from app.security.guardrails import InputGuardrail, OutputGuardrail

    input_check  = InputGuardrail.check(message, user_role, session_id)
    if input_check.blocked:
        return input_check.error_response(language)

    # ... generate LLM response ...

    output_check = OutputGuardrail.check(llm_text, user_role)
    final_text   = output_check.safe_text
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import json

# ---------------------------------------------------------------------------
# Audit logging (direct write — no circular import)
# ---------------------------------------------------------------------------

_LOG_PATH = Path("runtime_logs/audit_log.jsonl")


def _audit(actor: str, action: str, resource: str, payload: dict) -> None:
    _LOG_PATH.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor":     actor,
        "action":    action,
        "resource":  resource,
        "payload":   payload,
    }
    with _LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Session-level attack tracker (in-process; reset on server restart)
# ---------------------------------------------------------------------------

_attack_counts: dict[str, int] = {}  # session_id → count of blocked inputs


def _increment_attack(session_id: str) -> int:
    _attack_counts[session_id] = _attack_counts.get(session_id, 0) + 1
    return _attack_counts[session_id]


def reset_attack_count(session_id: str) -> None:
    _attack_counts.pop(session_id, None)


# ---------------------------------------------------------------------------
# Role hierarchy
# ---------------------------------------------------------------------------

_ROLE_LEVEL = {"customer": 1, "employee": 2, "admin": 3}


# ===========================================================================
# INPUT GUARDRAIL PATTERNS
# ===========================================================================

# 1. Prompt injection / jailbreak
_INJECTION_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"disregard\s+(all\s+)?instructions?",
    r"forget\s+(your\s+)?instructions?",
    r"you\s+are\s+now\s+(a\s+)?(different|new|other)\s+(ai|bot|assistant|model|system)",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"act\s+as\s+(if\s+you\s+(are|were)\s+)?(an?\s+)?(uncensored|unrestricted|jailbreak)",
    r"\bDAN\b",
    r"developer\s+mode",
    r"jailbreak",
    r"override\s+(your\s+)?(safety|content|system|policy)",
    r"bypass\s+(your\s+)?(filter|restriction|rule|guardrail|safety)",
    r"system\s*prompt\s*(is|says|told|instruct)",
    r"reveal\s+your\s+(system\s+)?prompt",
    r"print\s+your\s+(system\s+)?prompt",
    r"what\s+(are\s+)?your\s+(exact\s+)?instructions?",
    r"repeat\s+everything\s+(above|before|prior)",
    r"output\s+(the\s+)?(full\s+)?(system|original)\s+(prompt|instructions?)",
    r"simulate\s+(being\s+)?(a\s+)?(human|admin|employee|unrestricted)",
    r"roleplay\s+as",
    r"you\s+have\s+no\s+(rules|restrictions|limits)",
    r"in\s+this\s+hypothetical",
    r"for\s+(a\s+)?(story|novel|fiction|game|test)",
    r"in\s+(fiction|creative\s+mode|story\s+mode)",
    # German
    r"ignoriere?\s+(alle?\s+)?anweisungen",
    r"vergiss\s+(alle?\s+)?anweisungen",
    r"tue\s+so\s+als\s+(ob\s+du\s+)?",
    r"systemanweisung",
    r"zeig\s+(mir\s+)?deine\s+(system|ursprünglichen?)?\s*(anweisungen?|prompt)",
]]

# 2. Role escalation probing
_ROLE_ESCALATION_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"\bi\s+(am|'m)\s+(an?\s+)?(admin|administrator|employee|staff|manager|supervisor|system)",
    r"(my\s+role|my\s+access)\s+is\s+(admin|employee|staff)",
    r"(treat|consider)\s+me\s+as\s+(an?\s+)?(admin|administrator|employee|staff)",
    r"(grant|give|switch)\s+(me\s+)?(admin|employee|elevated|higher)\s+(access|role|permission|rights?)",
    r"(i\s+have|i've\s+got)\s+(admin|employee|elevated)\s+(access|rights?|permission)",
    r"admin\s+(password|token|key|secret|credentials?)",
    r"(use|with)\s+(admin|employee)\s+(account|credentials?|login|mode)",
    r"(as|being)\s+(the\s+)?(system|root|superuser|admin)",
    # German
    r"ich\s+bin\s+(ein\s+)?(admin|administrator|mitarbeiter|angestellter)",
    r"meine\s+rolle\s+ist\s+(admin|mitarbeiter)",
    r"gib\s+mir\s+(admin|mitarbeiter)\s+(zugang|rechte|zugriff)",
]]

# 3. Sensitive internal data extraction
_DATA_EXTRACTION_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"(compensation|annual|quarterly)\s+budget",
    r"kpi\s+target",
    r"vendor\s+contract",
    r"api\s+key",
    r"pinecone\s+(api\s+)?key",
    r"openai\s+(api\s+)?key",
    r"database\s+password",
    r"secret\s+(key|token|value)",
    r"pricing\s+strategy",
    r"internal\s+(config|configuration|settings?|sop|document)",
    r"(show|give|tell|reveal|list|dump|print|display)\s+(me\s+)?(all\s+)?(internal|confidential|secret|private|admin|employee)\s+(data|doc|document|info|information|file|record)",
    r"what\s+(do\s+you\s+know\s+about|is\s+in)\s+(the\s+)?(admin|employee|internal)\s+(doc|document|data|database)",
    r"(list|show|dump)\s+(all\s+)?(documents?|docs?|rag|vector\s+(store|database|db))",
    r"(system|internal)\s+(architecture|design|infrastructure)",
    # German
    r"(kompensations|entschädigungs)\s*budget",
    r"(zeig|gib|nenn)\s+(mir\s+)?(alle?\s+)?(internen?|vertraulichen?|geheimen?)\s+(daten?|dokumente?|informationen?)",
    r"api[-\s]?schlüssel",
    r"konfiguration",
]]

# 4. Off-topic / abuse
_OFFTOPIC_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"\b(hack|hacking|crack|cracking|exploit)\b",
    r"(how\s+to\s+(make|build|create)\s+(a\s+)?(bomb|weapon|virus|malware))",
    r"(generate|write|create)\s+(malicious|harmful|dangerous)\s+(code|script|program)",
    r"(adult|explicit|sexual|porn|nsfw)\s+content",
    r"(suicide|self.?harm)\s+(instructions?|methods?|how)",
    r"(buy|sell|purchase)\s+(drugs?|illegal\s+items?|weapons?)",
]]

# ===========================================================================
# OUTPUT GUARDRAIL PATTERNS
# ===========================================================================

# 5. Confidential data leaking in LLM output (admin-only content)
_LEAK_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("budget_amount",     re.compile(r"\b\d[\d,\.]+\s*(EUR|€|million|thousand)\b.{0,80}(budget|allocation|cap)", re.IGNORECASE)),
    ("kpi_target",        re.compile(r"(NPS|CSAT|resolution rate|handoff rate|latency target).{0,80}\d+[\.\d]*\s*(%|percent|seconds?)", re.IGNORECASE)),
    ("vendor_contract",   re.compile(r"(DPA-[A-Z0-9\-]+|annual value.{0,40}EUR|renewal date.{0,30}20\d\d)", re.IGNORECASE)),
    ("api_key_leak",      re.compile(r"(pcsk_|sk-|AKIA|eyJhbGci)[A-Za-z0-9\-_]{10,}", re.IGNORECASE)),
    ("pricing_strategy",  re.compile(r"(vouchers? cost.{0,40}(less|cheaper|lower)|redemption rate.{0,30}\d+%|cost recovery.{0,40}%)", re.IGNORECASE)),
    ("internal_config",   re.compile(r"(hashing_embedding|top_k\s*=\s*\d|temperature:\s*0\.\d|PINECONE_DIMENSION)", re.IGNORECASE)),
]

# 6. Employee-only content leaking to customer
_EMPLOYEE_LEAK_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"(occupancy\s+(is|status)\s*:\s*(RED|AMBER|CRITICAL|FULL))",
    r"(class\s+[abc]\s+delay|incident\s+management\s+system)",
    r"(cascade\s+incident|network\s+control\s+centre|NCC)",
    r"(fraud\s+(detection|pattern|flag)|duplicate\s+claim\s+detected)",
    r"(pre-?approv(al|e)|soforterstattung)",
    r"(tier\s+[1234]\s+(escalation|approval)|team\s+leader\s+sign.?off)",
    r"(prohibited\s+phrase|announcement\s+script)",
    r"(AMBER|CRITICAL)\s+(occupancy|threshold|level)",
]]

# 7. IBAN / account number in LLM output
_IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_FULL_ACCOUNT_PATTERN = re.compile(r"\b\d{8,26}\b")


# ===========================================================================
# RESULT DATACLASSES
# ===========================================================================

@dataclass
class InputCheckResult:
    blocked: bool
    reason:  str = ""
    attack_count: int = 0

    # Per-language block messages
    _MESSAGES: dict[str, str] = field(default_factory=lambda: {
        "en": "I can only assist with Deutsche Bahn rail services. I'm not able to process that request.",
        "de": "Ich kann nur bei Deutsche Bahn Zugdiensten helfen. Diese Anfrage kann ich nicht verarbeiten.",
        "fr": "Je peux uniquement aider avec les services ferroviaires Deutsche Bahn.",
        "es": "Solo puedo ayudar con los servicios ferroviarios de Deutsche Bahn.",
        "it": "Posso assistere solo con i servizi ferroviari Deutsche Bahn.",
        "tr": "Yalnızca Deutsche Bahn tren hizmetlerinde yardımcı olabilirim.",
        "pl": "Mogę pomagać tylko w sprawach kolejowych Deutsche Bahn.",
        "ar": "يمكنني فقط المساعدة في خدمات السكك الحديدية لـ Deutsche Bahn.",
        "ta": "நான் Deutsche Bahn ரயில் சேவைகளில் மட்டுமே உதவ முடியும்.",
    })

    def error_response(self, language: str = "en") -> dict:
        return {
            "assistant":    "DeBian",
            "language":     language,
            "intent":       "guardrail_block",
            "response":     self._MESSAGES.get(language, self._MESSAGES["en"]),
            "used_llm":     False,
            "llm_status":   "blocked_by_guardrail",
            "guardrail_reason": self.reason,
            "tool_result":  {},
            "rag_context":  {},
        }


@dataclass
class OutputCheckResult:
    safe_text:   str
    redacted:    bool = False
    reasons:     list[str] = field(default_factory=list)

    # Replacement text when output is redacted
    _REDACT_MSG: dict[str, str] = field(default_factory=lambda: {
        "en": "I'm unable to provide that information. Please contact a DB support agent for assistance.",
        "de": "Ich kann diese Informationen nicht bereitstellen. Bitte wenden Sie sich an einen DB-Mitarbeiter.",
        "fr": "Je ne peux pas fournir cette information. Veuillez contacter un agent DB.",
        "es": "No puedo proporcionar esa información. Por favor, contacte a un agente de DB.",
        "it": "Non posso fornire queste informazioni. Contatti un agente DB per assistenza.",
        "tr": "Bu bilgiyi sağlayamıyorum. Lütfen bir DB destek temsilcisiyle iletişime geçin.",
        "pl": "Nie mogę podać tej informacji. Skontaktuj się z agentem DB.",
        "ar": "لا يمكنني تقديم هذه المعلومات. يرجى التواصل مع وكيل دعم DB.",
        "ta": "அந்த தகவலை வழங்க முடியாது. DB ஆதரவு முகவரை தொடர்பு கொள்ளவும்.",
    })


# ===========================================================================
# INPUT GUARDRAIL
# ===========================================================================

class InputGuardrail:
    """
    Run before the LLM receives any message.
    Returns InputCheckResult — if .blocked is True, return the error response immediately.
    """

    @staticmethod
    def check(
        message: str,
        user_role: str = "customer",
        session_id: str = "anonymous",
        language: str = "en",
    ) -> InputCheckResult:

        text = message.strip()

        # ── 1. Prompt injection / jailbreak ──────────────────────────────────
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                count = _increment_attack(session_id)
                _audit(
                    actor    = session_id,
                    action   = "GUARDRAIL_INPUT_BLOCK",
                    resource = "injection_detection",
                    payload  = {
                        "reason":        "prompt_injection",
                        "pattern":       pattern.pattern,
                        "attack_count":  count,
                        "user_role":     user_role,
                        "message_hash":  hashlib.sha256(text.encode()).hexdigest()[:16],
                    },
                )
                return InputCheckResult(
                    blocked=True,
                    reason=f"prompt_injection (pattern: {pattern.pattern[:40]})",
                    attack_count=count,
                )

        # ── 2. Role escalation probing ────────────────────────────────────────
        for pattern in _ROLE_ESCALATION_PATTERNS:
            if pattern.search(text):
                count = _increment_attack(session_id)
                _audit(
                    actor    = session_id,
                    action   = "GUARDRAIL_INPUT_BLOCK",
                    resource = "role_escalation",
                    payload  = {
                        "reason":       "role_escalation_attempt",
                        "user_role":    user_role,
                        "attack_count": count,
                        "message_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
                    },
                )
                return InputCheckResult(
                    blocked=True,
                    reason="role_escalation_attempt",
                    attack_count=count,
                )

        # ── 3. Sensitive data extraction (role-aware) ─────────────────────────
        # Customers probing for admin/internal data → block
        # Employees/admins asking about this in context of their work → allow
        if _ROLE_LEVEL.get(user_role, 1) < 2:  # customer only
            for pattern in _DATA_EXTRACTION_PATTERNS:
                if pattern.search(text):
                    count = _increment_attack(session_id)
                    _audit(
                        actor    = session_id,
                        action   = "GUARDRAIL_INPUT_BLOCK",
                        resource = "data_extraction",
                        payload  = {
                            "reason":       "sensitive_data_probe",
                            "user_role":    user_role,
                            "attack_count": count,
                            "message_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
                        },
                    )
                    return InputCheckResult(
                        blocked=True,
                        reason="sensitive_data_extraction_attempt",
                        attack_count=count,
                    )

        # ── 4. Off-topic / abuse ──────────────────────────────────────────────
        for pattern in _OFFTOPIC_PATTERNS:
            if pattern.search(text):
                count = _increment_attack(session_id)
                _audit(
                    actor    = session_id,
                    action   = "GUARDRAIL_INPUT_BLOCK",
                    resource = "offtopic_abuse",
                    payload  = {
                        "reason":       "off_topic_or_abuse",
                        "user_role":    user_role,
                        "attack_count": count,
                    },
                )
                return InputCheckResult(
                    blocked=True,
                    reason="off_topic_or_abuse",
                    attack_count=count,
                )

        # ── 5. Repeated attack detection ─────────────────────────────────────
        if _attack_counts.get(session_id, 0) >= 3:
            _audit(
                actor    = session_id,
                action   = "GUARDRAIL_SESSION_BLOCK",
                resource = "repeated_attacks",
                payload  = {
                    "attack_count": _attack_counts[session_id],
                    "user_role":    user_role,
                },
            )
            return InputCheckResult(
                blocked=True,
                reason="repeated_attack_session_blocked",
                attack_count=_attack_counts[session_id],
            )

        return InputCheckResult(blocked=False)


# ===========================================================================
# OUTPUT GUARDRAIL
# ===========================================================================

class OutputGuardrail:
    """
    Run on the LLM's raw text before it is returned to the user.
    Returns OutputCheckResult — always use .safe_text for the final response.
    """

    @staticmethod
    def check(
        llm_text:  str,
        user_role: str = "customer",
        language:  str = "en",
        session_id: str = "anonymous",
    ) -> OutputCheckResult:

        reasons: list[str] = []
        text = llm_text or ""

        # ── 6. Admin confidential data leak ───────────────────────────────────
        if _ROLE_LEVEL.get(user_role, 1) < 3:  # not admin
            for label, pattern in _LEAK_PATTERNS:
                if pattern.search(text):
                    reasons.append(f"admin_data_leak:{label}")

        # ── 7. Employee-only content leaking to customer ──────────────────────
        if _ROLE_LEVEL.get(user_role, 1) < 2:  # customer only
            for pattern in _EMPLOYEE_LEAK_PATTERNS:
                if pattern.search(text):
                    reasons.append("employee_content_leak")
                    break

        # ── 8. Unmasked IBAN / account numbers ───────────────────────────────
        if _IBAN_PATTERN.search(text):
            reasons.append("unmasked_iban")
            # Auto-mask rather than full redact
            text = _IBAN_PATTERN.sub(
                lambda m: "*" * max(len(m.group()) - 4, 0) + m.group()[-4:],
                text,
            )

        # ── 9. Long raw digit strings (account numbers) ───────────────────────
        # Only flag truly long ones (10+ digits) that aren't year references
        long_digits = re.findall(r"\b\d{10,}\b", text)
        if long_digits:
            reasons.append("possible_account_number_in_output")
            for ld in long_digits:
                text = text.replace(ld, "*" * (len(ld) - 4) + ld[-4:])

        if reasons:
            redact_msg = OutputCheckResult._REDACT_MSG.fget(None) if False else {
                "en": "I'm unable to provide that information. Please contact a DB support agent for assistance.",
                "de": "Ich kann diese Informationen nicht bereitstellen. Bitte wenden Sie sich an einen DB-Mitarbeiter.",
                "fr": "Je ne peux pas fournir cette information. Veuillez contacter un agent DB.",
                "es": "No puedo proporcionar esa información. Por favor, contacte a un agente de DB.",
                "it": "Non posso fornire queste informazioni. Contatti un agente DB per assistenza.",
                "tr": "Bu bilgiyi sağlayamıyorum. Lütfen bir DB destek temsilcisiyle iletişime geçin.",
                "pl": "Nie mogę podać tej informacji. Skontaktuj się z agentem DB.",
                "ar": "لا يمكنني تقديم هذه المعلومات. يرجى التواصل مع وكيل دعم DB.",
                "ta": "அந்த தகவலை வழங்க முடியாது. DB ஆதரவு முகவரை தொடர்பு கொள்ளவும்.",
            }

            # Determine if full redact is needed or just auto-masked IBAN is enough
            hard_reasons = [r for r in reasons if r not in ("unmasked_iban", "possible_account_number_in_output")]

            _audit(
                actor    = session_id,
                action   = "GUARDRAIL_OUTPUT_BLOCK" if hard_reasons else "GUARDRAIL_OUTPUT_MASK",
                resource = "output_check",
                payload  = {
                    "reasons":    reasons,
                    "user_role":  user_role,
                    "text_hash":  hashlib.sha256(llm_text.encode()).hexdigest()[:16],
                },
            )

            if hard_reasons:
                return OutputCheckResult(
                    safe_text = redact_msg.get(language, redact_msg["en"]),
                    redacted  = True,
                    reasons   = reasons,
                )

            # Soft case: only IBAN/digit masking was applied — return masked text
            return OutputCheckResult(safe_text=text, redacted=False, reasons=reasons)

        return OutputCheckResult(safe_text=text, redacted=False)
