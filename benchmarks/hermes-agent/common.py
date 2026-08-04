"""Shared helpers for the Hermes Agent localization benchmark."""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


BENCH_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = BENCH_ROOT.parents[1]
WORK = BENCH_ROOT / "work"
RUNS = BENCH_ROOT / "runs"
REPORTS = BENCH_ROOT / "reports"
SOURCE = WORK / "source"
BLIND = WORK / "blind"
REFERENCE = WORK / "reference"
STAGING = WORK / "staging"
COPY = WORK / "copy"
EVIDENCE = BENCH_ROOT / "evidence"
REAL_IMPORTS = EVIDENCE / "real-imports"

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from runtime.localize_anything import PROTOCOL_VERSION  # noqa: E402
from runtime.localize_anything.json_adapter import dump_json, load_json  # noqa: E402


CONFIG = load_json(BENCH_ROOT / "benchmark.json")

_PATH_PLACEHOLDERS = [
    (str(COPY / "hermes"), "<hermes-copy>"),
    (str(COPY), "<hermes-copy>"),
    (str(SOURCE), "<hermes-source>"),
    (str(BENCH_ROOT), "<benchmark>"),
    (str(REPOSITORY_ROOT), "<repo>"),
    (str(WORK), "<work>"),
    (str(Path.home()), "<home>"),
]
_PATH_PLACEHOLDERS.sort(key=lambda item: len(item[0]), reverse=True)
_TEMP_PATH_PATTERNS = [
    re.compile(r"/private/var/folders/[A-Za-z0-9+/]+/T/[A-Za-z0-9._-]+"),
    re.compile(r"/var/folders/[A-Za-z0-9+/]+/T/[A-Za-z0-9._-]+"),
    re.compile(r"/tmp/[A-Za-z0-9._-]+"),
]


def sanitize_text(text: str) -> str:
    """Replace machine-specific paths with stable placeholders (deterministic)."""
    for path, placeholder in _PATH_PLACEHOLDERS:
        if path:
            text = text.replace(path, placeholder)
    for pattern in _TEMP_PATH_PATTERNS:
        text = pattern.sub("<temporary-directory>", text)
    return text


def sanitize_report(value: Any) -> Any:
    """Recursively sanitize strings in a report structure."""
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_report(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_report(child) for key, child in value.items()}
    return value


def write_json(value: Any, path: Path, raw: bool = False) -> None:
    if raw:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sanitize_text(value), encoding="utf-8", newline="\n")
        return
    dump_json(sanitize_report(value), path)


def read_json(path: Path) -> Any:
    return load_json(path)


def write_jsonl(segments: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for segment in segments:
            handle.write(json.dumps(segment, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def run(command: list[str], cwd: Path | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=False, text=True, capture_output=True, timeout=timeout)


def environment_record() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "node": _version(["node", "--version"]),
        "npm": _version(["npm", "--version"]),
        "git": _version(["git", "--version"]),
        "os": f"{platform.system()} {platform.release()}",
        "platform": platform.platform(),
    }


def _version(command: list[str]) -> str:
    try:
        result = subprocess.run(command, check=False, text=True, capture_output=True)
        return result.stdout.strip() or result.stderr.strip() or "unknown"
    except OSError:
        return "unavailable"


def surface_config() -> dict[str, Any]:
    return CONFIG["surfaces"]


def target_locale() -> str:
    return CONFIG["target_locale"]


def source_locale() -> str:
    return CONFIG["source_locale"]


# ---------------------------------------------------------------------------
# Engineering draft (explicitly not translation-quality evidence)
# ---------------------------------------------------------------------------

def apply_engineering_draft(segments: list[dict[str, Any]], curated: dict[str, str]) -> list[dict[str, Any]]:
    """Produce a conservative local draft: curated slice + identity copy.

    The identity copy carries English text through the pipeline unchanged and
    is flagged by the semantic review layer as untranslated English.  The
    curated slice (small, agent-drafted, never human-reviewed) proves that
    real target text flows through extraction -> staging -> rebuild -> QA ->
    build.  Nothing here counts as translation-quality evidence.
    """
    drafted: list[dict[str, Any]] = []
    for segment in segments:
        pointer = segment["context"].get("pointer")
        segment = dict(segment)
        segment["target_locale"] = target_locale()
        if pointer in curated:
            segment["target"] = curated[pointer]
            segment["quality_claim"] = "engineering_fixture_only"
            segment["generation_mode"] = "synthetic_curated_draft"
        else:
            segment["target"] = segment["source"]
            segment["quality_claim"] = "engineering_fixture_only"
            segment["generation_mode"] = "synthetic_identity"
        segment["status"] = "generated"
        drafted.append(segment)
    return drafted


def load_curated(surface: str) -> dict[str, str]:
    path = BENCH_ROOT / "fixtures" / f"curated-fr-{surface}.json"
    if not path.is_file():
        return {}
    return load_json(path)


def import_translated_segments(extracted: list[dict[str, Any]], imported_path: Path) -> list[dict[str, Any]]:
    """Validate and merge an externally generated segment JSONL file."""
    imported = read_jsonl(imported_path)
    extracted_ids = {segment["segment_id"] for segment in extracted}
    imported_ids = {segment["segment_id"] for segment in imported}
    missing = extracted_ids - imported_ids
    extra = imported_ids - extracted_ids
    if missing:
        raise ValueError(f"imported segments missing {len(missing)} segment ids (e.g. {sorted(missing)[:3]})")
    if extra:
        raise ValueError(f"imported segments contain {len(extra)} unknown segment ids (e.g. {sorted(extra)[:3]})")
    if len(imported_ids) != len(imported):
        raise ValueError("imported segments contain duplicate segment ids")
    by_id = {segment["segment_id"]: segment for segment in imported}
    merged: list[dict[str, Any]] = []
    for segment in extracted:
        imported_segment = by_id[segment["segment_id"]]
        if "target" not in imported_segment or not isinstance(imported_segment["target"], str):
            raise ValueError(f"imported segment lacks a string target: {segment['segment_id']}")
        merged_segment = dict(segment)
        merged_segment["target"] = imported_segment["target"]
        merged_segment["target_locale"] = imported_segment.get("target_locale", target_locale())
        merged_segment["quality_claim"] = imported_segment.get("quality_claim", "imported")
        merged_segment["generation_mode"] = imported_segment.get("generation_mode", "imported")
        if "classification" in imported_segment:
            merged_segment["candidate_classification"] = imported_segment["classification"]
        if "classification_note" in imported_segment:
            merged_segment["candidate_classification_note"] = imported_segment["classification_note"]
        merged_segment["status"] = "generated"
        merged.append(merged_segment)
    return merged


def write_prompts(segments: list[dict[str, Any]], run_dir: Path, surface: str, batch_plan: dict[str, Any]) -> None:
    """Write provider-agnostic handoff artifacts for real generation."""
    prompts_dir = run_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(segments, prompts_dir / "segments.jsonl")
    write_json(batch_plan, prompts_dir / "batch-plan.json")
    batched: dict[str, list[dict[str, Any]]] = {}
    for segment in segments:
        key = segment.get("context", {}).get("batch", "misc")
        batched.setdefault(key, []).append(segment)
    instructions = (
        f"# Hermes Agent {surface} localization handoff ({CONFIG['target_locale']})\n\n"
        f"- Upstream commit: {CONFIG['upstream']['commit']}\n"
        "- Translate each segment's `source` into French (`target_locale`: fr).\n"
        "- Preserve every {placeholder} token, every ${{...}} template expression, "
        "Markdown, backticks, command names, URLs and paths exactly.\n"
        "- Keep identifiers, brand names, model/provider names and code spans untranslated.\n"
        "- Emit one JSON object per line with segment_id, target, target_locale.\n"
        "- Do not reorder, add, or delete segment ids.\n"
    )
    for index, (batch, items) in enumerate(sorted(batched.items()), start=1):
        (prompts_dir / f"batch-{index:02d}-{batch}.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items),
            encoding="utf-8",
        )
    (prompts_dir / "INSTRUCTIONS.md").write_text(instructions, encoding="utf-8")


def batch_plan_for(surface: str) -> dict[str, Any]:
    """Semantic batch plan grouped by UI area, not token count."""
    return {
        "surface": surface,
        "target_locale": target_locale(),
        "batches": [
            "common",
            "app_shell",
            "status",
            "sessions",
            "analytics",
            "models",
            "logs",
            "settings",
            "gateway",
            "plugins",
            "skills",
            "errors",
            "approval",
            "documentation",
            "misc",
        ],
    }


def assign_batches(segments: list[dict[str, Any]]) -> None:
    """Assign each segment to a semantic batch by pointer prefix."""
    mapping = {
        "common": ["/common"],
        "app_shell": ["/app/", "/navigation", "/theme", "/language"],
        "status": ["/status", "/footer"],
        "sessions": ["/sessions", "/chat", "/resume", "/title", "/branch"],
        "analytics": ["/analytics", "/usage", "/context"],
        "models": ["/models", "/model", "/providers", "/provider"],
        "logs": ["/logs", "/debug"],
        "settings": ["/config", "/profiles", "/env", "/keys", "/settings", "/voice", "/reasoning", "/fast", "/verbose"],
        "gateway": ["/gateway", "/agents", "/background", "/cron", "/stop", "/restart", "/update"],
        "plugins": ["/plugins", "/plugin", "/reload_mcp", "/reload-mcp", "/mcp"],
        "skills": ["/skills", "/skill", "/reload_skills"],
        "errors": ["/errors", "/error", "/rollback", "/diff", "/compress"],
        "approval": ["/approval", "/approve", "/deny", "/yolo"],
        "documentation": ["/docs"],
    }
    for segment in segments:
        pointer = segment.get("context", {}).get("pointer", "")
        batch = "misc"
        best_length = -1
        for name, prefixes in mapping.items():
            for prefix in prefixes:
                if pointer.startswith(prefix) and len(prefix) > best_length:
                    batch = name
                    best_length = len(prefix)
        segment["context"]["batch"] = batch


RETENTION_CLASSIFICATIONS = {
    "intentional_identifier",
    "brand_or_product_name",
    "technical_term_retained",
    "not_applicable",
}

REVIEW_STATUSES = {"approved", "rejected", "needs_revision"}
RETENTION_ADJUDICATION_PATH = REPORTS / "retained-string-adjudication.json"

ENGINEERING_FIXTURE_MODES = {"synthetic_identity", "synthetic_curated_draft", "engineering_fixture_only"}
IMPORT_MODES = {"host_agent_import", "imported"}
KNOWN_QUALITY_CLAIMS = {
    "host_agent_generated",
    "engineering_fixture_only",
    "imported",
    "synthetic_identity",
    "synthetic_curated_draft",
}


def load_retention_approvals() -> dict[str, dict[str, Any]]:
    """Load separately approved retention decisions (never imported candidates)."""
    if not RETENTION_ADJUDICATION_PATH.is_file():
        return {}
    data = read_json(RETENTION_ADJUDICATION_PATH)
    approvals: dict[str, dict[str, Any]] = {}
    for row in data.get("rows", []):
        if row.get("review_status") == "approved":
            approvals[row["segment_id"]] = {
                "approved_classification": row.get("approved_classification"),
                "classification_note": row.get("classification_note"),
                "review_status": "approved",
                "reviewer_type": row.get("reviewer_type"),
            }
    return approvals


def apply_retention_approvals(segments: list[dict[str, Any]]) -> int:
    """Merge separately approved retention decisions into segments (in place)."""
    approvals = load_retention_approvals()
    applied = 0
    for segment in segments:
        approval = approvals.get(segment["segment_id"])
        if approval:
            segment.update(approval)
            applied += 1
    return applied


STALE_DURABLE_EVIDENCE_REFS = [
    "work/real-generation-metadata.json",
    "work/real-generation-summary.md",
    "work/e2-review-sheet.csv",
    "work/e2-review-summary.json",
    "work/e2-review-summary.md",
    "work/terminology-adjudication.csv",
    "work/terminology-adjudication.md",
    "work/official-reference-comparison.json",
    "work/visual-smoke-report.json",
    "work/visual-smoke-report.md",
    "work/real-evidence-verification.json",
    "work/real-evidence-verification.md",
]


def verify_evidence_references() -> list[str]:
    """Scan committed evidence files for stale or missing benchmark-relative refs."""
    problems: list[str] = []
    text_files: list[Path] = []
    for root in (REPORTS, EVIDENCE):
        if root.is_dir():
            for pattern in ("*.json", "*.md", "*.csv"):
                text_files.extend(sorted(root.glob(pattern)))
    for extra in (BENCH_ROOT / "README.md", REPOSITORY_ROOT / "docs" / "benchmarking.md"):
        if extra.is_file():
            text_files.append(extra)
    reference_re = re.compile(r"\b(?:reports|evidence)/[A-Za-z0-9_./-]+")
    for path in sorted(set(text_files)):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ref in STALE_DURABLE_EVIDENCE_REFS:
            if ref in text:
                problems.append(f"{path.name}: stale durable-evidence reference '{ref}'")
        for ref in reference_re.findall(text):
            ref = ref.rstrip(".,;:)]}")
            candidate = BENCH_ROOT / ref
            if candidate.is_file():
                continue
            if ref.endswith("/") and candidate.is_dir():
                continue
            if (
                candidate.parent.is_dir()
                and any(item.is_file() and item.stem == candidate.name for item in candidate.parent.iterdir())
            ):
                continue
            if not candidate.exists():
                problems.append(f"{path.name}: referenced evidence file does not exist '{ref}'")
    return problems


def retention_is_approved(segment: dict[str, Any]) -> bool:
    """Separate retention approval: candidate classification is not approval."""
    return (
        segment.get("review_status") == "approved"
        and segment.get("approved_classification") in RETENTION_CLASSIFICATIONS
        and bool(segment.get("classification_note"))
        and bool(segment.get("reviewer_type"))
    )


def generation_accounting(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Independent counts for the generation summary (definitions in README)."""
    from collections import Counter

    total = len(segments)

    def is_identity(segment: dict[str, Any]) -> bool:
        source = str(segment.get("source", ""))
        return bool(source) and str(segment.get("target", "")) == source

    identity_ids = {segment["segment_id"] for segment in segments if is_identity(segment)}
    imported_segments = sum(1 for s in segments if s.get("generation_mode") in IMPORT_MODES)
    engineering_fixture_segments = sum(
        1
        for s in segments
        if s.get("generation_mode") in ENGINEERING_FIXTURE_MODES
        or s.get("quality_claim") == "engineering_fixture_only"
    )
    target_identical_to_source_segments = len(identity_ids)
    classified_retained_segments = sum(
        1
        for s in segments
        if s["segment_id"] in identity_ids and s.get("candidate_classification") in RETENTION_CLASSIFICATIONS
    )
    approved_retained_segments = sum(
        1 for s in segments if s["segment_id"] in identity_ids and retention_is_approved(s)
    )
    unclassified_identity_segments = target_identical_to_source_segments - approved_retained_segments
    translated_non_identity_segments = total - target_identical_to_source_segments
    quality_claim_counts = dict(sorted(Counter(s.get("quality_claim", "<missing>") for s in segments).items()))
    generation_mode_counts = dict(sorted(Counter(s.get("generation_mode", "<missing>") for s in segments).items()))
    claims = [claim for claim in quality_claim_counts if claim != "<missing>"]
    quality_claim = claims[0] if len(claims) == 1 else ("mixed" if len(claims) > 1 else "<missing>")
    return {
        "total_segments": total,
        "imported_segments": imported_segments,
        "engineering_fixture_segments": engineering_fixture_segments,
        "target_identical_to_source_segments": target_identical_to_source_segments,
        "classified_retained_segments": classified_retained_segments,
        "approved_retained_segments": approved_retained_segments,
        "unclassified_identity_segments": unclassified_identity_segments,
        "translated_non_identity_segments": translated_non_identity_segments,
        "quality_claim": quality_claim,
        "quality_claim_counts": quality_claim_counts,
        "generation_mode_counts": generation_mode_counts,
    }


def validate_generation_metadata(segments: list[dict[str, Any]], mode: str) -> list[str]:
    """Fail-closed checks for a controlled real-evidence (import) run."""
    if mode != "import":
        return []
    problems: list[str] = []
    missing_metadata = [
        segment["segment_id"]
        for segment in segments
        if not segment.get("quality_claim") or not segment.get("generation_mode")
    ]
    if missing_metadata:
        problems.append(f"segments missing quality_claim/generation_mode: {sorted(missing_metadata)[:5]}")
    claims = {str(segment.get("quality_claim")) for segment in segments if segment.get("quality_claim")}
    unknown_claims = sorted(claims - KNOWN_QUALITY_CLAIMS)
    if unknown_claims:
        problems.append(f"unknown quality claims: {unknown_claims}")
    accounting = generation_accounting(segments)
    if accounting["engineering_fixture_segments"]:
        problems.append(
            f"engineering fixture segments present in import run: {accounting['engineering_fixture_segments']}"
        )
    if accounting["quality_claim"] == "mixed":
        problems.append(f"unexpected mixed quality claims: {accounting['quality_claim_counts']}")
    return problems


def segment_review_flags(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Conservative automated review diagnostics (E1, not human review)."""
    flags: list[dict[str, Any]] = []
    untranslated = 0
    placeholder_broken = 0
    for segment in segments:
        source = str(segment.get("source", ""))
        target = str(segment.get("target", ""))
        if target == source and not retention_is_approved(segment):
            untranslated += 1
            flags.append(
                {
                    "segment_id": segment["segment_id"],
                    "pointer": segment.get("context", {}).get("pointer"),
                    "category": "untranslated_english",
                    "severity": "actionable",
                    "note": (
                        "identity target lacks separate retention approval "
                        "(candidate classification is not approval)"
                    ),
                }
            )
        source_tokens = set(re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}", source))
        target_tokens = set(re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}", target))
        if source_tokens != target_tokens:
            placeholder_broken += 1
            flags.append(
                {
                    "segment_id": segment["segment_id"],
                    "pointer": segment.get("context", {}).get("pointer"),
                    "category": "placeholder_parity",
                    "severity": "blocking",
                    "note": f"source={sorted(source_tokens)} target={sorted(target_tokens)}",
                }
            )
    blocking = sum(flag["severity"] == "blocking" for flag in flags)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_level": "E1_automated_only",
        "human_review": False,
        "summary": {"flags": len(flags), "blocking": blocking, "untranslated_english": untranslated},
        "flags": flags,
    }


def flatten_yaml(path: Path) -> dict[str, str]:
    """Flatten a YAML catalog with a real parser for analysis/reference work.

    The existing ``core.yaml-toml`` span extractor is line-based and can
    misread multiline double-quoted scalars (real newlines), so reference
    comparison and audit counts use a real YAML parser instead.
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required for YAML reference analysis (install with `pip install -e '.[yaml]'`)")
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    flat: dict[str, str] = {}

    def visit(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{prefix}.{key}" if prefix else str(key)
                visit(value, child)
        elif isinstance(node, str):
            flat[prefix] = node

    visit(document, "")
    return flat


def report_markdown(report: dict[str, Any], title: str) -> str:
    """Render an aggregate report dict as compact Markdown."""
    lines: list[str] = [f"# {title}", ""]

    def render(value: Any, indent: int = 0) -> None:
        padding = "  " * indent
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    lines.append(f"{padding}- {key}:")
                    render(child, indent + 1)
                else:
                    lines.append(f"{padding}- {key}: {child}")
        elif isinstance(value, list):
            if len(value) > 8:
                lines.append(f"{padding}- {len(value)} items (sample):")
                for child in value[:8]:
                    render(child, indent + 1)
            else:
                for child in value:
                    render(child, indent)
        else:
            lines.append(f"{padding}- {value}")

    render(report)
    joined = "\n".join(lines)
    normalized = "\n".join(line.rstrip() for line in joined.split("\n"))
    return normalized.rstrip() + "\n"


def evaluate_build_gate(report: dict[str, Any] | None) -> tuple[bool, list[str]]:
    """Strong final gate: a build-validation report must exist and every
    required step must have passed. Optional steps may be skipped."""
    problems: list[str] = []
    if report is None:
        return False, ["build-validation report is missing"]
    if report.get("status") != "pass":
        problems.append(f"build-validation top-level status is {report.get('status')!r}, expected 'pass'")
    steps = report.get("steps")
    if not isinstance(steps, list):
        return False, problems + ["build-validation report has no steps list"]
    if not steps:
        return False, problems + ["build-validation report has no steps"]
    required_steps = [step for step in steps if step.get("required", True)]
    if not required_steps:
        return False, problems + ["build-validation report has no required steps"]
    for step in required_steps:
        name = step.get("check", "<unnamed>")
        status = step.get("status")
        passed = step.get("passed")
        if status == "passed" and passed is True:
            continue
        problems.append(
            f"required build step {name!r} did not pass (status={status!r}, passed={passed!r})"
        )
    return not problems, problems
