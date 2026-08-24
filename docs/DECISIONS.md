# AlphaPilot — Current Decisions

This file records decisions that must not be silently changed.

## 1. Package / Environment

Use uv.

Primary validation command:

.\run_checks.ps1

Do not introduce unrelated pip-based workflows.

## 2. Git Ownership

The user controls Git publishing.

Codex must NOT:
- git push
- force push
- push tags
- merge to main
- open/merge remote PRs

Codex should not automatically commit.

At the end of work Codex should provide:
- git status
- changed files
- recommended commit message

The user decides when to commit and push.

## 3. Backtesting Execution

Signal produced on trading day T executes at the next trading day's OPEN.

No lookahead is allowed.

Long-only baseline.

BUY while already long:
ignored.

SELL while flat:
ignored.

Final-day signal:
cannot execute.

## 4. Survivorship Bias

Historical S&P 500 experiments currently use the current active constituent list.

Therefore results have survivorship bias.

This must always be disclosed.

## 5. EMA20 vs EMA50

Do not declare either universally superior.

Observed behavior:

EMA20:
- more defensive
- lower drawdown/giveback in many cases

EMA50:
- preserves strong trends
- benefits some large winners

## 6. HYBRID Exit

HYBRID exists to combine EMA20 protection with EMA50 trend persistence.

Development threshold experiment:
1%, 2%, 3%, 4%, 5%.

Selected:
2%

Selection was made on:
2021-08-20 -> 2024-12-31

The threshold is frozen.

Do not retune it on validation data.

## 7. HYBRID Production Status

HYBRID 2% passed later validation as a balanced candidate.

It is NOT yet automatically the Scanner default.

Final strategy/default choice should wait for portfolio-level evidence.

## 8. Micho V1

Micho 150 is currently a mechanical deterministic baseline.

Current core rules:
- SMA150
- trend filter
- breakout
- bounce
- close-below-SMA150 exit

Do not describe it as an exact implementation of discretionary/proprietary rules.

Do not add during current Sprint 6 experiment:
- news
- AI
- volume
- alternative stops
- alternative SMA periods
- new chart patterns

## 9. Do Not Optimize Micho From Validation Data

Micho performed materially better on the full five-year period than on the later validation period.

This suggests possible regime sensitivity.

Do not immediately tune parameters to make validation look better.

First isolate strategy components.

## 10. Executed Entry Reason Analytics

Raw BUY signals are not the same as executed entries.

Completed trade diagnostics must be used when evaluating:
- BREAKOUT
- BOUNCE

This is because BUY signals can occur while already holding a position.

## 11. BOTH-Mode Breakout vs Bounce Was Not Sufficient

Initial completed-trade diagnostics showed Breakout generally stronger than Bounce.

However:
Breakout often opens the position before later Bounce signals can act.

Therefore Bounce had fewer independent opportunities.

Decision:

Do NOT remove Bounce based solely on BOTH-mode diagnostics.

## 12. MichoEntryMode

Implemented:
- both
- breakout-only
- bounce-only

Default:
both

Reason:

Allow controlled isolation of entry logic without changing original V1 behavior.

## 13. Category Isolation

In bounce-only:

a day already classified as Breakout must not fall through and be reclassified as Bounce.

Reason:

The experiment must isolate existing categories rather than invent a different strategy.

## 14. Separate Report Files

Each Micho entry mode must produce a unique report name.

Examples:
- strategy_universe_micho_150_both_...
- strategy_universe_micho_150_breakout_only_...
- strategy_universe_micho_150_bounce_only_...

Experiments must never silently overwrite each other.

## 15. Smoke Test Result

10-stock validation smoke passed for:
- both
- breakout-only
- bounce-only

Preliminary result:

BREAKOUT_ONLY looked strongest.

BOUNCE_ONLY looked weakest.

But:

No strategy decision may be made from the 10-stock smoke.

A full-universe experiment is required.

## 16. Current Final Sprint 6 Experiment

Run:
- BOTH
- BREAKOUT_ONLY
- BOUNCE_ONLY

on the full current S&P 500 universe.

Validation period:
2025-01-01 -> 2026-08-20

Only entry mode may change.

Keep all other assumptions consistent.

## 17. Micho V2 Is Not Yet Approved

Do not change permanent Micho rules until the A/B/C full-universe results have been analyzed.

Potential future V2 work may be justified by the data, but must be a separate experiment.

## 18. Sprint 6 Must Produce a Completion Report

At the end of Sprint 6 create:

docs/SPRINT6_COMPLETION_REPORT.md

The report must contain:
- work completed
- files changed
- tests/checks
- full A/B/C results
- comparison
- final conclusion
- limitations
- Git state
- recommended commit message
- recommendation for Sprint 7

The report must be understandable without access to the Codex conversation.

## 19. Codex Stops After Sprint 6

Codex must NOT begin Sprint 7 automatically.

After producing:

docs/SPRINT6_COMPLETION_REPORT.md

stop.

The user will review the report with ChatGPT.

Sprint 7 begins only after that review.

## 20. Likely Sprint 7 Direction

Current likely next major architectural step:

Multi-Stock Portfolio Backtesting

Possible flow:

Scanner
→ Ranking
→ Candidate Selection
→ Position Sizing
→ Simultaneous Positions
→ Portfolio Constraints
→ Portfolio Equity
→ Portfolio Drawdown
→ Benchmark

This is only a recommendation.

Do not implement it during Sprint 6.

## 21. News Intelligence Is Future Work

Planned future layer:

Technical Strategy
+
News Collection
+
AI News Analysis
+
Risk Layer
→ Decision

Keep it separate from current technical validation.

## 22. Portfolio Manager Is Future Work

Long-term AlphaPilot should eventually create an actionable portfolio report including:
- capital allocation
- cash allocation
- stocks to buy
- stocks to sell
- quantities
- risk/stop rules
- position management
- rationale

This comes after strategy and portfolio validation.