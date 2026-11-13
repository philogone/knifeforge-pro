"""Calibration plate (planche de contrôle): reference parts to cut on the workshop's machine
and measure with a caliper, to prove the whole chain (drawing → export → cut) is to size and to
find the kerf the machine really removes.

How the kerf is recovered. A part exported with a compensation of `k_used` (full kerf width,
outlines offset by k_used / 2) and cut by a beam that really removes `k_real`:
- an outside dimension (plate length, disc diameter) ends up `nominal + k_used - k_real`;
- an inside dimension (hole diameter, window) ends up `nominal - k_used + k_real`;
so each measurement gives an estimate of k_real, and their spread says how consistent the
machine is. A centre distance does not depend on the kerf at all: it checks the machine's
scale (steps per mm, backlash).

Every measured dimension is between two parallel straight edges or across a full circle, so a
caliper reads it directly.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Any, Literal

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.schemas.design import DesignDocument
from app.services.design_templates import _path, circle_nodes, document, rounded_rect_nodes
from app.services.parts_sheet import PT_PER_MM, _bezier_contour, hole_centres

TOLERANCE_MM = 0.1  # the product's promise
MAX_KERF_MM = 3.0

Kind = Literal["outside", "inside", "pitch"]


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    nominal_mm: float
    kind: Kind
    how: str
    # where the letter goes on the drawing (design mm)
    at: tuple[float, float]


FEATURES: list[Feature] = [
    Feature("A", "Longueur de la plaque", 120, "outside", "entre les deux bords droits", (60, 84)),
    Feature("B", "Largeur de la plaque", 80, "outside", "entre les bords haut et bas", (-5, 40)),
    Feature("C", "Côté du carré", 25, "outside", "entre deux côtés opposés", (142.5, 12.5)),
    Feature("D", "Diamètre du disque", 30, "outside", "diamètre extérieur", (142.5, 50)),
    Feature("E", "Perçage Ø 3", 3, "inside", "becs intérieurs du pied", (15, 9)),
    Feature("F", "Perçage Ø 5", 5, "inside", "becs intérieurs du pied", (30, 9)),
    Feature("G", "Perçage Ø 10", 10, "inside", "becs intérieurs du pied", (20, 56)),
    Feature("H", "Perçage Ø 20", 20, "inside", "becs intérieurs du pied", (60, 31)),
    Feature("I", "Fenêtre carrée", 20, "inside", "entre deux côtés opposés", (90, 33)),
    Feature("J", "Largeur de la fente", 6, "inside", "entre les deux bords droits", (60, 74)),
    Feature("K", "Entraxe des perçages Ø 10", 80, "pitch", "du bord gauche d'un trou au bord gauche de l'autre", (100, 56)),
]
BY_KEY = {f.key: f for f in FEATURES}


def plate_document() -> dict[str, Any]:
    """The reference parts, in mm, y down. Rounded corners (R 10) exercise the arcs, the
    straight edges between them carry the measured lengths."""
    objects = [
        _path("plate", "cut", "Plaque de contrôle", [rounded_rect_nodes(0, 0, 120, 80, 10)]),
        _path("square", "cut", "Carré 25", [rounded_rect_nodes(130, 0, 25, 25, 0)]),
        _path("disc", "cut", "Disque Ø 30", [circle_nodes(142.5, 50, 15)]),
        _path("e", "holes", "Perçage Ø 3", [circle_nodes(15, 15, 1.5)]),
        _path("f", "holes", "Perçage Ø 5", [circle_nodes(30, 15, 2.5)]),
        _path("g1", "holes", "Perçage Ø 10", [circle_nodes(20, 45, 5)]),
        _path("g2", "holes", "Perçage Ø 10 (entraxe)", [circle_nodes(100, 45, 5)]),
        _path("h", "holes", "Perçage Ø 20", [circle_nodes(60, 45, 10)]),
        _path("i", "holes", "Fenêtre 20 × 20", [rounded_rect_nodes(80, 8, 20, 20, 0)]),
        _path("j", "holes", "Fente 30 × 6", [rounded_rect_nodes(45, 62, 30, 6, 3)]),
    ]
    return document(objects)


# ------------------------------------------------------------------------------------------
# Analysis
# ------------------------------------------------------------------------------------------


@dataclass
class FeatureResult:
    key: str
    label: str
    kind: Kind
    nominal_mm: float
    measured_mm: float
    error_mm: float  # measured - nominal
    kerf_estimate_mm: float | None  # None for a centre distance
    within_tolerance: bool


@dataclass
class Analysis:
    kerf_used_mm: float
    features: list[FeatureResult]
    kerf_estimate_mm: float | None  # mean of the outside / inside estimates
    kerf_spread_mm: float | None  # max - min of those estimates
    suggested_kerf_mm: float | None  # what to type as compensation next time
    scale_error_ppm: float | None  # from the centre distance
    max_error_mm: float
    residual_mm: float | None  # worst error left once the suggested compensation is used
    within_tolerance: bool
    advice: list[str]


def analyse(kerf_used_mm: float, measurements: dict[str, float]) -> Analysis:
    if not 0 <= kerf_used_mm <= MAX_KERF_MM:
        raise ValueError(f"The compensation used must be between 0 and {MAX_KERF_MM} mm")
    unknown = set(measurements) - set(BY_KEY)
    if unknown:
        raise ValueError(f"Unknown feature(s): {', '.join(sorted(unknown))}")
    if not measurements:
        raise ValueError("Enter at least one measurement")

    results: list[FeatureResult] = []
    for f in FEATURES:
        if f.key not in measurements:
            continue
        m = float(measurements[f.key])
        if not 0 < m < f.nominal_mm * 2 + 10:
            raise ValueError(f"{f.key}: {m} mm is not a plausible measurement of {f.nominal_mm} mm")
        err = m - f.nominal_mm
        if f.kind == "outside":
            k = kerf_used_mm - err
        elif f.kind == "inside":
            k = kerf_used_mm + err
        else:
            k = None
        results.append(FeatureResult(f.key, f.label, f.kind, f.nominal_mm, m, err, k, abs(err) <= TOLERANCE_MM))

    estimates = [r.kerf_estimate_mm for r in results if r.kerf_estimate_mm is not None]
    kerf_est = mean(estimates) if estimates else None
    spread = (max(estimates) - min(estimates)) if estimates else None
    suggested = None
    if kerf_est is not None:
        suggested = round(min(MAX_KERF_MM, max(0.0, kerf_est)), 2)
    pitch = next((r for r in results if r.kind == "pitch"), None)
    scale_ppm = pitch.error_mm / pitch.nominal_mm * 1e6 if pitch else None

    # what each part would measure with the suggested compensation (same machine, same cut)
    residual = None
    if suggested is not None:
        left = []
        for r in results:
            if r.kind == "outside":
                left.append(r.error_mm + (suggested - kerf_used_mm))
            elif r.kind == "inside":
                left.append(r.error_mm - (suggested - kerf_used_mm))
            else:
                left.append(r.error_mm)
        residual = max(abs(x) for x in left)

    max_err = max(abs(r.error_mm) for r in results)
    ok = all(r.within_tolerance for r in results)

    advice: list[str] = []
    if ok:
        advice.append("ok")
    elif suggested is not None and residual is not None and residual <= TOLERANCE_MM:
        advice.append("use_suggested")
    if spread is not None and spread > 2 * TOLERANCE_MM:
        advice.append("inconsistent")
    if scale_ppm is not None and abs(pitch.error_mm) > TOLERANCE_MM:
        advice.append("scale")
    if kerf_est is not None and kerf_est < 0:
        advice.append("negative_kerf")
    if not ok and "use_suggested" not in advice and not {"inconsistent", "scale"} & set(advice):
        advice.append("recheck")

    return Analysis(kerf_used_mm, results, kerf_est, spread, suggested, scale_ppm, max_err, residual, ok, advice)


# ------------------------------------------------------------------------------------------
# Measurement sheet
# ------------------------------------------------------------------------------------------

INK = HexColor("#0f172a")
MUTED = HexColor("#6f6a60")
ACCENT = HexColor("#2a78d6")
RULE = HexColor("#cbd5e1")
KIND_LABEL = {"outside": "extérieure", "inside": "intérieure", "pitch": "entraxe"}


def sheet_pdf(kerf_used_mm: float = 0.0, machine: str | None = None, material: str | None = None, workshop: str | None = None) -> bytes:
    """One A4 page: the reference parts drawn at 1:1 with their letters, and the table to fill
    in with a caliper. The drawing doubles as a template: it can be glued and cut by hand."""
    doc = DesignDocument.model_validate(plate_document())
    page_w, page_h = A4
    mm = PT_PER_MM
    left = 15 * mm
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle("Planche de contrôle — fiche de relevé")
    c.setCreator("KnifeForge Pro")

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left, page_h - 18 * mm, "Planche de contrôle — fiche de relevé")
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    who = f"{workshop} · " if workshop else ""
    c.drawString(left, page_h - 23 * mm, f"{who}KnifeForge Pro · {date.today():%d/%m/%Y} · dessin à l'échelle 1:1, imprimer à 100 %")

    # the parts at 1:1, origin 20 mm below the title, 15 mm + room for letter B from the left
    ox, oy = 25.0, 32.0

    def to_pt(x: float, y: float) -> tuple[float, float]:
        return ((ox + x) * mm, page_h - (oy + y) * mm)

    c.setStrokeColor(INK)
    c.setLineWidth(0.35)
    for obj in doc.objects:
        path = c.beginPath()
        for contour in obj.contours:
            _bezier_contour(path, contour, obj.closed, to_pt)
        c.drawPath(path, stroke=1, fill=0)
    c.setLineWidth(0.25)
    for hx, hy in hole_centres(doc):
        px, py = to_pt(hx, hy)
        c.line(px - 2 * mm, py, px + 2 * mm, py)
        c.line(px, py - 2 * mm, px, py + 2 * mm)
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 9)
    for f in FEATURES:
        px, py = to_pt(*f.at)
        c.drawCentredString(px, py - 3, f.key)

    # setup lines
    y = page_h - (oy + 98) * mm
    c.setFillColor(INK)
    c.setFont("Helvetica", 9)
    fields = [
        ("Machine", machine or ""),
        ("Matière / épaisseur", material or ""),
        ("Compensation saisie à l'export", f"{kerf_used_mm:.2f} mm".replace(".", ",") if kerf_used_mm else "0 (aucune)"),
    ]
    for label, value in fields:
        c.drawString(left, y, f"{label} :")
        c.setStrokeColor(RULE)
        c.line(left + 55 * mm, y - 1.5, left + 180 * mm, y - 1.5)
        c.drawString(left + 57 * mm, y, value)
        y -= 7 * mm

    # table
    y -= 3 * mm
    cols = [left, left + 10 * mm, left + 62 * mm, left + 84 * mm, left + 104 * mm, left + 132 * mm, left + 158 * mm]
    heads = ["", "Cote", "Type", "Nominale", "Mesurée", "Écart", "OK ≤ 0,1"]
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(MUTED)
    for x, h in zip(cols, heads):
        c.drawString(x, y, h)
    y -= 2.5 * mm
    c.setStrokeColor(INK)
    c.line(left, y, left + 180 * mm, y)
    for f in FEATURES:
        y -= 8 * mm
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(cols[0], y + 1, f.key)
        c.setFillColor(INK)
        c.setFont("Helvetica", 9)
        c.drawString(cols[1], y + 1, f.label)
        c.setFont("Helvetica", 7)
        c.setFillColor(MUTED)
        c.drawString(cols[1], y - 3.2 * mm + 1, f.how)
        c.setFillColor(INK)
        c.setFont("Helvetica", 9)
        c.drawString(cols[2], y + 1, KIND_LABEL[f.kind])
        c.drawString(cols[3], y + 1, f"{f.nominal_mm:.2f}".replace(".", ","))
        c.setStrokeColor(RULE)
        c.line(cols[4], y - 1, cols[4] + 22 * mm, y - 1)
        c.line(cols[5], y - 1, cols[5] + 20 * mm, y - 1)
        c.rect(cols[6] + 4 * mm, y - 0.5, 3.2 * mm, 3.2 * mm, stroke=1, fill=0)

    y -= 10 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(left, y, "Lecture")
    c.setFont("Helvetica", 8)
    lines = [
        "Mesurer chaque cote deux fois et noter la moyenne, pièce ébavurée, à 20 °C environ.",
        "Cote extérieure trop petite / perçage trop grand : la machine enlève plus que la compensation saisie.",
        "Trait réel estimé = compensation + (perçage mesuré − nominal) = compensation − (extérieure mesurée − nominale).",
        "L'entraxe K ne dépend pas du trait : un écart sur K vient de l'échelle de la machine (pas par mm, jeu).",
        "Reporter les mesures dans KnifeForge (Dessin et découpe › Contrôle de découpe) pour le calcul.",
    ]
    for line in lines:
        y -= 4.5 * mm
        c.drawString(left, y, line)

    c.showPage()
    c.save()
    return buffer.getvalue()
