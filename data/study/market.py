"""Constant market collector.

Polls the public market endpoint on a fixed cadence and appends every successful
snapshot to market.jsonl. Two things come out of it:

  the series   quotes over time are the only way to evaluate the mean-reversion
               strategy without placing a single live trade. /api/stocks/history
               gives a window; this gives everything from now on, at our own
               resolution, and it keeps accruing while the site is unusable.

  availability every attempt goes through client.py, so the request log gets a
               steady unbiased sample instead of the bursty one the harvest
               driver produces. The uptime figure gets better for free.

It also grabs /api/stocks/history once, on the first attempt that succeeds,
because that is the backtest's cold start and it only needs fetching once.

Single instance enforced: two collectors would double our load against a backend
that is already answering about one call in six, and that mistake has been made
once in this study already.

    python market.py [--interval 30]
"""
import json, os, signal, sys, time

import client

HERE = os.path.dirname(os.path.abspath(__file__))
SERIES = os.path.join(HERE, "market.jsonl")
HISTORY = os.path.join(HERE, "raw", "api_stocks_history.json")
LOCK = os.path.join(HERE, "market.pid")

DEFAULT_INTERVAL = 30.0


def _alive(pid):
    try:
        os.kill(pid, 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def take_lock():
    if os.path.exists(LOCK):
        try:
            old = int(open(LOCK).read().strip())
        except (ValueError, OSError):
            old = None
        if old and _alive(old):
            print(f"un collecteur tourne deja (pid {old}) — abandon")
            return False
        print(f"verrou perime (pid {old}) — reprise")
    with open(LOCK, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def snapshot(body):
    """Keep the quote series small and regular; news is kept whole because a
    headline names the event that moved a price, which is the causal half."""
    d = json.loads(body.decode("utf-8"))
    return {
        "ts": int(time.time()),
        "quotes": {q["symbol"]: {"price": q.get("price"),
                                 "change_pct": q.get("change_pct"),
                                 "day_low": q.get("day_low"),
                                 "day_high": q.get("day_high"),
                                 "volume": q.get("volume")}
                   for q in d.get("quotes", [])},
        "trading_enabled": d.get("trading_enabled"),
        "fee_pct": d.get("fee_pct"),
        "depth": d.get("depth"),
        "news": d.get("news", [])[:5],
    }


def fetch_history_once():
    if os.path.exists(HISTORY):
        return
    try:
        status, body, _ = client.get("/api/stocks/history")
    except Exception as e:
        print(f"  history: {type(e).__name__}", flush=True)
        return
    if status == 200:
        os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
        with open(HISTORY, "wb") as f:
            f.write(body)
        print(f"  history capture: {len(body)} octets", flush=True)
    else:
        print(f"  history: HTTP {status}", flush=True)


def main():
    interval = DEFAULT_INTERVAL
    if "--interval" in sys.argv:
        interval = float(sys.argv[sys.argv.index("--interval") + 1])

    if not take_lock():
        return 2
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda *_: (release_lock(), sys.exit(0)))
        except (ValueError, OSError):
            pass

    print(f"collecteur marche demarre, 1 appel / {interval:.0f}s", flush=True)
    ok = fail = 0
    try:
        while True:
            try:
                status, body, _ = client.get("/api/stocks")
            except Exception as e:
                fail += 1
                print(f"{time.strftime('%H:%M:%S')}  {type(e).__name__}  "
                      f"(ok={ok} fail={fail})", flush=True)
                time.sleep(interval)
                continue

            if status == 200:
                try:
                    snap = snapshot(body)
                except (ValueError, KeyError) as e:
                    print(f"{time.strftime('%H:%M:%S')}  200 mais illisible: {e}",
                          flush=True)
                    time.sleep(interval)
                    continue
                with open(SERIES, "a", encoding="utf-8") as f:
                    f.write(json.dumps(snap, ensure_ascii=False) + "\n")
                ok += 1
                prices = " ".join(f"{s}={v['price']}"
                                  for s, v in sorted(snap["quotes"].items()))
                print(f"{time.strftime('%H:%M:%S')}  200  {prices}  "
                      f"(ok={ok} fail={fail})", flush=True)
                fetch_history_once()
            else:
                fail += 1
                print(f"{time.strftime('%H:%M:%S')}  {status}  "
                      f"(ok={ok} fail={fail})", flush=True)

            time.sleep(interval)
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
