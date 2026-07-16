import { PageHeader } from "../components/PageHeader";
import type { ObservabilityState } from "../types";

export function RemediationPage({ obs }: { obs: ObservabilityState }) {
  const { uniqueActions, approve, actions, approveError, approvingId } = obs;

  return (
    <div className="page remediation-page">
      <PageHeader
        title="Remediation Ladder"
        subtitle="Risk-ranked actions · observe → rate-limit → throttle → restart → rollback"
      />

      {approveError && (
        <div className="alert-banner alert-active anim-fade-in" role="alert">
          <span className="alert-chip">Approve failed: {approveError}</span>
        </div>
      )}

      {uniqueActions.length === 0 ? (
        <div className="empty-state anim-fade-in">
          <span className="empty-icon">⛊</span>
          <p>Actions appear when incidents fire during replay</p>
        </div>
      ) : (
        <div className="action-ladder">
          {uniqueActions.map((a, i) => (
            <div key={a.action_id} className="action-card anim-slide-up" style={{ animationDelay: `${i * 50}ms` }}>
              <div className="action-head">
                <span className="grade">{a.grade}</span>
                <span className="muted">→ {a.target}</span>
                <span className={`state-badge state-${a.state}`}>{a.state}</span>
                {a.risk_score != null && <span className="risk-tag">risk {(a.risk_score * 100).toFixed(0)}%</span>}
              </div>
              <p className="text-sm">{a.reason}</p>
              {a.blast_radius && <p className="muted text-sm">{a.blast_radius}</p>}
              {a.verification_criteria && <p className="verify text-sm">Verify: {a.verification_criteria}</p>}
              <code>{a.proposed_command}</code>
              {a.requires_approval && a.state === "proposed" && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={approvingId === a.action_id}
                  onClick={() => void approve(a.action_id)}
                >
                  {approvingId === a.action_id ? "Approving…" : "Approve"}
                </button>
              )}
              {a.state !== "proposed" && (
                <span className="chip chip-ml">State: {a.state.replace("_", " ")}</span>
              )}
            </div>
          ))}
        </div>
      )}
      {actions.length > 20 && (
        <p className="muted text-sm">Showing 20 unique actions — export remediation log for full audit.</p>
      )}
    </div>
  );
}
