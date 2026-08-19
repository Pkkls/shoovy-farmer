"""What a low-availability backend actually costs, once retries are allowed.

An earlier derivation multiplied every rate by availability, which quietly
assumed a failed call is a lost opportunity. For most of this game it is not: a
cast that 502s can be retried, and the only thing spent is time inside a window
that was going to elapse anyway.

That splits the mechanics into two populations, and the split matters more than
any single number:

  retryable    an action with a cooldown or a filling till. You get as many
               attempts as the window allows, so what matters is
               P(at least one success in the window) = 1 - (1-p)^k.

  deadline     an action that expires. A chest window closes; there is no
               second attempt. Here availability multiplies directly, and a
               multi-step flow compounds.

Ranking mechanics without that distinction produces a plan that is wrong in both
directions at once: too pessimistic about grinding, too optimistic about events.

    python budget.py        # runs the self-checks and prints the table
"""
import sys


def p_success_in_window(p, window_s, retry_every_s):
    """Probability at least one of the attempts inside a window lands."""
    if window_s <= 0 or retry_every_s <= 0:
        raise ValueError("fenetre et espacement doivent etre positifs")
    attempts = max(1, int(window_s // retry_every_s))
    return 1.0 - (1.0 - p) ** attempts, attempts


def attempts_for_confidence(p, target=0.95):
    """How many attempts before a single action is near-certain to have landed."""
    if not 0 < p < 1:
        raise ValueError("p doit etre dans ]0,1[")
    n = 1
    while 1.0 - (1.0 - p) ** n < target:
        n += 1
    return n


def retryable_rate(nominal_per_hour, p, retry_every_s):
    """Realised rate for a cooldown-bound action, retries included."""
    window = 3600.0 / nominal_per_hour
    hit, attempts = p_success_in_window(p, window, retry_every_s)
    return {
        "nominal_per_hour": nominal_per_hour,
        "window_s": round(window, 1),
        "attempts_per_window": attempts,
        "p_window": round(hit, 3),
        "effective_per_hour": round(nominal_per_hour * hit, 2),
        "calls_per_hour": round(nominal_per_hour * attempts, 1),
    }


def deadline_rate(p, steps=1):
    """Realised success for an action that cannot be retried."""
    return round(p ** steps, 4)


def demo():
    p = 0.158  # measured availability, itself a contaminated lower bound

    # Retrying inside a window recovers most of what naive multiplication lost.
    naive = 20.0 * p
    fish = retryable_rate(20.0, p, retry_every_s=30.0)
    assert fish["attempts_per_window"] == 6, fish
    assert 0.60 < fish["p_window"] < 0.70, fish
    assert fish["effective_per_hour"] > 3 * naive, (fish, naive)

    # Spacing retries tighter buys more, with diminishing returns.
    tight = retryable_rate(20.0, p, retry_every_s=10.0)
    assert tight["p_window"] > fish["p_window"]
    assert tight["calls_per_hour"] > fish["calls_per_hour"]

    # A slower cooldown is strictly easier to keep up with: more attempts fit.
    slow = retryable_rate(4.0, p, retry_every_s=30.0)
    assert slow["p_window"] > fish["p_window"], (slow, fish)

    # Deadline actions get no such relief, and compound with steps.
    assert deadline_rate(p, 1) == round(p, 4)
    assert deadline_rate(p, 2) < deadline_rate(p, 1) / 5

    # A one-off action is near-certain if you simply keep trying.
    assert attempts_for_confidence(p, 0.95) == 18, attempts_for_confidence(p, 0.95)

    print(f"disponibilite p = {p}\n")
    print("RETRYABLE (cooldown ou till qui se remplit)")
    print(f"{'mecanique':22} {'fenetre':>9} {'essais':>7} {'P(fenetre)':>11} "
          f"{'reel/h':>8} {'appels/h':>9}")
    for name, nominal, gap in [("peche (cd 180s)", 20.0, 30.0),
                               ("peche, essais 10s", 20.0, 10.0),
                               ("collecte (cd 15min)", 4.0, 30.0),
                               ("daily (cd 20h)", 0.05, 60.0)]:
        r = retryable_rate(nominal, p, gap)
        print(f"{name:22} {r['window_s']:>8.0f}s {r['attempts_per_window']:>7} "
              f"{r['p_window']:>11.3f} {r['effective_per_hour']:>8.2f} "
              f"{r['calls_per_hour']:>9.1f}")

    print("\nDEADLINE (la fenetre expire, pas de seconde chance)")
    for name, steps in [("1 appel", 1), ("2 appels", 2), ("3 appels", 3)]:
        print(f"  {name:22} {deadline_rate(p, steps):.4f}")

    print(f"\nune action ponctuelle est acquise a 95 % apres "
          f"{attempts_for_confidence(p, 0.95)} essais")
    print("\nself-checks pass")


if __name__ == "__main__":
    demo()
    sys.exit(0)
