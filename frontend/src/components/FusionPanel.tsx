import { ALERT_VERDICTS, formatMlSource } from "../lib/helpers";
import type { Fusion } from "../types";

export function FusionPanel({ fusion }: { fusion: Fusion | null }) {
  if (!fusion) return <p className="muted">Awaiting fusion evidence from replay…</p>;

  return (
    <>
      <p className="fusion-headline">{fusion.summary}</p>
      <div className="fusion-meta">
        {fusion.combination && <span className="badge unexplained">COMBINATION</span>}
        {fusion.primary_verdict && ALERT_VERDICTS.has(fusion.primary_verdict) && (
          <span className={`badge ${fusion.primary_verdict}`}>{fusion.primary_verdict.replace("_", " ")}</span>
        )}
        {(fusion.alert_domains ?? []).map((d) => (
          <span key={d} className="chip alert">alert · {d}</span>
        ))}
        {(fusion.unexplained_domains ?? []).map((d) => (
          <span key={`u-${d}`} className="chip chip-purple">unexplained · {d}</span>
        ))}
      </div>
      {(fusion.ml_sources ?? []).length > 0 && (
        <div className="mb-3">
          <div className="label-sm">ML evidence</div>
          <div className="fusion-meta">
            {fusion.ml_sources!.map((s) => (
              <span key={s} className="chip chip-ml">{formatMlSource(s)}</span>
            ))}
          </div>
        </div>
      )}
      {fusion.signals.length === 0 ? (
        <p className="muted text-sm">Detection driven by residual / ML pipeline on this minute.</p>
      ) : (
        fusion.signals.map((s, i) => (
          <div key={i} className="analyzer-block anim-fade-in" style={{ animationDelay: `${i * 60}ms` }}>
            <strong>{s.analyzer}</strong>
            <span className="muted"> → {s.domain} · </span>
            <span className={`badge ${s.verdict}`}>{s.verdict}</span>
            <span className="muted"> ({(s.confidence * 100).toFixed(0)}%)</span>
            <ul>
              {s.evidence.map((e, j) => <li key={j}>{e}</li>)}
            </ul>
          </div>
        ))
      )}
    </>
  );
}
