"""Talks to OpenStreetMap: Nominatim (suburb -> point) and Overpass (streets near a point)."""
import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

USER_AGENT = "tgs-guide/0.1 (traffic sign setup helper)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
ATTEMPTS_PER_SERVER = 2
RETRY_WAIT_S = 2.0

# Answers from OSM are saved here so we don't ask the free servers again.
# Roads rarely change, so a week is plenty. Delete the folder to force fresh data.
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "osm"
CACHE_TTL_S = 7 * 24 * 3600

ABBR = {
    "st": "street", "rd": "road", "ave": "avenue", "av": "avenue", "pde": "parade",
    "cres": "crescent", "cr": "crescent", "dr": "drive", "pl": "place", "hwy": "highway",
    "ct": "court", "cl": "close", "ln": "lane", "tce": "terrace", "blvd": "boulevard",
    "bvd": "boulevard", "cct": "circuit", "gr": "grove", "esp": "esplanade", "wy": "way",
    "sq": "square", "pwy": "parkway", "mt": "mount",
}
SUFFIXES = set(ABBR.values())
# Roads cars drive on (no footpaths, cycleways, steps...)
VEHICLE_HIGHWAYS = (
    "motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|"
    "motorway_link|trunk_link|primary_link|secondary_link|tertiary_link"
)


class OsmError(Exception):
    pass


def normalize(name: str) -> str:
    """'Lynch St.' -> 'lynch street'. Used to compare TGS names with OSM names."""
    words = re.sub(r"[.,'’]", " ", name.lower()).split()
    return " ".join(ABBR.get(w, w) for w in words)


def core_name(name: str) -> str:
    """'Lynch Street' -> 'lynch' (drops the suffix so the Overpass search is broad)."""
    words = normalize(name).split()
    if len(words) > 1 and words[-1] in SUFFIXES:
        words = words[:-1]
    return " ".join(words)


@dataclass
class Way:
    id: int
    name: str
    nodes: list[int]
    coords: list[tuple[float, float]]  # (lng, lat), same order as nodes
    tags: dict = field(default_factory=dict)


class OsmClient:
    def __init__(
        self,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
        cache_dir: Path | None = CACHE_DIR,
    ):
        self.timeout = timeout
        self.transport = transport  # tests pass a fake transport here
        self.cache_dir = cache_dir  # None = no disk cache
        self._cache: dict[str, object] = {}

    # ---------- disk cache ----------

    def _disk_path(self, kind: str, text: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"{kind}-{hashlib.sha1(text.encode()).hexdigest()[:16]}.json"

    def _disk_get(self, kind: str, text: str):
        path = self._disk_path(kind, text)
        if path is None or not path.exists():
            return None
        if time.time() - path.stat().st_mtime > CACHE_TTL_S:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # broken cache file: just ask OSM again

    def _disk_put(self, kind: str, text: str, data) -> None:
        path = self._disk_path(kind, text)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            transport=self.transport,
        )

    async def geocode(self, query: str) -> tuple[float, float]:
        """Returns (lat, lng) for a place like 'Young NSW 2594 Australia'."""
        key = "geo:" + query
        if key in self._cache:
            return self._cache[key]  # type: ignore[return-value]
        data = self._disk_get("geocode", query)
        if data is None:
            async with self._client() as c:
                r = await c.get(NOMINATIM_URL, params={"q": query, "format": "json", "limit": 1, "countrycodes": "au"})
                r.raise_for_status()
                data = r.json()
            if data:
                self._disk_put("geocode", query, data)
        if not data:
            raise OsmError(f"Could not find '{query}' on the map")
        result = (float(data[0]["lat"]), float(data[0]["lon"]))
        self._cache[key] = result
        return result

    async def _overpass(self, query: str) -> dict:
        """Tries each mirror, with a retry, until one answers. Free servers get busy.
        Successful answers are saved to disk and reused."""
        cached = self._disk_get("overpass", query)
        if cached is not None:
            return cached
        errors: list[str] = []
        async with self._client() as c:
            for url in OVERPASS_URLS:
                host = url.split("/")[2]
                for attempt in range(1, ATTEMPTS_PER_SERVER + 1):
                    try:
                        r = await c.post(url, data={"data": query})
                        if r.status_code == 200:
                            data = r.json()
                            self._disk_put("overpass", query, data)
                            return data
                        errors.append(f"{host} #{attempt}: HTTP {r.status_code}")
                        if r.status_code == 400:
                            raise OsmError(f"Overpass rejected the query (bad syntax): {r.text[:300]}")
                    except OsmError:
                        raise
                    except Exception as e:  # timeout, connection reset, bad JSON...
                        errors.append(f"{host} #{attempt}: {type(e).__name__} {e}".strip())
                    if attempt < ATTEMPTS_PER_SERVER:
                        await asyncio.sleep(RETRY_WAIT_S * attempt)
        raise OsmError("All Overpass servers failed: " + " | ".join(errors))

    async def fetch_ways(self, street: str, lat: float, lng: float, radius_m: int = 3000) -> list[Way]:
        """All road segments named like `street` within radius_m of the point."""
        key = f"ways:{normalize(street)}:{lat:.4f}:{lng:.4f}:{radius_m}"
        if key in self._cache:
            return self._cache[key]  # type: ignore[return-value]
        pattern = "^" + re.escape(core_name(street)) + "( |$)"
        q = (
            f"[out:json][timeout:25];"
            f'way(around:{radius_m},{lat},{lng})["highway"]["name"~"{pattern}",i];'
            f"out body geom;"
        )
        data = await self._overpass(q)
        target = normalize(street)
        ways = [
            Way(
                id=el["id"],
                name=el["tags"]["name"],
                nodes=el["nodes"],
                coords=[(g["lon"], g["lat"]) for g in el["geometry"]],
                tags=el.get("tags", {}),
            )
            for el in data.get("elements", [])
            if el.get("type") == "way" and "geometry" in el and normalize(el["tags"].get("name", "")) == target
        ]
        self._cache[key] = ways
        return ways

    async def road_names_near(self, lat: float, lng: float, radius_m: int = 60) -> list[str]:
        """Names of all drivable roads within radius_m of a point (e.g. an intersection)."""
        key = f"near:{lat:.5f}:{lng:.5f}:{radius_m}"
        if key in self._cache:
            return self._cache[key]  # type: ignore[return-value]
        q = (
            f"[out:json][timeout:25];"
            f'way(around:{radius_m},{lat},{lng})["highway"~"^({VEHICLE_HIGHWAYS})$"]["name"];'
            f"out tags;"
        )
        data = await self._overpass(q)
        names = sorted({el["tags"]["name"] for el in data.get("elements", []) if "name" in el.get("tags", {})})
        self._cache[key] = names
        return names

