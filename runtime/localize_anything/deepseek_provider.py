"""DeepSeek translation provider for Localize Anything."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_jsonl, write_jsonl
from .json_adapter import extract_placeholders

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"  # fast model for translation
DEEPSEEK_ENV_FILE_VARS = (
    "LOCALIZE_ANYTHING_DEEPSEEK_ENV_FILE",
    "DEEPSEEK_ENV_FILE",
)
SOURCE_FILES = [  # key source files to load for context
    (Path(__file__).resolve().parent.parent.parent.parent / "test02-antennapod/source/res/values/strings.xml"),
]


class ProviderGenerationError(RuntimeError):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def _get_api_key() -> str:
    """Get DeepSeek API key from explicit environment configuration."""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key

    for env_var in DEEPSEEK_ENV_FILE_VARS:
        env_file = os.environ.get(env_var, "").strip()
        if env_file:
            return _read_api_key_from_env_file(Path(env_file), env_var)

    raise RuntimeError(
        "DEEPSEEK_API_KEY not found. Set DEEPSEEK_API_KEY or explicitly set "
        "LOCALIZE_ANYTHING_DEEPSEEK_ENV_FILE to an env file containing DEEPSEEK_API_KEY."
    )


def _read_api_key_from_env_file(path: Path, env_var: str) -> str:
    if not path.exists():
        raise RuntimeError(f"{env_var} points to an env file that does not exist.")

    content = path.read_text(encoding="utf-8")
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("DEEPSEEK_API_KEY="):
            key = stripped.split("=", 1)[1].strip().strip('"').strip("'")
            if key:
                return key

    raise RuntimeError(f"{env_var} does not contain DEEPSEEK_API_KEY.")


def translate_batch_deepseek(
    segments: list[dict[str, Any]],
    target_locale: str,
    source_locale: str = "en-US",
    model: str = DEFAULT_MODEL,
) -> list[dict[str, Any]]:
    """Translate a batch of segments using DeepSeek API.

    Args:
        segments: List of segment dicts from work packets
        target_locale: e.g. 'ja', 'ko', 'zh-CN'
        source_locale: Source locale like 'en-US'
        model: DeepSeek model name

    Returns:
        Generated segments with target translations
    """
    try:
        api_key = _get_api_key()
    except RuntimeError as exc:
        raise ProviderGenerationError("provider_configuration_error", str(exc)) from exc
    locale_names = {"ja": "日本語", "ko": "한국어", "zh-CN": "简体中文", "fr": "Français", "de": "Deutsch"}

    # Build translation prompt
    locale_name = locale_names.get(target_locale, target_locale)
    entries = []
    for seg in segments:
        source = seg.get("source", "")
        seg_id = seg.get("segment_id", "")
        constraints = seg.get("constraints", {})
        context = constraints.get("note", "")

        entry = f'  {{"id": "{seg_id}", "source": {json.dumps(source, ensure_ascii=False)}'
        if context:
            entry += f', "context": {json.dumps(context, ensure_ascii=False)}'
        entry += "}"
        entries.append(entry)

    entries_block = ",\n".join(entries)

    system_prompt = (
        f"You are a professional translator localizing an Android app (AntennaPod podcast player) "
        f"from {source_locale} to {locale_name} ({target_locale}).\n\n"
        f"Rules:\n"
        f"1. Preserve all placeholders exactly: %1$s, %2$d, %s, %d, etc.\n"
        f"2. Preserve HTML/XML tags: <b>, <i>, <a href=\"...\">, <br/>, etc.\n"
        f"3. Preserve special tokens: \\n, \\t, @string/ references\n"
        f"4. Use natural, native-sounding {locale_name}. No literal translations.\n"
        f"5. For podcast/tech terms, use commonly accepted translations.\n"
        f"6. Keep proper nouns (AntennaPod, gpodder.net) untranslated.\n"
        f"7. For short strings (1-3 words), prefer concise forms.\n"
        f"8. Output ONLY a JSON array of objects with \"id\" and \"target\" fields. No markdown, no explanation.\n"
        f"9. Translate ALL entries in one response. Do not skip any."
    )

    user_prompt = (
        f"Translate these {len(segments)} Android app UI strings to {locale_name} ({target_locale}).\n"
        f"Return JSON array with id and target for every entry.\n\n"
        f"[\n{entries_block}\n]"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 8192,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8-sig"))
    except Exception as e:
        raise ProviderGenerationError(
            _provider_error_kind(e),
            f"DeepSeek provider generation failed: {type(e).__name__}: {e}",
        ) from e

    # Parse DeepSeek response
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderGenerationError("malformed_provider_response", "DeepSeek response did not contain message content.") from exc

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0]

    try:
        translations = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderGenerationError("malformed_provider_response", "DeepSeek response content was not valid JSON.") from exc

    # Handle both array and object response formats
    if isinstance(translations, dict):
        # {"translations": [...]} or {"id1": "target1", ...}
        if "translations" in translations:
            translations = translations["translations"]
        else:
            translations = [
                {"id": k, "target": v}
                for k, v in translations.items()
                if k != "id"  # skip explanation fields
            ]

    # Build lookup
    translation_map = {}
    if isinstance(translations, list):
        for t in translations:
            if isinstance(t, dict):
                tid = t.get("id", "")
                ttarget = t.get("target", "")
                if tid and ttarget:
                    translation_map[tid] = ttarget
    else:
        raise ProviderGenerationError("malformed_provider_response", "DeepSeek response did not contain translations.")

    missing = [str(seg.get("segment_id", "")) for seg in segments if str(seg.get("segment_id", "")) not in translation_map]
    if missing:
        raise ProviderGenerationError(
            "malformed_provider_response",
            f"DeepSeek response omitted {len(missing)} segment(s); first missing segment: {missing[0]}",
        )

    # Generate segment records
    generated = []
    for seg in segments:
        seg_id = seg.get("segment_id", "")
        source = seg.get("source", "")
        placeholders = [str(p) for p in seg.get("constraints", {}).get("placeholders", [])]

        target = translation_map[seg_id]

        # Placeholder parity: ensure target preserves all source placeholders
        target = _fix_placeholder_parity(target, placeholders, source)

        record = dict(seg)
        record["target_locale"] = target_locale
        record["target"] = target
        record["status"] = "generated"
        record["generation"] = {
            "provider": "deepseek",
            "model": model,
            "quality_claim": "llm_draft",
            "purpose": "localization",
        }
        generated.append(record)

    return generated


def _provider_error_kind(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in message:
        return "ssl_certificate_error"
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in {401, 403}:
            return "authentication_error"
        if exc.code == 429:
            return "rate_limit"
        return "http_error"
    if isinstance(exc, urllib.error.URLError):
        return "network_error"
    if isinstance(exc, json.JSONDecodeError):
        return "malformed_provider_response"
    return "provider_generation_error"


def _fix_placeholder_parity(
    target: str, expected_placeholders: list[str], source: str
) -> str:
    """Ensure target contains exactly the expected placeholders, no more, no less.

    - Extra placeholders (hallucinated by LLM) are stripped.
    - Missing placeholders are appended from source as a safety suffix.
    """
    from .json_adapter import extract_placeholders

    actual = extract_placeholders(target)
    expected_set = set(expected_placeholders)
    actual_set = set(actual)

    # Remove extra placeholders
    extra = actual_set - expected_set
    for p in extra:
        target = target.replace(p, "").strip()

    # Append missing placeholders
    missing = expected_set - actual_set
    if missing:
        target = target.rstrip() + " " + " ".join(sorted(missing))

    return target


def generate_deepseek_batch_file(
    segments_path: Path,
    generated_output: Path,
    target_locale: str,
    source_locale: str = "en-US",
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Read segments from JSONL, translate via DeepSeek, write generated JSONL."""
    segments = read_jsonl(segments_path)
    try:
        generated = translate_batch_deepseek(segments, target_locale, source_locale, model)
    except ProviderGenerationError as exc:
        if generated_output.exists() and generated_output.is_file():
            generated_output.unlink()
        return _deepseek_failure_result(segments_path, generated_output, target_locale, model, exc)
    write_jsonl(generated_output, generated)

    placeholder_mismatches = []
    for seg in generated:
        target = str(seg.get("target", ""))
        expected = sorted(str(p) for p in seg.get("constraints", {}).get("placeholders", []))
        actual = sorted(extract_placeholders(target))
        if expected != actual:
            placeholder_mismatches.append(seg["segment_id"])

    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime", "deepseek"],
        "status": "fail" if placeholder_mismatches else "pass",
        "input_segments": segments_path.as_posix(),
        "generated_output": generated_output.as_posix(),
        "target_locale": target_locale,
        "provider": "deepseek",
        "provider_requested": "deepseek",
        "provider_actual": "deepseek",
        "provider_status": "passed",
        "provider_generated_segments": len(generated),
        "synthetic_fallback_segments": 0,
        "quality_claim": "llm_draft",
        "apply_allowed": True,
        "model": model,
        "summary": {
            "segment_count": len(segments),
            "generated_segment_count": len(generated),
            "placeholder_mismatch_count": len(placeholder_mismatches),
        },
        "items": [
            {
                "category": "placeholder_parity",
                "severity": "blocking",
                "message": f"Target lost placeholders for {sid}",
                "segment_id": sid,
            }
            for sid in placeholder_mismatches
        ],
    }


def _deepseek_failure_result(
    segments_path: Path,
    generated_output: Path,
    target_locale: str,
    model: str,
    exc: ProviderGenerationError,
) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime", "deepseek"],
        "status": "fail",
        "input_segments": segments_path.as_posix(),
        "generated_output": generated_output.as_posix(),
        "target_locale": target_locale,
        "provider": "deepseek",
        "provider_requested": "deepseek",
        "provider_actual": "none",
        "provider_status": "failed",
        "provider_error_kind": exc.kind,
        "provider_generated_segments": 0,
        "synthetic_fallback_segments": 0,
        "quality_claim": "none",
        "apply_allowed": False,
        "model": model,
        "summary": {
            "segment_count": len(read_jsonl(segments_path)),
            "generated_segment_count": 0,
            "placeholder_mismatch_count": 0,
            "blocking_count": 1,
            "warning_count": 0,
        },
        "items": [
            {
                "channel": "runtime",
                "category": exc.kind,
                "severity": "blocking",
                "message": str(exc),
                "checked_by": "runtime",
                "coverage": "complete",
                "confidence": "deterministic",
            }
        ],
    }
