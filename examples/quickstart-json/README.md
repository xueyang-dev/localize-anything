# Quickstart JSON Fixture

This tiny fixture is a complete five-command Localize Anything quickstart.

It is intentionally small and public-safe. Demo output is synthetic/local
engineering evidence only, not translation quality proof.

From the repository root:

```bash
PROJECT="$(pwd)/examples/quickstart-json"

localize scan "$PROJECT" \
  --source-locale en-US \
  --target-locale ru-RU \
  --source locales/en-US.json

localize glossary bootstrap "$PROJECT"
```

For a zero-i18n project, stop before `scan`: the Coding Agent must first create
the project's i18n setup and the source file. This fixture already has the
source resource at `locales/en-US.json`.

Create or edit the target resource with project-native tools:

```bash
cat > "$PROJECT/locales/ru-RU.json" <<'JSON'
{
  "menu": {
    "start": "Начать игру",
    "welcome": "Добро пожаловать, {player}!"
  },
  "inventory": {
    "coins": "У вас {{count}} монет.",
    "weight": "Вес: %s кг"
  }
}
JSON

python3 -m json.tool "$PROJECT/locales/ru-RU.json" >/dev/null
```

Run deterministic checks and prepare the independent review packet:

```bash
localize check "$PROJECT" --target locales/ru-RU.json
localize review "$PROJECT" --target locales/ru-RU.json
```

The review packet is written to `.localize-anything/review-packet.json`. It
includes `source_target_mapping`, `project_memory`, `glossary`,
`deterministic_check`, aligned `files`, and `review_result_format`.

Record independent review output:

```bash
cat > "$PROJECT/review.json" <<'JSON'
{
  "reviewer": "fresh-review-context",
  "review_items": [
    {
      "id": "checked-placeholders",
      "severity": "informational",
      "status": "auto_cleared",
      "note": "Placeholders and printf tokens are preserved."
    }
  ],
  "findings": []
}
JSON

localize review "$PROJECT" --target locales/ru-RU.json --findings "$PROJECT/review.json"
localize report "$PROJECT"
```

Expected final report status for this fixture is `ready` when the target JSON
matches the source keys and no independent review finding requires human
confirmation.
