"""Phase A harvester: one serialized pass over everything shoovy.wtf serves
without a session. Saves raw bytes to raw/ so all analysis afterwards costs
zero requests.

Every request is logged by client.py into requests.jsonl.

Aborts on the first 429 and records where it stopped; rerunning skips whatever
is already on disk, so a blocked run resumes instead of refetching.

    python harvest.py
"""
import os, sys
import client

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")

# Pages carry the client-side game logic and constants. The public API endpoints
# carry the live economy. Both are free to read.
TARGETS = [
    "/", "/updates", "/commands", "/fishing", "/stocks", "/casino",
    "/games", "/crime", "/business", "/shop", "/raffles", "/stats",
    "/static/nav.js?v=3", "/static/theme.css?v=3",
    "/api/me", "/api/fishing", "/api/stocks", "/api/stocks/history",
    "/api/leaderboard", "/api/leaderboards", "/api/updates", "/api/feed",
    "/api/games/info", "/api/casino/lobby", "/api/business", "/api/crime",
    "/api/shop", "/api/raffles", "/api/stats", "/api/rakeback",
]


def slug(path):
    s = path.strip("/").replace("/", "_").split("?")[0]
    return (s or "index") + (".json" if path.startswith("/api/") else ".txt")


def main():
    os.makedirs(RAW, exist_ok=True)
    todo = [p for p in TARGETS if not os.path.exists(os.path.join(RAW, slug(p)))]
    print(f"{len(todo)}/{len(TARGETS)} a recuperer, gap={client.GAP_SECONDS}s "
          f"(~{len(todo) * client.GAP_SECONDS / 60:.0f} min)", flush=True)

    done = 0
    for path in todo:
        status, body, _ = client.get(path)
        print(f"  {path:26} HTTP {status}  {len(body):>7}o", flush=True)

        if status == 429:
            print(f"\n429 apres {done} succes. Arret, relance plus tard.", flush=True)
            return 1
        if status == 200:
            with open(os.path.join(RAW, slug(path)), "wb") as f:
                f.write(body)
            done += 1

    print(f"\n{done}/{len(todo)} recuperes dans {RAW}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
