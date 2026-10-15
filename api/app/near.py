"""Lists every road near an intersection, with the direction it leaves in.

    python -m app.near "Young NSW 2594" "Marina St" "Lynch St"
"""
import asyncio
import sys

from .geo import LocalGrid, bearing, dist
from .osm import OsmClient
from .placer import locate_intersection

RADIUS_M = 80


def compass(b: float) -> str:
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][round(b / 45) % 8]


async def main(place: str, street_a: str, street_b: str) -> None:
    osm = OsmClient()
    centre = await osm.geocode(place + " Australia")
    lat, lng, node = await locate_intersection(osm, [street_a, street_b], centre)
    print(f"Intersection {street_a} x {street_b}: {lat:.6f}, {lng:.6f} (OSM node {node})\n")

    q = (
        f"[out:json][timeout:25];"
        f'way(around:{RADIUS_M},{lat},{lng})["highway"];'
        f"out body geom;"
    )
    data = await osm._overpass(q)
    grid = LocalGrid(lat, lng)

    print(f"{'name':<28}{'type':<14}{'oneway':<8}{'ref':<8}{'start m':>8}  direction")
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        pts = [grid.to_xy(g["lon"], g["lat"]) for g in el.get("geometry", [])]
        if len(pts) < 2:
            continue
        near_end, far_end = (pts[0], pts[-1]) if dist(pts[0], (0, 0)) < dist(pts[-1], (0, 0)) else (pts[-1], pts[0])
        print(
            f"{tags.get('name', '(no name)'):<28}{tags.get('highway', ''):<14}"
            f"{tags.get('oneway', ''):<8}{tags.get('ref', ''):<8}"
            f"{dist(near_end, (0, 0)):>8.0f}  {compass(bearing((0, 0), far_end))}"
        )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
