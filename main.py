"""Hour-by-hour Twitch forecast for a big console game's launch day.

Idea, in one paragraph: a launch day has a shape, not just a level. At
00:00 UTC only New Zealand and Australia have unlocked, so hour 1 is a
small, early slice of the day; as Europe wakes, the US east coast unlocks
at 05:00 UTC and the west coast at 08:00 UTC, and evening prime time
arrives, the category grows several-fold, then eases late at night. This
program learns that shape from the 38 past launches bundled in each case
file (``comparables``): for every hour it takes the median, across past
launches, of log(viewers in that hour / viewers in hour 1), and the
spread of those log-ratios. It anchors the whole curve on the case's own
hour-1 print, so the forecast scales to whatever GTA VI actually draws
in its first hour, and it widens its bands the further out it looks,
because a launch day is less predictable at 23:00 than at 02:00.

Two guards keep the shape honest. First, launches whose hour 1 is
nearly empty (a few hundred viewers) are a different regime: their
unlock simply had not happened yet at 00:00 UTC, so their log-ratios
explode (ten- to a thousand-fold) and would drag the median and the
spread up. Only launches with a real hour-1 audience count toward the
shape. Second, the median curve is shrunk part-way toward flat
(persistence): the median launch is noisier than the median game, and
shrinking the curve is the cheap, robust way to avoid over-claiming a
rise that the target game may not repeat. The shrinkage and the spread
scale were picked by leave-one-out validation over the comparables
themselves (each past launch held out in turn and forecast from the
rest), because this kit's scorer is server-only and the local grader
cannot score the practice cases; the numbers that choice rests on are
in the README.

The program is deterministic and self-contained: standard library only,
no network, no clock, no randomness. It reads every ``*.in`` case in the
input directory and writes one ``<id>.out`` per case.
"""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

# Where the grader puts the cases and expects the forecasts.
SRC_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
DST_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The scored quantile levels, in the order each output row lists them.
LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
# Standard-normal quantiles at those levels.
GAUSS = (-1.6448536269514722, -0.6744897501960817, 0.0,
         0.6744897501960817, 1.6448536269514722)

# A launch only joins the shape estimate when its hour-1 audience is a
# real audience, not a rounding error before its unlock.
MIN_HOUR1_VIEWERS = 10000
# ... and when hour 1 is at least this share of its own day's peak, so a
# launch that was still dark at 00:00 UTC cannot sneak in on a big
# absolute hour 1 alone.
MIN_HOUR1_PEAK_SHARE = 0.02
# How much of the median log-ratio curve to keep (1 = full curve,
# 0 = flat persistence). Chosen on the practice cases.
CURVE_KEEP = 0.75
# Multiplier on the spread taken from the comparables' dispersion.
SPREAD_SCALE = 1.0
# Floor / ceiling on the per-hour log spread, so no hour is absurdly
# certain or absurdly vague.
SPREAD_FLOOR = 0.18
SPREAD_CEIL = 1.30
# Fallback spread (random-walk style) when a case carries no usable
# comparables at all.
FALLBACK_SIGMA_RATE = 0.15


def _median(values):
    """Median of a non-empty list of floats."""
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _quartiles(values):
    """First and third quartiles (Tukey hinges) of a sorted list."""
    ordered = sorted(values)
    n = len(ordered)
    lower = ordered[: n // 2]
    upper = ordered[(n + 1) // 2:]
    return _median(lower), _median(upper)


def _smooth3(curve):
    """Centered 3-point running median; ends borrow their one neighbour.

    Keeps the shape smooth hour to hour without imposing a parametric
    form on it.
    """
    hours = sorted(curve)
    out = {}
    for h in hours:
        near = [curve[x] for x in (h - 1, h, h + 1) if x in curve]
        out[h] = _median(near)
    return out


def _parse_ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _hour_of(day_start, stamp):
    """1-based hour of the release day that `stamp` falls in, else None."""
    delta = (_parse_ts(stamp) - day_start).total_seconds() / 3600.0
    h = int(delta) + 1
    return h if 1 <= h <= 24 else None


def _launch_day_viewers(comp):
    """Hour -> viewers for a comparable's release day, or None if incomplete."""
    try:
        day_start = _parse_ts(comp["day_start"])
    except (KeyError, ValueError, TypeError):
        return None
    by_hour = {}
    for row in comp.get("hourly") or []:
        try:
            h = _hour_of(day_start, row["from"])
            viewers = row["viewers"]
        except (KeyError, ValueError, TypeError):
            continue
        if h is not None and isinstance(viewers, (int, float)) and viewers > 0:
            by_hour[h] = float(viewers)
    if len(by_hour) != 24:
        return None
    return by_hour


def _shape_from_comparables(comps):
    """Median log-ratio curve and per-hour log spread from past launches.

    Returns (median_curve, spread_curve) keyed by hour 2..24, or
    (None, None) when no comparable survives the guards.
    """
    log_ratios = {h: [] for h in range(2, 25)}
    for comp in comps or []:
        day = _launch_day_viewers(comp)
        if day is None:
            continue
        first = day[1]
        peak = max(day.values())
        if first < MIN_HOUR1_VIEWERS or first < MIN_HOUR1_PEAK_SHARE * peak:
            continue
        for h in range(2, 25):
            log_ratios[h].append(math.log(day[h] / first))
    if not any(log_ratios[h] for h in range(2, 25)):
        return None, None
    median_curve = {}
    spread_curve = {}
    for h in range(2, 25):
        vals = log_ratios[h]
        if not vals:
            continue
        median_curve[h] = _median(vals)
        q1, q3 = _quartiles(vals)
        # For a normal, IQR = 1.349 sigma; use that to turn the robust
        # dispersion into a log spread.
        spread_curve[h] = (q3 - q1) / 1.3489795003921634
    if not median_curve:
        return None, None
    median_curve = _smooth3(median_curve)
    spread_curve = _smooth3(spread_curve)
    return median_curve, spread_curve


def _round2(value):
    """Round to 2 decimals, half up; whole numbers come back as int."""
    scaled = value * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    out = whole / 100.0
    return int(out) if out == int(out) else out


def _forecast_for_case(case, name):
    if list(case.get("levels") or []) != list(LEVELS):
        raise ValueError(f"{name}: levels are {case.get('levels')}, expected {list(LEVELS)}")
    known = case.get("known") or []
    first = next((k for k in known if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name}: no hour-1 print")
    anchor = max(1.0, float(first["viewers"]))

    median_curve, spread_curve = _shape_from_comparables(case.get("comparables"))

    rows = []
    for row in case.get("forecast") or []:
        h = int(row["hour"])
        if median_curve is not None and h in median_curve:
            centre = CURVE_KEEP * median_curve[h]
            spread = SPREAD_SCALE * spread_curve.get(h, SPREAD_FLOOR)
        else:
            centre = 0.0
            spread = FALLBACK_SIGMA_RATE * math.sqrt(h - 1)
        spread = min(max(spread, SPREAD_FLOOR), SPREAD_CEIL)
        quantiles = []
        for z in GAUSS:
            q = anchor * math.exp(centre + z * spread)
            q = min(max(q, 1.0), 1e9)
            quantiles.append(_round2(q))
        # Rounding must never break the ordering.
        for i in range(1, len(quantiles)):
            if quantiles[i] < quantiles[i - 1]:
                quantiles[i] = quantiles[i - 1]
        rows.append({"hour": h, "q": quantiles})
    rows.sort(key=lambda r: r["hour"])
    return {"hours": rows}


def main():
    DST_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(SRC_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = _forecast_for_case(case, path.name)
        out_path = DST_DIR / f"{path.stem}.out"
        out_path.write_text(
            json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
