"""Design document format shared by the editor (frontend), the database and the
geometry/export services.

All coordinates are millimetres in the editor's world space: x to the right,
**y downward** (screen convention). Bézier handles are stored *relative* to
their anchor (``ix, iy`` = incoming handle offset, ``ox, oy`` = outgoing), which
matches Paper.js segments one-to-one and keeps translations trivial.
"""

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

from app.models.design import DesignKind

MAX_OBJECTS = 2000
MAX_NODES_PER_CONTOUR = 5000
MAX_COORD_MM = 100_000.0

Coord = Annotated[float, Field(ge=-MAX_COORD_MM, le=MAX_COORD_MM, allow_inf_nan=False)]


class Node(BaseModel):
    x: Coord
    y: Coord
    ix: Coord = 0.0
    iy: Coord = 0.0
    ox: Coord = 0.0
    oy: Coord = 0.0


class Layer(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    # cut: outlines that get cut out (nested, exported as CUT)
    # hole: closed shapes subtracted from the cut parts they overlap (pin holes…)
    # engrave: marks/decoration — exported but never nested
    # construction: guides — ignored by every export
    # dimension: annotations — drawn on client plans
    role: Literal["cut", "hole", "engrave", "construction", "dimension"] = "cut"
    visible: bool = True
    locked: bool = False


class PathObject(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["path"] = "path"
    layer: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=100)
    closed: bool = True
    # More than one contour = compound path (outer outline + inner cut-outs),
    # filled with the even-odd rule.
    contours: list[Annotated[list[Node], Field(min_length=2, max_length=MAX_NODES_PER_CONTOUR)]] = Field(
        min_length=1, max_length=64
    )


class DimensionObject(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["dimension"] = "dimension"
    layer: str = Field(min_length=1, max_length=64)
    a: tuple[Coord, Coord]
    b: tuple[Coord, Coord]
    offset: Coord = 8.0
    label: str | None = Field(default=None, max_length=60)


DesignObject = Annotated[Union[PathObject, DimensionObject], Field(discriminator="type")]


class DesignDocument(BaseModel):
    version: Literal[1] = 1
    unit: Literal["mm"] = "mm"
    layers: list[Layer] = Field(min_length=1, max_length=32)
    objects: list[DesignObject] = Field(default_factory=list, max_length=MAX_OBJECTS)

    @model_validator(mode="after")
    def _check_layer_refs(self):
        layer_ids = [layer.id for layer in self.layers]
        if len(set(layer_ids)) != len(layer_ids):
            raise ValueError("Duplicate layer ids")
        known = set(layer_ids)
        seen: set[str] = set()
        for obj in self.objects:
            if obj.layer not in known:
                raise ValueError(f'Object "{obj.id}" references unknown layer "{obj.layer}"')
            if obj.id in seen:
                raise ValueError(f'Duplicate object id "{obj.id}"')
            seen.add(obj.id)
        return self


class DesignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    kind: DesignKind = DesignKind.BLADE
    notes: str | None = None
    knife_model_id: int | None = None
    material_id: int | None = None
    document: DesignDocument


class DesignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    kind: DesignKind | None = None
    notes: str | None = None
    knife_model_id: int | None = None
    material_id: int | None = None
    document: DesignDocument | None = None


class DesignSummaryOut(BaseModel):
    id: int
    name: str
    kind: DesignKind
    notes: str | None
    knife_model_id: int | None
    knife_model_name: str | None
    material_id: int | None
    material_name: str | None
    width_mm: float
    height_mm: float
    area_mm2: float
    perimeter_mm: float
    part_count: int
    is_mock: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DesignOut(DesignSummaryOut):
    document: DesignDocument


class OffsetRequest(BaseModel):
    contours: list[Annotated[list[Node], Field(min_length=3, max_length=MAX_NODES_PER_CONTOUR)]] = Field(
        min_length=1, max_length=64
    )
    distance_mm: float = Field(ge=-500, le=500, allow_inf_nan=False)
    join: Literal["round", "mitre", "bevel"] = "round"


class OffsetResult(BaseModel):
    contours: list[list[Node]]
