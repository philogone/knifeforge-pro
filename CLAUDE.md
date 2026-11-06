# KnifeForge Pro — consignes pour Claude Code

- Réponds en français.
- Si un message se termine par « L99 » (ou utilise /l99) : réponse d'expert approfondie — hypothèses explicites, cas limites, compromis, risques, vérification dans le code avant d'affirmer.
- Commandes du projet : /ghost (réécrire sans blabla), /document (documentation technique), /test (cas de test), /l99.
- Exigence non négociable : précision de l'outil meilleure que 0,1 mm. Ne pas augmenter la tolérance d'aplatissement des courbes (0,01 mm, DEFAULT_TOLERANCE_MM) ni affaiblir la garantie « espacement du nesting = minimum garanti » sans accord explicite. Voir HANDOVER.md, section « KnifeForge Pro ».
- Tests : `cd backend && pytest` (86 attendus) ; `cd frontend && npm test` (123 attendus), `npx vue-tsc --noEmit`, `npm run build`.
- Ne jamais commiter de .env. Ne pas modifier le dépôt d'origine philogone/KnifeForge.
