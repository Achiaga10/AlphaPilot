# Sprint 20 EMA Loss-Control Research Round 2 Protocol

Status: **FROZEN BEFORE ROUND 2 RESULT INSPECTION — 2026-08-30**

## Research status and honesty

This is a new hypothesis-family study after Sprint 20 Round 1 returned `NO_WINNER`. Every available historical period has already been observed by AlphaPilot. Development, reused-validation, and fold results are therefore **research evidence**, never fresh, pristine, or untouched OOS evidence. A passing result can be at most a human-reviewed `PAPER_FORWARD_CANDIDATE` for genuinely new manual Alpaca Paper observations.

## Infrastructure audit

The daily-OHLC engine already preserves the completed signal candle, signal-day ATR14, next-session OPEN entry, and deterministic stop activation/fill semantics. It can therefore simulate an entry-pattern boundary tied to the completed pullback/reclaim candle without future data. A completed-close EMA50 boundary merely duplicates frozen HYBRID strategy exit; an intraday EMA50 order would invent semantics. Percentage emergency stops require a new arbitrary threshold, and regime-aware variants would multiply parameters. Those families are excluded.

## Frozen candidate space

EMA20 Pullback remains HYBRID 2%, RS20, equal-slot, $100,000, 10 positions, zero commission, COST_LOW 5 bps per side, frozen Sprint 13 snapshot, and existing T+1 OPEN/accounting semantics.

1. `control`: frozen strategy exit only.
2. `atr-stop-2-0-reference`: Round 1’s strongest qualifying development arm, retained only as a reference; entry stop = entry OPEN − 2 × signal-day ATR14.
3. `signal-day-low-invalidation`: entry-pattern invalidation; initial boundary = completed BUY signal candle LOW. It is valid only when positive and strictly below next-session entry OPEN. Missing/invalid structure rejects that entry under the candidate arm rather than fabricating a boundary.

The signal-day-low candidate exists because an EMA pullback/reclaim thesis is structurally invalidated when price breaches the completed reclaim candle’s low. It uses an observed strategy event, not a nearby ATR multiplier. No hybrid, trailing, profit-target, percentage grid, regime variant, or additional candidate may be added after results.

## Execution semantics

The boundary is known from information available by signal day and freezes at entry. It activates only after the entry session. A later gap OPEN below the boundary fills at that worse OPEN; otherwise a daily LOW breach fills at the boundary. When daily OHLC cannot reveal stop-versus-other-exit order, conservative stop-first priority remains. Existing HYBRID exits remain active. Trailing and profit target remain `NONE`.

## Dataset and periods

- snapshot: `5dd60f87-8947-4850-ba87-4a7df655528c`
- dataset SHA-256: `b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`
- universe SHA-256: `369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8`
- development evidence: 2021-08-20–2024-12-31
- reused/previously observed validation evidence: 2025-01-01–2026-08-20
- folds: 2021-08-20–2022-12-31; 2023-01-01–2024-12-31; 2025-01-01–2026-08-20

The frozen universe is the current-constituent snapshot (502 constituents plus SPY), is survivorship biased, and has `LEGACY_PARTIAL` provenance despite value reproducibility.

## Frozen gates and selection

Development eligibility requires positive-control CAGR retention ≥75%; max-drawdown worsening ≤1.5 percentage points; Sharpe and Calmar retention ≥80%; turnover increase ≤25%; and ≥10% magnitude improvement in worst trade or fifth-percentile trade. If multiple candidates qualify, select by lowest fifth-percentile loss, then worst loss, drawdown, Calmar, Sharpe, and finally the structural candidate over the reused ATR reference.

The frozen candidate must then retain ≥70% of reused-validation positive-control CAGR; worsen drawdown by ≤1.5 points; retain ≥80% of Sharpe and Calmar; worsen top-5 positive-P&L concentration by ≤5 points; increase turnover ≤25%; improve/equal return, Sharpe, and drawdown in ≥2/3 folds; and have 20-session recovery ≤65%. Gap-through frequency, stop frequency, realized/unrealized P&L, concentration, and COST_LOW drag receive explicit economic review.

Failure of any gate means `NO_WINNER`. There is no least-bad fallback, gate edit, nearby threshold, Round 3, or automatic profile/default change in this work.
