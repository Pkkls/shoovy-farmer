# Per-streamer Shoovy analysis — parameterized

shoovy.wtf is one backend serving many streamer channels ("adaptable to any streamer, just
change the channel id"). This prompt runs the full economy + rank-1 analysis for ONE streamer.
You fill in the streamer; the analysis is scoped to that channel. **Never hardcode a streamer
name anywhere** — it is always the parameter below.

## Parameter (the operator provides this)

    STREAMER = <<STREAMER>>

If `<<STREAMER>>` is still a placeholder, stop and say the streamer was not provided.

## Absolute rules
- All requests go through the disciplined shared client, never raw curl/fetch in a loop:
  `shoovy-farmer/client` (package `shoovyclient`) or its CLI `shoovyreq`
  (`shoovyreq.exe` on PC, `shoovyreq-riscv64` on the Claw). It paces, backs off on 429/502,
  and logs every call. This is what stops an exploration loop from becoming a rate-limited burst.
- Never retry into a 429/502. One request, read, stop. Single client, requests spaced ≥3 s.
- Never hardcode a streamer; never login or enter credentials. Public endpoints only unless a
  valid session for THIS streamer is supplied.
- English output. Every number cites its source. Token-economical: derive with code over the
  saved bodies, never dump raw JSON into context.

## Step 0 — discover how the channel is selected (do this once, record it)
The captured recon never used a channel parameter, so the mechanism is unconfirmed. Determine it
empirically with at most 3 spaced probes via `shoovyreq`:
1. Baseline: `shoovyreq /api/leaderboard` → note the `channel` field in the response.
2. Query param: `shoovyreq -channel STREAMER /api/leaderboard` → did `channel` switch to STREAMER?
3. If not, try a subdomain (`https://STREAMER.shoovy.wtf/api/leaderboard`) or a header, one probe.
Record the working mechanism as a fact; every later call uses it. If none switches the channel,
the deployment may be single-channel right now — say so and analyze the default channel, noting
the limitation.

## Step 1 — pull this streamer's public data (through the client)
Into `data/study/streamers/STREAMER/<today>/`, one spaced request each:
- `/api/leaderboard` (this streamer's rank-1 target + top balances)
- `/api/stocks` (market: tickers, fee, depth) and `/api/games/info` (casino odds: rtp/payout/multiplier)
- `/api/fishing` (species, decay), `/api/stats` if public
Skip anything that 429s; the client is now in backoff, come back next run.

## Step 2 — analyze (offline, from the saved bodies)
- Rank-1 target for STREAMER: the #1 balance, and the net credits/day to catch it in 30 / 90 days.
- Mechanic economics for this channel: fishing catch value & cadence, market fee/depth,
  and casino EV per game computed from THIS channel's `games_info` odds. Flag any positive-EV
  game or where rakeback covers the house edge.
- Best earning loop for STREAMER, and whether the leaderboard is reachable at realistic rates.

## Step 3 — availability context
Availability is a property of the shared Railway backend, not of one channel, so the Claw
sentinel's `/root/shoovy/avail.jsonl` applies to every streamer. Read it (via ssh) rather than
probing again. If the backend is in a down window, note it and keep the analysis offline.

## Step 4 — report
Write `reports/streamers/STREAMER/<today>.md`: one-line verdict, channel mechanism, rank-1
target, mechanic economics, casino EV table, best loop, and the blocker (farming needs valid
sessions for STREAMER — a human login this prompt will not do). Match the sourced, layered voice
of `reports/ANALYSE_complete_recursive.md`.

## Done
Print the report path, STREAMER's rank-1 target, and whether the site was reachable this run.
Do not loop; you are invoked per streamer, on demand.
