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

### Pour qui

Les **couteliers** d'abord : c'est le message de vente (« le seul outil fait pour les
couteliers ») et l'ordre des priorités. Les **forgerons et ferronniers** ont des besoins voisins
(stock de barres, débit, gabarits 1:1, découpe, devis et factures) : ils sont servis par le même
programme grâce à un profil métier (lot 12), sans diluer le message ni ajouter d'outils
coutelier chez eux, ou l'inverse. Décidé le 13 novembre 2026.

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

## Lot 10 — À niveau des outils de facturation (fait le 13 novembre 2026, sauf la plateforme agréée)

- **Relances** des factures impayées (échéance, modèle de message, historique).
- **Export pour le comptable** : journal des ventes CSV et récapitulatif de TVA par période.
- **Envoi par e-mail** du devis ou de la facture depuis l'application (serveur SMTP de l'atelier).
- **Paiement** : acomptes et paiements partiels sur une facture.
- **Plateforme agréée** : connexion à une ou deux plateformes (dépôt automatique du Factur-X),
  avant l'obligation d'émission du 1er septembre 2027.
- **Sauvegarde et reprise des données** (demandé le 13 novembre 2026). Existe déjà : la
  sauvegarde complète téléchargeable et sa restauration dans les Réglages, l'export JSON lisible,
  la sauvegarde quotidienne automatique. À faire dans ce lot :
  - **reprendre une sauvegarde au premier lancement** : sur l'écran de création de l'accès et
    dans l'assistant de bienvenue, « J'ai déjà KnifeForge : reprendre ma sauvegarde » (nouvel
    ordinateur, réinstallation, passage de Docker à l'installeur ou l'inverse) ;
  - **restaurer une sauvegarde d'une version antérieure** : aujourd'hui refusée si la base n'est
    pas à la même version. Ce lot ajoute une migration de base (008) : sans cela, une sauvegarde
    faite en 0.9 ne se restaurerait plus en 0.10. La sauvegarde est chargée dans une base
    temporaire à sa version, mise à niveau, puis restaurée ; jamais l'inverse (une sauvegarde
    plus récente que le programme est refusée avec un message clair) ;
  - **sauvegarde manuelle à la demande** mise en avant (bouton visible, nom de fichier daté,
    rappel si aucune sauvegarde depuis 7 jours), et vérification du fichier avant restauration
    (aperçu : date, version, nombre de clients, commandes, factures).
- Plus tard, à part : **import depuis un autre outil** (clients, matières, modèles en CSV ou
  tableur), pour un atelier qui arrive avec ses données.

## Lot 11 — Maquette 3D du couteau monté (fait le 13 novembre 2026, sauf le STEP)

Juger la prise, l'équilibre et l'encombrement avant de toucher à l'acier, montrer le projet au
client. Les uns impriment en 3D, les autres usinent à la CNC : un seul assemblage, deux sorties.

- **Assemblage** : chaque pièce a un rôle (lame, plaquettes gauche / droite, garde, mitre,
  entretoise, rivets) et une épaisseur (celle de sa matière par défaut) ; empilement automatique
  aligné sur les perçages communs ; rivets et goupilles générés depuis les perçages. Vue 3D dans
  l'éditeur pour vérifier avant d'exporter.
- **Impression 3D** : 3MF (une pièce par objet, multi-couleurs) ou zip de STL, en mm, maillage à
  0,01 mm ; jeu des rivets réglable (0,2 mm par défaut) ; pièces posées à plat, sans supports.
- **Usinage CNC** (fraiseuse 3 axes, bois, résine, mousse) : un DXF par plaque avec son
  épaisseur, perçages en points de perçage, zéro Z en surface ; contrôle du diamètre de fraise
  (angles intérieurs trop serrés, trous plus petits que l'outil) ; solide exact STEP pour la FAO
  — choisir entre un moteur de CAO (fiable, ~100 Mo de plus) et une écriture maison (légère,
  plus de travail), après mesure.
- Limites écrites dès le départ : pièces à bords droits (ni émouture ni galbe au départ ;
  biseau simplifié jusqu'à la ligne d'émouture en deuxième temps) ; les attaches d'usinage se
  posent dans la FAO.

Terminé quand : volumes fermés et exacts, empilement juste au centième, rivets en face des trous,
un fichier de chaque sorte ouvert sans erreur dans un trancheur et une FAO courants.

## Lot 12 — Un cœur neutre, deux métiers : coutelier et forgeron (en grande partie fait le 13 novembre 2026)

**0. Avant le code** : interroger deux ou trois forgerons / ferronniers et regarder ce qu'ils
utilisent aujourd'hui (tableur, logiciel de devis du bâtiment), pour confirmer les besoins
ci-dessous plutôt que les supposer.

**1. Longueur développée** (demandée explicitement ; indépendante du reste, peut être avancée
dès qu'un lot laisse de la place) : on dessine une volute, un enroulement, un crochet ou un
anneau, KnifeForge donne la longueur de barre à débiter.
- Mesurée sur la **fibre neutre** : le tracé est la ligne médiane, ou un bord avec la section
  et le côté indiqués (décalage de la demi-épaisseur, ou du coefficient de fibre neutre réglable
  pour les cintrages serrés à froid).
- Section de la barre (rond, carré, plat sur chant ou à plat) prise dans le stock ; **surlongueurs**
  saisies (prise en pince, perte au feu, chutes de mise à longueur) ; résultat en mm, en pouces,
  et en **poids** de barre.
- Report direct dans la commande ou la liste de débit (optimiseur de barres existant).
- Utile aussi au coutelier : garde ou bélière cintrée, fil d'enroulement, et en variante
  « **débit de forge** » : la longueur de barre d'une section donnée qui contient le volume de la
  lame dessinée (conservation du volume, perte au feu en %).
- Juste : comparée à des longueurs calculées indépendamment (cercle, spirale d'Archimède,
  clothoïde) à mieux que 0,1 mm ; limites écrites (le refoulement et l'étirage à la forge
  ne se calculent pas, ils se saisissent en surlongueur).

**2. Cœur neutre** (profite aussi aux couteliers) :
- **Étapes d'atelier personnalisables** : nom, ordre, ajout, retrait (aujourd'hui écrites en dur
  pour le couteau). Un coutelier qui forge son damas ou coud ses étuis les veut aussi.
- **« Modèle »** au lieu de « Modèle de couteau » ; catégories de matières génériques (acier,
  profilés, bois, cuir…) avec celles du couteau comme exemples.
- **Stock au poids** et **profilés normalisés** (rond, carré, plat, tube, cornière, fer en T) :
  poids calculé par section × longueur × densité, achat et coût au kilo.

**3. Profil métier** au premier lancement, modifiable dans les Réglages : *Coutelier* ou
*Forgeron / ferronnier*. Il règle le vocabulaire, les étapes par défaut, les catégories de
matières, les formes de la bibliothèque (profils de lames d'un côté ; volutes, rinceaux,
pointes de lance, feuilles, colliers de l'autre) et les outils affichés (crantage, pliants,
équilibre chez le coutelier ; longueur développée en avant chez le forgeron). Un seul programme,
une seule base, rien de perdu en changeant de profil.

**4. Temps passé** par commande (pointage simple, comparé au devis) : en ferronnerie la
main-d'œuvre pèse plus que la matière ; le coutelier y gagne aussi un prix de revient réel.

Terminé quand : un forgeron fait un devis de rampe ou de chenets de bout en bout sans voir un
mot de coutellerie ; un coutelier ne voit aucun changement qu'il n'a pas choisi ; longueur
développée et poids vérifiés par des tests de précision ; guide complété.

Laissé de côté (décidé le 13 novembre 2026) : le **volet bâtiment** des ferronniers poseurs
(mention de l'assurance décennale sur devis et factures, situations de travaux, retenue de
garantie, TVA réduite en rénovation). À ne reprendre que comme un lot complet, si ces clients
sont visés un jour.

## Plus tard

- Vue téléphone de l'atelier (commandes du jour, étape, stock) en lecture.
- Nesting sur les chutes existantes.
- Matériaux comptés à l'unité dans le nesting.
- Cotation angulaire et radiale.
- Licence multi-ateliers.

## Ordre de marche

1. ~~Lot 6~~ → 2. ~~Lot 7~~ → 3. ~~Lot 8~~ et ~~lot 9~~ → 4. ~~Lot 10~~ → 5. ~~Lot 11~~ → 6. Lot 12
(la longueur développée peut être avancée seule : elle ne dépend d'aucun autre lot).

À chaque lot : tests verts (`pytest`, `npm test`, `vue-tsc`, build), captures vérifiées,
documentation à jour, puis fusion.
