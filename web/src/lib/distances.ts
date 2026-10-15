import type { Approach, ApproachSign, PlacedSign } from "./types";

function gapToMetres(sign: ApproachSign, dM: number | null): number {
  if (sign.gap_m != null) return sign.gap_m;
  if (sign.gap_d != null) {
    if (dM == null) throw new Error("This TGS uses D but d_m is not set in the job");
    return sign.gap_d * dM;
  }
  throw new Error(`Sign ${sign.type} has no gap_d or gap_m`);
}

function gapLabel(sign: ApproachSign): string {
  if (sign.gap_m != null) return `${sign.gap_m} m`;
  return sign.gap_d === 1 ? "D" : `${sign.gap_d}D`;
}

/** Adds up the written gaps (anchor outward) to get each sign's distance along the road. */
export function placeSigns(approach: Approach, dM: number | null): PlacedSign[] {
  let along = 0;
  return approach.signs.map((s) => {
    const gap = gapToMetres(s, dM);
    along += gap;
    return { type: s.type, gap_m: gap, gapLabel: gapLabel(s), along_m: along };
  });
}