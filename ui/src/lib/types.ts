export interface Weather {
  summary: string;
  condition: string;
  temp_f: number;
  precip_chance: number;
  recommended_format: "indoor" | "outdoor";
}

export interface Issue {
  id: string;
  title: string;
  area: string;
  summary: string;
  source_links: string[];
  salience: number;
}

export interface EventRecommendation {
  issue: Issue;
  area: string;
  proposed_date: string;
  weather: Weather;
  format: "indoor" | "outdoor";
  venue_suggestion: string;
  target_voters: string;
  talking_points: string[];
  rationale: string;
  draft_outreach?: string;
}

export interface Slate {
  region: string;
  horizon: string;
  ranked_events: EventRecommendation[];
}

export interface ProgressEvent {
  run_id: string;
  seq: number;
  agent: string;
  status: "started" | "tool_call" | "done" | "failed";
  detail: string;
}

export interface RunStatus {
  status: "pending" | "done" | "failed";
  slate?: Slate;
}
