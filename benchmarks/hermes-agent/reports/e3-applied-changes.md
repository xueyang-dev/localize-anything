# Hermes French E3 applied changes

Revisions applied: **5**

| segment_id | surface | pointer | old target | new target | reviewer note |
| --- | --- | --- | --- | --- | --- |
| `typescript-locale:apps/desktop/src/i18n/en.ts#13de2f9f88cfa0b27ed8` | desktop | /desktop/providerCredentialRequired | Ajoutez un justificatif de provider avant d'envoyer votre premier message. | Ajoutez des identifiants de provider avant d'envoyer votre premier message. | « Justificatif » est un faux sens pour « credential » ; en interface, « identifiants » est plus naturel. |
| `typescript-locale:apps/desktop/src/i18n/en.ts#76430f6fa3de3f3c61dc` | desktop | /settings/providers/removeTerminalConfirm#fn0 | Déconnecter ${provider} ? Cela exécute « ${command} » dans le terminal pour effacer le justificatif. | Déconnecter ${provider} ? Cela exécute « ${command} » dans le terminal pour effacer l'identifiant. | « Justificatif » pour « credential » : à remplacer par « identifiant ». |
| `typescript-locale:web/src/i18n/en.ts#1614543126091f4fee48` | web | /kanban/confirmBlocked | Marquer cette tâche comme bloquée ? La revendication du worker est libérée. | Marquer cette tâche comme bloquée ? Le worker est libéré de cette tâche. | « Revendication » est un faux sens pour « claim » (la prise en charge du worker). |
| `typescript-locale:web/src/i18n/en.ts#a9da5a1256310137f82f` | web | /cron/scheduleDescribe/dailyAt | Quotidien à {time} | Tous les jours à {time} | « Quotidien à » est peu naturel pour un horaire ; « Tous les jours à » est plus idiomatique. |
| `yaml:locales/en.yaml#d11cd0bd64bc1c2a4837` | yaml | /gateway/context/last_savings | Dernière compression libérée : {savings}% du contexte | La dernière compression a libéré {savings}% du contexte. | « Dernière compression libérée » est ambigu : « freed » porte sur le contexte, pas sur la compression. |
