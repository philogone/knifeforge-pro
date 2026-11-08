# Fiche de vente Gumroad — KnifeForge Pro

Décisions commerciales de référence : [`docs/decisions-commerciales.md`](docs/decisions-commerciales.md).

## Titre

**KnifeForge Pro — le logiciel d'atelier des couteliers : stock, commandes, factures, et un éditeur qui dessine vos pièces au centième**

## Prix

**99 €** — licence pour un atelier, code source auto-hébergé, **1 an de mises à jour inclus**.
Mises à jour ensuite : **30 € par an**, facultatif (la version installée reste utilisable sans limite de durée).

## Accroche

Le carnet du coutelier, en logiciel. KnifeForge Pro tient votre stock d'acier, de damas, de G10
et de bois au millimètre, vérifie que vous avez la matière avant de promettre un couteau, suit
chaque commande de la forge à la livraison, et édite des devis et des factures électroniques
**Factur-X** conformes à la réforme française. Son éditeur vectoriel dessine vos lames, gardes et
plaquettes à la cote, les place sur vos plaques et vos barres, et les exporte en DXF pour le
laser, le jet d'eau ou la CNC.

## Description

Un tableur ne vous empêche pas de promettre trois pliants en damas quand il ne reste qu'une
billette. Un logiciel de gestion générique ne sait pas ce qu'est une barre que l'on débite en
longueur, une plaque que l'on découpe en deux dimensions, ou une boîte de rivets que l'on compte.
KnifeForge Pro est construit autour du travail réel d'un atelier de coutellerie.

**L'éditeur et la découpe**
- Éditeur vectoriel intégré à l'échelle 1:1 en millimètres : plume Bézier, congés et chanfreins
  au rayon saisi, symétrie en direct, réseaux de perçages, texte en contours, booléens.
- Décalque d'une photo calibrée, ou redressée en perspective sur une feuille A4.
- **Nesting réel** des formes (perçages compris) sur vos plaques et barres, espacement garanti.
- Exports **SVG** (vraies courbes) et **DXF** en polylignes ou en arcs, avec **compensation du
  trait de coupe** : la pièce sort à la cote.
- **Plans clients cotés** A4 / A3 au nom de l'atelier, avec barre de contrôle de 100 mm.
- **Précision meilleure que 0,1 mm** de l'écran à la machine, vérifiée par des tests.

**L'atelier**
- Stock dimensionnel : barres (mm), plaques (mm²), pièces (unités), historique de chaque mouvement.
- Commandes avec déstockage tout-ou-rien, suivi d'étape (forge, trempe, émouture, manche,
  finition) et date promise.
- Recettes de traitement thermique et chimique (trempe, revenu, attaque du damas, bleuissage,
  patine), modèles de couteaux, coût de revient et prix de vente suggéré.

**Clients et facturation**
- Fichier clients avec export et effacement (RGPD).
- Devis → facture → avoir, numérotation continue, documents figés à l'émission.
- **Factur-X EN 16931** (PDF/A-3 avec XML structuré) : prêt pour l'obligation d'émission de
  factures électroniques des TPE et PME au 1er septembre 2027, mentions obligatoires comprises
  (SIREN du client, nature de l'opération, adresse de livraison, TVA sur les débits).
- Franchise en base de TVA (art. 293 B du CGI) ou régime réel, au choix.

**L'exploitation**
- Installation en une commande avec Docker, assistant de premier lancement.
- Sauvegarde automatique chaque nuit, sauvegarde et restauration complètes depuis l'interface.
- Interface en français et en anglais, mode sombre pour les longues soirées au bureau.

**Ce que vous recevez**
- Le code source complet (FastAPI, Vue 3, PostgreSQL), Docker Compose, migrations de base.
- Le guide d'installation (README) et le dossier de conception (HANDOVER.md).
- Les mises à jour pendant un an.

**Ce que ce n'est pas**
- Un service en ligne : vous l'installez sur votre ordinateur, votre serveur ou un VPS.
- Une plateforme agréée de facturation électronique : vous déposez vos factures Factur-X sur la
  plateforme de votre choix.
- Un logiciel de comptabilité ou une boutique en ligne.

**Technique :** FastAPI · SQLAlchemy 2 · PostgreSQL 16 · Vue 3 · TypeScript · Paper.js ·
Tailwind CSS · Docker Compose. Il suffit de Docker pour le faire tourner.

## Étiquettes

`coutellerie`, `knifemaking`, `atelier`, `auto-hébergé`, `self-hosted`, `facture électronique`,
`factur-x`, `dxf`, `nesting`, `gestion de stock`

## Questions fréquentes

**Faut-il savoir programmer ?**
Non pour l'utiliser : Docker et un fichier `.env` à remplir suffisent (le README détaille chaque
étape). Oui pour le modifier, avec des bases en Python et Vue.

**Mes données partent-elles quelque part ?**
Non. Tout reste sur la machine où vous l'installez, sauvegardes comprises.

**Est-ce conforme à la facturation électronique obligatoire ?**
Les factures sont produites au format Factur-X EN 16931, l'un des formats acceptés par la
réforme, avec les nouvelles mentions obligatoires. La transmission passe par une plateforme
agréée que vous choisissez ; KnifeForge Pro n'en est pas une. Vérifiez avec votre comptable les
règles propres à votre situation.

**Que se passe-t-il après un an ?**
Votre version continue de fonctionner sans limite. Le renouvellement à 30 € par an donne accès
aux nouvelles versions.

**Y a-t-il du support ?**
Le support est communautaire (questions et réponses entre utilisateurs). Aucun support
individuel n'est inclus.

**Puis-je l'installer dans plusieurs ateliers ?**
Une licence couvre un atelier. Pour plusieurs, contactez l'auteur.
