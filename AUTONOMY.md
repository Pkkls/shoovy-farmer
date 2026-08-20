# Autonomy

This repo runs itself. The goal is rank 1 on shoovy.wtf; the constraint is that the game's
backend (Railway) goes unhealthy in windows (429 "rate limited" / 502), so the whole system is
built around **measuring availability and never hammering a sick backend**. Everything below is
self-contained and reproducible.

## The pieces

| Piece | What it is | Runs where |
|---|---|---|
| `sentinel/` | A gentle 24/7 availability probe: one `GET /api/stocks` every 5 min, 60 s timeout (cold start ~40 s), single request, **never retries into a 429**. Appends `avail.jsonl`. | A RISC-V SBC, 24/7, restarted at boot by an `S99` init script. Pure stdlib, cross-compiles static to `riscv64`. |
| `client/` | `shoovyclient` — the one HTTP client every request goes through: serialized (one in flight), global min-gap spacing, exponential backoff on 429/502 with **no per-call retry**, optional TTL cache, one JSONL audit line per call. CLI: `shoovyreq`. | Imported by the bots; CLI on PC or the board. |
| `reports/` | The analysis. `ANALYSE_complete_recursive.md` is the 5-layer model (infra → availability → mechanics → economics → target). `RANK1_status.md` is the living status. `YYYY-MM-DD.md` are daily organic deltas. `streamers/<name>/` are per-streamer analyses. | Generated locally / by the daily task. |
| `PROMPT_streamer_analysis.md` | Parameterized analysis for one streamer's channel (shoovy is multi-channel). You supply the streamer; it scopes the analysis. Never hardcodes a name. | On demand. |
| `PROMPT_daily_autonomy.md` | The full daily cycle prompt: read availability, capture when up, advance the analysis, write the report, gate farming on valid sessions. | A daily scheduled task, also triggerable on demand. |
| `data/study/` | The captured corpus (anonymous, public): raw endpoint bodies, the typed fact store, chat/market logs, analysis scripts. Analysis costs zero further requests. | — |

## The rules that make it safe unattended

- **Availability, not request budget, is the scarce resource.** Pacing buys none of it. One
  shared client with a global budget; never three independent pollers.
- **Never retry into a 429/502.** One request, read, stop. The `client` enforces this: a 429
  sets backoff and the *next* call waits it out; a single call is never retried.
- **Never login or handle credentials.** Farming needs valid sessions; obtaining them is a human
  step. Until `accounts.json` (gitignored) exists, the system analyzes and monitors, never farms.
- **Never hardcode a streamer.** The channel is always a parameter.

## Build

    # the availability sentinel, static for a riscv64 board
    cd sentinel && CGO_ENABLED=0 GOOS=linux GOARCH=riscv64 go build -trimpath -ldflags="-s -w" -o shoovy-sentinel-riscv64 .

    # the shared client + CLI (host arch, or add GOOS/GOARCH for the board)
    cd client && go test ./... && go build -o shoovyreq ./cmd/shoovyreq

Binaries are gitignored on purpose — rebuild them; the source is the source of truth.

## Deploy the sentinel (board)

Copy `shoovy-sentinel-riscv64` to the board (e.g. `/root/shoovy/`), then install an init script
that starts it detached at boot and its own loop keeps it alive:

    #!/bin/sh
    # /etc/init.d/S99shoovysentinel  (busybox init runs S99* at boot)
    case "$1" in
      start|"") cd /root/shoovy && setsid ./shoovy-sentinel-riscv64 300 >>sentinel.out 2>&1 </dev/null & ;;
      stop) killall shoovy-sentinel-riscv64 2>/dev/null ;;
    esac

Read availability any time: `tail /root/shoovy/avail.jsonl`.
(Busybox notes: `ps` truncates names to 15 chars; use `killall`, not `pkill`; detach with `setsid`.)

## Trigger

The daily cycle runs on a schedule and on demand. Point it at `PROMPT_daily_autonomy.md`.
For a single streamer, fill `PROMPT_streamer_analysis.md` with the streamer and run it.
