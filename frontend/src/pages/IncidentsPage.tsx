import { API } from "../lib/helpers";
import { PageHeader } from "../components/PageHeader";
import type { ObservabilityState } from "../types";

export function IncidentsPage({ obs }: { obs: ObservabilityState }) {
  const { incidents, selectedInc, setSelectedInc, keyIncidents, incident } = obs;

  if (incidents.length === 0) {
    return (
      <div className="page incidents-page">
        <PageHeader
          title="Incidents & RCA"
          subtitle="Causal root-cause analysis with code localization"
        />
        <div className="empty-state anim-fade-in">
          <span className="empty-icon">⚡</span>
          <p>No incidents yet — start replay and jump to <strong>20:16 ★</strong></p>
        </div>
      </div>
    );
  }

  return (
    <div className="page incidents-page">
      <PageHeader
        title="Incidents & RCA"
        subtitle={`${incidents.length} incidents · click to inspect · export Markdown RCA`}
      />

      <div className="incident-tabs">
        {incidents.map((inc, i) => {
          const isKey = keyIncidents.some((k) => k.incident_id === inc.incident_id);
          return (
            <button
              key={inc.incident_id}
              type="button"
              className={`btn ${i === selectedInc ? "btn-primary" : "btn-ghost"} ${isKey ? "key-inc" : ""}`}
              onClick={() => setSelectedInc(i)}
            >
              {inc.started_at.slice(11, 16)}{isKey ? " ★" : ""}
            </button>
          );
        })}
      </div>

      {incident && (
        <div className="card anim-slide-up">
          <div className="incident-header">
            <div>
              <strong>{incident.incident_id}</strong>
              <span className="muted"> · conf {(incident.confidence * 100).toFixed(0)}% · {incident.status}</span>
            </div>
            <a href={`${API}/api/incidents/${incident.incident_id}/report`} target="_blank" rel="noreferrer">
              <button type="button" className="btn btn-ghost btn-sm">Export RCA</button>
            </a>
          </div>

          {incident.reasoning_summary && (
            <div className="causal-banner anim-fade-in">
              <strong>Causal chain:</strong> {incident.reasoning_summary}
            </div>
          )}

          {incident.mttr_detect_ms != null && (
            <div className="mttr-row">
              <span>Detect {incident.mttr_detect_ms.toFixed(1)}ms</span>
              <span>RCA {(incident.mttr_rca_ms ?? 0).toFixed(1)}ms</span>
              <span>Mitigate {(incident.mttr_mitigate_ms ?? 0).toFixed(1)}ms</span>
            </div>
          )}

          {incident.causal_graph && incident.causal_graph.edges.length > 0 && (
            <div className="causal-graph-box">
              <h4>Causal dependency graph</h4>
              {incident.causal_graph.reasoning_chain.map((s, i) => (
                <div key={i} className="causal-step">→ {s}</div>
              ))}
              {incident.causal_graph.edges.slice(0, 6).map((e, i) => (
                <div key={i} className="causal-edge mono text-sm">
                  {e.source.split(":").pop()} —{e.relation}→ {e.target.split(":").pop()}
                </div>
              ))}
            </div>
          )}

          <h4>Root causes</h4>
          {incident.roots.map((r, i) => (
            <div key={i} className="root-card anim-fade-in" style={{ animationDelay: `${i * 60}ms` }}>
              <div className="root-head">
                <strong>{r.service}</strong>
                <span className={`badge ${r.cause_class === "malicious" ? "attack" : "internal_fault"}`}>{r.cause_class}</span>
                <span className="muted">{(r.confidence * 100).toFixed(0)}%</span>
              </div>
              {r.file && <div className="mono text-sm">📁 {r.file}{r.function ? ` :: ${r.function}()` : ""}</div>}
              {r.file && r.function && (
                <span className="chip chip-purple text-sm">Parsed from stack trace</span>
              )}
              {r.config_key && <div className="config-tag">⚙ {r.config_key}{r.likely_commit ? ` · ${r.likely_commit.slice(0, 7)}` : ""}</div>}
              <p className="muted text-sm">{r.mechanism}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
