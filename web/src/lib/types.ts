export type Direction = "north" | "south" | "east" | "west";

export type SignType =
  | "ROADWORK_AHEAD"
  | "WORKER_SYMBOL"
  | "PREPARE_TO_STOP"
  | "TRAFFIC_CONTROLLER_AHEAD";

export interface ApproachSign {
  type: SignType;
  at_d: number;
}

export interface Approach {
  id: string;
  road: string;
  traffic_from: Direction;
  anchor: string;
  kerb: "left" | "right";
  signs: ApproachSign[];
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
  anchors: Anchor[];
  approaches: Approach[];
  controllers: Controller[];
  manual_items: ManualItem[];
  notes: string[];
}