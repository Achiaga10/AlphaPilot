# EMA20 Entry Extension Incident — AXON / FAST

## Scope

This is an execution/readiness incident review, not strategy optimization. It does not
claim that distance above EMA20 caused either loss and does not change the frozen EMA20
Pullback evaluator, HYBRID 2%, RS20, sizing, or News policy.

## Root cause

The frozen strategy defines a pullback using the session low inside 97%–101% of EMA20 and
a close at/above EMA20. It does not cap that closing price. The portfolio orchestrator
then treated the completed closing reference as actionable without a separate fresh
price-to-EMA entry revalidation, and the action-application path did not recheck geometry.
Consequently, a valid historical low-touch signal could remain presented after price had
moved beyond the intended 1% upper entry proximity.

## AXON evidence

- Profile: `ema20-pullback-v1`, version 1; HYBRID 2%; RS20; equal-slot.
- Stored recommendation/signal session: 2026-08-27.
- Recommendation/reference close: $611.16.
- Completed signal-session EMA20: $597.1382581750427727951172336.
- Candle: open $613.12, high $614.84, low $600.00, close $611.16.
- Low-to-EMA distance: approximately +0.479%, inside the frozen low-touch zone.
- Recommendation close-to-EMA distance: approximately +2.348%, outside 1%.
- Manual Paper entry: 16 shares at $609.00, recorded 2026-08-28 05:13 UTC.
- Paper fill-to-signal-anchor distance: approximately +1.986%, outside 1%.
- The historical live quote at the moment of user action was not persisted: UNAVAILABLE.
- Old entry evidence contains no entry-safety snapshot because it predates schema v2.

AXON was actionable because the low-touch technical signal was valid under frozen signal
semantics, while no downstream current-price geometry gate existed. Available stored
evidence is sufficient to reconstruct the completed signal and Paper fill relation, but
not the exact live quote that the UI displayed at action time.

## FAST evidence

- Profile: `ema20-pullback-v1`, version 1; HYBRID 2%; RS20; equal-slot.
- Stored recommendation/signal session: 2026-08-27.
- Recommendation/reference close: $51.12.
- Completed signal-session EMA20: $50.44696835243861901010882936.
- Candle: open $50.73, high $51.305, low $50.55, close $51.12.
- Low-to-EMA distance: approximately +0.204%, inside the frozen low-touch zone.
- Recommendation close-to-EMA distance: approximately +1.334%, outside 1%.
- Manual Paper entry: 195 shares at $50.28, recorded 2026-08-28 05:14 UTC.
- Paper fill-to-signal-anchor distance: approximately -0.331% (below EMA20), eligible.
- The historical live quote at the moment of user action was not persisted: UNAVAILABLE.

FAST's completed recommendation close itself was outside the current safety boundary, but
the authoritative stored manual fill was below the signal EMA20 and satisfies entry
geometry. This is only a positive geometry control; it does not prove the overall trade
was correct or compel a BUY after other gates.

## Current read-only state (2026-09-02 acceptance)

Latest authoritative completed-session facts were 2026-09-01:

| Ticker | Completed close | EMA20 | Distance | Geometry only |
|---|---:|---:|---:|---|
| AXON | $518.28 | $587.2708058334 | -11.748% | Below EMA20 / eligible geometry |
| FAST | $48.75 | $50.1340099265 | -2.761% | Below EMA20 / eligible geometry |

Both are already-held positions, so this table is not a new BUY decision. Today's values
must not be used to reconstruct their historical action-time quotes.

## Safety invariant

A technical EMA20 Pullback signal is necessary but not sufficient for an actionable BUY.
The current authoritative entry price must be at/below EMA20 or no more than the existing
1% above the fixed completed signal-session EMA20 anchor. Extended, missing, invalid, or
stale evidence is non-actionable. News and ranking cannot override the gate.
