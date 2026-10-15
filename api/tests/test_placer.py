"""Tests run without internet: a fake OSM gives a simple + shaped intersection.

           Lynch St (north)
                |
  Marina St ----+---- Marina St (east)
                |
           Lynch St (south)
"""
import json
import math
from pathlib import Path

import pytest

from app.geo import LocalGrid
from app.models import Job
from app.osm import Way, normalize
from app.placer import PlacementError, place_job

CENTRE = (-34.3130, 148.3000)  # fake intersection (lat, lng)
GRID = LocalGrid(*CENTRE)


def line(node_ids, xy_points, name, way_id):
    coords = [GRID.to_lnglat(x, y) for x, y in xy_points]
    return Way(id=way_id, name=name, nodes=node_ids, coords=coords, tags={"highway": "residential"})


class FakeOsm:
    def __init__(self, lynch_north_len=300, divided_south=False, south_is_wombat=False, wombat_bearing=180):
        # Lynch Street: north-south through node 100 at (0,0). Two separate OSM ways.
        north = [(0, y) for y in range(0, lynch_north_len, 50)] + [(0, lynch_north_len)]
        south = [(0, -y) for y in range(0, 301, 50)]
        self.ways = {
            "lynch street": [
                line([100] + list(range(200, 200 + len(north) - 1)), north, "Lynch Street", 1),
                line([100] + list(range(300, 300 + len(south) - 1)), south, "Lynch Street", 2),
            ],
            "marina street": [
                line([100, 401, 402, 403, 404, 405, 406], [(x, 0) for x in range(0, 301, 50)], "Marina Street", 3),
                line([100, 501, 502], [(-x, 0) for x in range(0, 101, 50)], "Marina Street", 4),
            ],
        }

        if divided_south:
            # Real-world case: south of the junction Lynch St is a divided road.
            # Its carriageways start 12 m away and never touch node 100.
            self.ways["lynch street"] = [
                self.ways["lynch street"][0],
                line([600, 601, 602, 603], [(4, -12), (4, -100), (4, -200), (4, -300)], "Lynch Street", 5),
                line([700, 701, 702, 703], [(-4, -300), (-4, -200), (-4, -100), (-4, -12)], "Lynch Street", 6),
            ]

        if south_is_wombat:
            # Real Young data: south of Marina St the road is called Wombat Street.
            self.ways["lynch street"].pop(1)
            r = math.radians(wombat_bearing)
            pts = [(math.sin(r) * d, math.cos(r) * d) for d in range(0, 301, 50)]
            self.ways["wombat street"] = [line([100, 801, 802, 803, 804, 805, 806], pts, "Wombat Street", 8)]

    async def road_names_near(self, lat, lng, radius_m=60):
        return sorted({w.name for ways in self.ways.values() for w in ways})

    async def geocode(self, query):
        return (CENTRE[0] + 0.002, CENTRE[1] - 0.002)  # suburb centre, a bit off the intersection

    async def fetch_ways(self, street, lat, lng, radius_m=3000):
        return self.ways.get(normalize(street), [])


def young_job(**overrides) -> Job:
    path = Path(__file__).resolve().parents[2] / "samples" / "young-marina-st.json"
    data = json.loads(path.read_text())
    data.update(overrides)
    return Job.model_validate(data)


def xy(sign):
    return GRID.to_xy(sign.lng, sign.lat)


@pytest.mark.asyncio
async def test_signs_follow_written_distances_and_left_kerb():
    result = await place_job(young_job(), FakeOsm())
    by_id = {a.id: a for a in result.approaches}
    assert result.anchors[0].osm_node == 100

    # Lynch St north: traffic heads south, so their left kerb is the EAST side (+x)
    north = by_id["lynch_north"]
    assert [s.along_m for s in north.signs] == [15, 30, 45, 60]
    for s in north.signs:
        x, y = xy(s)
        assert y == pytest.approx(s.along_m, abs=0.5)
        assert x == pytest.approx(4.5, abs=0.5)

    # Marina St east: traffic heads west, left kerb is the SOUTH side (-y)
    for s in by_id["marina_east"].signs:
        x, y = xy(s)
        assert x == pytest.approx(s.along_m, abs=0.5)
        assert y == pytest.approx(-4.5, abs=0.5)

    # Lynch St south: traffic heads north, left kerb is the WEST side (-x)
    for s in by_id["lynch_south"].signs:
        x, y = xy(s)
        assert y == pytest.approx(-s.along_m, abs=0.5)
        assert x == pytest.approx(-4.5, abs=0.5)

    assert not north.warnings


@pytest.mark.asyncio
async def test_mixed_gaps_add_up():
    job = young_job()
    job.approaches[0].signs[2].gap_d = None
    job.approaches[0].signs[2].gap_m = 30  # D, D, 30 m, D
    result = await place_job(job, FakeOsm())
    signs = result.approaches[0].signs
    assert [s.along_m for s in signs] == [15, 30, 60, 75]
    assert signs[2].gap_label == "30 m"
    assert signs[0].gap_label == "D"


@pytest.mark.asyncio
async def test_missing_d_is_an_error():
    with pytest.raises(PlacementError, match="d_m is not set"):
        await place_job(young_job(d_m=None), FakeOsm())


@pytest.mark.asyncio
async def test_short_road_gives_warning():
    result = await place_job(young_job(), FakeOsm(lynch_north_len=40))
    north = next(a for a in result.approaches if a.id == "lynch_north")
    assert any("only runs" in w for w in north.warnings)


def test_normalize_matches_tgs_and_osm_names():
    assert normalize("Lynch St") == normalize("Lynch Street") == "lynch street"
    assert normalize("Marina St.") == "marina street"


@pytest.mark.asyncio
async def test_divided_road_south_of_junction():
    result = await place_job(young_job(), FakeOsm(divided_south=True))
    south = next(a for a in result.approaches if a.id == "lynch_south")
    assert not south.warnings, south.warnings
    for s in south.signs:
        x, y = xy(s)
        assert y < -10            # really south of the junction
        assert x < 0              # west (left kerb for northbound traffic)
        assert abs(y) == pytest.approx(s.along_m, abs=3)


@pytest.mark.asyncio
async def test_road_changes_name_at_intersection():
    result = await place_job(young_job(), FakeOsm(south_is_wombat=True))
    south = next(a for a in result.approaches if a.id == "lynch_south")
    assert south.map_road == "Wombat Street"
    assert any("Wombat Street on the map" in w for w in south.warnings)
    for s in south.signs:
        x, y = xy(s)
        assert y == pytest.approx(-s.along_m, abs=0.5)   # really south
        assert x == pytest.approx(-4.5, abs=0.5)         # west kerb
    north = next(a for a in result.approaches if a.id == "lynch_north")
    assert north.map_road == "Lynch St" and not north.warnings


@pytest.mark.asyncio
async def test_renamed_road_running_south_west():
    # TGS says "traffic from south" but Wombat St actually runs 240° (WSW)
    result = await place_job(young_job(), FakeOsm(south_is_wombat=True, wombat_bearing=240))
    south = next(a for a in result.approaches if a.id == "lynch_south")
    assert south.map_road == "Wombat Street"
    assert any("60° off" in w for w in south.warnings)
    for s in south.signs:
        x, y = xy(s)
        assert y < 0 and x < 0   # south-west of the junction, not north
