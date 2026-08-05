# Hermes French E3 native-speaker review summary

- Reviewer type: **native-language reviewer** (`fr-native-01`), human review: **true**
- Professional localization review (E4): false | user accepted: false
- Overall status: **reviewed_with_pending_bilingual_checks**
- Sample size: 508 (all mandatory rows reviewed)
- AI assistance used by reviewer: True (recorded truthfully)
- Revisions proposed: 5 | applied: 5
- needs_bilingual_check: 6
- Rejected: 0 | deferred: 0
- Identity retentions confirmed: 203 | translated: 0 | unresolved: 0

## Counts by status

| status | count |
| --- | --- |
| approved | 456 |
| approved_with_note | 41 |
| needs_bilingual_check | 6 |
| needs_revision | 5 |

## Counts by native-quality rating

| rating | count |
| --- | --- |
| 2 | 1 |
| 3 | 10 |
| 4 | 35 |
| 5 | 462 |

## Bilingual questions left for the project owner

- `typescript-locale:apps/desktop/src/i18n/en.ts#01d871e8ebbbb81d8949` (/desktop/branchFailed): « Branch failed » : confirmer s'il s'agit de la création ou du changement de branche (git) ; « branchement » prête à confusion.
- `typescript-locale:apps/desktop/src/i18n/en.ts#1eb61138484c8cc68fd8` (/updates/moreChanges#fn0): Le gabarit `${count === 1 ? '' : 's'}` ne permet pas l'accord français correct (« 2 autres modification incluse » serait fautif). À faire corriger côté produit (pluriel explicite ou ICU).
- `typescript-locale:apps/desktop/src/i18n/en.ts#7a67643bb2d280d77c92` (/messaging/approvedHint): L'anglais « They » est pluriel (ou neutre) ; le français utilise le singulier « Il… son ». Vérifier le référent.
- `typescript-locale:apps/desktop/src/i18n/en.ts#7af64a6db5feeef77179` (/skills/hub/verdictDangerous): « Dangereuse » (féminin) suppose un nom féminin (commande, action) ; en étiquette isolée, préférer « Dangereux ».
- `typescript-locale:apps/desktop/src/i18n/en.ts#d6d56f5c17480c4a0dba` (/skills/disableUnused): « Désactiver les inutilisées » : l'objet (« unused ») n'est pas précisé et l'accord féminin est incertain.
- `typescript-locale:web/src/i18n/en.ts#96315f26d473ac06d96a` (/achievements/filters/visibility_secret): L'anglais est au singulier (« secret »), le français au pluriel (« secrets ») ; incohérence à vérifier.
