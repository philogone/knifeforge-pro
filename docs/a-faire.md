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
- ~~Pas de changement de mot de passe depuis l'interface~~ : fait (Réglages › Accès, version
  installée ; sous Docker, toujours par `.env`).
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
- ~~Dépassement du tranchant hors du manche, lame fermée~~ : fait (marge ou dépassement, partie
  qui dépasse en rouge).
- ~~Crantage le long d'une courbe~~ : fait (option « Suivre le contour »).

## Lot 9 — fait le 13 novembre 2026

- Planche de contrôle (Dessin et découpe › Contrôle de découpe) : pièces étalons, fiche de
  relevé 1:1, trait réel, échelle machine, compensation conseillée reportée dans l'export.
- Guide utilisateur (`docs/guide/README.md`), captures comprises, limites écrites.
- Démo publique en lecture seule (`DEMO=true`, `docker-compose.demo.yml`).
- Versions : `CHANGELOG.md`, étiquette `vX.Y.Z` = publication automatique des installeurs
  Windows, Linux (AppImage) et macOS (Apple Silicon), empreintes SHA-256, badges CI et version.
- Validation Factur-X indépendante : Mustang (schematron EN 16931 et PDF/A-3) dans la CI,
  rapports joints à chaque version.

Reste à faire (hors code) :
- **Découper une vraie planche** (laser et jet d'eau) et publier les mesures relevées.
- **Héberger la démo** (sun-lenovo ou autre) derrière HTTPS, et mettre son lien dans le README.
- **Vidéo** de 3 minutes, de l'esquisse à la facture.
- Les nouvelles tâches CI (Linux, macOS, Mustang) n'ont pas encore tourné : à vérifier au
  premier push. Mustang peut relever des écarts PDF/A que le schéma XSD ne voit pas.
- macOS : seulement Apple Silicon (pas d'Intel), application non notariée (compte Apple
  développeur payant pour l'éviter).
- Les liens « dernière version » du README ne marchent qu'avec une version **publiée** (pas une
  préversion) ; le dépôt étant privé, ils demandent un compte GitHub autorisé.

## Lot 10 — fait le 13 novembre 2026

Encaissements et factures d'acompte, envoi par e-mail (compte SMTP de l'atelier, hors base),
relances à trois niveaux avec historique, comptabilité (CA facturé / encaissé, TVA due par
exigibilité, journal au format du FEC, ventes CSV), reprise des sauvegardes d'une version
précédente, reprise dès l'assistant de bienvenue, rappel de sauvegarde.

Reste à faire ou à décider :
- **Plateforme agréée** : choisir une ou deux plateformes avec toi (compte, conditions, API),
  avant de coder le dépôt automatique. Obligation d'émission au 1er septembre 2027.
- Facture en franchise **sans** n° de TVA : refusée par la règle EN 16931 BR-E-02 ; aucune
  source fiable ne dit quoi mettre à la place. L'application conseille de demander le numéro.
- Factures **mixtes** (biens et services) : comptées comme biens pour l'exigibilité de la TVA.
- Pas d'**envoi automatique** des relances (choix : chaque relance est relue et envoyée par
  l'atelier).
- Le journal des ventes n'est pas un FEC complet (il vient du logiciel du comptable).
- Plus tard : **import depuis un autre outil** (clients, matières, modèles en CSV).

## Lot 11 — fait le 13 novembre 2026

Maquette 3D : rôles et épaisseurs, empilement, goupilles, garde fendue pour la soie, vue 3D
(three.js), 3MF / STL, DXF par plaque avec contrôle de la fraise.

Laissé en l'état :
- Pas de STEP : les DXF par plaque suffisent à l'usinage 2,5D ; un solide exact demanderait un
  moteur de CAO (~100 Mo) ou une écriture maison. À reprendre si un utilisateur en a besoin.
- Plaques à bords droits ; pas d'émouture ni de galbe.
- 3MF vérifié par sa structure (tests) ; pas encore ouvert dans un trancheur réel.

## Lot 12 — en grande partie fait le 13 novembre 2026

Longueur développée et débit de forge, métier (coutelier / forgeron), étapes d'atelier
personnalisables, temps passé par commande, vocabulaire du forgeron.

Reste du lot 12 :
- **Stock au poids et profilés normalisés** (rond, carré, plat, tube, cornière, fer en T ; poids
  et prix au kilo) : non fait.
- **Bibliothèque de formes du forgeron** (volutes, rinceaux, pointes de lance, feuilles,
  colliers) : non faite.
- **Étude** auprès de deux ou trois forgerons : à faire par toi.

## Prochain : fin du lot 12, puis ta passe de test

Voir [`roadmap.md`](roadmap.md).

## Audit complet — proposé, pas lancé

Marché, fonctionnalités / UX, solidité du code (claude-security, /code-review max, pip-audit,
npm audit, couverture), solidité métier (essai de découpe réel, validation Factur-X
indépendante, relecture comptable), juridique, synthèse notée.
