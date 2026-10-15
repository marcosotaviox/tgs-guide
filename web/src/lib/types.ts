export type Direction = "north" | "south" | "east" | "west";

export type SignType =
  | "ROADWORK_AHEAD"
  | "WORKER_SYMBOL"
  | "PREPARE_TO_STOP"
  | "TRAFFIC_CONTROLLER_AHEAD";

/** One sign, with the gap from the previous sign (or from the anchor for the first one).
 *  Exactly one of gap_d / gap_m is set, copied exactly as the TGS writes it. */
export interface ApproachSign {
  type: SignType;
  gap_d?: number; // gap written as multiples of D ("D" = 1, "2D" = 2)
  gap_m?: number; // gap written in metres ("30 m")
}

export interface Approach {
  id: string;
  road: string;
  traffic_from: Direction;
  anchor: string;
  kerb: "left" | "right";
  signs: ApproachSign[]; // ordered from the anchor outward
}

export interface Anchor {
  id: string;
  type: "intersection";
  streets: string[];
}

export interface Controller {
  id: string;
  anchor: string;
  position: string;
  equipment: string;
  note?: string;
}

export interface ManualItem {
  type: string;
  placement: "manual";
  description: string;
  qty?: number;
}

export interface Job {
  schema_version: number;
  tgs: {
    id: string;
    designer: string;
    client: string;
    council: string;
    design_date: string;
    scope: string;
    duration: string;
    source_file: string;
    to_scale: boolean;
  };
  location: {
    street: string;
    suburb: string;
    state: string;
    postcode: string;
    cross_streets: string[];
  };
  speed_kmh: number | null;
  d_m: number | null;
  d_m_confirmed: boolean;
  anchors: Anchor[];
  approaches: Approach[];
  controllers: Controller[];
  manual_items: ManualItem[];
  notes: string[];
}

/** A sign after the distances have been added up. */
export interface PlacedSign {
  type: SignType;
  gap_m: number;     // gap from the previous sign, in metres
  gapLabel: string;  // what the TGS says, e.g. "D" or "30 m"
  along_m: number;   // total distance from the anchor along the road
}