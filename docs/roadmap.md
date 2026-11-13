# Feuille de route — KnifeForge Pro

Arrêtée le 10 novembre 2026, après la comparaison avec le marché. Le détail du chantier en cours
est dans [`a-faire.md`](a-faire.md) ; les décisions commerciales dans
[`decisions-commerciales.md`](decisions-commerciales.md).

## Le cap

> **De l'esquisse à la facture, au centième, chez vous.**

Aucun concurrent ne relie le dessin, la matière, la commande et la facture. C'est la promesse à
tenir. Les outils gratuits ou bon marché (Plungeline, Knifeprint, Deepnest, Inkscape, Abby,
Dolibarr) resteront des concurrents, c'est le marché. Ils ne doivent pas être **inquiétants** :
sur ce qu'ils font bien, KnifeForge fait au moins aussi bien, et sur le reste, il fait ce qu'ils
ne font pas.

### Règle « pas de gadget »

Une fonction n'entre dans une version que si elle est :
1. **finie** : pas de demi-outil, pas de bouton qui mène à « bientôt » ;
2. **juste** : testée contre des valeurs calculées indépendamment, précision < 0,1 mm tenue ;
3. **expliquée** : documentée dans le guide, avec ses limites écrites ;
4. **réversible** : annulable, sauvegardée, restaurable.

Mieux vaut moins de fonctions irréprochables qu'un catalogue fragile : c'est ce qui fait dire
« il y a du sérieux ».

## Lot 6 — Finir l'interface (fait, 10 novembre 2026)

- Mise en page large : Réglages sur 3 colonnes, fiches sur 2 colonnes, listes en cartes.
- Menu regroupé : Atelier · Dessin et découpe · Ventes, avec sous-menus expliqués.
- **Tableau de bord d'accueil** : date, commandes par état et par étape d'atelier, faisabilité
  matière, gain potentiel, facturé et impayés, stock sous le seuil, jauges et graphiques sobres.
- Mention « aucune donnée chez l'éditeur » dans les décisions, la licence et la fiche de vente.

Terminé quand : captures validées à 1440 / 1900 px et téléphone, clair et sombre ; tests verts.

## Lot 7 — Installer sans Docker (fait le 10 novembre 2026, reste le test par un non-développeur)

Le frein n° 1 : un artisan ne passera pas par Docker, alors que les concurrents s'ouvrent dans un
navigateur.
- **Installeur Windows** en un clic : serveur et interface empaquetés, base SQLite (la suite de
  tests tourne déjà sur SQLite), icône sur le bureau, ouverture dans le navigateur.
- Sauvegarde automatique quotidienne dans un dossier choisi (clé USB, disque, dossier
  synchronisé), restauration en un clic.
- Mise à jour par téléchargement d'une nouvelle version, migrations appliquées seules, sauvegarde
  faite juste avant.
- Docker reste proposé pour un serveur ou un NAS.
- Toujours aucune donnée envoyée à l'éditeur, aucune télémétrie.

Terminé quand : installation testée sur un Windows neuf par une personne qui n'est pas
développeur, en moins de 10 minutes.

## Lot 8 — À niveau des outils de dessin gratuits (fait le 12 novembre 2026)

Ce que les outils dédiés proposent et qu'un coutelier s'attend à trouver :
- **Pouces** en plus des millimètres (saisie, règles, cotes, exports), conversion exacte.
- **Pliants** : pivot, rotation de la lame ouverte / fermée, contrôle du jeu avec le ressort et
  la butée, visualisation de la course.
- **Point d'équilibre** du couteau (lame + manche, densités des matières du stock).
- **Générateurs** : crantage (jimping), dentelure, au pas et à la profondeur saisis.
- **Feuille de pièces PDF** à l'échelle, avec marques de pointage des perçages.
- **Catalogue de profils** : une vingtaine de formes classiques paramétriques (drop-point, clip,
  tanto, wharncliffe, santoku, gyuto, nakiri, bowie, skinner…), à la cote.
- Export **STL** d'un gabarit extrudé (impression 3D de gabarits de traçage).

Terminé quand : chaque point a ses tests de précision et sa page de guide.

## Lot 9 — Les preuves du sérieux (fait le 13 novembre 2026, sauf la découpe réelle et la vidéo)

- **Planche de contrôle** : un DXF et un plan PDF de pièces étalons (carré, cercle, arc, perçages)
  à découper et mesurer au pied à coulisse, avec la fiche de relevé. Publier les mesures d'une
  vraie découpe (laser et jet d'eau).
- **Guide utilisateur** en français : premier lancement, dessiner une lame, nester, commander,
  facturer, sauvegarder. Avec captures.
- **Démo en ligne** en lecture seule, données fictives uniquement, réinitialisée chaque nuit.
- **Versions numérotées** et **journal des modifications** daté ; badges de CI dans le README.
- **Validation Factur-X indépendante** (validateur FNFE-MPE ou Mustang) jointe à chaque version.
- Vidéo courte : de l'esquisse à la facture en 3 minutes.

## Lot 10 — À niveau des outils de facturation (priorité 3)

- **Relances** des factures impayées (échéance, modèle de message, historique).
- **Export pour le comptable** : journal des ventes CSV et récapitulatif de TVA par période.
- **Envoi par e-mail** du devis ou de la facture depuis l'application (serveur SMTP de l'atelier).
- **Paiement** : acomptes et paiements partiels sur une facture.
- **Plateforme agréée** : connexion à une ou deux plateformes (dépôt automatique du Factur-X),
  avant l'obligation d'émission du 1er septembre 2027.

## Plus tard

- Vue téléphone de l'atelier (commandes du jour, étape, stock) en lecture.
- Nesting sur les chutes existantes.
- Matériaux comptés à l'unité dans le nesting.
- Cotation angulaire et radiale.
- Licence multi-ateliers.

## Ordre de marche

1. ~~Lot 6~~ → 2. ~~Lot 7~~ → 3. ~~Lot 8~~ et ~~lot 9~~ → 4. Lot 10.

À chaque lot : tests verts (`pytest`, `npm test`, `vue-tsc`, build), captures vérifiées,
documentation à jour, puis fusion.
