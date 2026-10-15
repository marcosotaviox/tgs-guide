"""Small geometry helpers. Works in a flat local metre grid around a centre point,
which is accurate to well under 1 m over the few hundred metres a TGS covers."""
import math

EARTH_R = 6371008.8
DIRECTION_BEARING = {"north": 0.0, "east": 90.0, "south": 180.0, "west": 270.0}


class LocalGrid:
    """Converts lng/lat <-> x/y metres around (lat0, lng0). x = east, y = north."""

    def __init__(self, lat0: float, lng0: float):
        self.lat0, self.lng0 = lat0, lng0
        self.ky = math.pi * EARTH_R / 180.0
        self.kx = math.cos(math.radians(lat0)) * self.ky

    def to_xy(self, lng: float, lat: float) -> tuple[float, float]:
        return ((lng - self.lng0) * self.kx, (lat - self.lat0) * self.ky)

    def to_lnglat(self, x: float, y: float) -> tuple[float, float]:
        return (self.lng0 + x / self.kx, self.lat0 + y / self.ky)


def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Compass bearing from a to b (x/y metres). 0 = north, 90 = east."""
    return (math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) + 360.0) % 360.0


def angle_diff(a: float, b: float) -> float:
    """Smallest difference between two bearings, 0..180."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def path_length(path: list[tuple[float, float]]) -> float:
    return sum(dist(path[i - 1], path[i]) for i in range(1, len(path)))


def point_along(path: list[tuple[float, float]], d: float) -> tuple[float, float, float]:
    """Point d metres along the path, plus the road bearing there.
    Clamps to the end of the path if d is longer than the path."""
    run = 0.0
    for i in range(1, len(path)):
        seg = dist(path[i - 1], path[i])
        if seg == 0:
            continue
        if run + seg >= d:
            t = (d - run) / seg
            a, b = path[i - 1], path[i]
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, bearing(a, b))
        run += seg
    a, b = path[-2], path[-1]
    return (b[0], b[1], bearing(a, b))


def offset(x: float, y: float, brg: float, metres: float, side: str) -> tuple[float, float]:
    """Move sideways from a point on the road. side='right' is to the right of brg."""
    turn = 90.0 if side == "right" else -90.0
    r = math.radians(brg + turn)
    return (x + math.sin(r) * metres, y + math.cos(r) * metres)
