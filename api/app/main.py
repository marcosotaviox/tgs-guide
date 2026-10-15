from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import Job, PlacedJob
from .osm import OsmClient, OsmError
from .placer import PlacementError, place_job

app = FastAPI(title="TGS Guide API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

osm = OsmClient()  # one shared client so results are cached between requests


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/jobs/place", response_model=PlacedJob)
async def place(job: Job):
    try:
        return await place_job(job, osm)
    except PlacementError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except OsmError as e:
        raise HTTPException(status_code=502, detail=str(e))
