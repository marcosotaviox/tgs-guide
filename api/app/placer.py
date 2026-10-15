"""The geo engine: job JSON in, GPS position for every sign out.

Rule: the TGS drawing is NOT to scale. Only the written gaps count.
For each approach we start at the real intersection, follow the real road
in the direction the traffic comes from, and drop each sign at its distance."""
from .geo import (DIRECTION_BEARING, LocalGrid, angle_diff, bearing, dist,
                  offset, path_length, point_along)
from .models import (Approach, ApproachSign, Job, PlacedAnchor, PlacedApproach,
                     PlacedJob, PlacedSign)
from .osm import OsmClient, Way, normalize

KERB_OFFSET_M = 4.5        # sideways distance from road centreline to sign
PROBE_M = 25.0             # how far down each branch we look to judge its direction
MAX_DIRECTION_ERROR = 60.0 # warn if the chosen branch is further off than this
FALLBACK_MAX_ERROR = 80.0  # a differently-named road may be this far off the TGS direction
                           # (TGS says "south", the real road runs south-west)
MAX_GAP_FALLBACK_M = 20.0  # intersection fallback when streets share no node
START_RADIUS_M = 40.0      # road nodes this close to the intersection can start an approach
                           # (divided roads and staggered junctions don't meet at one point)


class PlacementError(Exception):
    pass


# ---------- gaps ----------

def gap_metres(sign: ApproachSign, d_m: float | None) -> float:
    if sign.gap_m is not None:
        return sign.gap_m
    if sign.gap_d is not None:
        if d_m is None:
            raise PlacementError("This TGS uses D but d_m is not set in the job")
        return sign.gap_d * d_m
    raise PlacementError(f"Sign {sign.type} has no gap_d or gap_m")


def gap_label(sign: ApproachSign) -> str:
    if sign.gap_m is not None:
        return f"{sign.gap_m:g} m"
    return "D" if sign.gap_d == 1 else f"{sign.gap_d:g}D"


# ---------- road graph ----------

class RoadGraph:
    """All segments of one named road, joined at shared OSM nodes."""

    def __init__(self, ways: list[Way], grid: LocalGrid):
        self.xy: dict[int, tuple[float, float]] = {}
        self.adj: dict[int, set[int]] = {}
        for w in ways:
            for n, (lng, lat) in zip(w.nodes, w.coords):
                self.xy[n] = grid.to_xy(lng, lat)
                self.adj.setdefault(n, set())
            for a, b in zip(w.nodes, w.nodes[1:]):
                self.adj[a].add(b)
                self.adj[b].add(a)

    def nearest_node(self, p: tuple[float, float]) -> int:
        return min(self.xy, key=lambda n: dist(self.xy[n], p))

    def trace(self, start: int, first: int, max_m: float) -> list[int]:
        """Follow the road from start -> first, always taking the straightest way on."""
        path = [start, first]
        seen = {start, first}
        length = dist(self.xy[start], self.xy[first])
        while length < max_m:
            prev, cur = path[-2], path[-1]
            heading = bearing(self.xy[prev], self.xy[cur])
            options = [n for n in self.adj[cur] if n not in seen]
            if not options:
                break  # dead end
            nxt = min(options, key=lambda n: angle_diff(bearing(self.xy[cur], self.xy[n]), heading))
            path.append(nxt)
            seen.add(nxt)
            length += dist(self.xy[cur], self.xy[nxt])
        return path


# ---------- intersection ----------

async def locate_intersection(osm: OsmClient, streets: list[str], centre: tuple[float, float]) -> tuple[float, float, int | None]:
    """Returns (lat, lng, osm_node_id) where the two streets meet, nearest to centre."""
    if len(streets) != 2:
        raise PlacementError("An intersection anchor needs exactly 2 streets")
    lat0, lng0 = centre
    ways_a = await osm.fetch_ways(streets[0], lat0, lng0)
    ways_b = await osm.fetch_ways(streets[1], lat0, lng0)
    if not ways_a:
        raise PlacementError(f"Could not find {streets[0]} near this suburb")
    if not ways_b:
        raise PlacementError(f"Could not find {streets[1]} near this suburb")

    grid = LocalGrid(lat0, lng0)
    pos_a = {n: c for w in ways_a for n, c in zip(w.nodes, w.coords)}
    pos_b = {n: c for w in ways_b for n, c in zip(w.nodes, w.coords)}
    shared = set(pos_a) & set(pos_b)
    if shared:
        node = min(shared, key=lambda n: dist(grid.to_xy(*pos_a[n]), (0, 0)))
        lng, lat = pos_a[node]
        return lat, lng, node

    # Fallback: streets don't share a node (bad mapping). Use the closest pair of points.
    best = min(
        ((ca, cb) for ca in pos_a.values() for cb in pos_b.values()),
        key=lambda p: dist(grid.to_xy(*p[0]), grid.to_xy(*p[1])),
    )
    gap = dist(grid.to_xy(*best[0]), grid.to_xy(*best[1]))
    if gap > MAX_GAP_FALLBACK_M:
        raise PlacementError(f"{streets[0]} and {streets[1]} don't seem to meet near this suburb")
    return (best[0][1] + best[1][1]) / 2, (best[0][0] + best[1][0]) / 2, None


# ---------- one approach ----------

Branch = tuple[float, float, int, int]  # (score, direction error, start node, first node)


def best_branch(g: RoadGraph, want: float) -> Branch | None:
    """Best way to leave the intersection heading `want` degrees on this road.
    Looks at every road node near the intersection (divided roads and staggered
    junctions don't meet at one point). Score = direction error + a small
    penalty for starting further away."""
    near = [n for n in g.xy if dist(g.xy[n], (0.0, 0.0)) <= START_RADIUS_M]
    best: Branch | None = None
    for n in near:
        d0 = dist(g.xy[n], (0.0, 0.0))
        for nb in g.adj[n]:
            probe = g.trace(n, nb, PROBE_M)
            end = g.xy[probe[-1]]
            if dist(end, (0.0, 0.0)) < d0 + 10.0:
                continue  # heads back towards the intersection or goes nowhere
            err = angle_diff(bearing((0.0, 0.0), end), want)
            cand = (err + 0.5 * d0, err, n, nb)
            if best is None or cand < best:
                best = cand
    return best


async def road_graph(osm: OsmClient, name: str, grid: LocalGrid, anchor: PlacedAnchor) -> RoadGraph | None:
    ways = await osm.fetch_ways(name, anchor.lat, anchor.lng, radius_m=1500)
    return RoadGraph(ways, grid) if ways else None


async def place_approach(osm: OsmClient, job: Job, ap: Approach, anchor: PlacedAnchor) -> PlacedApproach:
    warnings: list[str] = []
    grid = LocalGrid(anchor.lat, anchor.lng)
    want = DIRECTION_BEARING[ap.traffic_from]

    # Distances along the road for each sign
    along, signs_in = 0.0, []
    for s in ap.signs:
        gap = gap_metres(s, job.d_m)
        along += gap
        signs_in.append((s, gap, along))
    needed = along + 10.0

    # 1) The road named on the TGS. Traffic comes FROM this direction,
    #    so we walk outward TOWARDS it.
    g = await road_graph(osm, ap.road, grid, anchor)
    branch = best_branch(g, want) if g else None
    map_road = ap.road

    # 2) Nothing heads that way? Roads often change name at an intersection
    #    (TGS says "Lynch St", the map says "Wombat Street"). Try every road
    #    that touches the intersection and use the one that heads the right way.
    if branch is None or branch[1] > MAX_DIRECTION_ERROR:
        best_other = None
        for name in await osm.road_names_near(anchor.lat, anchor.lng):
            if normalize(name) == normalize(ap.road):
                continue
            og = await road_graph(osm, name, grid, anchor)
            ob = best_branch(og, want) if og else None
            if ob and ob[1] <= FALLBACK_MAX_ERROR and (best_other is None or ob < best_other[1]):
                best_other = (name, ob, og)
        if best_other:
            map_road, branch, g = best_other
            warnings.append(
                f"TGS says {ap.road}, but the road heading {ap.traffic_from} from the intersection "
                f"is {map_road} on the map ({branch[1]:.0f}° off due {ap.traffic_from}). "
                f"Signs placed on {map_road}. Check on site."
            )

    if g is None or branch is None:
        raise PlacementError(f"Could not find any road heading {ap.traffic_from} from the intersection for {ap.road}")
    _, err, start, first = branch
    if map_road == ap.road and err > MAX_DIRECTION_ERROR:
        warnings.append(f"No road heads {ap.traffic_from} from the intersection (closest is {err:.0f}° off). Check the approach direction.")

    nodes = g.trace(start, first, needed)
    # Distances are measured from the intersection centre, so the path starts there.
    path = [(0.0, 0.0)] + [g.xy[n] for n in nodes]
    length = path_length(path)
    if length < along:
        warnings.append(f"{map_road} only runs {length:.0f} m {ap.traffic_from} before it ends or splits; signs past that point are placed at the end.")

    # Approaching traffic drives TOWARDS the anchor. Their left kerb is on the
    # right-hand side when you walk outward from the anchor.
    side = "right" if ap.kerb == "left" else "left"

    placed: list[PlacedSign] = []
    for i, (s, gap, d) in enumerate(signs_in, start=1):
        x, y, road_brg = point_along(path, d)
        sx, sy = offset(x, y, road_brg, KERB_OFFSET_M, side)
        lng, lat = grid.to_lnglat(sx, sy)
        placed.append(PlacedSign(
            seq=i, type=s.type, gap_label=gap_label(s), gap_m=gap, along_m=round(d, 1),
            lat=lat, lng=lng, kerb=ap.kerb, facing_bearing=round(road_brg, 1),
        ))

    return PlacedApproach(
        id=ap.id, road=ap.road, map_road=map_road, traffic_from=ap.traffic_from,
        path=[list(grid.to_lnglat(x, y)) for x, y in path],
        signs=placed, warnings=warnings,
    )


# ---------- whole job ----------

async def place_job(job: Job, osm: OsmClient) -> PlacedJob:
    loc = job.location
    centre = await osm.geocode(" ".join(p for p in [loc.suburb, loc.state, loc.postcode or "", "Australia"] if p))

    anchors: dict[str, PlacedAnchor] = {}
    for a in job.anchors:
        lat, lng, node = await locate_intersection(osm, a.streets, centre)
        anchors[a.id] = PlacedAnchor(id=a.id, streets=a.streets, lat=lat, lng=lng, osm_node=node)

    approaches = []
    for ap in job.approaches:
        if ap.anchor not in anchors:
            raise PlacementError(f"Approach {ap.id} uses unknown anchor {ap.anchor}")
        approaches.append(await place_approach(osm, job, ap, anchors[ap.anchor]))

    warnings = []
    if not job.d_m_confirmed:
        warnings.append("D is not confirmed. Check the TGS before setting up.")
    return PlacedJob(anchors=list(anchors.values()), approaches=approaches, warnings=warnings)
