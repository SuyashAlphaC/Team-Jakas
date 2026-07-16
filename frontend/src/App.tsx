import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Decomp = {
  domain: string;
  baseline: number;
  context_effect: number;
  observed: number;
  residual: number;
  z_score: number;
  verdict: string;
};

type Verdict = {
  domain: string;
  verdict: string;
  confidence: number;
  z_score: number;
  reason: string;
};

type FusionSignal = {
  analyzer: string;
  domain: string;
  verdict: string;
  confidence: number;
  evidence: string[];
};

type Fusion = {
  summary: string;
  combination: boolean;
  primary_verdict?: string;
  alert_domains?: string[];
  unexplained_domains?: string[];
  ml_sources?: string[];
  signals: FusionSignal[];
};

type TimelineEntry = {
  id: string;
  time: string;
  type: string;
  body: string;
  severity?: "info" | "alert" | "action";
};

type Incident = {
  incident_id: string;
  started_at: string;
  status: string;
  confidence: number;
  symptoms: string[];
  suppressed_domains: string[];
  roots: Array<{
    service: string;
    cause_class: string;
    confidence: number;
    file?: string;
    function?: string;
    proposed_fix: string;
    mechanism: string;
  }>;
  mttr_detect_ms?: number;
  mttr_rca_ms?: number;
  mttr_mitigate_ms?: number;
};

type Action = {
  action_id: string;
  grade: string;
  state: string;
  target: string;
  reason: string;
  confidence: number;
  proposed_command: string;
  requires_approval: boolean;
  blast_radius?: string;
  incident_id?: string;
};

type Validation = {
  score: number;
  total: number;
  accuracy: number;
  dataset?: string;
};

type DatasetInfo = {
  row_count: number;
  time_range?: string[];
};

const API = import.meta.env.VITE_API_URL || "";
const ALERT_VERDICTS = new Set(["attack", "internal_fault", "unexplained"]);

function verdictRank(v: string) {
  if (v === "attack") return 0;
  if (v === "internal_fault") return 1;
  if (v === "unexplained") return 2;
  return 3;
}

function formatMlSource(s: string) {
  return s.replace("prophet:", "Prophet · ").replace("pelt:", "PELT · ").replace("isolation_forest", "Isolation Forest").replace("lstm:", "LSTM · ");
}

function FusionPanel({ fusion }: { fusion: Fusion | null }) {
  if (!fusion) return <p style={{ color: "#8899a6" }}>Awaiting fusion…</p>;

  return (
    <>
      <p className="fusion-headline">{fusion.summary}</p>
      <div className="fusion-meta">
        {fusion.combination && <span className="badge unexplained">COMBINATION INCIDENT</span>}
        {fusion.primary_verdict && ALERT_VERDICTS.has(fusion.primary_verdict) && (
          <span className={`badge ${fusion.primary_verdict}`}>{fusion.primary_verdict.replace("_", " ")}</span>
        )}
        {(fusion.alert_domains ?? []).map((d) => (
          <span key={d} className="chip alert">alert · {d}</span>
        ))}
        {(fusion.unexplained_domains ?? []).map((d) => (
          <span key={`u-${d}`} className="chip" style={{ color: "#7856ff", borderColor: "#7856ff55" }}>unexplained · {d}</span>
        ))}
      </div>
      {(fusion.ml_sources ?? []).length > 0 && (
        <div style={{ marginBottom: "0.75rem" }}>
          <div style={{ fontSize: "0.75rem", color: "#8899a6", marginBottom: "0.35rem" }}>ML evidence</div>
          <div className="fusion-meta">
            {fusion.ml_sources!.map((s) => (
              <span key={s} className="chip ml">{formatMlSource(s)}</span>
            ))}
          </div>
        </div>
      )}
      {fusion.signals.length === 0 ? (
        <p style={{ fontSize: "0.85rem", color: "#8899a6" }}>
          No Tier-3 analyzer corroboration on this minute — detection driven by residual/ML pipeline.
        </p>
      ) : (
        fusion.signals.map((s, i) => (
          <div key={i} className="analyzer-block">
            <strong>{s.analyzer}</strong>
            <span style={{ color: "#8899a6" }}> → {s.domain} · </span>
            <span className={`badge ${s.verdict}`}>{s.verdict}</span>
            <span style={{ color: "#8899a6" }}> ({(s.confidence * 100).toFixed(0)}%)</span>
            <ul>
              {s.evidence.map((e, j) => <li key={j}>{e}</li>)}
            </ul>
          </div>
        ))
      )}
    </>
  );
}

export default function App() {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [decomp, setDecomp] = useState<Decomp[]>([]);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [fusion, setFusion] = useState<Fusion | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedInc, setSelectedInc] = useState<number>(-1);
  const [actions, setActions] = useState<Action[]>([]);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [replayProgress, setReplayProgress] = useState<{ index: number; total: number } | null>(null);
  const [replaySpeed, setReplaySpeed] = useState(6);
  const [status, setStatus] = useState("idle");
  const [currentTs, setCurrentTs] = useState("");
  const actionIds = useRef(new Set<string>());

  const refresh = useCallback(async () => {
    const [inc, act, val] = await Promise.all([
      fetch(`${API}/api/incidents`).then((r) => r.json()),
      fetch(`${API}/api/actions`).then((r) => r.json()),
      fetch(`${API}/api/validation`).then((r) => r.json()),
    ]);
    setIncidents(inc);
    setActions(act);
    act.forEach((a: Action) => actionIds.current.add(a.action_id));
    setValidation(val);
  }, []);

  useEffect(() => {
    fetch(`${API}/api/import`, { method: "POST" })
      .then((r) => r.json())
      .then((info) => setDataset({ row_count: info.row_count, time_range: info.time_range }))
      .then(() => refresh())
      .catch(() => {});
  }, [refresh]);

  useEffect(() => {
    if (status !== "replaying") return;
    const id = window.setInterval(() => {
      fetch(`${API}/api/actions`)
        .then((r) => r.json())
        .then((act: Action[]) => {
          setActions((prev) => {
            const merged = [...prev];
            for (const a of act) {
              if (!actionIds.current.has(a.action_id)) {
                actionIds.current.add(a.action_id);
                merged.push(a);
              }
            }
            return merged;
          });
        })
        .catch(() => {});
    }, 1500);
    return () => window.clearInterval(id);
  }, [status]);

  const pushTimeline = (entry: Omit<TimelineEntry, "id">) => {
    setTimeline((t) => [...t.slice(-80), { ...entry, id: `${entry.time}-${entry.type}-${t.length}` }]);
  };

  const addAction = (a: Action) => {
    if (actionIds.current.has(a.action_id)) return;
    actionIds.current.add(a.action_id);
    setActions((prev) => [...prev, a]);
  };

  const startReplay = async () => {
    setStatus("replaying");
    setTimeline([]);
    setDecomp([]);
    setVerdicts([]);
    setFusion(null);
    setIncidents([]);
    setActions([]);
    setSelectedInc(-1);
    setReplayProgress(null);
    setCurrentTs("");
    actionIds.current.clear();

    await fetch(`${API}/api/replay/start?speed=${replaySpeed}`, { method: "POST" });

    const es = new EventSource(`${API}/api/stream`);
    es.onmessage = (msg) => {
      const ev = JSON.parse(msg.data);
      if (ev.event_type === "connected") return;

      const ts = ev.timestamp ? ev.timestamp.slice(11, 16) : "";
      if (ts) setCurrentTs(ts);
      if (ev.data?.progress) setReplayProgress(ev.data.progress);

      if (ev.event_type === "fusion") {
        setFusion(ev.data);
        pushTimeline({ time: ts, type: "fusion", body: ev.data.summary, severity: ev.data.combination ? "alert" : "info" });
      } else if (ev.event_type === "unexplained") {
        const lines = (ev.data.domains ?? []).map((d: { domain: string; z_score: number }) => `${d.domain} (${d.z_score}σ)`).join(", ");
        pushTimeline({ time: ts, type: "unexplained", body: `Unexplained residual: ${lines}`, severity: "alert" });
      } else if (ev.event_type === "incident") {
        pushTimeline({
          time: ts,
          type: "incident",
          body: `${ev.data.incident_id} · ${ev.data.roots?.[0]?.service ?? "unknown"} · conf ${ev.data.confidence}`,
          severity: "alert",
        });
        setIncidents((i) => {
          const next = [...i.filter((x) => x.incident_id !== ev.data.incident_id), ev.data];
          setSelectedInc(next.length - 1);
          return next;
        });
      } else if (ev.event_type === "action") {
        addAction(ev.data);
        pushTimeline({
          time: ts,
          type: "action",
          body: `${ev.data.grade} → ${ev.data.target}: ${ev.data.reason}`,
          severity: "action",
        });
      } else if (ev.event_type === "suppress") {
        pushTimeline({ time: ts, type: "suppress", body: ev.data.reason ?? "Context explained surge", severity: "info" });
      } else if (ev.event_type === "observation") {
        pushTimeline({ time: ts, type: "tick", body: `Row ${ev.data.progress?.index ?? "?"}/${ev.data.progress?.total ?? "?"}`, severity: "info" });
      }

      if (ev.event_type === "decomposition") setDecomp(ev.data.domains);
      if (ev.event_type === "verdicts") setVerdicts(ev.data.verdicts);

      if (ev.event_type === "replay_complete") {
        setStatus("complete");
        es.close();
        refresh();
      }
    };
  };

  const approve = async (id: string) => {
    await fetch(`${API}/api/actions/${id}/advance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approve: true }),
    });
    refresh();
  };

  const sortedVerdicts = useMemo(
    () => [...verdicts].sort((a, b) => verdictRank(a.verdict) - verdictRank(b.verdict)),
    [verdicts],
  );

  const activeAlerts = useMemo(
    () => sortedVerdicts.filter((v) => ALERT_VERDICTS.has(v.verdict)),
    [sortedVerdicts],
  );

  const keyIncidents = useMemo(
    () => incidents.filter((inc) => inc.symptoms.some((s) => /COMBINATION|attack|Attack|ATTACK/i.test(s)) || inc.roots.some((r) => r.cause_class === "malicious")),
    [incidents],
  );

  const incident = incidents[selectedInc >= 0 ? selectedInc : incidents.length - 1];

  const uniqueActions = useMemo(() => {
    const seen = new Map<string, Action>();
    for (const a of actions) {
      const key = `${a.grade}:${a.target}:${a.proposed_command}`;
      if (!seen.has(key)) seen.set(key, a);
    }
    return [...seen.values()].slice(-12);
  }, [actions]);

  return (
    <div style={{ padding: "1.5rem", maxWidth: 1280, margin: "0 auto" }}>
      <header style={{ marginBottom: "1.25rem" }}>
        <h1 style={{ margin: 0 }}>Context-Aware Observability</h1>
        <p style={{ color: "#8899a6", margin: "0.35rem 0 0" }}>
          Decompose surge · flag unexplained residuals · RCA · graded remediation
        </p>
        {validation && (
          <p style={{ color: "#00ba7c", margin: "0.35rem 0 0", fontSize: "0.9rem" }}>
            Label accuracy: {validation.score}/{validation.total} ({(validation.accuracy * 100).toFixed(1)}%) on {validation.dataset || "seed"}
          </p>
        )}
        {dataset && (
          <p style={{ color: "#8899a6", margin: "0.35rem 0 0", fontSize: "0.85rem" }}>
            Dataset: {dataset.row_count} minutes · {dataset.time_range?.[0]?.slice(11, 16)}–{dataset.time_range?.[1]?.slice(11, 16)} UTC
            {currentTs && status === "replaying" && <span style={{ color: "#1d9bf0" }}> · now {currentTs}</span>}
            {replayProgress && status === "replaying" && (
              <span style={{ color: "#1d9bf0" }}> · {replayProgress.index}/{replayProgress.total}</span>
            )}
          </p>
        )}
      </header>

      <div className={`alert-banner ${activeAlerts.length ? "" : "calm"}`}>
        {activeAlerts.length === 0 ? (
          <span style={{ color: "#8899a6" }}>No active alerts on this minute — start replay to walk the timeline</span>
        ) : (
          activeAlerts.map((v) => (
            <div key={v.domain} className="alert-chip">
              <span className={`badge ${v.verdict}`}>{v.verdict.replace("_", " ")}</span>
              <strong>{v.domain}</strong>
              <span style={{ color: "#8899a6" }}>{v.z_score}σ · {(v.confidence * 100).toFixed(0)}%</span>
            </div>
          ))
        )}
      </div>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap", alignItems: "center" }}>
        <button onClick={startReplay} disabled={status === "replaying"}>
          {status === "replaying"
            ? `Replaying… ${replayProgress ? `${replayProgress.index}/${replayProgress.total}` : ""}`
            : `▶ Replay Championship Night (${dataset?.row_count ?? "…"} min)`}
        </button>
        <label style={{ fontSize: "0.85rem", color: "#8899a6" }}>
          Speed
          <input
            type="range"
            min={2}
            max={16}
            value={replaySpeed}
            onChange={(e) => setReplaySpeed(Number(e.target.value))}
            disabled={status === "replaying"}
            style={{ marginLeft: "0.5rem", verticalAlign: "middle", width: 100 }}
          />
          {replaySpeed}×
        </label>
        <button className="secondary" onClick={refresh}>Refresh</button>
        {incident && (
          <a href={`${API}/api/incidents/${incident.incident_id}/report`} target="_blank" rel="noreferrer">
            <button className="secondary" type="button">Export RCA (selected)</button>
          </a>
        )}
        <a href={`${API}/api/reports/remediation`} target="_blank" rel="noreferrer">
          <button className="secondary" type="button">Export Remediation Log</button>
        </a>
      </div>

      <div className="stats-row">
        <span><strong>{incidents.length}</strong> incidents</span>
        <span><strong>{actions.length}</strong> remediation actions</span>
        <span><strong>{keyIncidents.length}</strong> key (attack/combination)</span>
        {status === "complete" && <span style={{ color: "#00ba7c" }}>Replay complete — export RCA from incident tabs below</span>}
      </div>

      <div className="grid">
        <div className="card">
          <h3>Explained + Unexplained Residual</h3>
          {decomp.length === 0 && <p style={{ color: "#8899a6" }}>Start replay</p>}
          {decomp.map((d) => (
            <div key={d.domain} style={{ marginBottom: "0.75rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                <strong>{d.domain}</strong>
                <span className={`badge ${d.verdict}`}>{d.verdict}</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "#8899a6", marginTop: 4 }}>
                residual {d.residual >= 0 ? "+" : ""}{d.residual.toExponential(2)} · {d.z_score}σ
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3>Evidence Fusion Engine</h3>
          <FusionPanel fusion={fusion} />
        </div>
      </div>

      <div className="grid">
        <div className="card">
          <h3>Domain Verdicts</h3>
          {sortedVerdicts.length === 0 && <p style={{ color: "#8899a6" }}>Awaiting verdicts…</p>}
          {sortedVerdicts.map((v) => (
            <div key={v.domain} className={`verdict-row ${ALERT_VERDICTS.has(v.verdict) ? "alerting" : ""}`}>
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

        <div className="card">
          <h3>Live Timeline</h3>
          <div className="timeline">
            {timeline.length === 0 && <p style={{ color: "#8899a6" }}>Events appear here during replay</p>}
            {[...timeline].reverse().map((e) => (
              <div key={e.id} className="tl-entry">
                <span className="tl-time">{e.time}</span>
                <span className={`tl-type ${e.type}`}>{e.type}</span>
                <span className="tl-body">{e.body}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {incidents.length > 0 && (
        <div className="card">
          <h3>Incidents ({incidents.length}) — click to inspect · export RCA per incident</h3>
          <div className="incident-tabs">
            {incidents.map((inc, i) => {
              const isKey = keyIncidents.some((k) => k.incident_id === inc.incident_id);
              return (
                <button
                  key={inc.incident_id}
                  className={`${i === selectedInc ? "" : "secondary"} ${isKey ? "key" : ""}`.trim()}
                  type="button"
                  onClick={() => setSelectedInc(i)}
                >
                  {inc.started_at.slice(11, 16)}
                  {isKey ? " ★" : ""}
                </button>
              );
            })}
          </div>
          {incident && (
            <>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                <strong>{incident.incident_id}</strong>
                <span style={{ color: "#8899a6" }}>conf {(incident.confidence * 100).toFixed(0)}%</span>
                <a href={`${API}/api/incidents/${incident.incident_id}/report`} target="_blank" rel="noreferrer">
                  <button className="small secondary" type="button">Export this RCA</button>
                </a>
              </div>
              {(incident.mttr_detect_ms != null) && (
                <p style={{ fontSize: "0.85rem", color: "#00ba7c" }}>
                  MTTR: detect {incident.mttr_detect_ms.toFixed(1)}ms · RCA {(incident.mttr_rca_ms ?? 0).toFixed(1)}ms · mitigate {(incident.mttr_mitigate_ms ?? 0).toFixed(1)}ms
                </p>
              )}
              <h4>Root Causes</h4>
              {incident.roots.map((r, i) => (
                <div key={i} style={{ marginBottom: "0.75rem", padding: "0.6rem", background: "#0f1419", borderRadius: 6, fontSize: "0.9rem" }}>
                  <strong>{r.service}</strong> ({r.cause_class}) — {(r.confidence * 100).toFixed(0)}%
                  {r.file && <div>📁 {r.file}{r.function ? ` :: ${r.function}()` : ""}</div>}
                  <div style={{ color: "#8899a6", marginTop: 4 }}>{r.mechanism}</div>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      <div className="card">
        <h3>Remediation Ladder ({actions.length} proposed)</h3>
        {actions.length === 0 && (
          <p style={{ color: "#8899a6" }}>
            Actions appear when incidents fire. During replay they stream live; after replay use Refresh or wait for completion.
          </p>
        )}
        {uniqueActions.map((a) => (
          <div key={a.action_id} className="action-card">
            <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
              <div>
                <span className="grade">{a.grade}</span>
                <span style={{ color: "#8899a6" }}> → {a.target} · {a.state}</span>
                {a.blast_radius && <span style={{ fontSize: "0.75rem", color: "#8899a6" }}> · {a.blast_radius}</span>}
                <div style={{ fontSize: "0.85rem", marginTop: 4 }}>{a.reason}</div>
                <code>{a.proposed_command}</code>
              </div>
              {a.requires_approval && a.state === "proposed" && (
                <button className="small" onClick={() => approve(a.action_id)}>Approve</button>
              )}
            </div>
          </div>
        ))}
        {actions.length > 12 && (
          <p style={{ fontSize: "0.8rem", color: "#8899a6" }}>Showing 12 unique action types — Export Remediation Log for full audit trail.</p>
        )}
      </div>
    </div>
  );
}
