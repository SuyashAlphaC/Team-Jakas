import type { CSSProperties } from "react";
import { APP_NAME, APP_TAGLINE, TEAM_NAME, TEAM_TRACK } from "../lib/brand";
import type { ObservabilityState } from "../types";

const FEATURES = [
  {
    icon: "◈",
    title: "Context-aware CIS",
    desc: "Suppress expected merch & ingress surges — no alert fatigue",
    accent: "#1d9bf0",
  },
  {
    icon: "⚡",
    title: "Causal RCA",
    desc: "Symptom graph → service → root cause with deploy/config context",
    accent: "#7856ff",
  },
  {
    icon: "⛊",
    title: "Risk-aware remediation",
    desc: "observe → rate-limit → throttle → isolate → rollback",
    accent: "#00ba7c",
  },
  {
    icon: "▤",
    title: "Deterministic replay",
    desc: "240 rows · hash-chained audit · 100% seed accuracy",
    accent: "#ffad1f",
  },
] as const;

const DEMO_STEPS = [
  { time: "0:00", label: "Start replay", detail: "Show 240-min championship dataset" },
  { time: "1:30", label: "SUPPRESS", detail: "20:15 transaction surge explained (green)" },
  { time: "2:30", label: "COMBINATION ★", detail: "20:16 attack + internal fault incident" },
  { time: "3:30", label: "Export RCA", detail: "Stack-trace file:line patches" },
  { time: "4:30", label: "Close", detail: "100% seed label accuracy" },
] as const;

export function HomePage({ obs }: { obs: ObservabilityState }) {
  const { validation, dataset, startReplay, setTab, incidents, status } = obs;
  const replaying = status === "replaying";

  return (
    <div className="page home-page">
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-hero-bg" aria-hidden>
          <div className="landing-grid" />
          <div className="landing-orb landing-orb--1" />
          <div className="landing-orb landing-orb--2" />
          <div className="landing-orb landing-orb--3" />
          <div className="landing-shimmer" />
        </div>

        <div className="landing-hero-inner">
          <div className="landing-badge anim-reveal" style={{ animationDelay: "0.05s" }}>
            <span className="landing-badge-dot" />
            <span>Cisco Codathon</span>
            <span className="brand-tagline-sep">·</span>
            <span className="brand-team-name brand-team-name--badge">{TEAM_NAME}</span>
            <span className="brand-tagline-sep">·</span>
            <span className="brand-track-badge brand-track-badge--badge">{TEAM_TRACK}</span>
          </div>

          <p className="hero-eyebrow landing-eyebrow anim-reveal" style={{ animationDelay: "0.12s" }}>
            {APP_NAME}
          </p>

          <h1 id="landing-title" className="hero-display anim-reveal" style={{ animationDelay: "0.2s" }}>
            {APP_TAGLINE.split(" ").map((word, i) => (
              <span key={word} className="hero-display-word" style={{ animationDelay: `${0.28 + i * 0.07}s` }}>
                {word}
              </span>
            ))}
          </h1>

          <p className="hero-lead anim-reveal" style={{ animationDelay: "0.45s" }}>
            Decompose championship-night telemetry into explained vs unexplained residuals.
            Detect attacks during live merch drops, localize code bugs, and propose graded remediation —
            with causal reasoning and sub-second RCA.
          </p>

          <div className="hero-actions anim-reveal" style={{ animationDelay: "0.55s" }}>
            <button
              type="button"
              className={`btn btn-primary btn-xl landing-cta ${replaying ? "landing-cta--live" : ""}`}
              onClick={startReplay}
              disabled={replaying}
            >
              <span className="landing-cta-icon">{replaying ? "◉" : "▶"}</span>
              {replaying ? "Replay in progress…" : "Start 240-min Replay"}
            </button>
            <button type="button" className="btn btn-ghost btn-xl" onClick={() => setTab("monitor")}>
              Open Live Monitor
            </button>
            <button type="button" className="btn btn-ghost btn-xl" onClick={() => setTab("grafana")}>
              View Grafana
            </button>
          </div>

          <div className="landing-pills anim-reveal" style={{ animationDelay: "0.65s" }}>
            {["7 domains", "Stack-trace RCA", "Graded remediation", "Grafana alerting"].map((pill) => (
              <span key={pill} className="landing-pill">{pill}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="feature-grid landing-features" aria-label="Platform capabilities">
        {FEATURES.map((f, i) => (
          <article
            key={f.title}
            className="feature-card landing-feature-card anim-reveal"
            style={{ animationDelay: `${0.15 + i * 0.1}s`, "--feature-accent": f.accent } as CSSProperties}
          >
            <span className="feature-icon landing-feature-icon">{f.icon}</span>
            <h3>{f.title}</h3>
            <p className="muted">{f.desc}</p>
            <span className="landing-feature-glow" aria-hidden />
          </article>
        ))}
      </section>

      <section className="metrics-strip landing-metrics anim-reveal" style={{ animationDelay: "0.2s" }} aria-label="Key metrics">
        {[
          { val: dataset?.row_count ?? "—", lbl: "Telemetry minutes" },
          { val: validation ? `${(validation.accuracy * 100).toFixed(0)}%` : "—", lbl: "Label accuracy" },
          { val: "7", lbl: "Monitoring domains" },
          { val: incidents.length || "—", lbl: "Incidents (last run)" },
        ].map((m, i) => (
          <div key={m.lbl} className="metric landing-metric anim-reveal" style={{ animationDelay: `${0.3 + i * 0.08}s` }}>
            <span className="metric-val landing-metric-val">{m.val}</span>
            <span className="metric-lbl">{m.lbl}</span>
          </div>
        ))}
      </section>

      <section className="landing-demo anim-reveal" style={{ animationDelay: "0.25s" }}>
        <div className="landing-demo-header">
          <div>
            <span className="page-eyebrow">{APP_NAME}</span>
            <h2 className="landing-demo-title">5-minute demo script</h2>
            <p className="muted landing-demo-sub">Walk judges through the golden window · 20:14–20:19 UTC</p>
          </div>
          <button type="button" className="btn btn-primary btn-lg" onClick={startReplay} disabled={replaying}>
            Launch demo
          </button>
        </div>

        <ol className="landing-timeline">
          {DEMO_STEPS.map((step, i) => (
            <li
              key={step.time}
              className="landing-timeline-step anim-reveal"
              style={{ animationDelay: `${0.35 + i * 0.1}s` }}
            >
              <span className="landing-timeline-time">{step.time}</span>
              <div className="landing-timeline-body">
                <strong>{step.label}</strong>
                <span className="muted">{step.detail}</span>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
