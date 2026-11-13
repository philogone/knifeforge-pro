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

## Lot 8 — fait le 12 novembre 2026

Pouces (affichage et saisie, règles en fractions), feuille de pièces PDF 1:1 avec croix de
pointage et pages à assembler, crantage et dentelure, masse et point d'équilibre, pliants
(rotation et course de la lame), 12 profils de lames de plus, export STL.

Points laissés en l'état :
- Les plans clients et les exports restent en millimètres (le DXF déclare des mm, ce que les
  machines lisent sans ambiguïté) ; seul l'éditeur passe en pouces.
- Le point d'équilibre traite chaque pièce comme une plaque d'épaisseur constante : émouture,
  biseaux et plaquettes galbées ne sont pas pris en compte.
- La course d'un pliant se vérifie contre les obstacles choisis ; le dépassement du tranchant
  hors du manche une fois fermé n'est pas encore mesuré.
- Le crantage suit un tronçon droit ; pas encore le long d'une courbe.

## Prochain : lot 9 (preuves du sérieux), puis lot 10

Voir [`roadmap.md`](roadmap.md).

## Audit complet — proposé, pas lancé

Marché, fonctionnalités / UX, solidité du code (claude-security, /code-review max, pip-audit,
npm audit, couverture), solidité métier (essai de découpe réel, validation Factur-X
indépendante, relecture comptable), juridique, synthèse notée.
