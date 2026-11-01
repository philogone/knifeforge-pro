# HANDOVER.md — KnifeForge Manager

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

## What's deliberately NOT in this kit

- No barcode/serialized stock tracking (e.g. "this exact bar, cut from this exact billet") —
  stock is tracked as an aggregate total per material (total mm, total mm², total count), not
  per physical item. A shop wanting full lot/serial traceability would need to extend this.
- No overhead costing (rent, tool amortization beyond the SawBlade/consumable-wear mechanism,
  electricity) — `compute_full_costing()` accounts for materials and labor only. `sale_price`
  stays a field the maker sets themselves; the suggested price is an input to that decision, not
  an automatic override of it.
- No purchase-order/supplier-invoice tracking beyond the single price+shipping fields on a
  restock — no supplier records, no multi-line invoices, no currency conversion.
- No customer-facing storefront or public order form — this is an internal shop-management tool,
  not a sales channel. Orders are entered by the maker.
- No multi-user/role system — single admin login, matching the scale of a one-person or
  small-shop operation.
- No 2D nesting for AREA materials with mixed blank sizes, and no cutting optimizer for AREA at
  all (see above) — only LENGTH materials get cross-order bin packing.
- No scheduled/automatic backups — `Settings > Export data` is a manual, on-demand JSON snapshot
  the maker triggers and stores themselves; there's no cron job or off-site upload built in.
