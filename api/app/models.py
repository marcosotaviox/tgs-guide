"""Data shapes. These mirror web/src/lib/types.ts — keep both in sync."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

Direction = Literal["north", "south", "east", "west"]


class ApproachSign(BaseModel):
    type: str
    gap_d: Optional[float] = None  # gap written as multiples of D
    gap_m: Optional[float] = None  # gap written in metres


class Approach(BaseModel):
    id: str
    road: str
    traffic_from: Direction
    anchor: str
    kerb: Literal["left", "right"]
    signs: list[ApproachSign]  # ordered from the anchor outward


class Anchor(BaseModel):
    id: str
    type: Literal["intersection"]
    streets: list[str]


class Location(BaseModel):
    model_config = ConfigDict(extra="allow")
    street: str
    suburb: str
    state: str
    postcode: Optional[str] = None
    cross_streets: list[str] = []


class Job(BaseModel):
    """The job JSON. Extra fields (tgs, controllers, notes...) are accepted and ignored here."""
    model_config = ConfigDict(extra="allow")
    schema_version: int
    location: Location
    speed_kmh: Optional[float] = None
    d_m: Optional[float] = None
    d_m_confirmed: bool = False
    anchors: list[Anchor]
    approaches: list[Approach]


# ---------- output ----------

class PlacedSign(BaseModel):
    seq: int                 # 1 = nearest the anchor
    type: str
    gap_label: str           # what the TGS says: "D", "2D", "30 m"
    gap_m: float
    along_m: float           # distance from the anchor along the road
    lat: float
    lng: float
    kerb: Literal["left", "right"]
    facing_bearing: float    # direction the sign face points (towards oncoming traffic)


class PlacedApproach(BaseModel):
    id: str
    road: str                # name as written on the TGS
    map_road: str            # name of the road actually used on the map (may differ!)
    traffic_from: Direction
    path: list[list[float]]  # [[lng, lat], ...] road centreline from the anchor outward
    signs: list[PlacedSign]
    warnings: list[str] = []


class PlacedAnchor(BaseModel):
    id: str
    streets: list[str]
    lat: float
    lng: float
    osm_node: Optional[int] = None


class PlacedJob(BaseModel):
    anchors: list[PlacedAnchor]
    approaches: list[PlacedApproach]
    warnings: list[str] = []
