from typing import Literal

from pydantic import BaseModel, Field

RoleName = Literal["blade", "guard", "bolster", "spacer", "liners", "scales", "liner_left", "liner_right", "scale_left", "scale_right"]


class MockupPart(BaseModel):
    object_id: str = Field(min_length=1, max_length=64)
    role: RoleName
    thickness_mm: float = Field(gt=0, le=60)


class MockupIn(BaseModel):
    parts: list[MockupPart] = Field(min_length=1, max_length=40)
    # 3D printing: the pins a little thinner than their holes, to slide in
    pin_clearance_mm: float = Field(default=0.2, ge=0, le=2)
    # CNC: the cutter that profiles the plates
    tool_diameter_mm: float = Field(default=3.0, gt=0, le=25)
    output: Literal["3mf", "stl", "cnc"] = "3mf"
    layout: Literal["flat", "assembled"] = "flat"


class MockupCandidate(BaseModel):
    object_id: str
    name: str
    width_mm: float
    height_mm: float
    role: RoleName | None
    thickness_mm: float


class MockupMesh(BaseModel):
    name: str
    role: str
    colour: str
    z0: float
    z1: float
    positions: list[float]  # x, y, z per vertex (y flipped: up)
    indices: list[int]


class ToolIssueOut(BaseModel):
    part: str
    kind: Literal["corner", "hole_too_small", "hole_corner"]
    x: float
    y: float
    size_mm: float


class MockupPreview(BaseModel):
    meshes: list[MockupMesh]
    issues: list[ToolIssueOut]
    stack_mm: float
