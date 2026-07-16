import { API } from "../lib/helpers";
import type { ObservabilityState } from "../types";

export function Header({ obs }: { obs: ObservabilityState }) {
  const { validation, dataset, status, currentTs, replayProgress } = obs;

  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="logo-pulse" aria-hidden />
        <div>
          <h1>Context-Aware Observability</h1>
          <p className="tagline">Signal through the surge · Team Jakas · Track 2 Platinum</p>
        </div>
      </div>
      <div className="header-meta">
        {validation && (
          <span className="meta-chip meta-success">
            Accuracy {validation.score}/{validation.total} ({(validation.accuracy * 100).toFixed(1)}%)
          </span>
        )}
        {dataset && (
          <span className="meta-chip">
            {dataset.row_count} min · {dataset.time_range?.[0]?.slice(11, 16)}–{dataset.time_range?.[1]?.slice(11, 16)} UTC
          </span>
        )}
        {status === "replaying" && (
          <span className="meta-chip meta-live anim-pulse">
            LIVE {currentTs}
            {replayProgress && ` · ${replayProgress.index}/${replayProgress.total}`}
          </span>
        )}
        {status === "complete" && <span className="meta-chip meta-success">Replay complete</span>}
      </div>
    </header>
  );
}

export function NavBar({ obs }: { obs: ObservabilityState }) {
  const { tab, setTab, activeAlerts, incidents, actions, timeline } = obs;

  const items: { id: typeof tab; label: string; icon: string; badge?: number }[] = [
    { id: "home", label: "Home", icon: "⌂" },
    { id: "monitor", label: "Live Monitor", icon: "◉", badge: activeAlerts.length || undefined },
    { id: "analysis", label: "Analysis", icon: "◈" },
    { id: "incidents", label: "Incidents & RCA", icon: "⚡", badge: incidents.length || undefined },
    { id: "remediation", label: "Remediation", icon: "⛊", badge: actions.length || undefined },
    { id: "timeline", label: "Timeline", icon: "▤", badge: timeline.length || undefined },
    { id: "grafana", label: "Grafana", icon: "▣" },
  ];

  return (
    <nav className="app-nav" aria-label="Main navigation">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`nav-item ${tab === item.id ? "active" : ""}`}
          onClick={() => setTab(item.id)}
        >
          <span className="nav-icon">{item.icon}</span>
          <span className="nav-label">{item.label}</span>
          {item.badge != null && item.badge > 0 && (
            <span className="nav-badge">{item.badge > 99 ? "99+" : item.badge}</span>
          )}
        </button>
      ))}
      <div className="nav-spacer" />
      <a className="nav-link" href={`${API}/api/reports/remediation`} target="_blank" rel="noreferrer">
        Export log ↗
      </a>
    </nav>
  );
}

export function Footer() {
  return (
    <footer className="app-footer">
      <div className="footer-grid">
        <div>
          <strong>Sphere Sports Demo</strong>
          <p className="muted text-sm">240-min championship telemetry · 7 domains · causal RCA</p>
        </div>
        <div>
          <strong>Links</strong>
          <p className="text-sm">
            <a href="https://context-aware-observability.vercel.app" target="_blank" rel="noreferrer">Vercel demo</a>
            {" · "}
            <a href="https://github.com/SuyashAlphaC/Team-Jakas" target="_blank" rel="noreferrer">GitHub</a>
          </p>
        </div>
        <div>
          <strong>Golden window</strong>
          <p className="muted text-sm">20:14–20:19 UTC · COMBINATION at 20:16 ★</p>
        </div>
      </div>
      <p className="footer-copy">© 2026 Team Jakas · Cisco Codathon Track 2</p>
    </footer>
  );
}
