"""How much of the time is the backend actually usable?

Every request the study makes is already logged, and the harvest driver samples
the site continuously while it retries. So availability can be derived from
requests.jsonl at no extra cost in requests.

This is a first-order input to the whole plan, not a footnote: a 24/7 tool built
on a backend that answers a fifth of the time is a different design from one
built on a backend that answers reliably. It also bounds how fast the study can
possibly gather anything.

    python uptime.py
"""
import collections, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "requests.jsonl")

# 200 is usable. 429 and 502 are the two faces of the outage. A transport error
# (recorded with "error" and no "http") is counted as unusable too: from the
# caller's side a timeout and a 502 cost the same.
def classify(row):
    if "http" not in row:
        return "error"
    code = row["http"]
    if code == 200:
        return "ok"
    if code == 429:
        return "429"
    if 500 <= code < 600:
        return "5xx"
    return f"{code}"


def main():
    if not os.path.exists(LOG):
        print("pas de log")
        return 1
    rows = [json.loads(l) for l in open(LOG, encoding="utf-8")]
    rows = [r for r in rows if "shoovy.wtf" in r.get("url", "")]
    if not rows:
        print("aucune requete shoovy dans le log")
        return 1

    counts = collections.Counter(classify(r) for r in rows)
    total = sum(counts.values())
    span = rows[-1]["ts"] - rows[0]["ts"]

    print(f"{total} requetes sur {span/3600:.2f} h "
          f"({time.strftime('%H:%M', time.localtime(rows[0]['ts']))} -> "
          f"{time.strftime('%H:%M', time.localtime(rows[-1]['ts']))})\n")
    for k, n in counts.most_common():
        print(f"  {k:6} {n:4}  {n/total*100:5.1f}%")
    print(f"\n  utilisable: {counts['ok']/total*100:.1f}%")

    # Longest run of consecutive usable answers: that is the window a harvest
    # pass actually has to work with.
    best = run = 0
    for r in rows:
        run = run + 1 if classify(r) == "ok" else 0
        best = max(best, run)
    print(f"  plus longue serie de reponses utilisables: {best}")

    # Per-hour breakdown, so a pattern (e.g. recovery windows) can show up.
    by_hour = collections.defaultdict(collections.Counter)
    for r in rows:
        by_hour[time.strftime("%H", time.localtime(r["ts"]))][classify(r)] += 1
    if len(by_hour) > 1:
        print("\n  par heure:")
        for h in sorted(by_hour):
            c = by_hour[h]
            t = sum(c.values())
            print(f"    {h}h  n={t:3}  ok={c['ok']/t*100:5.1f}%  "
                  f"429={c['429']/t*100:5.1f}%  5xx={c['5xx']/t*100:5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
