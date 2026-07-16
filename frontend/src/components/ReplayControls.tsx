import { API } from "../lib/helpers";
import type { ObservabilityState } from "../types";

export function ReplayControls({ obs }: { obs: ObservabilityState }) {
  const { dataset, replaySpeed, setReplaySpeed, status, replayProgress, startReplay, refresh, incident } = obs;

  return (
    <div className="control-dock anim-slide-up">
      <button type="button" className={`btn btn-primary ${status === "replaying" ? "running" : ""}`} onClick={startReplay} disabled={status === "replaying"}>
        {status === "replaying"
          ? `Replaying ${replayProgress ? `${replayProgress.index}/${replayProgress.total}` : "…"}`
          : `▶ Replay Championship Night (${dataset?.row_count ?? "…"} min)`}
      </button>
      <label className="speed-control">
        Speed
        <input
          type="range"
          min={2}
          max={16}
          value={replaySpeed}
          onChange={(e) => setReplaySpeed(Number(e.target.value))}
          disabled={status === "replaying"}
        />
        <span>{replaySpeed}×</span>
      </label>
      <button type="button" className="btn btn-ghost" onClick={refresh}>Refresh</button>
      {incident && (
        <a href={`${API}/api/incidents/${incident.incident_id}/report`} target="_blank" rel="noreferrer">
          <button type="button" className="btn btn-ghost">Export RCA</button>
        </a>
      )}
    </div>
  );
}

export function AlertBanner({ obs }: { obs: ObservabilityState }) {
  const { activeAlerts } = obs;
  return (
    <div className={`alert-banner ${activeAlerts.length ? "alert-active anim-shake-once" : "calm"}`}>
      {activeAlerts.length === 0 ? (
        <span className="muted">No active alerts — start replay to walk the timeline</span>
      ) : (
        activeAlerts.map((v) => (
          <div key={v.domain} className="alert-chip anim-pop-in">
            <span className={`badge ${v.verdict}`}>{v.verdict.replace("_", " ")}</span>
            <strong>{v.domain}</strong>
            <span className="muted">{v.z_score}σ · {(v.confidence * 100).toFixed(0)}%</span>
          </div>
        ))
      )}
    </div>
  );
}

export function StatsRow({ obs }: { obs: ObservabilityState }) {
  const { incidents, actions, keyIncidents, status } = obs;
  return (
    <div className="stats-row anim-fade-in">
      <div className="stat-card"><span className="stat-val">{incidents.length}</span><span className="stat-lbl">Incidents</span></div>
      <div className="stat-card"><span className="stat-val">{actions.length}</span><span className="stat-lbl">Actions</span></div>
      <div className="stat-card"><span className="stat-val">{keyIncidents.length}</span><span className="stat-lbl">Key ★</span></div>
      {status === "complete" && <span className="meta-success text-sm">Replay complete</span>}
    </div>
  );
}
