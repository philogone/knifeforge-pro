# Gumroad listing — KnifeForge Manager

## Title

**KnifeForge Manager — Self-Hosted Inventory & Order ERP for Knifemakers (Source Code)**

## Price

**€119** one-time (single-deployment commercial license). Suggested extended license (multiple
end products / resale-adjacent use) at **€279**.

## Short pitch

Stop tracking steel bars, handle blocks, and orders in a spreadsheet. KnifeForge Manager is a
self-hosted inventory and order tool built specifically for custom knifemakers and bladesmiths —
it knows the difference between a bar you cut lengthwise, a sheet you cut in two dimensions, and
a box of rivets you just count. It visualizes exactly where each cut lands on your stock,
optimizes cutting across your whole order backlog to cut fewer bars, checks whether you actually
have enough material before you promise a customer a knife, and keeps a recipe book for both heat
treatment and chemical finishing (damascus etching, bluing, browning, forced patina).

## Full description

Generic inventory software doesn't understand what a knifemaker's stock actually looks like. A
spreadsheet doesn't stop you from promising three damascus folders when you only have one billet
left. KnifeForge Manager is built around the actual shape of the problem:

**What it does:**
- **Dimensional material tracking** — bars/rods tracked in mm, sheet stock (G10, wood, carbon
  fiber) tracked in mm², discrete items (pins, pre-cut blocks) tracked as whole units. Each
  material type is measured the way it's actually used.
- **Visual cutting/yield calculator** — tell it your blank size and how many you need; it shows
  you an actual diagram of the cuts on the bar or sheet, plus how many blanks come off one
  standard stock unit, the waste (saw kerf included), and how many to buy.
- **Cross-order cutting optimizer** — group cutting across your whole draft-order backlog, even
  mixing different knife models that use the same steel, and get an optimized plan (fewer bars,
  less waste) instead of cutting each order separately.
- **Saw/blade catalog** — kerf width belongs to the tool, not the steel. Define your saws once
  with their real cutting width and reuse them across materials.
- **Knife models** — define a knife once (type: fixed, folder, kitchen, table, Japanese...,
  materials required, cut dimensions, estimated build time, sale price, and its full process
  pipeline), then order any quantity of it.
- **Production view** — every draft order compared against current stock in one place, so you can
  see what's buildable right now and where the material crunch is before you promise a delivery
  date.
- **Rich material taxonomy** — metal type (stainless, carbon, titanium, mokume, brass, copper,
  nickel silver), steel grade, wood species/grade, and piece designation (scale pair, guard,
  mitre, rivet...) — free text with real-world suggestions, not a rigid list.
- **Order feasibility & stock deduction** — before confirming an order, see exactly which
  materials are short and by how much. Confirming deducts stock for the whole order atomically —
  no partial deductions, no order that silently oversells your steel. Cancelling a confirmed
  order restocks what it consumed.
- **Treatment recipe book** — one format for both thermal treatment (quench & temper schedules)
  and chemical/finishing treatment (ferric chloride damascus etching to reveal the pattern-weld,
  bluing, traditional browning, forced acid patinas), each as an ordered list of steps with
  temperature, duration, and medium. Chain several onto one knife model in sequence.
- **Bilingual interface** — toggle French/English from Settings, plus a one-click JSON export of
  your whole catalog, recipes, models, and order history whenever you want a backup.
- **Real cost-price and suggested pricing** — every material's landed cost (purchase + shipping)
  updates automatically as a weighted average each time you restock. Every knife model shows its
  full material cost breakdown, labor cost at your hourly rate, and a suggested sale price at your
  target margin (overridable per model) — so pricing a knife is a lookup, not a spreadsheet.
- Ships with a full demo catalog (steel, damascus billets, G10, walnut, pins, fittings, saw
  blades), four demo recipes, two demo knife models, and three demo orders in different states
  (draft, confirmed, cancelled) so you can see the whole pipeline working immediately.

**What you get:**
- Full source code (FastAPI backend, Vue 3 + Tailwind frontend), Docker Compose setup, Alembic
  migrations.
- A bilingual (FR/EN) admin interface, not just bilingual docs.
- HANDOVER.md explaining every non-obvious design decision — why area-yield is an estimate not
  real nesting, why order confirmation is all-or-nothing, why cancelling restocks, and more — so
  you're extending a documented system, not reverse-engineering one.
- A commercial license: one production deployment, modify and rebrand freely, source
  redistribution prohibited.

**What this is NOT:** a barcode/serial-tracked lot system (stock is tracked as aggregate totals
per material, not per physical bar — see HANDOVER.md), an accounting/costing package (material
cost rollup isn't automatic — sale price is entered per knife model), or a customer-facing
storefront (this is your internal shop tool; orders are entered by you).

**Stack:** FastAPI · SQLAlchemy 2 · PostgreSQL 16 · Redis 7 · Vue 3 · Tailwind CSS · Docker
Compose. Requires only Docker to run.

## Tags / categories

`self-hosted`, `saas-boilerplate`, `erp`, `inventory-management`, `knifemaking`, `fastapi`,
`vue`, `docker`, `starter-kit`, `source-code`

## FAQ

**Do I need to know Python/Vue to use this?**
To run it as-is, no — Docker Compose and a `.env` file is enough. To customize material
categories, add new treatment types, or extend the costing model, basic FastAPI/Vue familiarity
helps.

**Does it track exactly which physical bar a blade was cut from?**
No — stock is tracked as an aggregate total per material (e.g. total mm of "1095 steel" on hand),
not per serialized bar. Documented in HANDOVER.md; a shop needing full lot traceability would
need to extend this.

**Can I use it for materials beyond knifemaking (general metalworking, woodworking)?**
The dimensional stock model (length/area/count) and cutting calculator are generic enough to
apply to any bar/sheet/discrete-parts inventory — the demo data and default categories are
knife-flavored, but nothing in the schema is knife-specific.

**Does the cutting optimizer work for sheet materials (G10, wood) too?**
The cross-order optimizer is for bar/rod (`length`) materials only — mixed-size 2D nesting for
sheets is a much harder problem and out of scope. Sheet materials still get the visual yield
calculator for a single blank size.

**Is there support?**
No ongoing support/maintenance obligation is included in the base license (see LICENSE) — this
is a source-code sale, not a subscription.
