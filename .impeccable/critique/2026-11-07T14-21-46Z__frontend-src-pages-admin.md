---
target: admin app
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:D:\\GIT\\knifeforge-pro\\frontend\\src\\pages\\admin"
timestamp: 2026-11-07T14-21-46Z
slug: frontend-src-pages-admin
---
Method: dual-agent (A: design review · B: detector + browser)

## Design Health Score — 24/40 (Acceptable)
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of status | 3 | No active nav state on detail routes; active state not indigo |
| 2 | Match real world | 3 | FR locale leaks: dot decimals (toFixed), "$" price next to €, "unit(s)" |
| 3 | User control | 2 | One-click deletes (materials, models, recipes); Esc does not close Plan client |
| 4 | Consistency | 2 | Cancelled tag red vs grey; emoji chrome reuses layer colours; two primaries in Settings |
| 5 | Error prevention | 2 | No delete confirmation; placeholder-only labels; disabled nesting button unexplained |
| 6 | Recognition | 2 | 14 icon-only tools named by glyph; shortcuts buried in Document tab |
| 7 | Flexibility | 3 | Good shortcuts/numeric input; no search/sort/bulk on lists |
| 8 | Minimalist | 2 | Create forms before lists; repeated layer helper text |
| 9 | Error recovery | 2 | alert() with hard-coded English messages |
| 10 | Help | 3 | Good inline help; no cheat sheet |

## Specificity verdict
Content authored for knifemakers; shell is stock Tailwind admin. Detector: 5 gray-on-color CLI hits, all false positives (ternary :class). Browser overlay: real low-contrast on text-slate-400 (2.3–2.6:1: démo tags, dates, hints, footer), placeholders gray-400 2.5:1, emerald "Enregistré" 3.8:1. No designed focus style.

## Priority issues
- [P1] One-click irreversible deletes (MaterialsPage.vue:96, KnifeModelsPage.vue:93, TreatmentsPage.vue:66) + alert() in English → harden
- [P1] Numbers/identity not client-ready: $ prices, dot decimals, footer "KnifeForge Manager — kit de démarrage" → clarify, polish
- [P1] Editor chrome: emoji/glyph icons, no aria-label, layer colours in chrome → polish, harden
- [P2] Plan client dialog: unlabelled ↻ primary, Esc not handled, stale-plan risk → harden, clarify
- [P2] Management pages: create form before list, low-stock not signalled, low-contrast slate-400 metadata → distill, layout
- [P3] Nav active state on detail routes, footer under editor causes scroll, header wraps at 1024 → layout, adapt

## Persona red flags
Alex: Esc on plan, no bulk/search, 3 export buttons. Sam: glyph-named tools, colour-only status, placeholder labels, no modal role/focus, slate-400 contrast. Knifemaker+client: cost/margin on model detail, "démo" tags, dimension label struck by its line in editor, no plan action from order.

## Questions
Client plan reachable from order/model? Order-centred flow vs 8 tabs? A notebook action colour instead of indigo, and separate canvas selection colour?
