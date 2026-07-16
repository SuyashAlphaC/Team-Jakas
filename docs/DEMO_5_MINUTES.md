# Aperture — 5-Minute Demo Script

## Setup (30 sec)

```bash
cd context-aware-observability
docker compose up --build
```

Open **http://127.0.0.1:5173** → **Home** tab.

Optional: `curl -X POST http://localhost:8000/api/import` (backfill Grafana histograms).

---

## Act 1: The Problem (45 sec)

> "During a merch drop, traffic surges 5×. Traditional alerting fires on everything — checkout, auth, memory — causing alert fatigue. We can't tell: is this the event, an attack, or our own code breaking?"

Point to **Home** feature cards: context-aware CIS, causal RCA, risk-aware remediation, deterministic replay.

---

## Act 2: Context-Aware Decomposition (90 sec)

1. Click **Start 240-min Replay** (or go to **Live Monitor** tab)
2. Set speed **6×**
3. Watch **Timeline** or Monitor alert banner at **20:14–20:15**
4. Transaction domain: **expected** (green) — 5× surge explained by context multiplier
5. **Analysis** tab → fusion headline shows SUPPRESS

> "We decompose observed = baseline + context effect + residual. Residual within 3σ → suppress."

---

## Act 3: Attack + Stack-Trace Localization (90 sec)

1. At **20:16**, security flips to **attack**; process to **internal_fault**
2. **Incidents & RCA** tab → open ★ COMBINATION incident
3. Show **Parsed from stack trace** chip on root cards:
   - `services/payment-svc/retry.py:14 :: process_payment()`
   - `services/identity-svc/memory_leak.py:9 :: authenticate()`
4. Expand causal graph + reasoning chain
5. **Export RCA** (nav link or API) — diff patches in Markdown

> "Production stack trace parsed into file:line roots — not just metrics, actual code paths."

---

## Act 4: Grafana + Alerting (45 sec)

1. Open **Grafana** tab (embedded dashboard)
2. Start or continue replay — **Live Domain Utilization** panel updates
3. **Dotted vertical bars** appear at alert minutes (attack, combination)
4. **Alerting → Alert rules** — rules fire on model predictions

> "Same pipeline feeds Prometheus → Grafana alerting. Model verdicts drive rules — no separate alert config."

---

## Act 5: Graded Remediation + MTTR (45 sec)

1. **Remediation** tab — observe → rate-limit → restart ladder
2. Click **Approve** on a proposed action (state → executing)
3. Point to MTTR on incident card (detect ~ms, RCA ~ms)
4. Mention hash-chained audit ledger (`GET /api/audit`)

> "Human-in-the-loop for high blast-radius actions; sub-second detect vs hours manually."

---

## Act 6: Close (30 sec)

> "Aperture: explain legitimate surges, catch attacks in the noise, **parse stack traces into code fixes**, propose safe graded remediation — with a live tabbed dashboard. **100% label accuracy** on our canonical seed."

**Demo:** http://127.0.0.1:5173 · **Source:** https://github.com/SuyashAlphaC/Team-Jakas

---

## Tab cheat sheet

| Tab | Show judges |
|-----|-------------|
| Home | Problem statement + one-click replay |
| Live Monitor | Residuals, verdicts, alert banner |
| Analysis | Fusion + ML evidence |
| Incidents & RCA | Stack traces, causal graph, MTTR |
| Remediation | Approve flow |
| Timeline | Full autonomous event log |
| Grafana | Histograms + alert markers |

## Golden window

**20:14–20:19 UTC** — COMBINATION at **20:16** ★

Stack traces: `fixtures/stack_traces.json`
