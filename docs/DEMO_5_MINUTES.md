# 5-Minute Demo Script

## Setup (30 sec)
1. `docker compose up --build`
2. Open http://127.0.0.1:5173

## Act 1: The Problem (45 sec)
> "During a merch drop, traffic surges 5×. Traditional alerting fires on everything — checkout, auth, memory — causing alert fatigue. We can't tell: is this the event, an attack, or our own code breaking?"

## Act 2: Context-Aware Decomposition (90 sec)
1. Click **Replay Secret Seed**
2. Point to timeline: ingress event at 20:14
3. Show transaction domain verdict: **expected** (green) — 5× surge explained by context multiplier
4. "We decompose observed = baseline + context effect + residual. Residual within 3σ → suppress."

## Act 3: Attack During Event (90 sec)
1. Watch security verdict flip to **attack** at 20:16
2. "54% auth failure rate with no identity context scope — credential stuffing during the merch drop."
3. Show RCA panel: service → identity → validate_credentials
4. Proposed fix: rate-limit + WAF block
5. "This is DDoS-during-match — we scale fans AND block attackers."

## Act 4: Self-Inflicted Cascade (60 sec)
1. Process verdict: **internal_fault** — heap growth 1.2 MB/min
2. Code localization: `memory_leak.py :: authenticate`
3. Transaction errors suggest retry storm → `payment-svc/retry.py` MAX_RETRIES=999
4. "Symptom storm collapsed to two roots: attack + memory leak."

## Act 5: Graded Remediation + MTTR (45 sec)
1. Show proposed actions: rate-limit (attack), restart (process)
2. Approve one action — human-in-loop
3. MTTR: detect ~40ms, RCA ~60ms — "hours → seconds"
4. Audit ledger: hash-chained, tamper-evident

## Close (30 sec)
> "Context-aware observability: explain legitimate surges, catch attacks in the noise, localize code bugs, propose safe fixes — all in one autonomous pipeline."
