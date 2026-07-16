import { useEffect, useState } from "react";
import { APP_NAME } from "../lib/brand";
import { GRAFANA_AVAILABLE, GRAFANA_BASE, GRAFANA_EMBED_URL, GRAFANA_URL } from "../lib/helpers";

export function GrafanaPage() {
  const [loaded, setLoaded] = useState(false);
  const [reachable, setReachable] = useState<boolean | null>(null);

  useEffect(() => {
    if (!GRAFANA_AVAILABLE) {
      setReachable(false);
      return;
    }
    let cancelled = false;
    fetch(`${GRAFANA_BASE}/api/health`, { mode: "no-cors" })
      .then(() => {
        if (!cancelled) setReachable(true);
      })
      .catch(() => {
        if (!cancelled) setReachable(false);
      });
    const t = window.setTimeout(() => {
      if (!cancelled) setReachable((r) => (r === null ? true : r));
    }, 800);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, []);

  const showEmbed = GRAFANA_AVAILABLE && reachable !== false;

  return (
    <div className="page grafana-page anim-fade-in">
      <div className="page-header grafana-header">
        <div>
          <span className="page-eyebrow">{APP_NAME}</span>
          <h2>Grafana Metrics</h2>
          <p className="muted">
            Domain CPU histograms, utilization pie charts, and live gauges from Prometheus
          </p>
        </div>
        <div className="grafana-toolbar">
          <a className="btn btn-ghost btn-sm" href={GRAFANA_URL} target="_blank" rel="noreferrer">
            Open full screen ↗
          </a>
        </div>
      </div>

      {!showEmbed && (
        <div className="card grafana-unavailable anim-slide-up">
          <span className="empty-icon">📊</span>
          <h3>Start {APP_NAME} with Docker</h3>
          <p className="muted">
            Grafana runs alongside {APP_NAME} via Docker Compose at{" "}
            <strong>http://localhost:3001</strong>.
          </p>
          <ol className="demo-steps">
            <li>
              <code>docker compose up --build</code>
            </li>
            <li>
              <code>curl -X POST http://localhost:8000/api/import</code> — backfill histogram metrics
            </li>
            <li>Open {APP_NAME} at <strong>http://127.0.0.1:5173</strong> and return to the Grafana tab</li>
          </ol>
          <a className="btn btn-primary" href={GRAFANA_URL} target="_blank" rel="noreferrer">
            Open Grafana at localhost:3001 ↗
          </a>
        </div>
      )}

      {showEmbed && (
        <div className="grafana-frame-wrap anim-slide-up">
          {!loaded && (
            <div className="grafana-loading">
              <div className="logo-pulse" aria-hidden />
              <span>Loading Grafana dashboard…</span>
            </div>
          )}
          <iframe
            title={`${APP_NAME} · Domain CPU & Telemetry Utilization`}
            src={GRAFANA_EMBED_URL}
            className={`grafana-frame ${loaded ? "loaded" : ""}`}
            onLoad={() => setLoaded(true)}
            allow="fullscreen"
          />
        </div>
      )}

      {showEmbed && (
        <p className="grafana-hint muted text-sm">
          Tip: run replay on Live Monitor — the live time-series panel shows{" "}
          <strong>dotted vertical bars</strong> for each model alert (attack, internal fault, unexplained,
          combination). Check <strong>Alerting → Alert rules</strong> for firing state.
        </p>
      )}
    </div>
  );
}
