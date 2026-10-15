// Talks to the FastAPI geo engine. Shapes mirror api/app/models.py — keep both in sync.
import type { Direction, Job, SignType } from "./types";

export interface GeoSign {
  seq: number;
  type: SignType;
  gap_label: string;
  gap_m: number;
  along_m: number;
  lat: number;
  lng: number;
  kerb: "left" | "right";
  facing_bearing: number;
}

export interface GeoApproach {
  id: string;
  road: string; // as written on the TGS
  map_road: string; // road actually used on the map (can differ, e.g. Lynch St -> Wombat Street)
  traffic_from: Direction;
  path: [number, number][]; // [lng, lat]
  signs: GeoSign[];
  warnings: string[];
}

export interface GeoAnchor {
  id: string;
  streets: string[];
  lat: number;
  lng: number;
  osm_node: number | null;
}

export interface GeoJob {
  anchors: GeoAnchor[];
  approaches: GeoApproach[];
  warnings: string[];
}

// 127.0.0.1 instead of "localhost" avoids a common Windows IPv6 mix-up.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export async function placeJob(job: Job): Promise<GeoJob> {
  const res = await fetch(`${API_URL}/jobs/place`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(job),
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}
