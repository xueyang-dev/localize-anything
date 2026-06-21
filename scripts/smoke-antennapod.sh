#!/usr/bin/env bash
set -euo pipefail

PROJECT_PATH="${1:-}"
OUT_DIR="${2:-}"
PYTHON_BIN="${PYTHON:-}"

if [[ -z "$PROJECT_PATH" ]]; then
  echo "Usage: scripts/smoke-antennapod.sh /path/to/AntennaPod [output-dir]" >&2
  exit 2
fi

if [[ ! -d "$PROJECT_PATH" ]]; then
  echo "Project path does not exist: $PROJECT_PATH" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
PROJECT_PATH="$(cd "$PROJECT_PATH" && pwd -P)"

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
  else
    echo "Python was not found. Activate the project environment or set PYTHON=/path/to/python." >&2
    exit 2
  fi
fi

if ! git -C "$PROJECT_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Project path is not a Git checkout: $PROJECT_PATH" >&2
  exit 2
fi

if [[ -z "$OUT_DIR" ]]; then
  OUT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/localize-anything-antennapod.XXXXXX")"
else
  OUT_DIR="$("$PYTHON_BIN" -c 'import os, sys; print(os.path.realpath(os.path.abspath(sys.argv[1])))' "$OUT_DIR")"
fi

case "$OUT_DIR/" in
  "$PROJECT_PATH/"*)
    echo "Output directory must be outside the AntennaPod checkout: $OUT_DIR" >&2
    exit 2
    ;;
esac

case "$OUT_DIR/" in
  "$REPO_ROOT/"*)
    if ! git -C "$REPO_ROOT" check-ignore -q "$OUT_DIR"; then
      echo "Output inside Localize Anything must be gitignored: $OUT_DIR" >&2
      exit 2
    fi
    ;;
esac

mkdir -p "$OUT_DIR"

before_status="$(git -C "$PROJECT_PATH" status --porcelain --untracked-files=all)"

echo "Project: $PROJECT_PATH"
echo "Output: $OUT_DIR"
echo "+ git -C PROJECT rev-parse HEAD"
git -C "$PROJECT_PATH" rev-parse HEAD | tee "$OUT_DIR/antennapod-commit.txt"
echo "+ git -C LOCALIZE_ANYTHING rev-parse HEAD"
git -C "$REPO_ROOT" rev-parse HEAD | tee "$OUT_DIR/localize-anything-commit.txt"

cd "$REPO_ROOT"
echo "+ $PYTHON_BIN -m runtime.localize_anything inspect PROJECT --output OUTPUT/inspection.json"
"$PYTHON_BIN" -m runtime.localize_anything inspect \
  "$PROJECT_PATH" \
  --output "$OUT_DIR/inspection.json"
echo "+ $PYTHON_BIN -m runtime.localize_anything validate-protocol"
"$PYTHON_BIN" -m runtime.localize_anything validate-protocol > "$OUT_DIR/protocol-validation.json"
echo "+ $PYTHON_BIN -m runtime.localize_anything validate-contracts"
"$PYTHON_BIN" -m runtime.localize_anything validate-contracts > "$OUT_DIR/contract-validation.json"

after_status="$(git -C "$PROJECT_PATH" status --porcelain --untracked-files=all)"
if [[ "$before_status" != "$after_status" ]]; then
  echo "Project Git status changed during read-only inspection." >&2
  diff <(printf '%s\n' "$before_status") <(printf '%s\n' "$after_status") || true
  exit 1
fi

echo "Read-only inspection completed. Full pipeline steps remain manual; see docs/antennapod-smoke-test.md."
