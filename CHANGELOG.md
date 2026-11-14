# Journal des versions

Toutes les évolutions notables de KnifeForge Pro, de la plus récente à la plus ancienne. Les
numéros suivent [SemVer](https://semver.org/lang/fr/) : le deuxième chiffre augmente avec les
nouvelles fonctions, le troisième avec les corrections. Le numéro en cours est dans
[`VERSION`](VERSION) ; chaque version publiée a son étiquette Git `vX.Y.Z` et ses installeurs
dans les [versions GitHub](https://github.com/philogone/knifeforge-pro/releases).

Une mise à jour s'installe par-dessus la précédente : la base est copiée avant toute
modification (dossier « Sauvegardes avant mise à jour »), puis mise à niveau automatiquement.

## [Non publié]

### Modifié
- **Nouveau logo et nouvelle icône** (application, onglet du navigateur, installeurs) : une lame
  drop-point à soie pleine, lisible dès 16 px.
- **Profils de lames redessinés** : vraies pointes, ventre et dos tendus, choil d'affûtage, garde
  et manche ergonomique pour les lames fixes, talon droit pour la cuisine.
- Bibliothèque de formes rangée par familles (pièces, lames fixes, cuisine). **Nouveau gabarit**
  propose toutes ces lames comme point de départ, en plus des modèles de base.
- Modèles de départ et données de démonstration : lame à soie pleine, lame de pliant, plaquette
  de pliant galbée ; page de connexion, bannière du README et vidéo de présentation refaites avec
  ces dessins.

### Ajouté
- Modèle de départ et dessin de démonstration **« Félicie »** : une lame dessinée à la main avec
  l'outil (grand choil, talon en bec).

## [0.11.0] — 2026-11-13

Maquette 3D, outils du forgeron, licence libre.

### Ajouté
- **Maquette 3D du couteau monté** (éditeur › Fichier) : rôle et épaisseur par pièce, plaques
  empilées, goupilles générées dans les perçages communs, garde fendue pour la soie, vue 3D
  éclatée ; **3MF** (à plat ou assemblé) ou **STL** pour l'impression 3D ; **DXF par plaque** et
  contrôle du diamètre de fraise pour l'usinage CNC.
- **Vidéo de présentation** (docs/video).

- **Longueur développée** (fibre neutre, coefficient réglable, surlongueur, perte au feu, poids de
  barre) et **débit de forge** d'une pièce.
- **Métier** : coutelier ou forgeron / ferronnier (vocabulaire, étapes, outils affichés).
- **Étapes d'atelier personnalisables** (renommer, ajouter, retirer, réordonner).
- **Temps passé** par commande, comparé au temps prévu et chiffré au taux horaire.

### Modifié
- Base de données : migration 009 (étape d'une commande en texte libre, métier, temps passé).
- Licence : **GNU AGPL v3**, logiciel gratuit (NOTICE.md pour les avertissements).

## [0.10.1] — 2026-11-13

Finitions de l'outil initial.

### Ajouté
- **Changer le mot de passe** (et l'adresse) depuis Réglages › Accès, dans la version installée.
- **Crantage le long d'une courbe** : option « Suivre le contour », chaque entaille
  perpendiculaire au bord.
- **Pliants, lame fermée** : marge minimale jusqu'au bord du manche, ou dépassement, avec la
  partie qui dépasse en rouge.

## [0.10.0] — 2026-11-13

Feuille de route initiale terminée : preuves du sérieux (lot 9) et facturation (lot 10).

### Ajouté
- **Contrôle de découpe** (Dessin et découpe) : une planche de pièces étalons (plaque percée,
  carré, disque) à découper sur sa machine, une fiche de relevé PDF à l'échelle 1:1, et le
  calcul du trait de coupe réel, de l'échelle de la machine et de la compensation à saisir pour
  sortir à 0,1 mm près.
- **Installeurs Linux (AppImage) et macOS (Apple Silicon)**, en plus de Windows, construits et
  testés par l'intégration continue.
- **Publication automatique** : une étiquette de version construit les trois installeurs,
  valide les factures types et publie le tout avec ses empreintes SHA-256.
- **Validation Factur-X indépendante** : chaque version fait vérifier une facture avec TVA, un
  avoir et une facture en franchise par le validateur Mustang (règles EN 16931 et PDF/A-3) ;
  les rapports sont joints à la version.

- **Factures d'acompte** (pourcentage d'une commande, code Factur-X 386) déduites de la facture
  de solde ; **encaissements** multiples, reste dû, facture payée d'elle-même au solde.
- **Envoi par e-mail** des devis, factures et avoirs avec leur PDF, par le compte SMTP de
  l'atelier ; **relances** à trois niveaux (e-mail, courrier, téléphone), liste des factures en
  retard, historique ; textes modifiables.
- **Comptabilité** : chiffre d'affaires facturé et encaissé, TVA due par période et par taux,
  journal des ventes et des encaissements au format du FEC, liste des ventes CSV.
- **Reprise de sauvegarde** : aperçu du fichier avant restauration, sauvegarde d'une version
  précédente mise à niveau puis restaurée, reprise proposée dès l'assistant de bienvenue,
  rappel après 7 jours sans sauvegarde.

### Modifié
- Base de données : migration 008 (encaissements, historique, comptes). Les factures déjà
  marquées payées reçoivent l'encaissement correspondant.
- « Marquer payée » enregistre le reste dû comme un encaissement ; le tableau de bord compte ce
  qui reste réellement à encaisser.
- Factur-X : profil de couleur sRGB (PDF/A-3), adresses électroniques du vendeur et de
  l'acheteur, n° de TVA du vendeur aussi en franchise, date de la facture corrigée sur un avoir.
- Le dossier des données suit l'usage de chaque système : `%LOCALAPPDATA%\KnifeForge Pro`
  (Windows), `~/Library/Application Support/KnifeForge Pro` (macOS),
  `~/.local/share/knifeforge-pro` (Linux).

## [0.9.0] — 2026-11-13

Première préversion installable.

### Ajouté
- **Installeur Windows** sans Docker ni droits administrateur, base SQLite locale, création
  de l'accès au premier lancement, sauvegarde automatique quotidienne, copie de la base avant
  chaque mise à jour.
- **Tableau de bord** d'accueil : commandes par état et par étape, faisabilité matière, gain
  potentiel, facturé et impayés, stock sous le seuil.
- **Outils de coutelier dans l'éditeur** : millimètres ou pouces, feuille de pièces PDF 1:1
  avec croix de pointage, crantage et dentelure, masse et point d'équilibre, pliants (course
  de la lame), 14 profils de lames paramétriques, export STL.
- **Ventes** : clients (avec export et effacement RGPD), devis, factures et avoirs Factur-X
  (EN 16931), numérotation continue, mentions légales françaises.
- **Atelier** : suivi des commandes par étape, journal de stock qui explique chaque mouvement.
- **Précision jusqu'à la machine** : compensation du trait de coupe à l'export, arcs DXF à
  0,01 mm des courbes, nesting à espacement minimum garanti.
- **Éditeur vectoriel** : image de fond calibrée, mesure, magnétisme, guides, congés et
  chanfreins, arc 3 points, symétrie, perçages, texte, redressement de perspective, ligne
  d'émouture, bibliothèque de formes.
- Mode sombre, interface en français et en anglais, menu regroupé, pages larges.
- Intégration continue (SQLite, PostgreSQL et migrations, interface, images Docker,
  installeur) et revue de sécurité.

[Non publié]: https://github.com/philogone/knifeforge-pro/compare/v0.11.0...HEAD
[0.11.0]: https://github.com/philogone/knifeforge-pro/releases/tag/v0.11.0
[0.10.1]: https://github.com/philogone/knifeforge-pro/releases/tag/v0.10.1
[0.10.0]: https://github.com/philogone/knifeforge-pro/releases/tag/v0.10.0
[0.9.0]: https://github.com/philogone/knifeforge-pro/releases/tag/v0.9.0
