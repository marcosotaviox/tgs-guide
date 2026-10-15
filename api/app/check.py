"""Quick OSM check without the web app:

    python -m app.check "Young NSW 2594" "Marina St" "Lynch St"
"""
import asyncio
import sys

from .osm import OsmClient


async def main(place: str, streets: list[str]) -> None:
    osm = OsmClient()
    lat, lng = await osm.geocode(place + " Australia")
    print(f"{place}: {lat:.5f}, {lng:.5f}")
    for street in streets:
        ways = await osm.fetch_ways(street, lat, lng)
        names = sorted({w.name for w in ways})
        print(f"{street}: {len(ways)} OSM segments {names}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2:]))
