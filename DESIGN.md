---
name: KnifeForge Pro
description: Workshop manager and 1:1 vector editor for knifemakers, precise to the tenth of a millimetre.
colors:
  olive: "#4d5a1c"
  olive-deep: "#3f4a17"
  olive-mist: "#f4f6ea"
  olive-wash: "#e7ecd2"
  ink: "#1c1b18"
  graphite: "#2b2925"
  graphite-text: "#403d37"
  graphite-muted: "#6f6a60"
  graphite-faint: "#a39d90"
  rule-line: "#cdc7ba"
  hairline: "#e3dfd5"
  paper: "#ffffff"
  bench: "#f8f6f1"
  tag-wash: "#f0ede6"
  quench-red: "#b91c1c"
  temper-green: "#15803d"
  caution-amber: "#92400e"
  caution-amber-wash: "#fffbeb"
  layer-cut: "#0f172a"
  layer-hole: "#dc2626"
  layer-engrave: "#2563eb"
  layer-grind: "#0f766e"
  layer-construction: "#94a3b8"
  layer-dimension: "#334155"
  snap-amber: "#f59e0b"
typography:
  headline:
    fontFamily: "IBM Plex Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  title:
    fontFamily: "IBM Plex Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: "IBM Plex Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "IBM Plex Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.33
  numeric:
    fontFamily: "IBM Plex Mono, ui-monospace, Consolas, monospace"
    fontSize: "0.625rem"
    fontWeight: 400
    lineHeight: 1
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.olive}"
    textColor: "{colors.paper}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.olive-deep}"
  button-secondary:
    backgroundColor: "{colors.graphite}"
    textColor: "{colors.paper}"
    rounded: "{rounded.lg}"
    padding: "8px 16px"
  button-outline:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.graphite-text}"
    rounded: "{rounded.lg}"
    padding: "8px 16px"
  input-field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "8px 12px"
  input-compact:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "4px 8px"
  sheet:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.xl}"
    padding: "16px"
  tag-accent:
    backgroundColor: "{colors.olive-mist}"
    textColor: "{colors.olive-deep}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "2px 6px"
  tag-neutral:
    backgroundColor: "{colors.tag-wash}"
    textColor: "{colors.graphite-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "2px 6px"
---

# Design System: KnifeForge Pro

## Overview

**Creative North Star: "Le carnet du coutelier"**

KnifeForge Pro is a knifemaker's workshop notebook. The pages are warm paper on a faint 5 mm graph grid. The ink is a warm graphite, and the single action colour is a patinated olive, like an oiled tool handle. It is technical first: dimensions, drawings and stock counts are always legible, aligned and exact. The warmth lives in the material, not in decoration: the paper tone, a humanist engineered typeface (IBM Plex Sans), and the maker's own vocabulary in labels and hints.

Density follows the work. The editor runs edge to edge, with rulers, an icon rail, an inspector and a status bar. Management pages are calm centred columns: a page head (title, one-line lead, primary action), then the list, with creation forms opening on demand. The interface never competes with the drawing. Layer colours on the canvas carry meaning, and nothing in the chrome borrows them.

**Key Characteristics:**
- Warm graphite neutrals on paper (`bench`). White sheets with a hairline edge, and no shadows in the page flow.
- One action colour, olive. It marks primary buttons, the active navigation, selection on the canvas and links.
- IBM Plex Sans throughout, self-hosted. IBM Plex Mono only for ruler figures.
- Figures in the reader's convention (`182,0 mm`, `180,00 €`). Tabular numerals in tables.
- One drawn icon set (20 px, 1.5 px stroke, `currentColor`). No emoji or glyph icons.

## Colors

The palette is a warm graphite ramp with one olive accent. Semantic colours are kept for state, and a fixed set of layer colours is used only on the drawing.

### Primary
- **Olive** (`olive`): primary buttons, the active navigation underline, the active tool tile, canvas selection (`UI_COLOR`), focus rings and text actions (`olive-deep`).
- **Olive Mist / Wash**: category tags, text selection and the origin axes on the grid.

### Neutral
The ramp is exposed as Tailwind `slate-*`, overridden in `tailwind.config.js` so the whole interface stays on one warm ramp.
- **Ink**: titles and body text.
- **Graphite**: secondary solid buttons.
- **Graphite Text**: dense lists.
- **Graphite Muted**: labels, hints and metadata. Its contrast on white is about 5.3:1. Never go lighter than this for text.
- **Graphite Faint**: icons and disabled states only, never text.
- **Rule Line**: the borders of inputs and outline buttons.
- **Hairline**: sheet edges, dividers and the bar rules.
- **Paper**: sheets, dialogs, the nav and the canvas.
- **Bench**: the page background, with its 20 px graph grid.

### Semantic
- **Quench Red**: destructive actions, errors and shortfalls.
- **Temper Green**: "sufficient", "saved" and "feasible".
- **Caution Amber**: low stock, a missing template link and warnings.

All three are always paired with text, never colour alone.

### Layer colours (drawing only)
Each layer type has a fixed stroke colour, plus a dash pattern where shown:

| Layer | Colour | Stroke |
|---|---|---|
| cut | ink | solid; neutral translucent fill |
| hole | red | solid |
| engrave | blue | solid |
| grind | teal | dash-dot |
| construction | faint | dashed |
| dimension | slate | solid |

### Named Rules
**The Layer Colour Is Meaning Rule.** On the drawing and the client plan, a stroke's colour and dash identify its layer role. The chrome never uses these colours: no red magnet, no amber lock.

**The One Accent Rule.** Olive is the only accent. It means "you can act here" or "this is selected". Status colours speak only for state.

## Typography

**Body Font:** IBM Plex Sans, at weights 400, 500 and 600, self-hosted through `@fontsource`.
**Label/Mono Font:** IBM Plex Mono, used only for the canvas ruler figures.

**Character:** An engineered sans with a humanist hand. It reads like a technical drawing annotated by a person, which is the notebook in type.

### Hierarchy
- **Headline**: the page title, one per page.
- **Title**: sheet and section headings, and item names.
- **Body**: forms, lists, toolbars and the inspector. Leads are capped at about 65ch.
- **Label**: field labels (medium weight) and tags. Never below 12 px in the HTML interface.
- **Numeric**: ruler ticks on the canvas.

### Named Rules
**The Small And Exact Rule.** Body is 14 px and labels are 12 px. Numbers use the locale formatters in `@/i18n`:
- `num` for a fixed number of decimals;
- `money` for euros;
- `qty` for a quantity with its unit;
- `formatDecimal` for costs, up to 6 decimals.

Never use `toFixed` in a template. Never round a value for display below its stored precision; a unit cost of 0,000778 €/mm² stays 0,000778.

## Layout

- **Page shell:** a 56 px sticky nav. The brand mark sits on the left. Links follow in three groups (stock and know-how, orders, drawing) separated by hairlines. Settings and sign-out sit on the right. The active section, detail pages included, gets a 2 px olive underline flush with the bottom rule.
- **Management pages:**
  - `.page` with a max width of 3xl to 6xl, 20 px side padding and 32 px top padding.
  - `.page-head` holds the title, the lead and the primary action on the right.
  - Below it comes the list of sheets with 12 px gaps.
  - Creation forms are hidden until "+ Ajouter…" is pressed, then open above the list.
  - The footer is hidden on the editor.
- **Forms:** labels above fields (`.field-label`), on grids of 2 to 4 columns with 12 px gaps. Placeholder-only fields are not allowed.
- **Editor:** full height under the nav.
  - Header bar: back link, name, save state, model and material selects; then history, fit, 1:1, the File menu (import and exports), Plan client and Enregistrer.
  - Options bar.
  - Main area: icon rail, canvas with rulers, and the tabbed inspector.
  - Status bar along the bottom.
  - At 1024 px the header wraps onto two rows.
- **Responsive:** desktop-first. Login drops its drawing panel below `lg`.

## Elevation & Depth

The system is flat. Depth comes from tone and line: white sheets on the paper bench, separated by a hairline. Shadows appear only on layers that float: dialogs, the File menu and the snap menu.

### Shadow Vocabulary
- **Floating layer** (Tailwind `shadow-xl` / `shadow-lg`): dialogs and dropdown menus only.

### Named Rules
**The Flat Sheet Rule.** Nothing in the page flow casts a shadow. To separate two surfaces, use a hairline.

## Shapes

- **Radius:** 4 px for tags, 6 px for compact inputs and the editor's small buttons, 8 px for buttons and inputs, and 12 px for sheets and dialogs.
- **Borders:** always 1 px.
- **Empty states:** a dashed hairline marks a frame waiting for content, for example the nesting result area.
- **Drawing geometry** is never styled by the interface's shape language.

## Components

All primitives live in `frontend/src/assets/main.css` under `@layer components`. Pages compose them rather than restating utility strings.

### Buttons
- `.btn`, combined with one of:
  - `.btn-primary`: olive. One per form or page head.
  - `.btn-secondary`: graphite. For an inline commit such as "Réapprovisionner".
  - `.btn-outline`: paper with a rule-line border. Cancel, secondary and neutral actions, and dangerous actions in red text.
- `.btn-sm` gives a compact size. Disabled buttons drop to 50 % opacity.
- **Text actions:** `.link-action` (olive) and `.link-danger` (red), with an underline on hover.

### Tags
- `.tag` combined with one of `tag-accent` (category or type), `tag-neutral` (démo, draft), `tag-info` (confirmed), `tag-success`, `tag-warning` or `tag-danger`.
- Order states come from `ORDER_STATUS_TAG` in `constants/referenceData.ts`, so the list and the detail page always agree.

### Sheets
- `.sheet` is paper, a 1 px hairline and a 12 px radius, with 16 to 20 px padding. It is never nested inside another sheet.
- `.sheet-title` and `.sheet-hint` style headings and hints inside it.

### Inputs / Fields
- `.input` is for forms; `.input-sm` is for dense rows and the editor inspector.
- Hovering darkens the border. Keyboard focus gets a 2 px olive outline (global `:focus-visible`), with an olive border on fields.
- Placeholders use Graphite Muted.

### Navigation
- Grouped top bar with underline-active state and `aria-current="page"`.
- Editor tabs use a 2 px olive underline, ink text when active and muted text when inactive.

### Editor chrome (signature component)
- **Icons:** `EditorIcon.vue` is the only icon source in the editor. Each tool button has an `aria-label` and a tooltip containing its shortcut.
- **Tool rail:** the active tool sits on an olive tile.
- **Canvas grid and rulers:** warm minor and major lines and warm ruler colours, with olive origin axes.
- **Dimension labels:** set in Plex Sans, centred a clear gap off their line, so they are never struck through.
- **Plan client dialog:** `role="dialog"`. Esc closes it. The preview follows the form. "Imprimer / PDF" is the primary action, and a 100 % scale reminder sits underneath.

### Login (the one authored moment)
A split screen: a blade plate draws its outline once, then its holes, grind line and dimensions settle in. This is the editor's own visual language, and it respects `prefers-reduced-motion`. The form sits on the right.

## Do's and Don'ts

### Do:
- **Do** start every management page with `.page-head`: a title, a one-line lead in the maker's words, and one primary action.
- **Do** put the list first and open forms on demand. Give every field a visible label.
- **Do** format every number through the `@/i18n` helpers, and use tabular numerals in tables.
- **Do** confirm destructive actions by naming the item, and show errors in the page, translated (no `alert()`).
- **Do** flag what blocks nesting (a missing template for a model and material) in caution amber, with a link to fix it.

### Don't:
- **Don't** add shadows to sheets, buttons or inputs.
- **Don't** use emoji or Unicode glyphs as icons. Draw them in `EditorIcon.vue`.
- **Don't** use layer colours (red, blue, teal, amber) for chrome inside the editor.
- **Don't** set text lighter than Graphite Muted, or smaller than 12 px.
- **Don't** write "$". The workshop prices in euros through `money()`.
