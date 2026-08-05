# Instructions de revue E3 — français natif

Merci d’accepter de relire la localisation française de **Hermes Agent**.
Vous intervenez en tant qu’**évaluateur natif** (E3) : vous jugez le français
comme un utilisateur francophone, et non pas comme un traducteur professionnel
(cette dernière expertise correspond au niveau E4, distinct de cette revue).

## Votre rôle

Vous évaluez principalement :

- le caractère naturel, fluide et idiomatique du français ;
- le registre et la cohérence des formulations ;
- la clarté et la brièveté adaptée à une interface (UI) ;
- la ponctuation et la typographie ;
- l’acceptabilité, pour un utilisateur français, des termes anglais conservés ;
- l’absence d’allure « générée par machine » ou non naturelle.

## Règles impératives

1. **Ne modifiez jamais les éléments protégés** : balises d’espace réservé
   (`{name}`, `%1$s`, `{count}`…), expressions de gabarit (``${...}``),
   commandes, identifiants, URL, chemins, noms de marque, extraits de code.
2. **Préservez** identifiants, noms de produits/modèles/fournisseurs, chaînes
   en code (`backticks`), Markdown et sauts de ligne échappés.
3. **Corrigez** le français maladroit ou non naturel en fournissant une
   proposition dans la colonne `reviewer_target_fr`.
4. **Signalez les questions de sens** avec `needs_bilingual_check = true`
   plutôt que de deviner.
5. **Contrôlez la longueur** des libellés à l’écran (risque d’écrasement UI).
6. **Jugez les termes anglais conservés** : sont-ils acceptables pour un
   utilisateur français ? S’ils doivent être traduits, choisissez
   `translate_retained_term` (proposition dans `reviewer_target_fr`).
7. **Notez chaque révision** dans `reviewer_note`.
8. **Ne remplissez jamais** `user_decision` ni `final_accepted_target` : ces
   champs sont réservés à l’utilisateur ou au responsable de maintenance.
9. **Ne supprimez ni ne réordonnez aucune ligne** du fichier CSV.

## Statuts de revue

- `approved` : le français actuel est acceptable.
- `approved_with_note` : acceptable, avec une remarque (par ex. variante
  recommandée) consignée dans `reviewer_note`.
- `needs_revision` : une proposition de remplacement **obligatoire** doit être
  fournie dans `reviewer_target_fr`.
- `needs_bilingual_check` : incertitude sur le sens ou le comportement du
  produit ; ne pas inventer de traduction.
- `reject` : la chaîne est inutilisable ou trompeuse.
- `defer` : à traiter ultérieurement / hors de portée de cette revue.

## Échelle de qualité native

- `5` = français natif entièrement naturel ;
- `4` = acceptable avec un léger problème stylistique ;
- `3` = compréhensible mais nettement non naturel ;
- `2` = déroutant ou passablement maladroit ;
- `1` = inutilisable ou trompeur.

## Terminologie

Si un choix de terme vous semble incohérent selon les écrans (par ex.
`gateway`, `session`, `skill`, `fournisseur` vs `provider`), indiquez-le dans
`terminology_decision` et précisez votre recommandation dans `reviewer_note`.

## Métadonnées obligatoires

Renseignez le fichier `reviewer-metadata-template.json` (copiez-le et
remplissez-le) : attestation de langue native, région, date, outils, aide IA
éventuelle, conflits d’intérêts, consentement à la publication des résultats
anonymisés. Aucune information personnelle d’identification n’est requise.

## Livrable

Renvoyez :

1. le CSV complété (`e3-review-sheet.csv`), sans réordonner ni supprimer de
   lignes ;
2. le JSON de métadonnées rempli.

Ne renseignez pas `user_decision` ni `final_accepted_target`.
