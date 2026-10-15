export const SIGN_INFO: Record<string, { label: string; color: string }> = {
  ROADWORK_AHEAD:           { label: "Roadwork Ahead",           color: "#ff8a00" },
  WORKER_SYMBOL:            { label: "Worker symbol",            color: "#ff8a00" },
  PREPARE_TO_STOP:          { label: "Prepare to Stop",          color: "#dc2626" },
  TRAFFIC_CONTROLLER_AHEAD: { label: "Traffic Controller Ahead", color: "#ff8a00" },
  DETOUR:                   { label: "Detour",                   color: "#facc15" },
  ROAD_CLOSED_DETOUR:       { label: "Road Closed / Detour",     color: "#facc15" },
  NO_EXIT:                  { label: "No Exit",                  color: "#ffffff" },
  FOOTPATH_CLOSED:          { label: "Footpath Closed",          color: "#facc15" },
  PEDESTRIANS_ARROW:        { label: "Pedestrians →",            color: "#facc15" },
  TOILETS_ACCESSIBLE:       { label: "Toilets Are Accessible",   color: "#ffffff" },
  BARRELS_ATF_FENCING:      { label: "Barrels / ATF fencing",    color: "#f97316" },
};

export function signLabel(type: string) {
  return SIGN_INFO[type]?.label ?? type;
}

export function signColor(type: string) {
  return SIGN_INFO[type]?.color ?? "#9ca3af";
}