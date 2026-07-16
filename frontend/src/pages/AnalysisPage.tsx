import { FusionPanel } from "../components/FusionPanel";
import type { ObservabilityState } from "../types";

export function AnalysisPage({ obs }: { obs: ObservabilityState }) {
  const { fusion, decomp } = obs;

  return (
    <div className="page analysis-page">
      <div className="page-header anim-fade-in">
        <h2>Evidence Fusion & Analysis</h2>
        <p className="muted">Tier-3 analyzers, ML corroboration, and cross-domain synthesis</p>
      </div>

      <div className="card card-highlight anim-slide-up">
        <h3>Evidence Fusion Engine</h3>
        <FusionPanel fusion={fusion} />
      </div>

      <div className="grid-2">
        <div className="card anim-slide-up" style={{ animationDelay: "80ms" }}>
          <h3>ML Pipeline</h3>
          <ul className="pipeline-list">
            {["Prophet + STL baseline", "Isolation Forest anomalies", "LSTM auth autoencoder", "PELT change-point (heap)", "3 Tier-3 analyzers", "Evidence fusion + causal graph"].map((s, i) => (
              <li key={s} className="anim-fade-in" style={{ animationDelay: `${i * 50}ms` }}>{s}</li>
            ))}
          </ul>
        </div>
        <div className="card anim-slide-up" style={{ animationDelay: "120ms" }}>
          <h3>Context multipliers (active)</h3>
          {decomp.length === 0 ? (
            <p className="muted">Replay to see context-adjusted domains</p>
          ) : (
            decomp.map((d) => (
              <div key={d.domain} className="ctx-row">
                <span>{d.domain}</span>
                <span className="muted">ctx {d.context_effect.toExponential(2)}</span>
                <span className={`badge ${d.verdict}`}>{d.verdict}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
