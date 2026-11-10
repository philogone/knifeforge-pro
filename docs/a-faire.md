# À faire

Feuille de route générale : [`roadmap.md`](roadmap.md).

## Lot 6 — terminé le 10 novembre 2026

Mise en page large, menu regroupé (Atelier · Dessin et découpe · Ventes, menu repliable sous
1024 px), tableau de bord d'accueil (`/`, API `GET /api/admin/dashboard`), Matériaux déplacés en
`/materials`, mention « aucune donnée chez l'éditeur » dans les décisions, la licence et la fiche
de vente.

Points laissés en l'état, à reprendre si besoin :
- Le tableau de bord ne se rafraîchit pas tout seul : il se recharge à chaque ouverture.
- Les jauges de stock sont graduées sur deux fois le seuil d'alerte ; une matière sans seuil n'a
  pas de jauge (seulement sa quantité).
- La marge potentielle compte les commandes en brouillon et confirmées, même déjà facturées en
  partie.

## Prochain : lot 7 — installer sans Docker

Voir [`roadmap.md`](roadmap.md#lot-7--installer-sans-docker-priorité-1).

## Audit complet — proposé, pas lancé

Marché, fonctionnalités / UX, solidité du code (claude-security, /code-review max, pip-audit,
npm audit, couverture), solidité métier (essai de découpe réel, validation Factur-X
indépendante, relecture comptable), juridique, synthèse notée.
