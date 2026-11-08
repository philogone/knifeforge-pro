# Décisions commerciales

Arrêtées le 8 novembre 2026. Elles orientent le produit ; les modifier ici avant de changer le code qui en dépend.

| Sujet | Décision | Conséquence dans le produit |
|---|---|---|
| Modèle | Code source **auto-hébergé**, un atelier par installation | Pas de multi-tenant ; installation Docker en une commande, assistant de premier lancement, sauvegardes |
| Marché | **France d'abord** | Interface, données de démo, documentation et vitrine en français ; l'anglais reste disponible |
| Prix | **99 €** avec 1 an de mises à jour, puis **30 €/an** (optionnel) | Fiche de vente, notes de version datées |
| Support | **Communauté** seulement | FAQ et dépannage dans la documentation ; pas d'engagement de délai |
| Licence | **Commerciale propriétaire** | `LICENSE` : modification libre pour son atelier, ni revente ni redistribution |
| Factures | Statut fiscal **réglable par l'utilisateur** (micro-entreprise « TVA non applicable, art. 293 B du CGI » ou assujetti) | Réglages › Facturation ; mentions légales générées selon le statut |
| Facture électronique | Conforme à la réforme française (réception depuis le 1er septembre 2026, émission obligatoire pour les PME et micro-entreprises au 1er septembre 2027) et à la norme EN 16931 | Factures **Factur-X** (PDF/A-3 + XML CII), numérotation continue, avoirs, nouvelles mentions (SIREN client, adresse de livraison, nature de l'opération, TVA sur les débits). Dépôt sur la plateforme agréée choisie par l'atelier |
| Données clients | **Outils RGPD de base** | Export et effacement des données d'un client, modèle de mentions d'information |
