import { AlertBanner, ReplayControls, StatsRow } from "../components/ReplayControls";
import { PageHeader } from "../components/PageHeader";
import type { ObservabilityState } from "../types";

export function MonitorPage({ obs }: { obs: ObservabilityState }) {
  const { decomp, sortedVerdicts } = obs;

  return (
    <div className="page monitor-page">
      <PageHeader
        title="Live Monitor"
        subtitle="Real-time alerts, residuals, and domain verdicts during replay"
      />

      <ReplayControls obs={obs} />
      <AlertBanner obs={obs} />
      <StatsRow obs={obs} />

      <div className="grid-2">
        <div className="card anim-slide-up">
          <h3>Residual Decomposition</h3>
          {decomp.length === 0 && <p className="muted">Start replay to see CIS decomposition</p>}
          <div className="decomp-list">
            {decomp.map((d, i) => (
              <div key={d.domain} className="decomp-row anim-fade-in" style={{ animationDelay: `${i * 40}ms` }}>
                <div className="decomp-head">
                  <strong>{d.domain}</strong>
                  <span className={`badge ${d.verdict}`}>{d.verdict}</span>
                </div>
                <div className="sigma-bar">
                  <div className="sigma-fill" style={{ width: `${Math.min(100, Math.abs(d.z_score) * 15)}%` }} />
                </div>
                <div className="muted text-sm">
                  residual {d.residual >= 0 ? "+" : ""}{d.residual.toExponential(2)} · {d.z_score}σ
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card anim-slide-up" style={{ animationDelay: "60ms" }}>
          <h3>Domain Verdicts</h3>
          {sortedVerdicts.length === 0 && <p className="muted">Awaiting verdicts…</p>}
          {sortedVerdicts.map((v, i) => (
            <div key={v.domain} className={`verdict-row ${v.verdict !== "expected" ? "alerting" : ""} anim-fade-in`} style={{ animationDelay: `${i * 40}ms` }}>
              <div className="head">
                <strong>{v.domain}</strong>
                <span>
                  <span className={`badge ${v.verdict}`}>{v.verdict.replace("_", " ")}</span>
                  {" "}{(v.confidence * 100).toFixed(0)}% · {v.z_score}σ
                </span>
              </div>
              <div className="reason">{v.reason}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
