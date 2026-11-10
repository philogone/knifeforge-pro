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

## Lot 7 — fait le 10 novembre 2026

Installeur Windows (PyInstaller + Inno Setup, construit par la CI), SQLite, création de l'accès
au premier lancement, sauvegarde quotidienne automatique, copie de la base avant chaque mise à
jour. Testé sur l'exécutable : démarrage, migrations, accès, facture Factur-X validée, DXF,
nesting, plan, sauvegarde, mise à jour simulée, double lancement.

Reste à faire :
- **Le test par un non-développeur** sur un Windows neuf (critère du lot) : installation, premier
  lancement, une commande, une facture, en moins de 10 minutes.
- L'installeur n'est pas signé numériquement : Windows SmartScreen affichera « éditeur
  inconnu » au premier lancement. Un certificat de signature de code (payant) l'évite.
- Pas de changement de mot de passe depuis l'interface (seulement la remise à zéro par
  `config.json`).
- Premier démarrage plus lent la toute première fois (analyse antivirus des fichiers).

## Prochain : lots 8 et 9

Voir [`roadmap.md`](roadmap.md).

## Audit complet — proposé, pas lancé

Marché, fonctionnalités / UX, solidité du code (claude-security, /code-review max, pip-audit,
npm audit, couverture), solidité métier (essai de découpe réel, validation Factur-X
indépendante, relecture comptable), juridique, synthèse notée.
