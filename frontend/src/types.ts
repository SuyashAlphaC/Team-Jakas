export type TabId = "home" | "monitor" | "analysis" | "incidents" | "remediation" | "timeline" | "grafana";

export type Decomp = {
  domain: string;
  baseline: number;
  context_effect: number;
  observed: number;
  residual: number;
  z_score: number;
  verdict: string;
};

export type Verdict = {
  domain: string;
  verdict: string;
  confidence: number;
  z_score: number;
  reason: string;
};

export type FusionSignal = {
  analyzer: string;
  domain: string;
  verdict: string;
  confidence: number;
  evidence: string[];
};

export type Fusion = {
  summary: string;
  combination: boolean;
  primary_verdict?: string;
  alert_domains?: string[];
  unexplained_domains?: string[];
  ml_sources?: string[];
  signals: FusionSignal[];
};

export type TimelineEntry = {
  id: string;
  time: string;
  type: string;
  body: string;
  severity?: "info" | "alert" | "action";
};

export type Incident = {
  incident_id: string;
  started_at: string;
  status: string;
  confidence: number;
  symptoms: string[];
  suppressed_domains: string[];
  reasoning_summary?: string;
  causal_graph?: {
    nodes: Array<{ node_id: string; node_type: string; label: string; confidence: number }>;
    edges: Array<{ source: string; target: string; relation: string; evidence: string }>;
    reasoning_chain: string[];
  };
  deployment_context?: Array<{
    service: string;
    version: string;
    commit: string;
    message: string;
    config_snapshot: Record<string, string>;
  }>;
  roots: Array<{
    service: string;
    cause_class: string;
    confidence: number;
    file?: string;
    function?: string;
    config_key?: string;
    likely_commit?: string;
    proposed_fix: string;
    mechanism: string;
  }>;
  mttr_detect_ms?: number;
  mttr_rca_ms?: number;
  mttr_mitigate_ms?: number;
};

export type Action = {
  action_id: string;
  grade: string;
  state: string;
  target: string;
  reason: string;
  confidence: number;
  proposed_command: string;
  requires_approval: boolean;
  blast_radius?: string;
  risk_score?: number;
  verification_criteria?: string;
  outcome?: string;
  incident_id?: string;
};

export type Validation = {
  score: number;
  total: number;
  accuracy: number;
  dataset?: string;
};

export type DatasetInfo = {
  row_count: number;
  time_range?: string[];
};

export type ObservabilityState = {
  tab: TabId;
  setTab: (t: TabId) => void;
  timeline: TimelineEntry[];
  decomp: Decomp[];
  verdicts: Verdict[];
  fusion: Fusion | null;
  incidents: Incident[];
  selectedInc: number;
  setSelectedInc: (i: number) => void;
  actions: Action[];
  validation: Validation | null;
  dataset: DatasetInfo | null;
  replayProgress: { index: number; total: number } | null;
  replaySpeed: number;
  setReplaySpeed: (n: number) => void;
  status: string;
  currentTs: string;
  sortedVerdicts: Verdict[];
  activeAlerts: Verdict[];
  keyIncidents: Incident[];
  incident: Incident | undefined;
  uniqueActions: Action[];
  startReplay: () => Promise<void>;
  refresh: () => Promise<void>;
  approve: (id: string) => Promise<void>;
  approveError: string | null;
  approvingId: string | null;
};
