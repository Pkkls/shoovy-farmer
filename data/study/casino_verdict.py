"""Settle the casino question from the server's own numbers.

The page turned out to be a rendering engine with no odds in it, so this waited
on two captures: /api/games/info for the payout tables and /api/rakeback for the
rebate. Both are now in raw/, so the question is arithmetic.

The question was never "is the casino fun". A casino game is negative expectancy
by construction; the only thing that could put it in the plan is a rebate larger
than the edge. So: compute each game's return to player from the tables the
server itself hands the client, and compare the shortfall against the rakeback.

    python casino_verdict.py
"""
import collections, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")


def load():
    with open(os.path.join(RAW, "api_games_info.json"), encoding="utf-8") as f:
        info = json.load(f)
    with open(os.path.join(RAW, "api_rakeback.json"), encoding="utf-8") as f:
        rb = json.load(f)
    return info, rb


def plinko_rtp(mults):
    """A ball takes n independent left/right hops, so the landing slot is
    binomial(n, 1/2). RTP is the multiplier table weighted by that."""
    n = len(mults) - 1
    return sum(math.comb(n, k) / 2 ** n * mults[k] for k in range(n + 1))


def wheel_rtp(layout, payouts):
    """Each segment is equally likely. Betting a category wins when the wheel
    stops on one of that category's segments."""
    counts = collections.Counter(layout)
    total = len(layout)
    return {cat: (counts[cat] / total) * pay
            for cat, pay in payouts.items() if cat in counts}


def verdicts(info, rb):
    rate = rb["rate_pct"] / 100.0
    out = []

    # Binary games: the multiplier is stated, the probability is one half by
    # construction. Ties on RPS refund, so among decisive outcomes it is a coin.
    out.append(("coinflip", 0.5 * info["coinflip_multiplier"]))
    out.append(("rps (hors egalite)", 0.5 * info["rps_multiplier"]))

    payouts = {int(k): v for k, v in info["wheel"]["payouts"].items()}
    for cat, rtp in sorted(wheel_rtp(info["wheel"]["layout"], payouts).items()):
        out.append((f"wheel mise {cat}", rtp))

    for rows in sorted(info["plinko_tables"], key=int):
        for risk in ("low", "medium", "high"):
            out.append((f"plinko {rows}r {risk}",
                        plinko_rtp(info["plinko_tables"][rows][risk])))

    return rate, out


def report():
    info, rb = load()
    rate, rows = verdicts(info, rb)

    print(f"rakeback: {rate * 100:.2f}% du mise, "
          f"cooldown {rb['cooldown_hours']}h, claim minimum {rb['min_claim']}\n")
    print(f"{'jeu':22} {'RTP':>8} {'edge':>7} {'couvert':>9} {'net':>8}")
    print("-" * 58)
    best = None
    for name, rtp in rows:
        e = 1 - rtp
        net = rate - e
        cover = rate / e * 100 if e > 0 else float("inf")
        print(f"{name:22} {rtp:8.4f} {e * 100:6.2f}% {cover:8.1f}% {net * 100:7.2f}%")
        if best is None or net > best[1]:
            best = (name, net)

    print(f"\nmeilleur cas: {best[0]}, net {best[1] * 100:.2f}% par credit mise")

    # What it costs to reach the minimum claim, in the least bad game.
    wager = rb["min_claim"] / rate
    worst_case_loss = wager * (1 - max(r for _, r in rows))
    print(f"\npour reclamer le minimum de {rb['min_claim']} credits il faut miser "
          f"{wager:,.0f} credits.")
    print(f"dans le jeu le moins mauvais cela coute {worst_case_loss:,.0f} credits "
          f"d'esperance, soit {worst_case_loss - rb['min_claim']:,.0f} de perte nette.")

    verdict = "EXCLU" if best[1] < 0 else "A CONSIDERER"
    print(f"\nverdict: {verdict}")
    return best[1]


def demo():
    # The RTP formula, checked where the answer is known by hand.
    assert abs(plinko_rtp([2.0, 2.0]) - 2.0) < 1e-9          # flat table
    assert abs(plinko_rtp([0.0, 2.0, 0.0]) - 1.0) < 1e-9     # only the middle, p=1/2
    assert abs(plinko_rtp([1.0, 1.0, 1.0]) - 1.0) < 1e-9     # all ones

    # A fair coin paying 2x returns exactly the stake; 1.94 keeps 3 percent.
    assert abs(0.5 * 2.0 - 1.0) < 1e-9
    assert abs((1 - 0.5 * 1.94) - 0.03) < 1e-9

    # A wheel where every segment pays its own inverse frequency is fair.
    fair = wheel_rtp([1, 1, 2, 2], {1: 2, 2: 2})
    assert all(abs(v - 1.0) < 1e-9 for v in fair.values()), fair

    print("self-checks pass\n")


if __name__ == "__main__":
    demo()
    best = report()
    sys.exit(0 if best is not None else 1)
