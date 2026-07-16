import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ALERT_VERDICTS, API, verdictRank } from "../lib/helpers";
import type {
  Action,
  DatasetInfo,
  Decomp,
  Fusion,
  Incident,
  TabId,
  TimelineEntry,
  Validation,
  Verdict,
} from "../types";

export function useObservability() {
  const [tab, setTab] = useState<TabId>("home");
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [decomp, setDecomp] = useState<Decomp[]>([]);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [fusion, setFusion] = useState<Fusion | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedInc, setSelectedInc] = useState(-1);
  const [actions, setActions] = useState<Action[]>([]);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [replayProgress, setReplayProgress] = useState<{ index: number; total: number } | null>(null);
  const [replaySpeed, setReplaySpeed] = useState(6);
  const [status, setStatus] = useState("idle");
  const [currentTs, setCurrentTs] = useState("");
  const [approveError, setApproveError] = useState<string | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const actionIds = useRef(new Set<string>());

  const refresh = useCallback(async () => {
    try {
      const [incRes, actRes, valRes] = await Promise.all([
        fetch(`${API}/api/incidents`),
        fetch(`${API}/api/actions`),
        fetch(`${API}/api/validation`),
      ]);
      const inc = incRes.ok ? await incRes.json() : [];
      const act = actRes.ok ? await actRes.json() : [];
      const val = valRes.ok ? await valRes.json() : null;
      setIncidents(Array.isArray(inc) ? inc : []);
      if (Array.isArray(act)) {
        setActions(act);
        act.forEach((a: Action) => actionIds.current.add(a.action_id));
      }
      if (val && typeof val.accuracy === "number") setValidation(val);
    } catch {
      /* backend starting */
    }
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
        .then((r) => (r.ok ? r.json() : []))
        .then((act: Action[]) => {
          if (!Array.isArray(act)) return;
          setActions((prev) => {
            const byId = new Map(prev.map((a) => [a.action_id, a]));
            for (const a of act) {
              byId.set(a.action_id, a);
              actionIds.current.add(a.action_id);
            }
            return [...byId.values()];
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
    if (actionIds.current.has(a.action_id)) {
      setActions((prev) => prev.map((x) => (x.action_id === a.action_id ? a : x)));
      return;
    }
    actionIds.current.add(a.action_id);
    setActions((prev) => [...prev, a]);
  };

  const startReplay = async () => {
    setTab("monitor");
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
    setApproveError(null);
    setApprovingId(id);
    try {
      const res = await fetch(`${API}/api/actions/${encodeURIComponent(id)}/advance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approve: true }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `Approve failed (${res.status})`);
      }
      const updated = (await res.json()) as Action;
      setActions((prev) => prev.map((a) => (a.action_id === id ? updated : a)));
      await refresh();
    } catch (err) {
      setApproveError(err instanceof Error ? err.message : "Could not approve action");
    } finally {
      setApprovingId(null);
    }
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
    () =>
      incidents.filter((inc) =>
        inc.symptoms.some((s) => /COMBINATION|attack|Attack|ATTACK/i.test(s)) ||
        inc.roots.some((r) => r.cause_class === "malicious"),
      ),
    [incidents],
  );

  const incident = incidents[selectedInc >= 0 ? selectedInc : incidents.length - 1];

  const uniqueActions = useMemo(() => {
    const seen = new Map<string, Action>();
    for (const a of actions) {
      const key = `${a.grade}:${a.target}:${a.proposed_command}`;
      seen.set(key, a);
    }
    return [...seen.values()].slice(-20);
  }, [actions]);

  return {
    tab,
    setTab,
    timeline,
    decomp,
    verdicts,
    fusion,
    incidents,
    selectedInc,
    setSelectedInc,
    actions,
    validation,
    dataset,
    replayProgress,
    replaySpeed,
    setReplaySpeed,
    status,
    currentTs,
    sortedVerdicts,
    activeAlerts,
    keyIncidents,
    incident,
    uniqueActions,
    startReplay,
    refresh,
    approve,
    approveError,
    approvingId,
  };
}
