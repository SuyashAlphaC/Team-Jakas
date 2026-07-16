import type { ObservabilityState } from "../types";

export function HomePage({ obs }: { obs: ObservabilityState }) {
  const { validation, dataset, startReplay, setTab, incidents, status } = obs;

  return (
    <div className="page home-page">
      <section className="hero anim-fade-in">
        <div className="hero-glow" aria-hidden />
        <div className="hero-content">
          <span className="hero-eyebrow">Autonomous Observability</span>
          <h2 className="hero-title">Signal through the surge</h2>
          <p className="hero-sub">
            Decompose championship-night telemetry into explained vs unexplained residuals.
            Detect attacks during live merch drops, localize code bugs, and propose graded remediation — with causal reasoning.
          </p>
          <div className="hero-actions">
            <button type="button" className="btn btn-primary btn-lg" onClick={startReplay} disabled={status === "replaying"}>
              ▶ Start 240-min Replay
            </button>
            <button type="button" className="btn btn-ghost btn-lg" onClick={() => setTab("monitor")}>
              Open Live Monitor
            </button>
          </div>
        </div>
      </section>

      <section className="feature-grid">
        {[
          { icon: "◈", title: "Context-aware CIS", desc: "Suppress expected merch & ingress surges — no alert fatigue" },
          { icon: "⚡", title: "Causal RCA", desc: "Symptom graph → service → root cause with deploy/config context" },
          { icon: "⛊", title: "Risk-aware remediation", desc: "observe → rate-limit → throttle → isolate → rollback" },
          { icon: "▤", title: "Deterministic replay", desc: "240 rows · hash-chained audit · 100% seed accuracy" },
        ].map((f, i) => (
          <article key={f.title} className="feature-card anim-slide-up" style={{ animationDelay: `${i * 80}ms` }}>
            <span className="feature-icon">{f.icon}</span>
            <h3>{f.title}</h3>
            <p className="muted">{f.desc}</p>
          </article>
        ))}
      </section>

      <section className="metrics-strip anim-fade-in">
        <div className="metric">
          <span className="metric-val">{dataset?.row_count ?? "—"}</span>
          <span className="metric-lbl">Telemetry minutes</span>
        </div>
        <div className="metric">
          <span className="metric-val">{validation ? `${(validation.accuracy * 100).toFixed(0)}%` : "—"}</span>
          <span className="metric-lbl">Label accuracy</span>
        </div>
        <div className="metric">
          <span className="metric-val">7</span>
          <span className="metric-lbl">Monitoring domains</span>
        </div>
        <div className="metric">
          <span className="metric-val">{incidents.length || "—"}</span>
          <span className="metric-lbl">Incidents (last run)</span>
        </div>
      </section>

      <section className="card demo-script anim-slide-up">
        <h3>5-minute demo script</h3>
        <ol className="demo-steps">
          <li><strong>0:00</strong> — Start replay · show 240-min dataset</li>
          <li><strong>1:30</strong> — 20:15 transaction SUPPRESS (green)</li>
          <li><strong>2:30</strong> — 20:16 COMBINATION ★ incident</li>
          <li><strong>3:30</strong> — Export RCA · file:line patches</li>
          <li><strong>4:30</strong> — 100% seed accuracy · close</li>
        </ol>
      </section>
    </div>
  );
}
