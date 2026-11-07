---
name: KnifeForge Pro
description: Workshop manager and 1:1 vector editor for knifemakers, precise to the tenth of a millimetre.
colors:
  action-indigo: "#4f46e5"
  action-indigo-deep: "#4338ca"
  action-indigo-mist: "#eef2ff"
  ink: "#0f172a"
  graphite: "#1e293b"
  slate-text: "#334155"
  slate-muted: "#64748b"
  slate-faint: "#94a3b8"
  rule-line: "#cbd5e1"
  hairline: "#e2e8f0"
  paper: "#ffffff"
  bench: "#f8fafc"
  tag-wash: "#f1f5f9"
  quench-red: "#dc2626"
  quench-red-wash: "#fef2f2"
  temper-green: "#16a34a"
  caution-amber: "#d97706"
  caution-amber-wash: "#fffbeb"
  engrave-blue: "#2563eb"
  grind-teal: "#0f766e"
  snap-amber: "#f59e0b"
typography:
  headline:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.33
  title:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.43
  label:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.33
  numeric:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.33
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.action-indigo}"
    textColor: "{colors.paper}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.action-indigo-deep}"
  button-secondary:
    backgroundColor: "{colors.graphite}"
    textColor: "{colors.paper}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  button-outline:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.slate-text}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
  input-field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  input-compact:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
  card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.lg}"
    padding: "16px"
  tag-demo:
    backgroundColor: "{colors.tag-wash}"
    textColor: "{colors.slate-faint}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "2px 6px"
  dialog:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.lg}"
    padding: "16px"
---

# Design System: KnifeForge Pro

## Overview

**Creative North Star: "Le carnet du coutelier"**

KnifeForge Pro should feel like a knifemaker's workshop notebook: a technical record kept by a craftsman. On the left page, measured drawings, dimensions and stock counts that must be exact. In the margins, the maker's notes. The notebook is technical first: numbers, drawings and dimensions are always legible, aligned and unambiguous. The artisan warmth lives at the edges: in the voice of notes and hints, in how materials (steel, wood, G10) are named and recognised, in a sense of care. It never gets in the way of a dimension.

The current implementation is the notebook's sober base. It is a neutral cool-slate interface on stock Tailwind values, with white cards on a near-white bench and a single indigo action accent. It is dense where work happens: the editor runs edge to edge, with rulers, a tool rail and an inspector. Management pages are calm, centred columns of cards and forms. Warmth is a direction, not yet a token. Any warm material colour introduced later must be recorded here before use, and it must never touch the editor's layer colours, which carry meaning.

**Key Characteristics:**
- Flat white sheets on a pale bench, separated by hairline borders, never by shadows.
- One action accent (indigo, provisional), used for primary actions, active navigation and selection.
- Small type (14 px body, 12 px labels): an information-dense tool for long desk sessions.
- Colour on the drawing is semantic: each layer role has a fixed stroke colour and dash pattern.
- System fonts throughout. Nothing decorative competes with the drawing.

## Colors

A cool slate neutral ramp carries almost everything. One indigo accent marks action and selection, and a small set of semantic colours carries meaning, both in status and on the drawing.

### Primary
- **Action Indigo** (`action-indigo`): primary buttons ("Ajouter", "Créer la commande", "Enregistrer"), active navigation and tabs, links ("Modifier", "+ Ajouter une ligne"), the editor's selection and UI overlay colour (`UI_COLOR`), and the translucent fill of cut parts. **Provisional:** it is inherited from Tailwind's default palette, not chosen for the trade, and may be replaced by a colour closer to the notebook world. Until then, use it exactly as documented.
- **Action Indigo Deep** (`action-indigo-deep`): hover state of primary buttons.
- **Action Indigo Mist** (`action-indigo-mist`): selected or highlighted rows and active toggles.

### Neutral
- **Ink** (`ink`): page titles, primary text, and the stroke of cut outlines on the drawing.
- **Graphite** (`graphite`): secondary solid buttons (for example "Ajouter une scie") and dark toolbar chips.
- **Slate Text** (`slate-text`): body copy in dense lists, and dimension lines on the drawing.
- **Slate Muted** (`slate-muted`): field labels, hints and secondary metadata. This is the most used text colour.
- **Slate Faint** (`slate-faint`): tertiary metadata, the footer, "démo" tags, and construction lines on the drawing.
- **Rule Line** (`rule-line`): the border of every input, select and outline button.
- **Hairline** (`hairline`): card borders, the navigation bottom rule and dividers.
- **Paper** (`paper`): cards, dialogs, navigation and the editor canvas.
- **Bench** (`bench`): the app background behind the cards.
- **Tag Wash** (`tag-wash`): neutral tag and badge backgrounds.

### Semantic
- **Quench Red** (`quench-red`, wash `quench-red-wash`):
  - Destructive actions ("Supprimer") and errors.
  - Shortages, and cancelled orders.
  - On the drawing, the stroke of hole (perçage) layers.
- **Temper Green** (`temper-green`): success, for example a saved state or a feasible order.
- **Caution Amber** (`caution-amber`, wash `caution-amber-wash`): low stock and warnings.
- **Engrave Blue** (`engrave-blue`): engrave layer strokes on the drawing.
- **Grind Teal** (`grind-teal`): the grind line (émouture) on the drawing and client plan, always dash-dot.
- **Snap Amber** (`snap-amber`): the editor's snap marker.

### Named Rules
**The Layer Colour Is Meaning Rule.** On the drawing and the client plan, a stroke's colour and dash identify its layer role:
- cut: ink, solid;
- hole: red;
- engrave: blue;
- grind: teal, dash-dot;
- construction: faint, dashed;
- dimension: slate.

Never reuse these colours decoratively elsewhere in the editor, and never restyle a role without updating the plan export.

**The One Accent Rule.** Indigo is the only accent. It marks what you can act on, or what is selected. Status colours (red, green, amber) speak only for state, never for decoration.

## Typography

**Display Font:** none (no display face)
**Body Font:** the system UI sans (`ui-sans-serif, system-ui`)
**Label/Mono Font:** the system monospace, used sparingly for numeric readouts

**Character:** Plain, native and legible. The type stays out of the way so that dimensions and drawings lead, like the printed grid of a notebook rather than its handwriting.

### Hierarchy
- **Headline:** page titles ("Matériaux", "Commandes"). One per page.
- **Title:** card and section headings, and item names in lists.
- **Body:** the default for forms, lists, buttons and the editor's toolbars and inspector.
- **Label:** field labels (Slate Muted), hints, metadata lines, tags and the editor's status bar.
- **Numeric:** monospace readouts where digits must align.

### Named Rules
**The Small And Exact Rule.** The interface is set small (body 14 px, labels 12 px) because it is a dense desk tool. Never shrink below 12 px. Dimensions and numeric fields are never truncated or rounded for display beyond their stored precision.

## Layout

- **Management pages:** a single centred column (`max-w-3xl` to `max-w-6xl` depending on the page), 16 px side padding and 32 px top padding. Content is stacked as cards with 24 to 32 px between them.
- **Forms:** grids of 2 columns on small screens and 3 to 5 from `md` upward, with 8 to 12 px gaps. Labels sit above their fields.
- **Navigation:** a full-width white bar with a hairline bottom border. The brand sits on the left, the page links follow, and "Déconnexion" sits on the far right. It wraps on narrow screens.
- **Editor:** full bleed below the navigation.
  - Header bar: back link, design name and save state on the left; history, zoom, import/export and "Enregistrer" on the right.
  - Options bar: grid, nodes and snapping toggles.
  - Main area: a vertical tool rail on the left, the canvas with mm rulers in the centre, and a tabbed inspector on the right (Objet, Calques, Fond, Document).
  - Status bar at the bottom: hint text, cursor position and zoom level.
- **Rhythm:** spacing comes from the 4 px Tailwind scale. 8 px is the workhorse gap, 16 px the card padding.
- **Responsive:** the system is desktop-first. Only about 15 responsive overrides exist, all switching form grids at `md`. Mobile and tablet use is not a designed target.

## Elevation & Depth

The system is flat. Depth comes from tone and line: white sheets (Paper) sit on a pale Bench and are outlined by a hairline border. Shadows appear only on layers that float above the page, such as modal dialogs (perspective correction, the shape library, confirmations) and dropdown menus.

### Shadow Vocabulary
- **Floating layer** (`box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)`): modal dialogs only.

### Named Rules
**The Flat Sheet Rule.** Nothing that sits in the page flow casts a shadow: no card, button, input or panel. A shadow means "this floats above the page", so only dialogs and menus get one. Use a hairline border to separate, never a shadow.

## Shapes

Gently rounded and consistent by size:
- **Small (4 px):** tags, compact inputs and the small buttons of the editor's toolbars.
- **Medium (8 px):** standard inputs, selects and primary or secondary buttons.
- **Large (12 px):** cards and dialogs.
- **Fully round:** rare, reserved for dots and toggles.

Borders are always 1 px solid. Drawing geometry (parts, dimension arrows, rulers) is never rounded or styled by the interface's shape language.

## Components

### Buttons
- **Primary:** Action Indigo with white medium-weight text, 8 px radius and 8 × 16 px padding. Hover moves to Action Indigo Deep. When disabled, opacity drops to 50 %. Use one per form or toolbar ("Ajouter", "Enregistrer").
- **Secondary (solid):** Graphite with white text, 8 px radius and 6 × 12 px padding, for inline add actions inside a card.
- **Outline:** a white button with a Rule Line border, Slate Text, a 4 px radius and compact padding. The editor's toolbar actions (Importer un SVG, Exporter SVG/DXF, Plan client…, 1:1) use it.
- **Text actions:** an Action Indigo link ("Modifier", "+ Ajouter une ligne") or a Quench Red one ("Supprimer"), at 12 to 14 px, with no background.
- **Focus:** no custom focus style exists, so the browser default ring is relied on. This is a known gap.

### Chips / Tags
- **Demo tag:** Tag Wash background, Slate Faint 12 px text, 4 px radius, 2 × 6 px padding. It marks seed data.
- **Order status:**
  - "brouillon" (draft): neutral slate wash.
  - "confirmée" (confirmed): blue wash.
  - "annulée" (cancelled): red wash.
  - All three share the tag shape, aligned to the right of the card.

### Cards / Containers
- **Corner Style:** 12 px.
- **Background:** Paper on the Bench.
- **Shadow Strategy:** none (see the Flat Sheet Rule).
- **Border:** 1 px Hairline.
- **Internal Padding:** 16 px. Collapsible cards ("Catalogue scies / lames") put their title on the left and a faint +/− on the right.

### Inputs / Fields
- **Style:** Paper background with a 1 px Rule Line border.
  - Form fields: 8 px radius and 8 × 12 px padding, 14 px text.
  - Compact fields: 4 px radius and 4 × 8 px padding, used in the editor inspector and in dense tables.
- **Label:** 12 px Slate Muted, above the field, with 4 px between them.
- **Focus:** only one field defines a focus colour (an indigo border), so the browser default is relied on elsewhere. This is a known gap.
- **Error:** inline Quench Red text below or beside the field.

### Navigation
- **Top bar:**
  - The bold brand wordmark sits at 18 px.
  - Page links are 14 px Slate Muted and darken to Ink on hover. The active link is Action Indigo and medium weight.
  - The sign-out link sits on the far right.
- **Tabs:** the editor inspector and some pages use underline tabs. The active tab gets a 2 px Action Indigo bottom border and indigo text; inactive tabs are Slate Muted.

### Editor Canvas (signature component)
- **Canvas and grid:** the drawing sits on a white canvas with a faint millimetre grid. Rulers in mm run along the top and left edges.
- **Tool rail:** single icons, with the active tool on an Action Indigo tile.
- **Parts:**
  - Cut parts get an Ink outline and a translucent indigo fill (14 % opacity).
  - Holes are red circles on an opaque white fill.
- **Dimensions:** slate lines with arrowheads and a centred "112 mm" label.
- **Snap feedback:** an amber marker with an amber-brown label.
- **Status bar:** at 12 px, it gives the hint for the current tool on the left, and the cursor position and zoom level on the right.

## Do's and Don'ts

### Do:
- **Do** separate surfaces with the 1 px Hairline border on white Paper over the Bench, the way every page already works.
- **Do** keep one primary indigo button per form or toolbar. Everything else is outline, text or secondary.
- **Do** put labels above fields in 12 px Slate Muted, and keep 8 px as the default gap.
- **Do** respect the layer colour code on the drawing and the client plan:
  - cut: ink;
  - hole: red;
  - engrave: blue;
  - grind: teal, dash-dot;
  - construction: faint, dashed;
  - dimension: slate.
- **Do** bring the "carnet" warmth through voice, material naming and notes first. Record any warm colour or texture token in this file before using it.

### Don't:
- **Don't** add shadows to cards, panels, buttons or inputs. Shadows are for dialogs and menus only (the Flat Sheet Rule).
- **Don't** introduce a second accent colour, or use red, green or amber decoratively.
- **Don't** reuse layer colours (red, blue, teal, amber) for interface chrome inside the editor, where they would be read as geometry.
- **Don't** set any text below 12 px, and never display a dimension rounded beyond its stored precision.
- **Don't** treat the indigo as a brand commitment. It is provisional and may be replaced as a whole, never mixed with a new accent.
