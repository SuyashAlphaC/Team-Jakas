export const API = import.meta.env.VITE_API_URL || "";

export const GRAFANA_BASE =
  import.meta.env.VITE_GRAFANA_URL?.replace(/\/d\/.*$/, "") || "http://localhost:3001";

export const GRAFANA_DASHBOARD_UID = "domain-cpu-telemetry";

export const GRAFANA_URL = `${GRAFANA_BASE}/d/${GRAFANA_DASHBOARD_UID}`;

export const GRAFANA_EMBED_URL =
  `${GRAFANA_URL}?orgId=1&kiosk=tv&theme=dark&refresh=5s`;

export const GRAFANA_AVAILABLE =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    Boolean(import.meta.env.VITE_GRAFANA_URL));

export const ALERT_VERDICTS = new Set(["attack", "internal_fault", "unexplained"]);

export function verdictRank(v: string) {
  if (v === "attack") return 0;
  if (v === "internal_fault") return 1;
  if (v === "unexplained") return 2;
  return 3;
}

export function formatMlSource(s: string) {
  return s
    .replace("prophet:", "Prophet · ")
    .replace("pelt:", "PELT · ")
    .replace("isolation_forest", "Isolation Forest")
    .replace("lstm:", "LSTM · ");
}

export function formatVerdict(v: string) {
  return v.replace(/_/g, " ");
}

export function pct(n: number, digits = 0) {
  return `${(n * 100).toFixed(digits)}%`;
}

export function isKeyIncident(symptoms: string[], roots: Array<{ cause_class: string }>) {
  return (
    symptoms.some((s) => /COMBINATION|attack|Attack|ATTACK/i.test(s)) ||
    roots.some((r) => r.cause_class === "malicious")
  );
}
