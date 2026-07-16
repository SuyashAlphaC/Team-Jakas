import { API } from "../lib/helpers";
import { APP_NAME, TEAM_NAME } from "../lib/brand";
import { BrandTagline } from "./BrandTagline";
import type { ObservabilityState } from "../types";

export function Header({ obs }: { obs: ObservabilityState }) {
  const { validation, dataset, status, currentTs, replayProgress } = obs;

  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="header-logo" aria-hidden>
          <span className="header-logo-ring" />
          <span className="header-logo-core" />
        </div>
        <div className="header-brand-text">
          <h1>{APP_NAME}</h1>
          <BrandTagline variant="header" />
        </div>
      </div>
      <div className="header-meta">
        {validation && (
          <span className="meta-chip meta-success">
            <span className="meta-chip-dot" />
            Accuracy {validation.score}/{validation.total} ({(validation.accuracy * 100).toFixed(1)}%)
          </span>
        )}
        {dataset && (
          <span className="meta-chip">
            <span className="meta-chip-icon">▤</span>
            {dataset.row_count} min · {dataset.time_range?.[0]?.slice(11, 16)}–{dataset.time_range?.[1]?.slice(11, 16)} UTC
          </span>
        )}
        {status === "replaying" && (
          <span className="meta-chip meta-live anim-pulse">
            <span className="meta-chip-dot meta-chip-dot--live" />
            LIVE {currentTs}
            {replayProgress && ` · ${replayProgress.index}/${replayProgress.total}`}
          </span>
        )}
        {status === "complete" && (
          <span className="meta-chip meta-success">
            <span className="meta-chip-dot" />
            Replay complete
          </span>
        )}
      </div>
    </header>
  );
}

export function NavBar({ obs }: { obs: ObservabilityState }) {
  const { tab, setTab, activeAlerts, incidents, actions, timeline } = obs;

  const items: { id: typeof tab; label: string; icon: string; badge?: number; shortLabel?: string }[] = [
    { id: "home", label: "Home", shortLabel: "Home", icon: "⌂" },
    { id: "monitor", label: "Live Monitor", shortLabel: "Monitor", icon: "◉", badge: activeAlerts.length || undefined },
    { id: "analysis", label: "Analysis", shortLabel: "Analysis", icon: "◈" },
    { id: "incidents", label: "Incidents & RCA", shortLabel: "Incidents", icon: "⚡", badge: incidents.length || undefined },
    { id: "remediation", label: "Remediation", shortLabel: "Fix", icon: "⛊", badge: actions.length || undefined },
    { id: "timeline", label: "Timeline", shortLabel: "Timeline", icon: "▤", badge: timeline.length || undefined },
    { id: "grafana", label: "Grafana", shortLabel: "Grafana", icon: "▣" },
  ];

  return (
    <nav className="app-nav" aria-label={`${APP_NAME} main navigation`}>
      <div className="nav-scroll">
        <div className="nav-track" role="tablist">
          {items.map((item, i) => {
            const active = tab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={active}
                className={`nav-item ${active ? "active" : ""}`}
                style={{ animationDelay: `${i * 45}ms` }}
                onClick={() => setTab(item.id)}
              >
                <span className="nav-icon-wrap">
                  <span className="nav-icon">{item.icon}</span>
                </span>
                <span className="nav-label">{item.label}</span>
                <span className="nav-label-short">{item.shortLabel}</span>
                {item.badge != null && item.badge > 0 && (
                  <span className={`nav-badge ${item.id === "monitor" ? "nav-badge--alert" : ""}`}>
                    {item.badge > 99 ? "99+" : item.badge}
                  </span>
                )}
                {active && <span className="nav-active-glow" aria-hidden />}
              </button>
            );
          })}
        </div>
      </div>
      <div className="nav-actions">
        <a className="nav-export-btn" href={`${API}/api/reports/remediation`} target="_blank" rel="noreferrer">
          <span className="nav-export-icon">↗</span>
          <span className="nav-export-label">Export log</span>
        </a>
      </div>
    </nav>
  );
}

export function Footer() {
  return (
    <footer className="app-footer">
      <div className="footer-grid">
        <div>
          <strong>{APP_NAME}</strong>
          <p className="muted text-sm">Sphere Sports championship demo · 240-min telemetry · 7 domains</p>
        </div>
        <div>
          <strong>Links</strong>
          <p className="text-sm">
            <a href="http://127.0.0.1:5173" target="_blank" rel="noreferrer">{APP_NAME}</a>
            {" · "}
            <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API docs</a>
            {" · "}
            <a href="https://github.com/SuyashAlphaC/Team-Jakas" target="_blank" rel="noreferrer">GitHub</a>
          </p>
        </div>
        <div>
          <strong>Golden window</strong>
          <p className="muted text-sm">20:14–20:19 UTC · COMBINATION at 20:16 ★</p>
        </div>
      </div>
      <p className="footer-copy">
        © 2026 <span className="brand-team-name brand-team-name--footer">{TEAM_NAME}</span> · {APP_NAME} · Cisco Codathon Track 2
      </p>
    </footer>
  );
}
