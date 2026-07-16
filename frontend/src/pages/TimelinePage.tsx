import type { ObservabilityState } from "../types";

export function TimelinePage({ obs }: { obs: ObservabilityState }) {
  const { timeline } = obs;

  return (
    <div className="page timeline-page">
      <div className="page-header anim-fade-in">
        <h2>Live Timeline</h2>
        <p className="muted">SSE event stream — fusion, incidents, actions, suppressions</p>
      </div>

      <div className="card timeline-card anim-slide-up">
        {timeline.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">▤</span>
            <p>Events appear here during replay</p>
          </div>
        ) : (
          <div className="timeline">
            {[...timeline].reverse().map((e, i) => (
              <div key={e.id} className={`tl-entry anim-fade-in tl-${e.severity ?? "info"}`} style={{ animationDelay: `${Math.min(i * 30, 300)}ms` }}>
                <span className="tl-time">{e.time}</span>
                <span className={`tl-type ${e.type}`}>{e.type}</span>
                <span className="tl-body">{e.body}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
