# Hermes Agent Terminology Adjudication (fr)

Adjudicator: host agent (AI-assisted), informed by the official Hermes `fr.yaml` and Web `fr.ts` references.

| Term | YAML/CLI | Web | Desktop | Decision | Note |
| --- | --- | --- | --- | --- | --- |
| agent | agent | agent | agent | intentional | retained on all surfaces; matches official Hermes French |
| session | session | session | session | intentional | retained on all surfaces; matches official Hermes French |
| token | tokens | tokens | tokens | intentional | retained on all surfaces |
| prompt | prompt | prompt | prompt | intentional | retained on all surfaces (product term) |
| skill | skill(s) | skill(s) | skill(s) | intentional | retained on all surfaces (product term); YAML matches official |
| plugin | plugin | plugin | plugin | intentional | retained on all surfaces |
| provider | fournisseur | provider | provider (fournisseur d'identité) | context_dependent | YAML follows official fr.yaml ('fournisseur'); Web/Desktop retain 'provider' for product/provider names; generic 'identity provider' translated as 'fournisseur d'identité' |
| gateway | gateway | gateway | gateway | intentional | retained on all surfaces; matches official Hermes French |
| model | modèle | modèle | modèle | intentional | translated on all surfaces; command names (/model) preserved |
| tool | outil(s) | outil(s) | outil(s) | intentional | translated on all surfaces |
| reasoning | raisonnement | raisonnement | raisonnement | intentional | translated on all surfaces; /reasoning command preserved |
| approval | approbation | approbation | approbation | intentional | translated on all surfaces |
| allowlist | liste d'autorisation | n/a | liste d'autorisation | intentional | unified to 'liste d'autorisation' (matches official fr.yaml) after review; one desktop string updated |
| blocklist | liste de blocage | n/a | n/a | intentional | YAML only; matches official fr.yaml ('liste de blocage inconditionnel') |
| background | arrière-plan | arrière-plan | arrière-plan | intentional | translated on all surfaces; /background command preserved |
| workspace | n/a | espace de travail | espace de travail | intentional | translated consistently on Web/Desktop |
| restart | redémarrage/redémarrer | redémarrer | redémarrage/redémarrer | intentional | translated on all surfaces; `hermes gateway restart` command preserved |
| delete | supprimé(s) | supprimer | supprimer | intentional | translated on all surfaces |
| clear | effacer | effacer | effacer | intentional | translated on all surfaces |
| reset | /reset preserved; 'effacer' for clear | rétablir (aux valeurs par défaut) | rétablir / réinitialiser | context_dependent | 'reset to defaults' -> 'rétablir les valeurs par défaut'; memory/service resets -> 'réinitialiser'; command tokens (/reset) preserved |

## Decisions

- **intentional** (18): terms retained or translated consistently on every surface, matching official Hermes French where one exists.
- **context_dependent** (2): `provider` (YAML follows official `fournisseur`; Web/Desktop retain the product term, generic compounds like `fournisseur d'identité` are translated) and `reset` (two standard French renderings depending on object: `rétablir` for defaults, `réinitialiser` for memory/services).
- **unresolved**: 0 | **error**: 0

## Actions taken

- Unified the Desktop approval string `allowlist` → `liste d'autorisation permanente` (matches official `fr.yaml`); Desktop rerun passed (QA pass, 0 flags).
- Applied the two E2 corrections to YAML (`goal_cleared`, `reasoning/choice_reset`); YAML rerun passed (QA pass, 0 flags).
