# Shoovy Farmer (PC edition)

A small set of bots that farm and consolidate virtual credits on **shoovy.wtf** (a streamer's
channel-points game), running 24/7 on a single **Windows PC**. No servers, no boards, nothing
to rent. You fill in your accounts once, run one installer, and it keeps going in the background.

**New here? Follow [TUTORIAL.md](TUTORIAL.md) step by step.** It assumes zero experience.

> [!WARNING]
> These are virtual game credits with no real-world value. Automating a chat game and running
> several accounts may break the site's or Kick's rules and can get accounts **timed out or
> banned**. This is a personal / educational project, provided as-is, no warranty. Use at your
> own risk.

---

## What it does

| Bot | Job |
|-----|-----|
| **fisher** | Casts `!fish` in chat on each worker account, on the real game cooldown, spread out so accounts never post at the same time. Strong anti-spam guards. |
| **econ** | Claims the free `!daily` and sends each worker's spare credits to your **main account** with `!tip`, at most once every 36 hours (discreet). |
| **trader** | Mean-reversion bot for the in-game stock market. **Ships in PAPER mode** (it only logs the trades it *would* make). Turn it live only when you trust it. Advanced, optional. |
| **collector** | Logs market prices + events to `data/` so you can study/backtest the market. Passive, harmless. |
| **watchdog** | Safety guard. If any bot ever starts spamming, it logs an alert and hits the kill-switch automatically. |
| **dashboard** | A local web page (`http://127.0.0.1:8088`) showing balances, the main account total, live trades/PnL, and a big **STOP** button. |
| **supervisor** | Starts all of the above, restarts anything that crashes, and honors the STOP button. This is what runs at Windows startup. |

Your **main account** only ever *receives* tips. No bot posts or trades on it.

Want to understand how it all works (the market, the strategy, the safety design, and the story
of a spam bug and its fix)? Read **[ARCHITECTURE.md](ARCHITECTURE.md)** — it documents everything.

---

## Requirements

- Windows 10 or 11.
- [Go](https://go.dev/dl/) installed (free, one download) to build the bots once.
- One or more Kick accounts logged into shoovy.wtf.

## Install (short version)

Full walkthrough with screenshots-level detail is in **[TUTORIAL.md](TUTORIAL.md)**. In short:

1. Install Go, download this repo.
2. Double-click **`build.bat`** (builds the bots into `bin\`).
3. Copy `accounts.example.json` to `accounts.json` and paste your accounts' cookies into it.
4. Set your main account name in `econ.config.json` and `dashboard.config.json`, and your
   worker account names in `fisher.config.json` / `econ.config.json`.
5. Double-click **`install-startup.bat`** — it starts everything now and every time you log in.
6. Open **http://127.0.0.1:8088** to watch it.

Stop it any time with the STOP button on the dashboard, or `stop.bat`. Resume with `start.bat`.

---

## Files

```
build.bat            Build all bots into bin\
install-startup.bat  Run the bots now + every time you log in (background)
uninstall-startup.bat Remove the auto-start
run.bat              Run once in the foreground (for testing, shows a console)
stop.bat / start.bat Stop / resume the bots (kill-switch)
accounts.example.json  Template for your credentials (copy to accounts.json)
*.config.json        Settings for each bot (channel is preset for shoovy)
fisher/ econ/ watchdog/ dashboard/ supervisor/   Go source of each bot
data/                Logs, state, stop flag (created at runtime)
```

Nothing is committed with your credentials in it: `accounts.json`, `data/`, and `bin/` are
gitignored.
