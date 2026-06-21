"""
Deterministic UI role / risk classification for Android string resources.

Classifies extracted Android segments based on deterministic resource-name and
source-text patterns, plus actual protected structural metadata.

Does NOT perform semantic translation scoring or call an LLM.
"""

from __future__ import annotations

import re
from typing import Any


# ── Classification output types ─────────────────────────────────────────────

UI_ROLES = {
    "button",
    "title",
    "message",
    "error",
    "warning",
    "permission",
    "legal",
    "privacy",
    "auth",
    "payment",
    "destructive_action",
    "unknown",
}

RISK_LEVELS = {"low", "medium", "high", "critical"}
REVIEW_PRIORITIES = {"normal", "review_recommended", "owner_review_required"}
EVIDENCE_KEYS = {
    "resource_name_pattern",
    "source_text_pattern",
    "resource_comment_pattern",
    "structural_constraint",
    "unsupported_markup",
    "placeholder_or_markup_protected",
}


# ── Rule definitions ────────────────────────────────────────────────────────
# Each rule is (word_patterns, ui_roles, risk_level, review_priority).
# Patterns are matched case-insensitively against resource name AND source text.
# When both name and text match, confidence is higher.

# ── 1. Destructive actions ──────────────────────────────────────────────────
DESTRUCTIVE_WORDS = {
    "delete", "remove", "erase", "clear", "reset", "revoke",
    "cancel subscription", "delete account",
}

# ── 2. Auth / security ──────────────────────────────────────────────────────
AUTH_WORDS = {
    "login", "sign in", "sign out", "sign-in", "sign-out",
    "password", "passcode", "two-factor", "2fa", "verification code",
    "reset password", "security", "authenticate", "authentication",
}

# ── 3. Privacy / permission ─────────────────────────────────────────────────
PRIVACY_PERMISSION_WORDS = {
    "privacy", "permission", "location", "camera", "microphone",
    "contacts", "notification permission", "allow access",
    "grant access", "grant permission",
}

# ── 4. Legal / consent ──────────────────────────────────────────────────────
LEGAL_WORDS = {
    "terms", "policy", "consent", "agree", "accept",
    "license", "disclaimer", "tos", "eula",
}

# ── 5. Payment / purchase ───────────────────────────────────────────────────
PAYMENT_WORDS = {
    "purchase", "subscribe", "subscription", "billing",
    "payment", "refund", "price", "renew", "trial", "checkout",
}

# ── 6. Error / warning ──────────────────────────────────────────────────────
ERROR_WARNING_WORDS = {
    "error", "warning", "failed", "cannot", "unable",
    "danger", "irreversible",
}

# ── 7. UI role heuristics from resource name suffixes ───────────────────────
_TITLE_PATTERNS = re.compile(
    r"_(title|heading|header|label)$", re.IGNORECASE
)
_BUTTON_PATTERNS = re.compile(
    r"_(button|btn|action|cta)$", re.IGNORECASE
)
_MESSAGE_PATTERNS = re.compile(
    r"_(message|msg|text|body|description|summary|detail|subtitle|content)$", re.IGNORECASE
)


def classify_segment(resource: dict[str, Any]) -> dict[str, Any]:
    """Return classification metadata for an Android string resource.

    Args:
        resource: The internal resource dict from the Android adapter
                  (must have name, value, type, resource_comment, markup_policy,
                   markup_signature, cdata, etc.)

    Returns:
        Dict with ui_role, risk_level, review_priority, classification_evidence.
    """
    name = str(resource.get("name", "")).lower()
    text = str(resource.get("value", "")).lower()
    markup_policy = resource.get("markup_policy", {}) or {}
    markup_signature = resource.get("markup_signature") or []
    owner_review_required = bool(markup_policy.get("owner_review_required"))
    protected_structure = _has_protected_structure(resource)

    ui_roles: list[str] = []
    risk_level = "low"
    review_priority = "normal"
    evidence: list[str] = []

    # ── Normalised matching helper ───────────────────────────────────────
    def _match_any(words: set[str]) -> tuple[bool, bool]:
        """Return (name_matched, text_matched)."""
        name_hit = any(w in name for w in words)
        text_hit = any(w in text for w in words)
        return name_hit, text_hit

    # ── 1. Destructive actions ───────────────────────────────────────────
    name_hit, text_hit = _match_any(DESTRUCTIVE_WORDS)
    if name_hit:
        evidence.append("resource_name_pattern")
    if text_hit:
        evidence.append("source_text_pattern")
    if name_hit or text_hit:
        ui_roles.append("destructive_action")
        # If both name AND text match, risk is critical + owner_review_required
        if name_hit and text_hit:
            risk_level = "critical"
            review_priority = "owner_review_required"
        else:
            risk_level = "high"
            review_priority = "review_recommended"

    # ── 2. Auth / security ───────────────────────────────────────────────
    name_hit, text_hit = _match_any(AUTH_WORDS)
    if name_hit and "resource_name_pattern" not in evidence:
        evidence.append("resource_name_pattern")
    if text_hit and "source_text_pattern" not in evidence:
        evidence.append("source_text_pattern")
    if name_hit or text_hit:
        ui_roles.append("auth")
        if risk_level in ("low", "medium"):
            risk_level = "high"
        review_priority = _escalate_priority(review_priority, "review_recommended")

    # ── 3. Privacy / permission ──────────────────────────────────────────
    name_hit, text_hit = _match_any(PRIVACY_PERMISSION_WORDS)
    if name_hit and "resource_name_pattern" not in evidence:
        evidence.append("resource_name_pattern")
    if text_hit and "source_text_pattern" not in evidence:
        evidence.append("source_text_pattern")
    if name_hit or text_hit:
        if "privacy" in name or "privacy" in text or "permission" in name or "permission" in text:
            ui_roles.append("privacy")
        else:
            ui_roles.append("permission")
        if risk_level in ("low", "medium"):
            risk_level = "high"
        review_priority = _escalate_priority(review_priority, "review_recommended")

    # ── 4. Legal / consent ───────────────────────────────────────────────
    name_hit, text_hit = _match_any(LEGAL_WORDS)
    if name_hit and "resource_name_pattern" not in evidence:
        evidence.append("resource_name_pattern")
    if text_hit and "source_text_pattern" not in evidence:
        evidence.append("source_text_pattern")
    if name_hit or text_hit:
        ui_roles.append("legal")
        if risk_level in ("low", "medium"):
            risk_level = "high"
        review_priority = _escalate_priority(review_priority, "owner_review_required")

    # ── 5. Payment / purchase ────────────────────────────────────────────
    name_hit, text_hit = _match_any(PAYMENT_WORDS)
    if name_hit and "resource_name_pattern" not in evidence:
        evidence.append("resource_name_pattern")
    if text_hit and "source_text_pattern" not in evidence:
        evidence.append("source_text_pattern")
    if name_hit or text_hit:
        ui_roles.append("payment")
        if risk_level in ("low", "medium"):
            risk_level = "high"
        review_priority = _escalate_priority(review_priority, "review_recommended")

    # ── 6. Error / warning ───────────────────────────────────────────────
    name_hit, text_hit = _match_any(ERROR_WARNING_WORDS)
    if name_hit and "resource_name_pattern" not in evidence:
        evidence.append("resource_name_pattern")
    if text_hit and "source_text_pattern" not in evidence:
        evidence.append("source_text_pattern")
    if name_hit or text_hit:
        if "error" in name or "error" in text or "failed" in name or "failed" in text:
            ui_roles.append("error")
        else:
            ui_roles.append("warning")
        if risk_level == "low":
            risk_level = "medium"
        if risk_level in ("high", "critical"):
            pass  # don't downgrade from destructive/auth/legal
        review_priority = _escalate_priority(review_priority, "review_recommended")

    # ── 7. UI role heuristics from resource name suffixes ─────────────────
    if _TITLE_PATTERNS.search(name):
        if not ui_roles:
            ui_roles.append("title")
    if _BUTTON_PATTERNS.search(name):
        if "button" not in ui_roles:
            ui_roles.append("button")
    if _MESSAGE_PATTERNS.search(name):
        if not any(r in ui_roles for r in ("error", "warning", "message", "legal", "auth", "privacy")):
            ui_roles.append("message")

    # ── Structural risk escalation ───────────────────────────────────────────
    if owner_review_required:
        evidence.append("structural_constraint")
        if "unsupported_markup" not in evidence:
            evidence.append("unsupported_markup")
        if risk_level == "low":
            risk_level = "medium"
        review_priority = _escalate_priority(review_priority, "owner_review_required")

    # Check if markup <a href> is in legal/privacy/auth/payment context
    has_link_markup = any(
        isinstance(m, dict) and m.get("tag") == "a" and m.get("attributes", {}).get("href")
        for m in markup_signature
    )
    risky_roles = {"legal", "privacy", "auth", "payment", "destructive_action"}
    if has_link_markup and risky_roles & set(ui_roles):
        evidence.append("placeholder_or_markup_protected")
        if risk_level == "medium":
            risk_level = "high"
        review_priority = _escalate_priority(review_priority, "review_recommended")

    # Structural evidence is emitted only when protected structure is present.
    if protected_structure:
        evidence.append("placeholder_or_markup_protected")

    # ── Fallback ─────────────────────────────────────────────────────────────
    if not ui_roles:
        ui_roles.append("unknown")

    # ── Deduplicate and sort evidence ────────────────────────────────────────
    deduped_evidence = list(dict.fromkeys(evidence))

    return {
        "ui_role": ui_roles,
        "risk_level": risk_level,
        "review_priority": review_priority,
        "classification_evidence": deduped_evidence,
    }


def _escalate_priority(current: str, target: str) -> str:
    """Escalate review priority only if target is higher."""
    order = {"normal": 0, "review_recommended": 1, "owner_review_required": 2}
    return target if order.get(target, 0) > order.get(current, 0) else current


def _has_protected_structure(resource: dict[str, Any]) -> bool:
    """Return whether classification input contains real protected structure."""
    constraints = resource.get("constraints")
    constraints = constraints if isinstance(constraints, dict) else {}
    markup_policy = resource.get("markup_policy")
    markup_policy = markup_policy if isinstance(markup_policy, dict) else {}
    constraint_policy = constraints.get("markup_policy")
    constraint_policy = constraint_policy if isinstance(constraint_policy, dict) else {}

    collection_fields = (
        resource.get("placeholder_signature"),
        resource.get("escape_signature"),
        resource.get("markup_signature"),
        resource.get("markup_structure_signature"),
        resource.get("protected_spans"),
        constraints.get("placeholders"),
        constraints.get("placeholder_signature"),
        constraints.get("escape_signature"),
        constraints.get("markup"),
        constraints.get("markup_signature"),
        constraints.get("protected_spans"),
    )
    if any(bool(value) for value in collection_fields):
        return True
    if bool(resource.get("cdata")) or bool(constraints.get("cdata")):
        return True
    if bool(resource.get("preserve_inline_xml")):
        return True
    return bool(
        markup_policy.get("owner_review_required")
        or markup_policy.get("categories")
        or constraint_policy.get("owner_review_required")
        or constraint_policy.get("categories")
    )
