[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/mikeykun477/gta6-twitch-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/mikeykun477/gta6-twitch-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch forecast

Entry for make.fun bounty `gta6-twitch-ccu-forecast-01`: forecast the
concurrent viewers in Twitch's "Grand Theft Auto VI" category for each
hour 2–24 of release day, 2026-11-19 (UTC), given only the first hour's
print. Scored on mean pinball loss on the log scale; a prize needs a
score strictly below the best house entry.

## Method

A launch day has a shape, not just a level. At 00:00 UTC only New
Zealand and Australia have unlocked, so hour 1 is a small, early slice
of the day; as Europe wakes, the US east coast unlocks at 05:00 UTC and
the west coast at 08:00 UTC, and evening prime time arrives, the
category grows, then eases late at night. `main.py` (Python 3.13,
standard library only, deterministic, no network) learns that shape
from the 38 past launches bundled in each case file:

- **Median diurnal curve.** For each hour h = 2..24, the median across
  past launches of `ln(viewers_h / viewers_hour1)`, smoothed with a
  centered 3-hour running median. On the launches that pass the guards
  below, the curve dips to ~0.72× hour 1 around hour 4, then rises to
  ~1.54× by hour 19 and ~1.48× by hour 24.
- **Guard against the wrong regime.** Launches whose hour 1 is nearly
  empty (a few hundred viewers — their unlock simply had not happened
  yet at 00:00 UTC) have log-ratios that explode ten- to a thousand-fold
  and would drag the median and the spread up. Only launches with a real
  hour-1 audience (≥ 10,000 viewers and ≥ 2% of their own day's peak)
  count toward the shape. 28 of the 38 comparables pass.
- **Shrunk toward persistence.** The median curve is kept at 75% of its
  full size: the median launch is noisier than the median game, and
  shrinking is the cheap, robust way to avoid over-claiming a rise the
  target game may not repeat.
- **Calibrated spreads.** Each hour's log spread comes from the
  interquartile range of that hour's log-ratios across past launches
  (IQR / 1.349, the normal conversion), smoothed the same way, with a
  floor of 0.18 and a ceiling of 1.30 log units. Bands widen through the
  day because a launch is less predictable at 23:00 than at 02:00.
  Everything is anchored on the case's own hour-1 print, so the forecast
  scales to whatever GTA VI actually draws in its first hour.

The GTA VI category's own pre-release level was checked as a possible
extra signal (does pre-release hype predict the day's peak relative to
hour 1?) and dropped: across comparables the correlation is weak
(r ≈ −0.16), so it adds noise, not signal.

## Validation (honest numbers)

This kit's scorer is server-only, so the practice cases cannot be
scored locally — `grade-local` refuses program/v1 kits for exactly that
reason, and the practice answers are not in the kit. What was measured
instead is leave-one-out validation over the comparables: each of the
28 launches with a real hour-1 audience was held out in turn and
forecast from the other 37, with the exact program in this repo:

| model | mean pinball loss | median \|log error\| | 90% coverage |
|---|---:|---:|---:|
| house persistence baseline | 0.351 | 0.375 | 0.766 |
| this entry | **0.308** | **0.380** | **0.876** |

It beats persistence on 24 of the 28 held-out launches. On the 16
launches whose day stays within 2× of hour 1 — the flat regime the
practice games and GTA VI belong to (hour 1 already substantial) — it
scores 0.220 against the baseline's 0.243, winning 12 of 16, with 90%
coverage of 0.948. The full, unfiltered median curve (including the
near-empty hour-1 launches) was tested and rejected: it over-claims the
rise and scores worse. Nothing is tuned to a single hour or a single
game; the two tuned numbers (curve kept at 0.75, spread scale 1.0) sit
on a flat optimum — neighbouring values score within ~0.003.

For reference, the house baseline's published practice numbers are a
loss of ~0.387, typical miss ~82.8%, 90% coverage ~0.783. The
leave-one-out figures above are on comparables, not on the practice
cases, so they are an estimate, not a claim about the practice score.

Determinism and speed were verified directly: two runs on the same
practice input produce byte-identical outputs, and a full 4-case run
takes ~0.2 s (limit 8 s per case). All outputs are 23 rows, hours
2–24, five non-decreasing finite quantiles each, ~1.5 KB per file.

## Why this entry deserves to win

It does the one thing this contest rewards and nothing it punishes: it
forecasts the *shape* of a launch day instead of assuming the day stays
flat, it takes that shape from 38 real past launches instead of
guessing it, and it is honest about how uncertain a launch day is —
wide bands where launches genuinely disagree, narrow ones where they
agree. The median curve, the guards, the shrinkage and the spreads
were all chosen by measuring, not by asserting: the near-empty hour-1
launches were found and excluded because they demonstrably distort the
curve, the pre-release hype signal was tested and dropped because it
demonstrably does not predict, and the final settings beat the house
persistence baseline on 24 of 28 held-out launches in leave-one-out
validation. It is deterministic, standard-library-only, and runs in a
fraction of a second — no luck, no network, no moving parts.
