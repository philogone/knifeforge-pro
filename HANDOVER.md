# HANDOVER.md — KnifeForge Pro

Internal notes for whoever owns this codebase next. Explains *why* it's built this way.

---

## Why three dimension types instead of one generic "stock quantity"

`Material.dimension_type` is `length`, `area`, or `count` because a maker's raw stock genuinely
comes in three different shapes that consume differently:

- A steel bar is cut along its length — stock and consumption are both in mm, and every cut
  loses a bit of material to the saw kerf.
- A handle sheet (G10, carbon fiber, sometimes wood) is cut in two dimensions — stock and
  consumption are in mm², estimated by area ratio (see below on why this isn't real nesting).
- A pin, a rivet, a pre-cut handle block — you don't "cut" these, you use one, so stock and
  consumption are just whole units.

Collapsing these into one "quantity" field would either lose the cutting math entirely or force
every material through length/width fields that don't mean anything for a bag of rivets. Three
explicit types keep both the yield calculator and the stock deduction math honest for what the
material actually is.

## Why AREA yield is simple grid packing, not real nesting

> **KnifeForge Pro update:** real true-shape nesting now exists as a separate, read-only planner
> (`nesting_service.py`, *Nesting* page). `compute_yield()` below is unchanged and still drives
> order feasibility; the two are deliberately not merged (see the Pro section at the end).

`compute_yield()` for an `area` material tries the blank in both orientations (as given, and
rotated 90°) as a simple row/column grid — `floor(sheet_length / blank_length) *
floor(sheet_width / blank_width)` — and keeps whichever orientation fits more whole pieces. It
does **not** do general 2D bin-packing/nesting: it won't stagger rows, mix orientations within
one sheet, or use irregular leftover offcuts. A maker optimizing complex irregular-shape nesting
from odd sheet remnants needs dedicated nesting software, not a starter kit's grid estimate. The
upside of grid packing over a pure area-ratio estimate (the original approach) is that it's both
a *tighter* number and something concrete to draw — `grid_cols`/`grid_rows` in the yield-calc
response is exactly the layout `SheetGridVisual.vue` renders.

## Why the cutting-bar visual exists, and why it's built from the same numbers as the API

`CuttingBarsVisual.vue` (materials page) and the cutting-optimizer bars are both just SVG rects
sized proportionally to `stockLength`/piece lengths — no separate "layout engine" on the
frontend. The backend is the single source of truth for how many pieces fit and how they're
grouped; the frontend only draws what the API already computed. This matters because a maker
comparing "what I see" against "what gets deducted from stock" needs those two things to be
provably the same calculation, not two independently-drifting implementations of cutting math.

## Why LENGTH yield always includes kerf in the pitch

`pitch = blank_length_mm + material.kerf_mm`, and `pieces_per_stock_unit = floor(standard_length_mm
/ pitch)`. Every cut loses kerf width to the saw, including cuts between consecutive blanks — so
the true "cost" of one blank on the bar is its own length plus one kerf, not just its own length.
This slightly undercounts real yield by one kerf width in edge cases (the very last piece on a
bar doesn't need a *following* cut), but that's a conservative bias — better to estimate slightly
fewer blanks per bar than to run short mid-build. Not correcting for it is a deliberate choice to
keep the formula simple and always err toward "buy slightly more stock."

## Why treatment recipes are one schema for both thermal and chemical processes

The initial brief only mentioned heat treatment, but knifemaking process pipelines routinely
involve chemical/finishing steps too — acid etching to reveal a damascus pattern-weld, bluing,
traditional rust browning, forced acid patinas. All of these are, structurally, the same thing: an
ordered list of steps, each with an optional temperature, a duration, and a "medium" (quench oil,
ferric chloride solution, vinegar, tempering oven air). Rather than building a separate
"ChemicalTreatment" table with near-identical fields, `TreatmentRecipe`/`TreatmentStep` carry a
`treatment_type` enum (`heat_treatment`, `damascus_etch`, `bluing`, `browning`, `acid_patina`,
`other`) and the same step shape covers all of them. A knife model references an **ordered list**
of recipes (`KnifeModelTreatment`, not a single FK) because a real build often chains several —
quench & temper, then an etch, then a patina.

## Why order confirmation is all-or-nothing, and cancellation restocks

`confirm_order()` in `order_service.py` computes total material requirements across every line on
the order, checks every material against current stock, and only deducts if **all** lines are
feasible — never partially. A maker confirming an order is committing real material to a real
build; deducting stock for some lines but not others would leave the inventory in a state that
doesn't correspond to any real decision the maker actually made.

Cancelling a `confirmed` order restocks exactly what it consumed, because the deduction was never
"this material is gone" — it was "this material is reserved/consumed for this specific build."
If the build isn't happening, the material is still on the shelf. `completed` orders do **not**
restock on delete/cancel (in fact `completed` can't be cancelled at all) — by the time an order is
completed, the knife was actually made and the material is genuinely gone.

## Why order lines lock once an order leaves DRAFT

The `PATCH /orders/{id}` endpoint refuses to change `lines` once an order is no longer `draft`
(`update_order` in `routers/orders.py`). Once stock has been deducted against a specific set of
lines, silently editing those lines afterward would desync the deduction from what's actually
recorded as consumed — the stock math has no way to "diff" an edit against a past deduction.
Cancel and recreate the order instead; that goes through the real feasibility/restock path and
keeps the numbers honest.

## Why materials/recipes referenced by a knife model can't be deleted (RESTRICT, not CASCADE)

`KnifeModelMaterial.material_id` and `KnifeModelTreatment.treatment_recipe_id` use
`ondelete="RESTRICT"`, not `CASCADE` or `SET NULL`. Deleting a `Material` or `TreatmentRecipe`
that's still referenced by a knife model would silently break that knife model's cost/process
data. The API returns a 409 in that case (see the `IntegrityError` handlers in the material/
treatment/knife-model routers) — the maker has to update or remove the knife model first, which
is a deliberate speed bump against losing data by accident.

## Why saw/blade kerf is a separate catalog, not just a number on Material

Early on, `kerf_mm` was just a field a maker typed into each material. That's backwards: kerf
width is a property of the *tool doing the cut* (a bandsaw blade, an abrasive chop wheel), not of
the steel itself — the same 1095 bar has a different real kerf depending on which saw cuts it.
`SawBlade` (name, type, diameter, kerf) is a small reusable catalog; picking one on a material
auto-fills `Material.kerf_mm`, which stays the number actually used in the yield/cutting-optimizer
math (`Material.saw_blade_id` is `ondelete="SET NULL"` — deleting a blade never breaks a
material's stock math, it just loses the "which saw" provenance). `kerf_mm` remains independently
editable after auto-fill, since a maker's real-world kerf can drift from a blade's nominal spec
(wear, wobble, technique) — the catalog is a convenience, not a lock.

## Why the cutting optimizer is First-Fit-Decreasing bin packing, scoped to LENGTH materials only

`cutting_service.optimize_cutting()` aggregates blank-length demand for one material across
**every DRAFT and CONFIRMED order** by default (even mixing different knife models with different
blank lengths — a 400mm blade blank and three 150mm ones can share a bar if they fit), sorts
pieces longest-first, and greedily places each into the first bar with room, opening a new bar
only when none fits. This is FFD, a well-known heuristic — typically within ~22% of optimal,
often exact for the small piece counts a one-person shop actually has. It is deliberately not a
guaranteed-optimal solver (that's column generation / integer programming, real complexity for
marginal real-world gain at this scale). AREA materials are excluded entirely: mixed-size 2D
rectangle packing is a substantially harder problem than 1D bar packing and is out of scope here
— the single-blank-size grid estimate in `yield_service.py` is what's offered for sheets.

**Why CONFIRMED orders are included, not just DRAFT**: an early version scoped this to draft
orders only, on the assumption that stock hadn't been committed yet. That's backwards for the
actual question a maker is asking — a *confirmed* order already passed feasibility and had its
stock deducted, which makes it the order most likely to physically go under the saw next, not
less. COMPLETED orders are excluded (already built, nothing left to cut) and so are CANCELLED
ones (not happening); see `_CUTTABLE_STATUSES` in `cutting_service.py`.

**The order picker**: `GET /materials/{id}/cutting-candidates` lists every eligible order for a
material (customer, status, how many pieces and total length they'd contribute), so the frontend
can render a checkbox list — pre-checked by default — before running the optimizer. Passing an
explicit `order_ids` list to `POST /materials/{id}/cutting-optimizer` runs it against exactly that
subset instead of the full default set; passing an empty list deliberately returns zero pieces
rather than silently falling back to "all orders" (`None` means "use the default set", `[]` means
"none, on purpose" — `collect_pieces()` distinguishes the two explicitly). This is the "separate
module to pick which orders I'm about to produce on the stock I'm about to work" workflow — same
endpoint, no separate module needed, since the picker is just a UI over `order_ids`.

Each `check_feasibility()`-style "is this order buildable" question is necessarily per-order, but
the cutting optimizer explicitly crosses order boundaries — it answers "if I cut all these draft
orders' steel needs together, how many bars do I actually need," which is a different, additive
question. It reuses `load_order_with_relations` from `order_service.py` for consistency but lives
in its own module since it doesn't touch stock deduction at all — it's read-only planning output.

## Why the production/backlog view doesn't resolve contention between orders

`production_service.build_overview()` computes each draft order's feasibility independently, as
if it were the only order being confirmed — it does not simulate "if I confirm order A first,
does order B still fit." Two orders can both show `feasible: true` while competing for the same
last bar of steel; confirming one changes whether the other still is. Actually resolving that
requires making a prioritization decision only the maker can make (which customer waits) — the
view surfaces the raw numbers (aggregate demand vs. stock, per-order feasibility) rather than
silently picking a winner.

## Why the taxonomy fields (metal type, steel grade, wood species/grade, piece designation) are
mostly free text, not closed enums

`metal_type` (blade/fitting materials) is a small fixed enum because there are only so many metal
families a knifemaker works in. Everything more specific — `steel_grade` ("1095", "N690Co"),
`wood_species`, `wood_grade`, and `piece_type` (the physical designation: "jeu de plaquettes",
"quillon", "mitre") — is free text with `<datalist>` suggestions (`constants/referenceData.ts`,
seeded from real supplier nomenclature) rather than a closed enum. Steel grade naming isn't
standardized across suppliers, wood species/grading conventions vary by region and vendor, and a
buyer's actual catalog will always include names this list didn't anticipate — free text with
starting suggestions beats a rigid list a buyer immediately has to fight.

## Demo data is seeded through the real service functions, not raw inserts

`seed_service.py` builds its demo materials/recipes/knife models with the ORM as usual, but the
three demo *orders* are pushed through `confirm_order()` / `cancel_order()` from
`order_service.py` — the same functions the API uses. This means every time the app starts with
`SEED_MOCK_DATA_ON_STARTUP=true` and an empty database, the seeding process is itself a live
smoke test of the feasibility-check → deduct → restock pipeline; if that logic ever breaks,
startup seeding breaks loudly instead of silently shipping wrong demo numbers.

## Why the frontend has a hand-rolled i18n composable instead of vue-i18n

`src/i18n/index.ts` is ~30 lines: a `locale` ref, a flat `t(key, vars?)` lookup against
`en.ts`/`fr.ts` dictionaries, persisted to `localStorage`, defaulting from
`navigator.language`. A buyer whose customers are French-speaking (or who just prefers a French
UI) gets a real toggle in Settings without pulling in vue-i18n's ICU message format, lazy-loading,
and pluralization machinery this app doesn't need — every string here is either static or takes
one simple `{n}`-style substitution. If a buyer's use case grows into needing plurals/ICU
formatting, swapping in vue-i18n later is a contained change (the `t()` call sites don't need to
move) since the dictionaries are already keyed and organized by page.

## Why `unit_cost` means "cost per base unit", and why restocking blends a weighted average

`Material.unit_cost` is EUR per mm for a `length` material, EUR per mm² for `area`, EUR per unit
for `count` — the same unit `quantity_in_stock` is already tracked in. That single choice is what
makes the whole costing system fall out for free: a knife's material cost is just consumption
(already computed by `order_service`'s feasibility/deduction math) times `unit_cost`, summed
across its `KnifeModelMaterial` lines — no "cost per bar, divide by bar length" conversion
anywhere (`costing_service.compute_material_cost`). Earlier drafts stored `unit_cost` as "cost of
one whole stock unit" (e.g. one 1000mm bar), which is how a maker naturally thinks about a
purchase invoice, but forced a length-division at every consumption calculation and made
`unit_cost` incompatible with `quantity_in_stock`'s unit for the weighted-average math below.

`POST /materials/{id}/restock` optionally takes `purchase_price` and `shipping_cost` for the
batch being added, and blends them into the existing `unit_cost` with the standard
weighted-average-cost (WAC) inventory method: `new_cost = (old_qty * old_cost + purchase_price +
shipping_cost) / new_qty` (`costing_service.apply_weighted_average_restock`). Restocking without a
price (a correction, found forgotten stock, a personal-project deduction) leaves `unit_cost`
untouched — recomputing an average from a non-purchase quantity change would silently corrupt the
cost history. A purchase price is rejected outright if paired with a non-positive `quantity_delta`
(you can't "buy" a stock decrease).

## How tool wear (sanding belts, grinding discs) folds into material cost without a new entity

The brief asked for grinding-disc and sanding-belt wear to count toward a knife's cost price.
Rather than invent a "wear item" entity, this reuses `Material` (`category=CONSUMABLE`,
`dimension_type=COUNT`) with a *fractional* mental model: `quantity_in_stock` isn't "how many
discs I own", it's "how many whole discs' worth of life remain" (starts at `1.0` for one fresh
disc), and a knife model's `KnifeModelMaterial.quantity` is the fraction of a disc's life that one
build consumes (e.g. `0.01` = 1%). `unit_cost` is simply what one disc costs. The existing
COUNT-material math (`consumption = kmm.quantity`, cost = `consumption * unit_cost`) handles this
with zero special-casing — see the demo `Disque de meulage` material and its use on `Bushcraft
1095 Walnut` in `seed_service.py`. Restocking a fully-worn disc is just `quantity_delta=1.0` with
the price of a replacement, same as buying more steel.

## How the suggested sale price is calculated, and why margin-on-price not markup-on-cost

`compute_full_costing()` extends the material cost breakdown with labor and a suggested price:

```
cost_price = total_material_cost + (base_labor_hours * hourly_rate)
suggested_sale_price = cost_price / (1 - margin_percent / 100)
```

This is **margin-on-price** (a 30% margin means 30% of the *sale* price is profit), not
**markup-on-cost** (30% markup means cost * 1.30). They give different numbers for the same
"30%" and are easy to conflate — margin-on-price was chosen because it's how a maker usually
frames the question ("I want 30% of what I charge to be profit"), and because it composes
correctly: margin_percent is always the fraction of the *final* sale price that's profit,
regardless of what the cost happens to be, whereas markup-on-cost's effective margin shifts as
cost changes. `hourly_rate` and the shop-wide `default_margin_percent` live in the singleton
`ShopSettings` row (`GET`/`PATCH /settings/shop`, lazily created on first access — see
`shop_settings_service.get_shop_settings`); a knife model's own `margin_percent_override` wins
over the shop default when set, so a fussier build (a folder, a damascus piece) can carry a
different margin without changing the default for everything else.

This is a *suggestion*, not an automatic pricing engine: `sale_price` stays a field the maker
sets and edits themselves (still shown as "current sale price" alongside the suggestion, with the
delta between them), because a maker's actual price also reflects market position, a specific
customer relationship, or simply what they've always charged — none of which belongs in a cost
formula.

## KnifeForge Pro — vector designs, nesting and the precision contract

**Design document.** A `Design` stores one JSON document (layers + Bézier paths + dimensions) in
millimetres, y-down, Bézier handles stored *relative* to their anchor so moving a node never
rewrites its handles. Width/height/area/perimeter/part_count are *derived on save* by shapely, so
list views and nesting never trust client-sent numbers. Layer **role** is the contract:
`cut` (nested, exported), `hole` (subtracted from overlapping cut parts), `engrave` (exported,
never nested), `construction` (ignored), `dimension` (plan annotations); hidden layers are
excluded everywhere; compound paths use even-odd.

**Precision contract (non-negotiable requirement: better than 0.1 mm).**
- Curves are flattened with Wang's formula at 0.01 mm tolerance (`DEFAULT_TOLERANCE_MM`). Chords are
  *inscribed*, so flattened areas/perimeters are slightly small (area deficit ≤ perimeter × 0.01 mm).
- Nesting spacing is a **hard minimum**: each part's guard is a buffer enlarged for (a) the chord
  error (+0.01 mm), (b) Shapely's inscribed round joins (1/cos(π/64)) and (c) simplification
  (+0.002 mm), so the real distance is never below the request; it over-delivers by ≤ ~0.05 mm.
  Candidate positions use the same exact gap. Tests assert `distance ≥ spacing − 1e-6` on curved
  parts (`tests/test_precision.py`).
- SVG export keeps true Béziers, 3 decimals (1 µm). DXF carries flattened polylines at 0.01 mm.
- The 4-node Bézier circle/ellipse has a ≤ 0.0273 % radial error — known, tested, documented.
- Editor numeric fields are exact (e.g. 123.4 × 17.6 saves as exactly 123.4 × 17.6, area 2171.84).
- Not promised: screen rendering (1:1 zoom assumes 96 dpi), printer scaling, saw/laser kerf.

**Nesting** is greedy bottom-left with compaction, run for all requested rotations *and* for its
axis-aligned subsets (0/180, 90/270), keeping the best (fewest unplaced, fewest sheets, shortest
used length). Deterministic, fast, not optimal. It is read-only: stock is still deducted by order
confirmation. Order selection convention: `order_ids = null` → all draft/confirmed orders,
`[]` → none. A design belongs to an order line when its `knife_model_id` and `material_id` match.

**Reference image, guides, snapping (editor lot 1).**
- The tracing photo lives in its own `designs.background` column (migration 003), *not* in
  `document`: exports, nesting, metrics, the undo history and the dirty check never see it, and
  list endpoints stay light. PATCH semantics: field omitted = unchanged, `null` = removed. Only
  base64 JPEG / PNG / WebP data URLs are accepted (no SVG, no remote URL), ≤ 12 MB; the editor
  keeps originals ≤ 4000 px untouched and re-encodes larger ones to JPEG. nginx allows 16 MB
  request bodies on `/api/` (its 1 MB default would reject a save with a photo with a 413).
- Calibration (`editor/background.ts`) scales about the first clicked point so the two points
  end up exactly the typed distance apart, optionally straightening A→B with the smallest
  rotation. The clicks are deliberately *not* snapped. What it cannot fix: perspective and lens
  distortion of a photo, and the pixel size (shown as mm/pixel, flagged above 0.1 mm). Tracing a
  photo is therefore an approximation; key dimensions should still be typed in.
- Guides are part of the document (`guides`, omitted when empty) so they are saved and undoable;
  geometry and exports ignore them. Snapping priority: node → intersection → midpoint → centre →
  outline (off by default) → guides → grid, within a radius in screen pixels. A dragged node
  never snaps onto its own path. The drawn grid is the snap grid (thinned 2×/5×/10× when dense).

**Drafting aids (editor lot 2)** — pure geometry in `editor/drafting.ts` and `editor/text.ts`.
- Fillet / chamfer apply only to corner nodes between two *straight* edges (an exact tangent arc
  between curves is a different problem; such corners are reported, never approximated). The arc
  is Bézier pieces of ≤ 90° (radial error ≤ 0.027 % of r) with its ends pinned on the tangent
  points. When both ends of an edge are treated, each may use at most half of it.
- Arc through 3 points uses the same arc construction; aligned points give a straight segment.
- Symmetry (pen): a half outline whose two ends touch the axis (within 9 px) becomes one closed
  contour, ends pinned on the axis; otherwise the mirror is added as a separate path.
- Text → outlines through opentype.js (lazy-loaded chunk) with the bundled Inter (WOFF, latin
  subset incl. French accents) or the user's TTF/OTF/WOFF (WOFF2 unsupported). Size = capital
  height in mm (OS/2 `sCapHeight`); quadratic glyph segments become exact cubics. One compound
  path per text, even-odd: fine for normal fonts, wrong only if a font has overlapping contours.
  Outline fonts suit laser engraving; for a cutter, a single-stroke font is better.
- Open paths are no longer filled on screen: they are lines, and are never cut or nested.
- Node tool: dragging a segment away from its nodes bends it (`dragCurvePoint`): the grabbed
  point follows the pointer exactly, ends fixed, only the two inner handles move (Inkscape's
  weighting). Unlike Inkscape, neighbouring segments are never touched: a smooth end may become
  a corner (the user's choice: bending the edge must not move the spine). The grab time is
  clamped to [0.05, 0.95].

**Photo, library and grind lines (editor lot 3).**
- Perspective correction (`editor/perspective.ts`): the four clicked corners of a known rectangle
  give the homography (Hartley-normalised 8×8 solve); the photo is resampled (bilinear) so the
  rectangle is exactly W × H mm, then stored as WebP (transparent surround; JPEG on white if no
  WebP encoder or > 11.5 MB) and marked calibrated. Output resolution = the sharpest side of the
  rectangle on the photo, capped at 4000 px; the area is the photo clipped to 1.5 × the
  rectangle's longest side (≥ 100 mm) around it. Corner order may go either way round: the
  result is never mirrored, and side 1→2 keeps its direction rounded to a quarter turn. Only the
  rectangle's plane is corrected (parts must lie flat in it; thickness causes parallax) and lens
  distortion is not. The pre-correction photo can be restored until the page is left.
- Shape library (`editor/shapes.ts`): parametric parts on exact Bézier nodes (corners and holes
  use the ≤ 0.027 % arc), inserted on the layer of each part's role in one undo step; "my
  templates" inserts the cut / hole / engrave / grind paths of another design.
- Layer role `grind`: dash-dot on screen and on the client plan (with a legend in the title
  block), never cut, exported (SVG / DXF), nested, nor counted in a part's size.

**Known limits / next steps.** No per-object fill/stroke styling, no groups, no text objects,
COUNT materials are not nestable, nesting does not
use leftover offcuts, and the dimension tool places aligned dimensions only.

## KnifeForge Pro — customers, invoicing and operations

**Invoices are legal documents, so they are frozen, numbered without gaps, and never edited.**
`billing_service.issue()` assigns the next number from `DocumentCounter` (per kind and year:
`D-`, `F-`, `A-YYYY-0001`) in the same transaction that copies the workshop identity and the
customer into `seller_snapshot` / `buyer_snapshot` and recomputes the totals. After that the
document no longer reads settings or the customer record: renaming the workshop or erasing a
customer (GDPR) does not rewrite an invoice already sent. Drafts carry no number, so deleting a
draft never leaves a hole. An issued invoice is corrected only by a credit note (`corrects_id`,
foreign key NO ACTION: it blocks deleting the corrected invoice, yet lets a full restore empty
the table in one statement on PostgreSQL, which RESTRICT would refuse on a self-reference).

**Why Factur-X EN 16931.** France makes e-invoicing mandatory (reception since 1 September
2026, issuing for SMEs and micro-businesses on 1 September 2027) through approved platforms
that accept Factur-X, UBL and CII. Factur-X is the only one of the three a customer can also
simply open: a PDF/A-3 (`facturx_service.render_pdf`, embedded fonts) carrying the CII XML
(`build_cii_xml`), validated against the official XSD by the `factur-x` library before it is
returned. Mentions added by the reform are fields of their own: customer SIREN, delivery
address, nature of the operation (BT-23 framework B1 / S1 / M1), VAT on debits. The
franchise regime emits VAT category E with the art. 293 B CGI exemption reason. KnifeForge Pro
produces the file; transmitting it to an approved platform is the workshop's step.

**Backups are generic over the schema.** `backup_service` walks `Base.metadata.sorted_tables`,
so a new table is backed up without touching the service. A backup carries the Alembic
revision and is refused by a different one (restoring rows into a schema they were not written
for corrupts silently). Restore is one transaction, parents before children, then resets the
PostgreSQL sequences. The nightly `pg_dump` service in docker-compose covers the disaster case.

**Stock ledger.** Every stock change goes through `stock_ledger.record_movement()` (initial stock,
restock or manual correction, order confirmation, cancellation), so the history explains the current
quantity instead of approximating it.

**Security choices.** JWT via PyJWT with `exp` and `sub` required (python-jose is unmaintained
and had algorithm-confusion CVEs); `SECRET_KEY` refused when short or a placeholder; uvicorn
trusts `X-Forwarded-For` from nginx only (port 8000 is bound to localhost) so the login rate
limit sees visitors, not the proxy. nginx sends a strict CSP with no inline or eval script:
the theme bootstrap lives in `public/theme-init.js`, and Vite aliases `paper` to
`paper-core.js`, because paper-full bundles acorn for PaperScript and acorn builds functions
with `new Function` at load time.

## KnifeForge Pro — the desktop build (Windows installer)

**Why a desktop build at all.** Docker stops most workshops at the door, while the competing
tools open in a browser. The same backend therefore also runs as a Windows program:
`backend/desktop/launcher.py`, packed by PyInstaller (`desktop/knifeforge.spec`) and installed by
Inno Setup (`installer/knifeforge.iss`, per user, no administrator rights). CI builds the
installer and smoke-tests the packed program on every change.

**SQLite, not PostgreSQL.** One workshop, one machine, one process: SQLite in the data folder
needs no service. The test suite and every migration already run on SQLite (CI checks the
schema with `alembic check` on both engines). Migration 007 uses batch mode for that reason.

**Configuration without environment variables.** `app/core/desktop.py` keeps in
`%LOCALAPPDATA%\KnifeForge Pro\config.json` what Docker passes in `.env`: the token signing key
(generated on the first launch), the admin account and the backup settings. It sets the
environment before `app.config` is imported, so the rest of the backend is unchanged.

**The account is created in the app.** `POST /api/auth/setup` works once, only in desktop mode,
only while no account exists; the server listens on 127.0.0.1 only. A forgotten password is
reset by removing the two account lines from `config.json` (documented in the README): whoever
can edit the data folder already owns the data.

**The backend serves the interface** (`FRONTEND_DIST`), with the same security headers as
`frontend/nginx.conf`. Login attempts are rate-limited in memory when there is no Redis.

**Updates never lose data.** Before migrating, the launcher copies the database to
`Sauvegardes avant mise à jour\` when its revision differs from the program's. Uninstalling never
touches the data folder. A daily backup (`app/services/auto_backup.py`) writes the restorable
JSON backup to a folder the workshop chooses and prunes only its own old files.

**Packing pitfalls met.** numpy (under shapely) loads parts of `numpy._core` dynamically and the
stock PyInstaller hook misses some: they are listed explicitly. A windowed program has no
console, so a crash at start shows nothing: the launcher logs to `Journaux\` and dumps the
stacks to `demarrage-lent.txt` if starting takes more than 90 s. Build with `KF_CONSOLE=1` for
a diagnostic variant with a console.

## What's deliberately NOT in this kit

- No barcode/serialized stock tracking (e.g. "this exact bar, cut from this exact billet") —
  stock is tracked as an aggregate total per material (total mm, total mm², total count), not
  per physical item. A shop wanting full lot/serial traceability would need to extend this.
- No overhead costing (rent, tool amortization beyond the SawBlade/consumable-wear mechanism,
  electricity) — `compute_full_costing()` accounts for materials and labor only. `sale_price`
  stays a field the maker sets themselves; the suggested price is an input to that decision, not
  an automatic override of it.
- No purchase-order/supplier-invoice tracking beyond the single price+shipping fields on a
  restock — no supplier records, no currency conversion. Sales invoices exist (see above);
  accounting entries do not.
- No customer-facing storefront or public order form — this is an internal shop-management tool,
  not a sales channel. Orders are entered by the maker.
- No multi-user/role system — single admin login, matching the scale of a one-person or
  small-shop operation.
- No 2D nesting for AREA materials with mixed blank sizes, and no cutting optimizer for AREA at
  all (see above) — only LENGTH materials get cross-order bin packing.
- No off-site backup upload — the nightly dump and the on-demand backup stay on the machine;
  copying them elsewhere is the workshop's job.
