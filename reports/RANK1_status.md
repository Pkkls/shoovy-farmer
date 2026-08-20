# Rank-1 status (living doc, updated by the /loop)

Goal: reach rank 1 on shoovy.wtf. This doc is the current state of that pursuit; the dated
files in this folder are the day-by-day analysis, `ANALYSE_complete_recursive.md` is the model.

## Layer 0 flipped: the site is UP (2026-08-20 ~00:28 UTC)

Measured from the Claw sentinel and from the PC: `GET /api/stocks` → 200, ~0.6–1.8 s,
5 tickers, `up:true`. Yesterday's 429/502 was a transient sick-deployment window, not a ban
(consistent with the refuted ban hypothesis). Availability is now being sampled continuously
so we stop guessing — see the sentinel below.

## Deployed to the Claw (192.168.1.59, riscv64)

`shoovy-sentinel` — a gentle 24/7 availability probe. One `GET /api/stocks` every 5 min,
60 s timeout (cold start is ~40 s), single request, **never retries into a 429**. Appends one
JSONL line per probe to `/root/shoovy/avail.jsonl`. This is the Layer-0 gate: it tells us when
the site is servable without any manual probing, and it survives reboot via
`/etc/init.d/S99shoovysentinel` (mirrors the clawd pattern). Source: `sentinel/main.go`,
cross-compiled static to riscv64, zero dependencies.

Read the availability history any time:
`ssh claw 'tail /root/shoovy/avail.jsonl'`.

## Fresh captures banked while up (`data/study/live/2026-08-20/`)

- **`games_info.json`** — the big one. `/api/games/info` now carries the casino **odds**
  (`rtp`, `payout`, `multiplier`, `plinko_tables`, `keno`, `dragon`, `cases`, `wheel`,
  `coinflip_multiplier`, `rps_multiplier`, `crash_history`). This flips the casino from
  "EV not computable offline" to **computable** — the next offline analysis step.
- **`leaderboard.json`** — target moved: rank 1 = **Mackie33 886,890**, rank 2 = 408,722,
  rank 3 = 211,910. The number to beat is ~887k and climbing.
- **`fishing.json`** — species/decay, for a fresh catch-value re-sample.

## The path, and the honest blocker

The earning loop the analysis trusts is fishing + daily + tips into one account. At full
availability, fishing alone (~19 casts/h × ~210 cr) clears even the aggressive catch-up pace.
The market (1 % fee) is near break-even; the casino is a bonus only if `games_info` odds show a
positive-EV game or the rakeback covers the edge — that is the next thing to compute.

**Blocker for actual farming**: it needs valid `shoovy_session` + Kick cookies per worker
account, and those are ~1 month expired (`accounts.json` absent). Getting them requires a human
login (Kick + shoovy "Log in with Kick") — I cannot and will not do that step. Until fresh
cookies exist, the loop advances the analysis and monitors availability; it cannot accumulate
credits.

## What the loop does next (no human needed)

1. Confirm the sentinel is looping cleanly (avail.jsonl gains ~1 line/5 min, not per-restart).
2. Compute casino EV per game from `games_info.json` — pure offline, "analyse tout ce qui est
   possible". Flag any positive-EV surface (rare, but rakeback can tip it).
3. Re-sample fishing catch value to kill the n=2.
4. Keep reading Claw availability; when the site's uptime looks stable, that is the signal to
   ask the operator for fresh sessions and start the farm.

## What needs the operator

Fresh worker + main account sessions (Kick + shoovy cookies), dropped into
`shoovy-farmer/accounts.json`. That single unblock turns the whole thing on.
