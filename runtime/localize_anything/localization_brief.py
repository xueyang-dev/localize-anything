from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import write_json


LOCALIZATION_BRIEF_JSON = "localization-brief.json"
LOCALIZATION_BRIEF_YAML = "localization-brief.yaml"


def build_localization_brief(
    inspection: dict[str, Any],
    *,
    source_locale: str,
    source_files: list[str],
    target_locales: list[str],
    operating_mode: str,
    reference_policy: str,
    workflow_depth: str,
    preflight_mode: str,
    privacy_mode: str,
    data_classification: str,
) -> dict[str, Any]:
    supported_files = inspection.get("supported_files", [])
    adapter_counts = dict(sorted(inspection.get("adapter_counts", {}).items()))
    project_type = _detected_project_type(adapter_counts)
    primary_adapter = _primary_adapter(adapter_counts)
    scenario = _scenario(project_type, primary_adapter)
    style = _style_defaults(scenario)
    allowed_transformations = _allowed_transformations(scenario)
    forbidden_behaviors = _forbidden_behaviors()
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-localization-brief-v1",
        "status": "draft",
        "document_type": _document_type(project_type, primary_adapter),
        "source_genre": _source_genre(scenario, project_type),
        "target_mode": _target_mode(scenario, operating_mode),
        "target_audience": ["unknown_requires_user_confirmation"],
        "style": style,
        "allowed_transformations": allowed_transformations,
        "forbidden_behaviors": forbidden_behaviors,
        "task_intent": {
            "scenario": scenario,
            "source_locale": source_locale,
            "target_locales": target_locales,
            "operating_mode": operating_mode,
            "reference_policy": reference_policy,
            "target_delivery_form": "reviewable_delivery_bundle",
            "requires_user_confirmation": True,
        },
        "source_surface": {
            "project_path": inspection.get("project_root"),
            "detected_project_type": project_type,
            "primary_adapter": primary_adapter,
            "supported_file_count": len(supported_files),
            "selected_source_files": source_files,
            "adapter_counts": adapter_counts,
            "unprocessed_non_text_asset_count": len(inspection.get("unprocessed_non_text_assets", [])),
        },
        "strategy": {
            "workflow_depth": workflow_depth,
            "preflight_mode": preflight_mode,
            "privacy_mode": privacy_mode,
            "data_classification": data_classification,
            "style": style,
            "allowed_transformations": allowed_transformations,
            "forbidden_behaviors": forbidden_behaviors,
        },
        "constraints": {
            "do_not_invent_facts": True,
            "preserve_core_data": True,
            "preserve_placeholders": True,
            "preserve_markup": True,
            "flag_unconfirmed_names": True,
            "localize_policy_terms": scenario == "document_localization",
        },
        "required_human_confirmations": _required_confirmations(inspection, scenario),
        "evidence": {
            "derived_from": ["inspect_project", "initialize_project"],
            "confidence": "deterministic_defaults",
            "limitations": [
                "brief is a deterministic draft and does not prove task intent has been accepted by the user",
                "semantic audience, claims, and terminology still require review before review_ready delivery",
            ],
        },
    }


def write_localization_brief(state_dir: Path, brief: dict[str, Any]) -> dict[str, str]:
    json_path = state_dir / LOCALIZATION_BRIEF_JSON
    yaml_path = state_dir / LOCALIZATION_BRIEF_YAML
    write_json(json_path, brief)
    yaml_path.write_text(render_localization_brief_yaml(brief), encoding="utf-8", newline="\n")
    return {
        "localization_brief": LOCALIZATION_BRIEF_JSON,
        "localization_brief_yaml": LOCALIZATION_BRIEF_YAML,
    }


def localization_brief_asset_paths(state_dir: Path) -> dict[str, str]:
    assets: dict[str, str] = {}
    if (state_dir / LOCALIZATION_BRIEF_JSON).is_file():
        assets["localization_brief"] = LOCALIZATION_BRIEF_JSON
    if (state_dir / LOCALIZATION_BRIEF_YAML).is_file():
        assets["localization_brief_yaml"] = LOCALIZATION_BRIEF_YAML
    return assets


def render_localization_brief_yaml(brief: dict[str, Any]) -> str:
    lines = ["# Localize Anything Localization Brief", ""]
    lines.extend(_yaml_lines(_strip_protocol_fields(brief)))
    return "\n".join(lines) + "\n"


def _detected_project_type(adapter_counts: dict[str, int]) -> str:
    if not adapter_counts:
        return "unknown"
    platform_adapters = {
        "core.android-strings": "android",
        "core.ios-strings": "ios",
        "core.xcstrings": "xcstrings",
    }
    detected = [
        (adapter, project_type)
        for adapter, project_type in platform_adapters.items()
        if adapter_counts.get(adapter)
    ]
    if len(detected) == 1 and sum(adapter_counts.values()) == adapter_counts[detected[0][0]]:
        return detected[0][1]
    if adapter_counts.get("core.word-document") and sum(adapter_counts.values()) == adapter_counts["core.word-document"]:
        return "document"
    if detected:
        return "mixed"
    return "generic"


def _primary_adapter(adapter_counts: dict[str, int]) -> str | None:
    if not adapter_counts:
        return None
    return sorted(adapter_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _scenario(project_type: str, primary_adapter: str | None) -> str:
    if project_type in {"android", "ios", "xcstrings"}:
        return "software_resource_localization"
    if project_type == "document" or primary_adapter == "core.word-document":
        return "document_localization"
    return "project_localization"


def _document_type(project_type: str, primary_adapter: str | None) -> str:
    if project_type == "document" or primary_adapter == "core.word-document":
        return "unclassified_document"
    if project_type == "android":
        return "android_resource_project"
    if project_type == "ios":
        return "ios_resource_project"
    if project_type == "xcstrings":
        return "xcstrings_catalog_project"
    if project_type == "mixed":
        return "mixed_localization_project"
    return "generic_localization_project"


def _source_genre(scenario: str, project_type: str) -> str:
    if scenario == "document_localization":
        return "unclassified_document_source"
    if scenario == "software_resource_localization":
        return f"{project_type}_resource_strings"
    return "project_locale_assets"


def _target_mode(scenario: str, operating_mode: str) -> str:
    if scenario == "document_localization":
        return "review_ready_localized_document"
    if operating_mode == "blind_benchmark":
        return "blind_evaluation_delivery"
    if operating_mode == "existing_locale_maintenance":
        return "existing_locale_maintenance_delivery"
    if operating_mode == "rewrite_or_harmonization":
        return "rewrite_or_harmonization_delivery"
    return "greenfield_localization_delivery"


def _style_defaults(scenario: str) -> dict[str, str]:
    if scenario == "document_localization":
        return {
            "formality": "high",
            "literalness": "medium_low",
            "publicity_tone": "restrained",
        }
    return {
        "formality": "contextual",
        "literalness": "preserve_function",
        "publicity_tone": "not_applicable",
    }


def _allowed_transformations(scenario: str) -> list[str]:
    if scenario == "document_localization":
        return [
            "split",
            "merge",
            "localized_rewrite",
            "explanatory_expansion",
            "structural_relocation",
        ]
    return ["localized_rewrite", "terminology_adaptation"]


def _forbidden_behaviors() -> list[str]:
    return [
        "unsupported_official_recognition",
        "invented_awards",
        "metric_boundary_change",
        "placeholder_loss",
        "markup_corruption",
        "silent_scope_expansion",
    ]


def _required_confirmations(inspection: dict[str, Any], scenario: str) -> list[dict[str, str]]:
    confirmations = [
        {
            "item": "task_intent",
            "reason": "runtime can infer a draft strategy but cannot accept task intent for the user",
            "status": "required",
        },
        {
            "item": "target_audience",
            "reason": "audience assumptions affect style, terminology, and acceptable transformations",
            "status": "required",
        },
    ]
    if scenario == "document_localization":
        confirmations.append(
            {
                "item": "claims_and_metrics",
                "reason": "document localization can change perceived facts, numbers, awards, or institutional claims",
                "status": "required",
            }
        )
    if inspection.get("unprocessed_non_text_assets"):
        confirmations.append(
            {
                "item": "non_text_assets",
                "reason": "non-text assets were inventoried but not localized",
                "status": "required",
            }
        )
    if inspection.get("android_coverage", {}).get("visible_ui_coverage_warning"):
        confirmations.append(
            {
                "item": "android_visible_ui_coverage",
                "reason": "source-only Android localization may not cover merged dependency or runtime UI strings",
                "status": "required",
            }
        )
    return confirmations


def _strip_protocol_fields(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: child
        for key, child in value.items()
        if key not in {"protocol_version", "schema"}
    }


def _yaml_lines(value: Any, indent: int = 0) -> list[str]:
    prefix = "  " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(child, indent + 1))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(child)}")
        return lines
    if isinstance(value, list):
        lines = []
        for child in value:
            if isinstance(child, dict):
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(child, indent + 1))
            elif isinstance(child, list):
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(child, indent + 1))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(child)}")
        return lines
    return [f"{prefix}{_yaml_scalar(value)}"]


def _yaml_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    text = str(value)
    if not text:
        return '""'
    if any(character in text for character in (":", "#", "\n", "[", "]", "{", "}")):
        return '"' + text.replace('"', '\\"') + '"'
    return text
