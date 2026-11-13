# Décisions commerciales

Arrêtées le 8 novembre 2026. Elles orientent le produit ; les modifier ici avant de changer le code qui en dépend.

| Sujet | Décision | Conséquence dans le produit |
|---|---|---|
| Modèle | Logiciel **auto-hébergé**, un atelier par installation | Pas de multi-tenant ; installation Docker en une commande, assistant de premier lancement, sauvegardes |
| Marché | **France d'abord** | Interface, données de démo, documentation et vitrine en français ; l'anglais reste disponible |
| Prix | **Gratuit** (décidé le 13 novembre 2026, remplace 99 € + 30 €/an) | Installeurs publiés librement ; pas de certificat de signature payant |
| Support | **Communauté** seulement | FAQ et dépannage dans la documentation ; pas d'engagement de délai |
| Licence | **GNU AGPL v3** (décidé le 13 novembre 2026, remplace la licence commerciale) | `LICENSE` (texte AGPL) et `NOTICE.md` (données, factures, calculs) ; toute version modifiée diffusée ou mise en ligne reste libre |
| Factures | Statut fiscal **réglable par l'utilisateur** (micro-entreprise « TVA non applicable, art. 293 B du CGI » ou assujetti) | Réglages › Facturation ; mentions légales générées selon le statut |
| Facture électronique | Conforme à la réforme française (réception depuis le 1er septembre 2026, émission obligatoire pour les PME et micro-entreprises au 1er septembre 2027) et à la norme EN 16931 | Factures **Factur-X** (PDF/A-3 + XML CII), numérotation continue, avoirs, nouvelles mentions (SIREN client, adresse de livraison, nature de l'opération, TVA sur les débits). Dépôt sur la plateforme agréée choisie par l'atelier |
| Responsabilité des données | **Aucune donnée chez l'éditeur** | L'atelier héberge l'outil chez lui. Aucun hébergement, aucune télémétrie, aucun appel vers l'éditeur ; les polices et scripts sont servis localement et la CSP limite les connexions à l'installation (`connect-src 'self'`). L'atelier est seul responsable de traitement (RGPD) ; l'éditeur n'est pas sous-traitant |
| Données clients | **Outils RGPD de base** | Export et effacement des données d'un client, modèle de mentions d'information |
