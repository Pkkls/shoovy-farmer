"""Characterise what shoovy.wtf is actually doing right now.

We have seen three different answers within minutes: 200, 429 ("rate limited",
served by the Railway edge) and 502 (Cloudflare, origin down). Before treating
the 429 as a rate limiter aimed at us, establish whether it simply tracks the
site being unhealthy.

Samples one endpoint on a fixed cadence and records the status distribution.
Every request lands in requests.jsonl via client.py.

    python availability.py [samples]
"""
import collections, sys, time
import client


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    seen = collections.Counter()
    print(f"{n} echantillons, 1 toutes les {client.GAP_SECONDS:.0f}s "
          f"(~{n * client.GAP_SECONDS / 60:.0f} min)", flush=True)

    for i in range(n):
        try:
            status, body, _ = client.get("/api/me")
            snippet = body[:60].decode("utf-8", "replace").replace("\n", " ")
        except Exception as e:
            status, snippet = f"ERR:{type(e).__name__}", str(e)[:60]
        seen[status] += 1
        print(f"  {time.strftime('%H:%M:%S')}  #{i+1:<3} {status}  {snippet}",
              flush=True)

    print("\ndistribution:", dict(seen), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
