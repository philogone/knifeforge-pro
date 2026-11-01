"""The cutting/yield calculator: given a raw-material stock unit (a bar or
a sheet as purchased) and the blank size needed per knife, work out how
many blanks come out of one stock unit, how much is wasted, and how many
stock units a given order quantity requires. Also returns a simple grid
layout (grid_cols x grid_rows) so the frontend can render an actual visual
cutting diagram, not just numbers.

AREA materials (sheet stock) are packed with simple shelf/grid packing
(try the blank in both orientations, keep whichever fits more), not a
general irregular-shape nester — good enough for a maker's planning
estimate and for drawing a sensible diagram, not a substitute for real
nesting software when optimizing irregular offcut usage.
"""

import math

from app.models.material import DimensionType, Material
from app.schemas.material import YieldCalcResult


def compute_yield(material: Material, blank_length_mm: float, blank_width_mm: float | None, quantity_needed: int) -> YieldCalcResult:
    if material.dimension_type == DimensionType.LENGTH:
        if not material.standard_length_mm:
            raise ValueError("Material has no standard_length_mm set — required for LENGTH yield calculations")
        pitch = blank_length_mm + material.kerf_mm
        pieces_per_stock_unit = int(material.standard_length_mm // pitch)
        if pieces_per_stock_unit < 1:
            raise ValueError("Blank length (plus kerf) is longer than the material's standard stock length")
        waste = material.standard_length_mm - pieces_per_stock_unit * pitch
        stock_units_needed = math.ceil(quantity_needed / pieces_per_stock_unit)
        total_consumption = quantity_needed * pitch
        unit = "mm"
        denominator = material.standard_length_mm
        grid_cols, grid_rows, rotated = pieces_per_stock_unit, 1, False

    elif material.dimension_type == DimensionType.AREA:
        if not material.standard_length_mm or not material.standard_width_mm:
            raise ValueError("Material has no standard sheet dimensions set — required for AREA yield calculations")
        if not blank_width_mm:
            raise ValueError("blank_width_mm is required for AREA materials")

        sheet_area = material.standard_length_mm * material.standard_width_mm

        # Simple shelf packing: try the blank as-is, then rotated 90°, keep
        # whichever orientation fits more whole pieces on the sheet.
        cols_a = int(material.standard_length_mm // blank_length_mm)
        rows_a = int(material.standard_width_mm // blank_width_mm)
        count_a = cols_a * rows_a

        cols_b = int(material.standard_length_mm // blank_width_mm)
        rows_b = int(material.standard_width_mm // blank_length_mm)
        count_b = cols_b * rows_b

        if count_b > count_a:
            grid_cols, grid_rows, pieces_per_stock_unit, rotated = cols_b, rows_b, count_b, True
        else:
            grid_cols, grid_rows, pieces_per_stock_unit, rotated = cols_a, rows_a, count_a, False

        if pieces_per_stock_unit < 1:
            raise ValueError("Blank is larger than the material's standard sheet in both orientations")

        blank_area = blank_length_mm * blank_width_mm
        waste = sheet_area - pieces_per_stock_unit * blank_area
        stock_units_needed = math.ceil(quantity_needed / pieces_per_stock_unit)
        total_consumption = quantity_needed * blank_area
        unit = "mm^2"
        denominator = sheet_area

    else:  # COUNT
        pieces_per_stock_unit = 1
        waste = 0.0
        stock_units_needed = quantity_needed
        total_consumption = float(quantity_needed)
        unit = "unit"
        denominator = 1.0
        grid_cols, grid_rows, rotated = None, None, False

    waste_percentage = round((waste / denominator) * 100, 2) if denominator else 0.0

    return YieldCalcResult(
        pieces_per_stock_unit=pieces_per_stock_unit,
        waste_per_stock_unit=round(waste, 2),
        waste_percentage=waste_percentage,
        stock_units_needed=stock_units_needed,
        total_consumption=round(total_consumption, 2),
        unit=unit,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
        rotated=rotated,
    )
