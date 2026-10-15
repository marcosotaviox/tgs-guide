import { Suspense } from "react";
import JobMap from "@/components/JobMap";
import jobData from "@/data/young-marina-st.json";
import type { Job } from "@/lib/types";
import { signColor, signLabel } from "@/lib/signs";
import { placeJob, type GeoJob } from "@/lib/api";

const job = jobData as Job;
const YOUNG_CENTRE = { lng: 148.301, lat: -34.3135 };

export default function Home() {
  return (
    <Suspense
      fallback={
        <main className="flex h-screen items-center justify-center bg-neutral-950 text-neutral-400">
          Placing signs on the map…
        </main>
      }
    >
      <JobView />
    </Suspense>
  );
}

// Async part: asks the geo engine for GPS points. Lives inside <Suspense> (Next 16 rule).
async function JobView() {
  let geo: GeoJob | null = null;
  let error: string | null = null;
  try {
    geo = await placeJob(job);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  const warnings = geo ? [...geo.warnings, ...geo.approaches.flatMap((a) => a.warnings)] : [];

  return (
    <main className="flex h-screen flex-col bg-neutral-950 text-neutral-100 md:flex-row">
      <aside className="order-2 overflow-y-auto p-4 md:order-1 md:w-96">
        <h1 className="text-xl font-bold">{job.location.street}</h1>
        <p className="text-sm text-neutral-400">
          {job.location.suburb} {job.location.state} · TGS {job.tgs.id}
        </p>
        <p className="mb-3 text-sm text-neutral-400">
          Speed: {job.speed_kmh ?? "?"} km/h · D = {job.d_m ?? "?"} m
        </p>

        {error && (
          <p className="mb-3 rounded-lg bg-red-500/15 px-3 py-2 text-sm text-red-300">
            Geo engine error: {error}
            <span className="block text-xs text-red-400/80">
              {error === "fetch failed"
                ? "Can't reach the API. Is it running on port 8000?"
                : error.includes("Overpass")
                  ? "The free map servers are busy. Wait a minute and refresh."
                  : "Check the job JSON and the API terminal for details."}
            </span>
          </p>
        )}
        {warnings.map((w, i) => (
          <p key={i} className="mb-2 rounded-lg bg-amber-500/15 px-3 py-2 text-xs text-amber-300">
            {w}
          </p>
        ))}

        {geo?.approaches.map((a) => (
          <section key={a.id} className="mb-4 rounded-xl bg-neutral-900 p-3">
            <h2 className="font-semibold">
              {a.road} · traffic from {a.traffic_from}
            </h2>
            {a.map_road !== a.road && (
              <p className="text-xs font-medium text-amber-300">On the map: {a.map_road}</p>
            )}
            <p className="mb-2 text-xs text-neutral-400">Set up furthest first</p>
            <ol className="space-y-1">
              {[...a.signs].reverse().map((s) => (
                <li key={s.seq} className="flex items-center gap-2 text-sm">
                  <span
                    className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-black"
                    style={{ backgroundColor: signColor(s.type) }}
                  >
                    {s.seq}
                  </span>
                  <span>{signLabel(s.type)}</span>
                  <span className="ml-auto text-right text-neutral-400">
                    {s.along_m} m
                    <span className="block text-[10px] text-neutral-500">
                      gap {s.gap_label} · {s.kerb} kerb
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </aside>

      <div className="order-1 h-[55vh] md:order-2 md:h-full md:flex-1">
        <JobMap geo={geo} fallbackCenter={YOUNG_CENTRE} />
      </div>
    </main>
  );
}
