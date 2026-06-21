"""
v0.2.2-J Android UI Role / High-Risk Context Classification Baseline benchmark.

Runs classification checks against the fixture-risk Android resources
and validates that destructive/auth/legal/payment strings are classified
correctly while generic strings are not over-classified.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY))

from runtime.localize_anything.android_strings_adapter import extract_segments  # noqa: E402
from runtime.localize_anything.io_utils import write_json  # noqa: E402

SOURCE_LOCALE = "en-US"
SOURCE_FILE = "app/src/main/res/values/strings.xml"
FIXTURE = ROOT / "fixture-risk"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run v0.2.2-J Android risk classification benchmark"
    )
    parser.add_argument("--report-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    report = run_benchmark(args.report_dir)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["status"] == "pass" else 1


def run_benchmark(report_dir: Path = ROOT) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    source_path = FIXTURE / SOURCE_FILE
    segments = extract_segments(source_path, SOURCE_LOCALE, SOURCE_FILE)
    by_key = {seg["context"]["resource_key"]: seg for seg in segments}

    # ── Expected classifications ────────────────────────────────────────
    expectations = {
        "string:delete_account_button": {
            "ui_role": "destructive_action",
            "risk_level": "critical",
            "review_priority": "owner_review_required",
            "evidence_present": True,
            "protected_evidence": False,
        },
        "string:delete_account_warning": {
            "ui_role": "destructive_action",
            "risk_level": "high",
            "review_priority": "review_recommended",
            "evidence_present": True,
        },
        "string:reset_password_title": {
            "ui_role_any": {"auth", "destructive_action"},
            "risk_level_any": {"high", "critical"},
            "review_priority_min": "review_recommended",
            "evidence_present": True,
        },
        "string:two_factor_code_message": {
            "ui_role": "auth",
            "risk_level": "high",
            "review_priority_min": "review_recommended",
            "evidence_present": True,
        },
        "string:allow_location_permission": {
            "ui_role_any": {"permission", "privacy"},
            "risk_level": "high",
            "review_priority_min": "review_recommended",
            "evidence_present": True,
        },
        "string:privacy_policy_link": {
            "ui_role": "privacy",
            "risk_level": "high",
            "review_priority_min": "review_recommended",
            "evidence_present": True,
            "protected_evidence": True,
        },
        "string:accept_terms_checkbox": {
            "ui_role": "legal",
            "risk_level": "high",
            "review_priority_min": "review_recommended",
            "evidence_present": True,
        },
        "string:purchase_subscription_button": {
            "ui_role": "payment",
            "risk_level": "high",
            "review_priority_min": "review_recommended",
            "evidence_present": True,
            "protected_evidence": True,
        },
        "string:billing_error": {
            "ui_role_any": {"error", "payment"},
            "risk_level": "high",
            "review_priority_min": "review_recommended",
            "evidence_present": True,
        },
        "string:confirm_remove_device": {
            "ui_role": "destructive_action",
            "risk_level_any": {"high", "critical"},
            "review_priority_min": "review_recommended",
            "evidence_present": True,
        },
        "string:onboarding_consent": {
            "ui_role": "legal",
            "risk_level": "high",
            "review_priority_min": "owner_review_required",
            "evidence_present": True,
        },
    }

    negative_expectations = {
        "string:generic_title": {
            "not_roles": {"destructive_action", "legal", "payment", "auth", "privacy", "permission"},
            "not_risk_levels": {"high", "critical"},
        },
        "string:playlist_name": {
            "not_roles": {"destructive_action", "legal", "payment", "auth", "privacy", "permission"},
            "not_risk_levels": {"high", "critical"},
        },
    }

    # ── Evaluate expectations ───────────────────────────────────────────
    results: list[dict[str, Any]] = []
    failures: list[str] = []

    for key, expected in expectations.items():
        segment = by_key.get(key)
        if not segment:
            failures.append(f"MISSING_SEGMENT: {key}")
            results.append({"resource_key": key, "pass": False, "reason": "segment_not_found"})
            continue

        cls = segment.get("ui_risk_classification", {})
        checks: list[dict[str, Any]] = []

        # ui_role check
        if "ui_role" in expected:
            role_match = expected["ui_role"] in cls.get("ui_role", [])
            checks.append({"check": "ui_role", "expected": expected["ui_role"], "actual": cls.get("ui_role"), "pass": role_match})
            if not role_match:
                failures.append(f"UI_ROLE_MISMATCH: {key} expected {expected['ui_role']!r}, got {cls.get('ui_role')}")

        if "ui_role_any" in expected:
            role_match = bool(expected["ui_role_any"] & set(cls.get("ui_role", [])))
            checks.append({"check": "ui_role_any", "expected": list(expected["ui_role_any"]), "actual": cls.get("ui_role"), "pass": role_match})
            if not role_match:
                failures.append(f"UI_ROLE_ANY_MISMATCH: {key} expected any of {expected['ui_role_any']}, got {cls.get('ui_role')}")

        # risk_level check
        if "risk_level" in expected:
            rl_match = cls.get("risk_level") == expected["risk_level"]
            checks.append({"check": "risk_level", "expected": expected["risk_level"], "actual": cls.get("risk_level"), "pass": rl_match})
            if not rl_match:
                failures.append(f"RISK_LEVEL_MISMATCH: {key} expected {expected['risk_level']}, got {cls.get('risk_level')}")

        if "risk_level_any" in expected:
            rl_match = cls.get("risk_level") in expected["risk_level_any"]
            checks.append({"check": "risk_level_any", "expected": list(expected["risk_level_any"]), "actual": cls.get("risk_level"), "pass": rl_match})
            if not rl_match:
                failures.append(f"RISK_LEVEL_ANY_MISMATCH: {key} expected one of {expected['risk_level_any']}, got {cls.get('risk_level')}")

        # review_priority check
        if "review_priority" in expected:
            rp_match = cls.get("review_priority") == expected["review_priority"]
            checks.append({"check": "review_priority", "expected": expected["review_priority"], "actual": cls.get("review_priority"), "pass": rp_match})
            if not rp_match:
                failures.append(f"REVIEW_PRIORITY_MISMATCH: {key} expected {expected['review_priority']}, got {cls.get('review_priority')}")

        # review_priority_min check
        if "review_priority_min" in expected:
            priority_order = {"normal": 0, "review_recommended": 1, "owner_review_required": 2}
            actual_priority = cls.get("review_priority", "normal")
            actual_level = priority_order.get(actual_priority, 0)
            min_level = priority_order.get(expected["review_priority_min"], 0)
            rp_match = actual_level >= min_level
            checks.append({"check": "review_priority_min", "expected_min": expected["review_priority_min"], "actual": actual_priority, "pass": rp_match})
            if not rp_match:
                failures.append(f"REVIEW_PRIORITY_TOO_LOW: {key} expected at least {expected['review_priority_min']}, got {actual_priority}")

        # evidence_present check
        if expected.get("evidence_present"):
            ev_match = bool(cls.get("classification_evidence"))
            checks.append({"check": "evidence_present", "actual": cls.get("classification_evidence"), "pass": ev_match})
            if not ev_match:
                failures.append(f"EVIDENCE_MISSING: {key}")

        if "protected_evidence" in expected:
            actual_protected = "placeholder_or_markup_protected" in cls.get("classification_evidence", [])
            protected_match = actual_protected == expected["protected_evidence"]
            checks.append({
                "check": "protected_evidence",
                "expected": expected["protected_evidence"],
                "actual": actual_protected,
                "pass": protected_match,
            })
            if not protected_match:
                failures.append(
                    f"PROTECTED_EVIDENCE_MISMATCH: {key} expected {expected['protected_evidence']}, "
                    f"got {actual_protected}"
                )

        all_pass = all(c.get("pass", False) for c in checks)
        results.append({
            "resource_key": key,
            "pass": all_pass,
            "segment": {
                "source": segment.get("source"),
                "ui_role": cls.get("ui_role"),
                "risk_level": cls.get("risk_level"),
                "review_priority": cls.get("review_priority"),
                "classification_evidence": cls.get("classification_evidence"),
            },
            "checks": checks,
        })

    # ── Negative checks ─────────────────────────────────────────────────
    negative_results: list[dict[str, Any]] = []
    for key, not_expected in negative_expectations.items():
        segment = by_key.get(key)
        if not segment:
            negative_results.append({"resource_key": key, "pass": False, "reason": "segment_not_found"})
            continue

        cls = segment.get("ui_risk_classification", {})
        issues: list[str] = []

        if "not_roles" in not_expected:
            bad_roles = set(cls.get("ui_role", [])) & not_expected["not_roles"]
            if bad_roles:
                issues.append(f"unexpected_roles: {sorted(bad_roles)}")

        if "not_risk_levels" in not_expected:
            if cls.get("risk_level") in not_expected["not_risk_levels"]:
                issues.append(f"unexpected_risk_level: {cls.get('risk_level')}")

        if "placeholder_or_markup_protected" in cls.get("classification_evidence", []) and not _has_protected_structure(segment):
            issues.append("false_protected_structure_evidence")

        pass_neg = not issues
        if not pass_neg:
            failures.append(f"NEGATIVE_CHECK_FAILED: {key}: {'; '.join(issues)}")

        negative_results.append({
            "resource_key": key,
            "pass": pass_neg,
            "segment": {
                "source": segment.get("source"),
                "ui_role": cls.get("ui_role"),
                "risk_level": cls.get("risk_level"),
                "review_priority": cls.get("review_priority"),
                "classification_evidence": cls.get("classification_evidence"),
            },
            "issues": issues,
        })

    # ── Summary ─────────────────────────────────────────────────────────
    classified_segments = [s for s in segments if s.get("ui_risk_classification")]
    total_classified = len(classified_segments)
    high_risk = sum(
        1 for s in classified_segments
        if s["ui_risk_classification"]["risk_level"] == "high"
    )
    critical = sum(
        1 for s in classified_segments
        if s["ui_risk_classification"]["risk_level"] == "critical"
    )
    low_risk = sum(
        1 for s in classified_segments
        if s["ui_risk_classification"]["risk_level"] == "low"
    )
    owner_review = sum(
        1 for s in classified_segments
        if s["ui_risk_classification"]["review_priority"] == "owner_review_required"
    )
    review_recommended = sum(
        1 for s in classified_segments
        if s["ui_risk_classification"]["review_priority"] == "review_recommended"
    )
    evidence_count = sum(
        1 for s in classified_segments
        if s["ui_risk_classification"].get("classification_evidence")
    )

    structural_evidence_issues = []
    for segment in classified_segments:
        cls = segment["ui_risk_classification"]
        evidence_present = "placeholder_or_markup_protected" in cls.get("classification_evidence", [])
        protected_structure_present = _has_protected_structure(segment)
        if evidence_present != protected_structure_present:
            structural_evidence_issues.append({
                "resource_key": segment.get("context", {}).get("resource_key"),
                "protected_structure_present": protected_structure_present,
                "protected_evidence_present": evidence_present,
            })
    if structural_evidence_issues:
        failures.append("STRUCTURAL_EVIDENCE_TRUTHFULNESS_FAILED")

    all_expectations_pass = all(r["pass"] for r in results)
    all_negatives_pass = all(r["pass"] for r in negative_results)
    status = "pass" if (all_expectations_pass and all_negatives_pass and not structural_evidence_issues) else "fail"

    # ── Example records ─────────────────────────────────────────────────
    examples = []
    for r in results:
        seg = r.get("segment", {})
        if seg:
            examples.append({
                "resource_key": r["resource_key"],
                "source": seg.get("source"),
                "ui_role": seg.get("ui_role"),
                "risk_level": seg.get("risk_level"),
                "review_priority": seg.get("review_priority"),
                "classification_evidence": seg.get("classification_evidence"),
            })

    report = {
        "schema": "localize-anything-v022-android-risk-classification-baseline",
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": status,
        "fixture_path": FIXTURE.as_posix(),
        "source_file": SOURCE_FILE,
        "ui_risk_classification_check": {
            "pass": status == "pass",
            "classified_segments": total_classified,
            "high_risk_segments": high_risk,
            "critical_segments": critical,
            "owner_review_required_segments": owner_review,
            "review_recommended_segments": review_recommended,
            "low_risk_segments": low_risk,
            "false_negative_checks_pass": all_expectations_pass,
            "false_positive_checks_pass": all_negatives_pass,
            "evidence_present": evidence_count > 0,
            "structural_evidence_truthful": not structural_evidence_issues,
            "structural_evidence_issues": structural_evidence_issues,
            "examples": examples,
        },
        "results": results,
        "negative_results": negative_results,
        "failures": failures,
    }

    write_json(report_dir / "risk-classification-report.json", report)
    return report


def _has_protected_structure(segment: dict[str, Any]) -> bool:
    constraints = segment.get("constraints")
    constraints = constraints if isinstance(constraints, dict) else {}
    policy = constraints.get("markup_policy")
    policy = policy if isinstance(policy, dict) else {}
    collection_fields = (
        segment.get("placeholder_signature"),
        segment.get("escape_signature"),
        segment.get("markup_signature"),
        segment.get("protected_spans"),
        constraints.get("placeholders"),
        constraints.get("placeholder_signature"),
        constraints.get("escape_signature"),
        constraints.get("markup"),
        constraints.get("markup_signature"),
        constraints.get("protected_spans"),
    )
    return bool(
        any(bool(value) for value in collection_fields)
        or segment.get("cdata")
        or constraints.get("cdata")
        or segment.get("owner_review_required")
        or policy.get("owner_review_required")
        or policy.get("categories")
    )


if __name__ == "__main__":
    raise SystemExit(main())
