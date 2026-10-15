import JobMap from "@/components/JobMap";
import jobData from "@/data/young-marina-st.json";
import type { Job } from "@/lib/types";
import { signColor, signLabel } from "@/lib/signs";
import { placeSigns } from "@/lib/distances";

const job = jobData as Job;

// Approximate centre of Young NSW. Phase 3 will find the real intersection.
const YOUNG_CENTRE = { lng: 148.301, lat: -34.3135 };

export default function Home() {
  return (
    <main className="flex h-screen flex-col bg-neutral-950 text-neutral-100 md:flex-row">
      <aside className="order-2 overflow-y-auto p-4 md:order-1 md:w-96">
        <h1 className="text-xl font-bold">{job.location.street}</h1>
        <p className="text-sm text-neutral-400">
          {job.location.suburb} {job.location.state} · TGS {job.tgs.id}
        </p>
        <p className="text-sm text-neutral-400">
          Speed: {job.speed_kmh ?? "?"} km/h · D = {job.d_m ?? "?"} m
        </p>
        {!job.d_m_confirmed && (
          <p className="mt-2 rounded-lg bg-amber-500/15 px-3 py-2 text-xs text-amber-300">
            D is a placeholder. Confirm it on the TGS before setting up.
          </p>
        )}
        {!job.tgs.to_scale && (
          <p className="mt-2 mb-4 text-xs text-neutral-500">
            TGS is not to scale. Positions use the written distances only.
          </p>
        )}

        {job.approaches.map((a) => {
          const placed = placeSigns(a, job.d_m);
          return (
            <section key={a.id} className="mb-4 rounded-xl bg-neutral-900 p-3">
              <h2 className="font-semibold">
                {a.road} · traffic from {a.traffic_from}
              </h2>
              <p className="mb-2 text-xs text-neutral-400">
                Signs on the {a.kerb} kerb, set up furthest first
              </p>
              <ol className="space-y-1">
                {[...placed].reverse().map((s) => (
                  <li key={s.type + s.along_m} className="flex items-center gap-2 text-sm">
                    <span
                      className="h-3 w-3 rounded-sm"
                      style={{ backgroundColor: signColor(s.type) }}
                    />
                    <span>{signLabel(s.type)}</span>
                    <span className="ml-auto text-right text-neutral-400">
                      {s.along_m} m
                      <span className="block text-[10px] text-neutral-500">
                        gap {s.gapLabel}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          );
        })}

        <section className="rounded-xl bg-neutral-900 p-3">
          <h2 className="mb-2 font-semibold">Manual items</h2>
          <ul className="space-y-1 text-sm">
            {job.manual_items.map((m, i) => (
              <li key={i}>
                <span className="font-medium">
                  {signLabel(m.type)}
                  {m.qty ? ` ×${m.qty}` : ""}
                </span>
                <span className="block text-xs text-neutral-400">{m.description}</span>
              </li>
            ))}
          </ul>
        </section>
      </aside>

      <div className="order-1 h-[55vh] md:order-2 md:h-full md:flex-1">
        <JobMap lng={YOUNG_CENTRE.lng} lat={YOUNG_CENTRE.lat} />
      </div>
    </main>
  );
}