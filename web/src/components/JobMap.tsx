"use client";

import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoJob } from "@/lib/api";
import { signColor, signLabel } from "@/lib/signs";

const SATELLITE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    sat: {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      // Regional areas often have no zoom-19 imagery (Esri sends "Map data not yet
      // available" tiles). Stop at 18 and let MapLibre stretch it when zooming in.
      maxzoom: 18,
      attribution: "Imagery © Esri",
    },
    labels: {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      maxzoom: 18,
    },
  },
  layers: [
    { id: "sat", type: "raster", source: "sat" },
    { id: "labels", type: "raster", source: "labels" },
  ],
};

// One colour per approach so you can tell the legs apart on the map
const APPROACH_COLORS = ["#38bdf8", "#a78bfa", "#34d399", "#f472b6", "#facc15"];

interface Props {
  geo: GeoJob | null;
  fallbackCenter: { lng: number; lat: number };
}

function signMarker(seq: number, type: string, ring: string) {
  const el = document.createElement("div");
  el.style.cssText = `width:26px;height:26px;border-radius:50%;background:${signColor(type)};
    border:3px solid ${ring};color:#111;font:800 12px/20px system-ui;text-align:center;
    box-shadow:0 2px 6px rgba(0,0,0,.6);cursor:pointer`;
  el.textContent = String(seq);
  el.title = signLabel(type);
  return el;
}

export default function JobMap({ geo, fallbackCenter }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Load MapLibre's background worker from our own /public folder.
    // (The built-in inline worker fails in some setups: "Worker failed to load".)
    maplibregl.setWorkerUrl("/maplibre-gl-csp-worker.js");

    const anchor = geo?.anchors[0];
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: SATELLITE_STYLE,
      center: anchor ? [anchor.lng, anchor.lat] : [fallbackCenter.lng, fallbackCenter.lat],
      zoom: anchor ? 18 : 15,
      maxZoom: 21,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      if (!geo) return;
      const bounds = new maplibregl.LngLatBounds();

      geo.approaches.forEach((ap, i) => {
        const color = APPROACH_COLORS[i % APPROACH_COLORS.length];

        // Road centreline the engine followed
        map.addSource(`path-${ap.id}`, {
          type: "geojson",
          data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: ap.path } },
        });
        map.addLayer({
          id: `path-${ap.id}`,
          type: "line",
          source: `path-${ap.id}`,
          paint: { "line-color": color, "line-width": 4, "line-opacity": 0.8 },
        });
        ap.path.forEach((p) => bounds.extend(p));

        // One marker per sign
        ap.signs.forEach((s) => {
          const popup = new maplibregl.Popup({ offset: 16 }).setHTML(
            `<div style="color:#111;font:13px system-ui">
               <b>${signLabel(s.type)}</b><br/>
               ${ap.map_road}, traffic from ${ap.traffic_from}<br/>
               ${s.along_m} m from intersection (gap ${s.gap_label})<br/>
               ${s.kerb} kerb · ${s.lat.toFixed(6)}, ${s.lng.toFixed(6)}
             </div>`,
          );
          new maplibregl.Marker({ element: signMarker(s.seq, s.type, color) })
            .setLngLat([s.lng, s.lat])
            .setPopup(popup)
            .addTo(map);
          bounds.extend([s.lng, s.lat]);
        });
      });

      geo.anchors.forEach((a) => {
        new maplibregl.Marker({ color: "#ef4444" })
          .setLngLat([a.lng, a.lat])
          .setPopup(new maplibregl.Popup().setText(a.streets.join(" × ")))
          .addTo(map);
      });

      if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 60, maxZoom: 19, duration: 0 });
    });

    return () => map.remove();
  }, [geo, fallbackCenter.lng, fallbackCenter.lat]);

  return <div ref={containerRef} className="h-full w-full" />;
}
