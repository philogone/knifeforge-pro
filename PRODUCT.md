# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two primary audiences, weighted equally:

- **The author's own workshop.** The author is a custom knifemaker who uses KnifeForge Pro daily to run the shop: drawing templates, nesting parts on stock, preparing client plans and tracking orders.
- **Independent knifemakers who buy it.** The product is sold as self-hosted source code to artisan knifemakers and bladesmiths. They run it on their own machine or server and manage their own shop with it.

Both audiences do the same job: turn a knife design into a correctly-sized, cut and delivered knife, without running short of material or losing track of an order.

## Product Purpose

KnifeForge Pro is a self-hosted workshop manager for knifemakers. It combines dimensional stock, orders, heat and chemical treatment recipes, costing, and a built-in vector editor. The editor draws parts at 1:1 scale in millimetres, nests them on real stock and exports them for cutting.

Success means:

- A maker can go from a design to a machine-ready file (SVG/DXF) and a dimensioned client plan.
- The maker knows beforehand whether the stock covers the order.
- Every dimension can be trusted to better than 0.1 mm.

## Positioning

Generic inventory tools and generic vector editors each cover half the job. KnifeForge Pro is built around how a knifemaker's material is actually measured and used:

- Bars are tracked in mm, sheets in mm², and discrete items as units.
- Kerf belongs to the saw.
- Nesting places the true part shapes, holes included.
- One recipe format covers both quench and temper schedules and finishing such as damascus etching or bluing.

Precision is the central, testable claim: curves are flattened at ≤ 0.01 mm, nesting spacing is a guaranteed minimum, and numeric entry is exact. Each guarantee is backed by automated tests (`backend/tests/test_precision.py`).

## Operating Context

- **Desk, large screen, mouse and keyboard.** Template drawing, nesting, client plans and order management happen here. The editor is a dense, precision tool used for long sessions.
- **In front of the client.** The maker shows a dimensioned A4/A3 client plan or the knife's details to a customer. Output must look professional and trustworthy on screen and in print.
- **Printing.** Client plans are printed at 100% scale and must stay to scale.
- **Downstream machines.** Exports feed laser, waterjet or CNC cutting, so file correctness outranks on-screen appearance.

Phone and tablet use in the shop is not a confirmed primary context.

## Capabilities and Constraints

- **Stack:** FastAPI + SQLAlchemy (PostgreSQL in production, SQLite in development), Vue 3 + TypeScript + Vite + Pinia, Paper.js for the editor, deployed with Docker Compose.
- **Workshop management:**
  - Dimensional stock: bars, sheets and units.
  - Orders move draft → confirmed → done, with all-or-nothing stock deduction.
  - Treatment recipes, a cross-order cutting optimizer and a saw catalog with kerf.
  - Cost price and suggested sale price.
- **Vector editor, 1:1 in mm:**
  - Drawing: Bézier pen, node editing (drag a segment to bend it), basic shapes and 3-point arc.
  - Corner and shape operations: fillet and chamfer, booleans, offset.
  - Precise input: typed length and angle, live symmetry, hole arrays, text to outlines.
  - Reuse: a parametric shape library and the maker's own templates.
  - Typed layers: cut, hole, engrave, grind, construction and dimension.
  - Photo tracing with calibration or perspective correction, measure tool, full snapping, grid and guides.
- **Outputs:**
  - True-shape nesting on sheets and bars. It is read-only and deducts no stock.
  - SVG with real Béziers, DXF R2010, and dimensioned A4/A3 client plans.
- **Interface languages:** French and English (FR/EN toggle in Settings).
- **Precision contract, non-negotiable:** better than 0.1 mm end to end. The curve-flattening tolerance (0.01 mm) must never be loosened, and nesting spacing must remain a guaranteed minimum, unless the owner explicitly agrees.
- **Explicitly not guaranteed:**
  - Screen rendering: the 1:1 zoom assumes 96 dpi.
  - Printer scaling.
  - Saw and laser kerf compensation, which the maker applies with the Offset tool.
  - Optimality of the nesting heuristic.
- **Terminology:**
  - Tools and objects: gabarit (template), nesting, plan client (client plan), cote (dimension), trait de scie (kerf).
  - Blade and handle parts: émouture (grind line), plaquette (handle scale), garde (guard), soie (tang).

## Brand Commitments

- **Voice: technical and sober.** Precise and factual, with no marketing flourish. Claims are stated as verifiable facts, and precision is the argument.
- Name: KnifeForge Pro.

## Evidence on Hand

- **Product screenshots** in `docs/screenshots/`: editor, nesting on a sheet and on a bar, client plan, template library.
- **Banner:** `docs/banner.svg`.
- **Precision guarantees:** documented in `README.md` and `HANDOVER.md`, and verified by `backend/tests/test_precision.py`.
- **Draft sales listing:** `GUMROAD_LISTING.md`. It predates the Pro features and is not confirmed final copy.
- **No customer testimonials, case studies, press, user counts or benchmarks exist.** Do not invent them.

## Product Principles

1. **The number is the truth.** Dimensions, typed values and exports outrank what the screen shows. The interface must never make a value look more or less precise than it is.
2. **Speak the workshop's language.** Model stock, parts and processes the way a knifemaker measures and names them, not the way generic software does.
3. **Never surprise the stock.** Show shortfalls before commitment, deduct atomically, and keep planning tools (nesting, optimizer) read-only.
4. **Client-ready by default.** Anything a client might see, such as plans and exports, is correct, to scale and presentable without manual cleanup.
5. **Dense where work happens, calm everywhere else.** The editor rewards expertise and long sessions. Management screens stay quick to scan.
