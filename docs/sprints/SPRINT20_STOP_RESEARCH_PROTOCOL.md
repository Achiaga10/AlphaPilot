# Sprint 20 Frozen Stop Research Protocol

Status: **FROZEN BEFORE RESULT INSPECTION** — 2026-08-29

## Audit and evidence status

Sprint 12 already tested static ATR14 1.5×/2×/3×, ATR trailing 2×/3×, partial
+2R and full +3R on operational data. EMA 3× and Micho 1.5× remained
RESEARCH_ONLY: EMA improved only 1/3 folds on return/Sharpe/Calmar; Micho worsened
validation drawdown/concentration and 79.07% of measurable validation stops
recovered above entry within 20 sessions. Trails caused whipsaw; profit exits
failed the frozen 80% CAGR-retention gate. All 2021-08-20–2026-08-20 periods are
previously seen and are **RESEARCH EVIDENCE**, never untouched OOS.

## Frozen dataset

- snapshot: `5dd60f87-8947-4850-ba87-4a7df655528c`
- dataset SHA-256: `b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`
- universe SHA-256: `369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8`
- 502 frozen current constituents + SPY; `LEGACY_PARTIAL`, value reproducible;
  survivorship biased and not point-in-time membership.

## Frozen experiment

Strategies remain EMA20 Pullback/HYBRID 2%/RS20/equal-slot and Micho V1
BOTH/RS20/ATR-volatility-normalized. Capital $100,000; 10 positions; COST_LOW,
zero commission and 5 bps slippage per side. ATR period is 14.

Development: 2021-08-20–2024-12-31. Reused validation:
2025-01-01–2026-08-20. Folds: 2021-08-20–2022-12-31,
2023-01-01–2024-12-31, 2025-01-01–2026-08-20.

Closed protective candidates:

- EMA: control, static entry ATR14 2.0×, 2.5×, 3.0×.
- Micho: control, static entry ATR14 1.0×, 1.5×, 2.0×, 2.5×.

No EMA50 emergency stop is included: an intraday EMA50 order would be a new
semantic rule and a completed-close version merely duplicates the strategy exit.

Entry stop = entry OPEN − multiplier × ATR14 frozen from signal-day completed
history. It activates next session. Daily low triggers; a gap open below the
effective stop fills at the worse OPEN, otherwise at the stop. Whole shares and
declared friction apply. This is conservative daily-OHLC simulation, not
intraday precision. Initial stop never changes.

## Frozen selection and gates

Development ranks candidates by: all gates pass, then lowest 5th-percentile
trade loss, lowest drawdown, highest Calmar, Sharpe, then wider multiplier.
Candidate must retain ≥75% of positive control CAGR; drawdown may worsen ≤2.0
percentage points; Sharpe and Calmar must each retain ≥80% of positive control;
turnover may rise ≤25%; and either worst-trade or 5th-percentile loss must improve
by ≥10% in magnitude.

The frozen candidate then must retain ≥70% of positive reused-validation CAGR;
validation drawdown may worsen ≤1.5 points; Sharpe/Calmar each retain ≥80%;
top-5 positive-P&L share may worsen ≤5 points; turnover may rise ≤25%; it must
improve or equal control return, Sharpe, and drawdown in at least 2/3 folds; and
20-session recovery rate must be ≤65%. Gap fills and stop frequency are reviewed
for economic interpretability. Failure of any gate means `NO_WINNER`; there is
no least-bad fallback and gates cannot be edited after outcomes.

## Secondary policies

Protective selection is independent. Prior closed evidence freezes trailing
candidate to NONE versus ATR14 2×/3× and profit candidate to NONE versus partial
+2R/full +3R. Because prior declared candidates were rejected and no fresh data
exists, Sprint 20 does not re-search them: trailing = NONE, profit target = NONE.

At most a passing protective candidate is eligible for human-reviewed
`PAPER_FORWARD_CANDIDATE`; never production-ready/default. Otherwise new trades
remain RESEARCH_ONLY and not ACTIONABLE. Forward paper evidence is required.
