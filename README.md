# KnifeForge Manager

A self-hosted, dockerized inventory and order management tool built for custom knifemakers and
bladesmiths — dimensional raw material stock (steel bars, sheet handle scales, discrete
hardware), a cutting/yield calculator, order feasibility checks with automatic stock deduction,
and a treatment recipe book covering both thermal processes (quench & temper) and chemical /
finishing processes (damascus pattern-reveal etching, bluing, browning, forced patina).

**Stack:** FastAPI (Python) · Vue 3 + Tailwind CSS · PostgreSQL · Redis · Docker Compose

> This is a starter kit / boilerplate, not a running product — see [`LICENSE`](LICENSE) for what
> that means for you as a buyer, and [`HANDOVER.md`](HANDOVER.md) for the domain model and the
> product decisions behind it.

---

## 🇫🇷 Français

### Démarrage en une commande

```bash
cp .env.example .env
# Éditez .env : SECRET_KEY, POSTGRES_PASSWORD, ADMIN_EMAIL, ADMIN_PASSWORD_HASH (voir plus bas).
docker compose up -d --build
```

L'admin est disponible sur `http://localhost:8080`.

### Générer le hash du mot de passe admin

```bash
docker compose run --rm backend python scripts/hash_password.py "VotreMotDePasseFort"
```

Collez le résultat dans `ADMIN_PASSWORD_HASH` de votre `.env`, puis démarrez (ou redémarrez)
la stack.

> ⚠️ **Piège classique avec Docker Compose** : un hash bcrypt contient des `$` (ex.
> `$2b$12$...`). Docker Compose interprète les `$` d'un fichier `.env` comme des références de
> variable et les supprimerait silencieusement, corrompant le hash. **Doublez chaque `$` en
> `$$`**, par exemple : `ADMIN_PASSWORD_HASH=$$2b$$12$$RRlpfX93...`.

### Le modèle métier

- **Matériaux** (`materials`) : stock dimensionnel. Trois façons de mesurer un stock selon le
  type de matériau : `length` (barres/tiges, stock en mm), `area` (plaques, stock en mm²),
  `count` (pièces discrètes — rivets, blocs de manche pré-taillés — stock en unités).
- **Calculateur de découpe/rendement** : pour un matériau `length` ou `area`, indiquez la taille
  de la pièce à découper (et la largeur pour `area`) et la quantité voulue — l'outil calcule
  combien de pièces sortent d'une barre/plaque standard, la perte (kerf de scie inclus pour les
  barres), et combien de barres/plaques acheter.
- **Modèles de couteaux** (`knife_models`) : associent une liste de matériaux requis (avec leurs
  dimensions de découpe) et une **séquence ordonnée** de recettes de traitement.
- **Recettes de traitement** (`treatment_recipes`) : un seul format couvre le traitement
  thermique (trempe, revenu) ET les traitements chimiques/finition (révélation acide du damas,
  brunissement, ternissement/patine forcée) — chaque recette est une liste d'étapes ordonnées
  avec température, durée et médium (huile de trempe, solution de perchlorure de fer, vinaigre...).
- **Commandes** (`orders`) : `draft` → `confirmed` → `completed`, ou annulée à tout moment avant
  `completed`. Confirmer une commande vérifie la faisabilité (stock suffisant pour **toutes** les
  lignes) et déduit le stock en une seule transaction — tout ou rien, jamais de déduction
  partielle. Annuler une commande `confirmed` **restitue** automatiquement le stock consommé.
- **Catalogue scies/lames** (`saw_blades`) : le trait de scie dépend de l'outil, pas du matériau —
  définissez vos scies/lames une fois (avec leur trait de coupe réel), puis sélectionnez-en une
  sur un matériau pour préremplir son `kerf_mm` (reste modifiable).
- **Optimiseur de découpe multi-commandes** : pour un matériau `length`, regroupe la demande de
  **toutes** les commandes en brouillon (même avec des modèles de couteaux différents) et calcule
  un plan de découpe optimisé (algorithme First-Fit-Decreasing) minimisant le nombre de barres et
  la perte — avec un rendu visuel des barres.
- **Production** : vue d'ensemble comparant chaque commande en brouillon au stock actuel, avec la
  demande matière agrégée sur tout le carnet de commandes.
- **Taxonomie des matériaux** : type de métal (inox, carbone, titane, mokume, laiton, cuivre,
  maillechort), nuance d'acier, essence et qualité de bois, désignation de la pièce (plaquettes,
  quillon, mitre...) — tous en texte libre avec suggestions, adaptables à votre propre catalogue.
- **Interface bilingue FR/EN**, bascule dans Réglages, et export JSON complet de vos données à la
  demande (sauvegarde manuelle).
- **Coût de revient et prix de vente suggéré** : chaque matériau a un coût de revient au mm/mm²/pièce
  (mis à jour automatiquement en coût moyen pondéré à chaque achat, port compris), chaque modèle de
  couteau affiche son coût matière détaillé ligne par ligne, sa main d'œuvre (taux horaire réglable),
  et un prix de vente suggéré selon une marge cible (réglage global, avec possibilité de marge
  spécifique par modèle).

### Tests

```bash
docker compose exec backend pytest
```

---

## 🇬🇧 English

### One-command launch

```bash
cp .env.example .env
# Edit .env: SECRET_KEY, POSTGRES_PASSWORD, ADMIN_EMAIL, ADMIN_PASSWORD_HASH (see below).
docker compose up -d --build
```

The admin panel is available at `http://localhost:8080`.

### Generating the admin password hash

```bash
docker compose run --rm backend python scripts/hash_password.py "YourStrongPassword"
```

Paste the result into `ADMIN_PASSWORD_HASH` in your `.env`, then start (or restart) the stack.

> ⚠️ **Classic Docker Compose gotcha**: a bcrypt hash contains `$` characters (e.g.
> `$2b$12$...`). Docker Compose treats `$` in a `.env` file as a variable reference and will
> silently strip it, corrupting the hash. **Double every `$` into `$$`**, e.g.
> `ADMIN_PASSWORD_HASH=$$2b$$12$$RRlpfX93...`.

### The domain model

- **Materials** (`materials`): dimensional stock. Three ways to measure stock depending on the
  material's shape: `length` (bars/rods, stock in mm), `area` (sheets, stock in mm²), `count`
  (discrete units — rivets, pre-cut handle blocks — stock in whole units).
- **Cutting/yield calculator**: for a `length` or `area` material, give the blank size you need
  to cut (plus width for `area`) and the quantity needed — the tool computes how many blanks
  come out of one standard bar/sheet, the waste (saw kerf included for bars), and how many
  bars/sheets to buy.
- **Knife models** (`knife_models`): tie together a list of required materials (with their cut
  dimensions) and an **ordered sequence** of treatment recipes.
- **Treatment recipes** (`treatment_recipes`): one format covers both thermal treatment (quench,
  temper) AND chemical/finishing treatment (damascus acid-etch pattern reveal, bluing, browning,
  forced patina) — each recipe is an ordered list of steps with temperature, duration, and medium
  (quench oil, ferric chloride solution, vinegar, etc.).
- **Orders** (`orders`): `draft` → `confirmed` → `completed`, or cancelled any time before
  `completed`. Confirming an order checks feasibility (enough stock for **every** line) and
  deducts stock in one transaction — all or nothing, never a partial deduction. Cancelling a
  `confirmed` order automatically **restocks** what it had consumed.
- **Saw/blade catalog** (`saw_blades`): kerf width belongs to the tool, not the material — define
  your saws/blades once (with their real cutting width), then pick one on a material to pre-fill
  its `kerf_mm` (still independently editable).
- **Cross-order cutting optimizer**: for a `length` material, aggregates demand across **every**
  draft order (even across different knife models) and computes an optimized cutting plan
  (First-Fit-Decreasing bin packing) minimizing bars used and waste — rendered as a visual
  diagram.
- **Production**: an overview comparing every draft order against current stock, plus aggregate
  material demand across the whole backlog.
- **Material taxonomy**: metal type (stainless, carbon, titanium, mokume, brass, copper, nickel
  silver), steel grade, wood species/grade, piece designation (scale pair, guard, mitre...) — all
  free text with suggestions, so it adapts to your own catalog rather than fighting a fixed list.
- **Bilingual FR/EN UI**, toggled from Settings, plus an on-demand full JSON export of your data
  (manual backup).
- **Landed cost and suggested sale price**: every material carries a cost per mm/mm²/unit,
  automatically updated as a weighted average whenever you log a purchase (price + shipping).
  Each knife model shows its full material cost breakdown, labor cost (configurable hourly rate),
  and a suggested sale price at a target margin (shop-wide default, overridable per model).

### Tests

```bash
docker compose exec backend pytest
```

---

## ✒️ KnifeForge Pro — éditeur vectoriel / vector editor

**🇫🇷** Cette version ajoute un éditeur vectoriel intégré (type Inkscape, basé sur Paper.js) :

- **Gabarits à l'échelle 1:1 en mm** (lames, plaquettes, gardes, mitres…), rattachés à un modèle de couteau et à une matière. Menu *Gabarits*.
- Éditeur : plume Bézier, édition de nœuds, rectangle/ellipse/ligne/polygone, booléens (union, différence, intersection, exclusion), combiner/séparer, décalage (agrandir/réduire), alignement/répartition, miroir/rotation, calques typés (découpe, perçage, gravure, construction, cotation), cotes, import SVG, annuler/rétablir, grille jusqu'à 0,1 mm, saisie numérique exacte.
- **Nesting réel sur stock** (menu *Nesting*) : vraies formes avec perçages, rotations, espacement et marge ; nombre de plaques/barres, taux d'utilisation, comparaison au stock ; lecture seule (ne décompte pas le stock).
- **Exports** : SVG (courbes de Bézier vraies, 1 unité = 1 mm), DXF (R2010, polylignes, calques CUT/ENGRAVE/SHEET), plaques de nesting en SVG/DXF, **plans clients cotés** (A4/A3, échelle normalisée, cartouche).

**Précision (exigence de conception : meilleur que 0,1 mm).**

| Élément | Garantie |
|---|---|
| Coordonnées stockées | 0,0001 mm |
| SVG exporté | 0,001 mm, courbes de Bézier non aplaties |
| Aires, périmètres, DXF, nesting | courbes aplaties à ≤ 0,01 mm |
| Espacement du nesting | **minimum garanti** (jamais en dessous de la valeur demandée ; excédent ≤ ~0,05 mm) |
| Marge de bord | respectée au micron sur les polygones aplatis (≤ 0,01 mm d'écart sur courbes) |
| Cercle/ellipse dessinés | approximation Bézier à 4 nœuds : écart radial ≤ 0,027 % du rayon (0,03 mm pour R = 100 mm) |

Limites à connaître : un écran n'est pas un instrument de mesure (le zoom « 1:1 » suppose 96 dpi) — fiez-vous aux cotes et aux champs numériques ; imprimez les plans à **100 % (sans « ajuster à la page »)** pour qu'ils soient à l'échelle ; un SVG importé sans unité est lu à 96 dpi (vérifiez avec une cote) ; le DXF contient des polylignes (pas d'arcs) ; le trait de scie / l'offset laser ne sont pas compensés automatiquement (utilisez l'outil *Décalage*) ; le nesting est une heuristique rapide et déterministe, pas un optimum mathématique.

**🇬🇧** This edition adds an integrated vector editor (Inkscape-style, built on Paper.js): real-scale mm patterns linked to knife models and materials, a full node/Bézier/boolean/offset toolset, true-shape nesting on stock, SVG/DXF export and dimensioned client plans. Precision target is better than 0.1 mm: coordinates are stored to 0.0001 mm, SVG keeps true Béziers (0.001 mm), areas/DXF/nesting use curves flattened to ≤ 0.01 mm, and nesting spacing is a hard minimum. Caveats: the screen is not a measuring tool (print plans at 100 %), imported unit-less SVG is read at 96 dpi, DXF carries polylines, saw kerf is not auto-compensated, and nesting is a fast deterministic heuristic.

### Tests (Pro)

```bash
docker compose exec backend pytest          # 76 tests: geometry, nesting, exports, API, metrology
cd frontend && npm test                     # 36 editor-engine tests (vitest)
```

Local dev without Docker: `cd frontend && npm run dev` proxies `/api` to `http://localhost:8000`
(override with `VITE_PROXY_TARGET`).

## Structure

```
knifeforge/
├── frontend/src/
│   ├── pages/admin/           Login, materials, recipes, knife models (+detail), orders, production, settings
│   ├── components/            CuttingBarsVisual.vue, SheetGridVisual.vue, NestingSheetVisual.vue
│   ├── editor/                Paper.js engine, tools, history, grid/rulers (+ vitest tests)
│   ├── pages/admin/           … + DesignsPage, DesignEditorPage, NestingPage
│   ├── i18n/                  Minimal FR/EN dictionaries + t() composable
│   └── stores/app.store.ts    Pinia store — all API calls
├── backend/app/
│   ├── models/                 material, saw_blade, treatment, knife_model, order
│   ├── routers/                 auth, materials, saw_blades, treatments, knife_models, orders, production, settings
│   └── services/
│       ├── yield_service.py     Cutting/yield math (single blank size, one material)
│       ├── cutting_service.py   Cross-order cutting optimizer (FFD bin packing, LENGTH only)
│       ├── order_service.py     Feasibility check + stock deduction/restock
│       ├── production_service.py Backlog vs stock overview
│       ├── geometry_service.py  Bézier flattening, parts/holes, metrics, offset (shapely)
│       ├── nesting_service.py   True-shape 2D nesting (greedy bottom-left, guaranteed spacing)
│       ├── export_service.py    SVG / DXF (ezdxf) / dimensioned client plans
│       └── seed_service.py      Demo data (seeded through the real order service)
├── docker-compose.yml
├── .env.example
├── HANDOVER.md
└── README.md
```

## Licence / License

See [`LICENSE`](LICENSE) — commercial license, one end product per purchase, source
redistribution prohibited.
