"""Parametric economy model.

The structure of two mechanics is already known from the site's own command
reference, and both have a closed-form optimum that does not need any measured
constant to derive. Writing them down now means the moment the constants land,
the ranking falls out instead of having to be reasoned about again.

Every rate here is a free parameter. Nothing in this file is a measurement.

    python model.py     # runs the self-checks
"""
from dataclasses import dataclass


# --------------------------------------------------------------------------
# Business: a till fills at a rate and then STOPS. Collecting is the mechanic.
# --------------------------------------------------------------------------
#
# Income per unit time when collecting every T:
#
#     rate(T) = min(r*T, C) / T
#
# For T <= C/r that is exactly r: no loss. For T > C/r it is C/T, which decays
# hyperbolically. So the optimum is any T <= C/r, and the *cheapest* optimum in
# requests is T* = C/r precisely, i.e. collect exactly when the till fills.
#
# Collecting more often than C/r earns nothing extra and burns requests. That is
# the whole trade, and it means the request cost of business is 1/T* = r/C per
# hour per business, which a manager (3x capacity) divides by three.

@dataclass
class Business:
    fill_rate: float      # credits per hour into the till
    capacity: float       # credits the till holds before it stops
    manager: bool = False # a manager triples capacity

    @property
    def effective_capacity(self):
        return self.capacity * (3.0 if self.manager else 1.0)

    @property
    def optimal_period_hours(self):
        """Collect exactly this often: any sooner is wasted requests, any later
        is lost income."""
        return self.effective_capacity / self.fill_rate

    @property
    def credits_per_hour(self):
        """At the optimal cadence the till never stalls, so it is just the rate."""
        return self.fill_rate

    @property
    def requests_per_hour(self):
        return 1.0 / self.optimal_period_hours

    @property
    def credits_per_request(self):
        return self.effective_capacity

    def credits_per_hour_at(self, period_hours):
        """What you actually get if you collect every `period_hours`."""
        return min(self.fill_rate * period_hours,
                   self.effective_capacity) / period_hours


# Two facts that complicate the clean answer, both from the command reference:
#
#  - Shops earn their full rate only while the stream is live, a fraction after.
#    So `fill_rate` is not constant: C/r stretches when the stream is offline,
#    and the optimal cadence follows the streamer's schedule, not the clock.
#
#  - A `!boom` drops N hours of takings into every till at once, and a full till
#    cannot take any more. That is a call option on empty till space, paying off
#    at an unpredictable time. It biases the optimum *below* C/r: you give up
#    nothing by collecting early except requests, and you keep room for a boom.
#
# Both are why the cadence has to be event-driven, not a fixed timer.


def boom_headroom_value(b: Business, period_hours, boom_hours, boom_prob_per_hour):
    """Expected credits captured from booms, given a collection cadence.

    A boom pays into whatever room the till has. Average room under a sawtooth
    filling to `min(r*T, C)` and emptying is half the peak.
    """
    peak = min(b.fill_rate * period_hours, b.effective_capacity)
    average_room = b.effective_capacity - peak / 2.0
    boom_payout = min(b.fill_rate * boom_hours, average_room)
    return boom_payout * boom_prob_per_hour


# --------------------------------------------------------------------------
# Fishing: catches decay, so the net is a perishable flow.
# --------------------------------------------------------------------------
#
# Public /api/fishing gives decay = 10 %/day, a 24 h fresh window, and a 10 %
# floor. So a catch holds full value for `fresh_hours`, then decays
# geometrically toward `floor` of its original value.
#
# Selling costs one request and sells the whole net, so the question is cadence:
# sell too often and you spend requests on nothing, sell too rarely and the
# oldest fish bleed.

FRESH_HOURS = 24.0      # measured, public API
DECAY_PER_DAY = 0.10    # measured, public API
FLOOR_FRACTION = 0.10   # measured, public API


def catch_value_fraction(age_hours,
                         fresh_hours=FRESH_HOURS,
                         decay_per_day=DECAY_PER_DAY,
                         floor=FLOOR_FRACTION):
    """Fraction of original value a catch still has at `age_hours`."""
    if age_hours <= fresh_hours:
        return 1.0
    days_decaying = (age_hours - fresh_hours) / 24.0
    return max(floor, (1.0 - decay_per_day) ** days_decaying)


def fishing_yield(period_hours, catches_per_hour=1.0, **decay_kw):
    """Average value realised per catch when the net is sold every
    `period_hours`. Catches are assumed uniform over the period, so a catch's
    age at sale is uniform on [0, period]."""
    steps = 200
    total = 0.0
    for i in range(steps):
        age = period_hours * (i + 0.5) / steps
        total += catch_value_fraction(age, **decay_kw)
    per_catch = total / steps
    return {
        "value_fraction_per_catch": per_catch,
        "credits_per_hour_factor": per_catch * catches_per_hour,
        "requests_per_hour": 1.0 / period_hours,
    }


# Reading of the above: because catches are FULL value for a whole 24 h, selling
# more often than once a day buys nothing at all. The decay only starts biting
# past 24 h, and even then at 10 %/day toward a 10 % floor, which is slow. So
# fishing's sell cadence is cheap: roughly one sale per day per account, and the
# request budget belongs to casting, not selling.


def demo():
    # Business: the optimum is flat up to C/r, then falls away.
    b = Business(fill_rate=100.0, capacity=400.0)
    assert abs(b.optimal_period_hours - 4.0) < 1e-9
    assert abs(b.credits_per_hour_at(2.0) - 100.0) < 1e-9   # early: no loss
    assert abs(b.credits_per_hour_at(4.0) - 100.0) < 1e-9   # exactly full
    assert abs(b.credits_per_hour_at(8.0) - 50.0) < 1e-9    # late: half wasted
    assert b.credits_per_request == 400.0

    # A manager triples capacity, so it thirds the request cost.
    m = Business(fill_rate=100.0, capacity=400.0, manager=True)
    assert abs(m.optimal_period_hours - 12.0) < 1e-9
    assert abs(m.requests_per_hour - b.requests_per_hour / 3.0) < 1e-9

    # Boom headroom: collecting early keeps room, so it captures more.
    early = boom_headroom_value(b, 1.0, boom_hours=6.0, boom_prob_per_hour=0.05)
    late = boom_headroom_value(b, 8.0, boom_hours=6.0, boom_prob_per_hour=0.05)
    assert early > late, (early, late)

    # Fishing: nothing decays inside the fresh window.
    assert catch_value_fraction(0.0) == 1.0
    assert catch_value_fraction(24.0) == 1.0
    assert catch_value_fraction(48.0) < 1.0
    assert catch_value_fraction(10_000.0) == FLOOR_FRACTION

    # So selling twice a day is indistinguishable from selling once a day:
    # both keep 100 %, because nothing has started decaying yet.
    half = fishing_yield(12.0)["value_fraction_per_catch"]
    daily = fishing_yield(24.0)["value_fraction_per_catch"]
    assert abs(half - 1.0) < 1e-9, half
    assert abs(daily - 1.0) < 1e-9, daily
    # A week-long net keeps ~78 %: real, but far from a catastrophe.
    weekly = fishing_yield(168.0)["value_fraction_per_catch"]
    assert 0.77 < weekly < 0.79, weekly

    print("model self-checks pass")
    print(f"  business r=100/h C=400  -> collect every {b.optimal_period_hours:.1f} h, "
          f"{b.requests_per_hour:.3f} req/h, {b.credits_per_request:.0f} cr/req")
    print(f"  with a manager          -> collect every {m.optimal_period_hours:.1f} h, "
          f"{m.requests_per_hour:.3f} req/h, {m.credits_per_request:.0f} cr/req")
    print(f"  fishing sell daily      -> {daily * 100:.1f}% of value kept")
    print(f"  fishing sell weekly     -> {weekly * 100:.1f}% of value kept")


if __name__ == "__main__":
    demo()
