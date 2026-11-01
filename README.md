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

## Structure

```
knifeforge/
├── frontend/src/
│   ├── pages/admin/           Login, materials, recipes, knife models (+detail), orders, production, settings
│   ├── components/            CuttingBarsVisual.vue, SheetGridVisual.vue
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
│       └── seed_service.py      Demo data (seeded through the real order service)
├── docker-compose.yml
├── .env.example
├── HANDOVER.md
└── README.md
```

## Licence / License

See [`LICENSE`](LICENSE) — commercial license, one end product per purchase, source
redistribution prohibited.
