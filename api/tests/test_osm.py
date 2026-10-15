"""Checks the retry logic with a fake network: first servers fail, a later one answers."""
import httpx
import pytest

from app import osm as osm_mod
from app.osm import OsmClient, OsmError


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(osm_mod, "RETRY_WAIT_S", 0)


def fake_transport(handler):
    return httpx.MockTransport(handler)


GOOD = {"elements": [{"type": "way", "id": 1, "nodes": [1, 2], "tags": {"name": "Lynch Street", "highway": "residential"},
                      "geometry": [{"lat": -34.31, "lon": 148.30}, {"lat": -34.309, "lon": 148.30}]}]}


@pytest.mark.asyncio
async def test_falls_back_to_next_server():
    calls = []

    def handler(req):
        calls.append(req.url.host)
        if req.url.host == "overpass-api.de":
            return httpx.Response(504)
        return httpx.Response(200, json=GOOD)

    ways = await OsmClient(transport=fake_transport(handler), cache_dir=None).fetch_ways("Lynch St", -34.31, 148.30)
    assert len(ways) == 1
    assert calls[:2] == ["overpass-api.de", "overpass-api.de"]  # retried once before moving on


@pytest.mark.asyncio
async def test_reports_every_failure():
    def handler(req):
        return httpx.Response(500)

    with pytest.raises(OsmError) as e:
        await OsmClient(transport=fake_transport(handler), cache_dir=None).fetch_ways("Lynch St", -34.31, 148.30)
    msg = str(e.value)
    assert "overpass-api.de #1: HTTP 500" in msg and "overpass.kumi.systems #2: HTTP 500" in msg


@pytest.mark.asyncio
async def test_disk_cache_survives_restart(tmp_path):
    calls = []

    def handler(req):
        calls.append(req.url.host)
        return httpx.Response(200, json=GOOD)

    first = OsmClient(transport=fake_transport(handler), cache_dir=tmp_path)
    await first.fetch_ways("Lynch St", -34.31, 148.30)
    assert len(calls) == 1

    # A brand-new client (like after the API restarts) with every server down
    def down(req):
        return httpx.Response(503)

    second = OsmClient(transport=fake_transport(down), cache_dir=tmp_path)
    ways = await second.fetch_ways("Lynch St", -34.31, 148.30)
    assert len(ways) == 1  # came from the disk cache
