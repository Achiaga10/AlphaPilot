# Sprint 20 Completion Report

## Outcome

Sprint 20 and its required hardening completed locally. Both EMA stop rounds and the Micho ATR study produced `NO_WINNER`; no EMA protective-stop default changed. Micho's existing numeric SMA150 completed-close exit is now explicitly represented as active strategy loss control, not an intraday broker stop, and can satisfy the loss-control portion of decision readiness when complete/fresh. The Copilot accepts Hebrew/mixed questions but always answers in English.

## Architecture and work performed

- Added an application-wide floating AlphaPilot AI panel with one unified visible chat; GENERAL, PORTFOLIO, and POSITION remain internal typed scopes selected through automatic intent/ticker resolution. Missing position tickers receive clarification. The panel includes user/assistant bubbles, a three-dot pending bubble, textarea Enter/Shift+Enter behavior, fixed outer layout with only message-history scrolling, and a direct handoff from Position Intelligence.
- Added an English-only direct-answer provider policy and small deterministic intent filter. Hebrew user text remains unchanged/RTL; assistant output is always English/LTR. Relevant evidence is secondary and collapsible.
- Added canonical read-only product/navigation facts and high-level General/Portfolio Copilot endpoints. Navigation answers cannot mutate state or execute actions.
- Preserved “Why this position?” and its detailed intelligence workflow.
- Added numeric distance dollars/percent to backend-owned strategy-exit references; these remain completed-close strategy references, not protective broker stops.
- Generalized readiness to immutable numeric `LossControlEvidence`. A BUY without approved numeric boundary and explicit trigger is `RESEARCH_ONLY / NO_APPROVED_LOSS_CONTROL_POLICY`. Valid Micho `SMA150_COMPLETED_CLOSE_EXIT` evidence is `ACTIONABLE / LOSS_CONTROL_READY` at the decision layer while `broker_stop_order=false`; this never submits an order.
- Preserved normal Micho BOTH re-entry only. There is no automatic re-buy shortcut after an SMA150 exit.
- Added 1.0× and 2.5× static ATR14 candidates to the existing no-lookahead daily-OHLC trade-management engine without changing existing 1.5×/2.0×/3.0× behavior.
- Added a snapshot-bound, identity-stable Strategy Lab protocol, closed candidate spaces, explicit stage guards, development/validation gate evaluators, and no-fallback tests.
- Ran the complete declared development/validation/fold experiment. Full tables and interpretation are in [SPRINT20_STOP_RESEARCH_RESULTS.md](SPRINT20_STOP_RESEARCH_RESULTS.md).
- Froze and ran the distinct Round 2 structural study documented in [SPRINT20_EMA_STOP_RESEARCH_ROUND2_PROTOCOL.md](SPRINT20_EMA_STOP_RESEARCH_ROUND2_PROTOCOL.md); full results are in [SPRINT20_EMA_STOP_RESEARCH_ROUND2_RESULTS.md](SPRINT20_EMA_STOP_RESEARCH_ROUND2_RESULTS.md).

## Files created

- `backend/src/alphapilot/portfolio/execution_readiness.py`
- `backend/src/alphapilot/copilot/intent.py`
- `backend/src/alphapilot/copilot/navigation.py`
- `backend/src/alphapilot/strategy_lab/sprint20_stop_protocol.py`
- `backend/tests/backtesting/test_sprint20_protocol.py`
- `backend/tests/portfolio/test_execution_readiness.py`
- `backend/tests/strategy_lab/test_sprint20_stop_protocol.py`
- `frontend/src/features/copilot/FloatingCopilot.tsx`
- `docs/sprints/SPRINT20_PLAN.md`
- `docs/sprints/SPRINT20_STOP_RESEARCH_PROTOCOL.md`
- `docs/sprints/SPRINT20_STOP_RESEARCH_RESULTS.md`
- `docs/sprints/SPRINT20_COMPLETION_REPORT.md`
- `docs/sprints/SPRINT20_EMA_STOP_RESEARCH_ROUND2_PROTOCOL.md`
- `docs/sprints/SPRINT20_EMA_STOP_RESEARCH_ROUND2_RESULTS.md`

## Files modified

`AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, trade-management protocol/CLI/models/tests, Copilot policy/tests, decision models/schemas, stop-exit guidance/tests, frontend layout/styles/types, Position Intelligence panel, and layout tests. See final `git diff --stat` for exact paths.

## Protective-stop semantics

ATR14 is computed only through signal day. Static stop = entry price − candidate multiple × frozen entry ATR14. It activates on the next session; a gap through fills at open, otherwise a low breach fills at the stop. Existing strategy exits remain active. Daily OHLC ambiguity is resolved conservatively in favor of the stop. Whole existing cost/accounting semantics remain unchanged. Trailing and profit candidates were not reopened because Sprint 12 closed that evidence.

## Research governance and result

Canonical snapshot: `5dd60f87-8947-4850-ba87-4a7df655528c`; dataset SHA-256 `b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`; universe SHA-256 `369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8`. Development was 2021-08-20–2024-12-31; reused/previously observed validation evidence was 2025-01-01–2026-08-20; folds were the three declared periods. COST_LOW was 5 bps per side with zero commission.

EMA froze 2.0× after development, then failed validation because drawdown worsened 1.62 points against the 1.5-point ceiling. Micho froze 1.5×, then failed validation due 2.00-point drawdown worsening, 8.19-point top-5 concentration worsening, and 79.07% 20-session stop recovery. Both were directionally better on return, Sharpe, and drawdown in 2/3 folds. Hard failures take precedence: both outcomes are `NO_WINNER`, with no fallback or parameter retuning.

## Exact commands

All commands were run from `backend/` with `$env:DEBUG='false'`:

```text
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage sprint20-development --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label development --configuration control --configuration atr-stop-2-0 --configuration atr-stop-2-5 --configuration atr-stop-3-0 --output-dir backtest_reports/sprint20
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage sprint20-development --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label development --configuration atr-stop-2-5 --configuration atr-stop-3-0 --output-dir backtest_reports/sprint20
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2021-08-20 --end 2024-12-31 --stage sprint20-development --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label development --configuration control --configuration atr-stop-1-0 --configuration atr-stop-1-5 --configuration atr-stop-2-0 --configuration atr-stop-2-5 --output-dir backtest_reports/sprint20
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2025-01-01 --end 2026-08-20 --stage sprint20-validation --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label validation --configuration control --configuration atr-stop-2-0 --output-dir backtest_reports/sprint20
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2025-01-01 --end 2026-08-20 --stage sprint20-validation --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label validation --configuration control --configuration atr-stop-1-5 --output-dir backtest_reports/sprint20
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2022-12-31 --stage sprint20-fold --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label fold-1 --configuration control --configuration atr-stop-2-0 --output-dir backtest_reports/sprint20
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2023-01-01 --end 2024-12-31 --stage sprint20-fold --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label fold-2 --configuration control --configuration atr-stop-2-0 --output-dir backtest_reports/sprint20
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2021-08-20 --end 2022-12-31 --stage sprint20-fold --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label fold-1 --configuration control --configuration atr-stop-1-5 --output-dir backtest_reports/sprint20
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2023-01-01 --end 2024-12-31 --stage sprint20-fold --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label fold-2 --configuration control --configuration atr-stop-1-5 --output-dir backtest_reports/sprint20
```

The first EMA development process was interrupted after writing control and 2.0×; the second listed command resumed only missing 2.5×/3.0× artifacts. Configuration-identical validation artifacts were verified and reused as fold 3 rather than rerun.

Round 2 commands, frozen before result inspection:

```text
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage sprint20-round2-development --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label development --configuration control --configuration atr-stop-2-0 --configuration signal-day-low-invalidation --output-dir backtest_reports/sprint20/ema-round2
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2025-01-01 --end 2026-08-20 --stage sprint20-round2-validation --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label reused-validation --configuration control --configuration atr-stop-2-0 --output-dir backtest_reports/sprint20/ema-round2
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2022-12-31 --stage sprint20-round2-fold --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label fold-1 --configuration control --configuration atr-stop-2-0 --output-dir backtest_reports/sprint20/ema-round2
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2023-01-01 --end 2024-12-31 --stage sprint20-round2-fold --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label fold-2 --configuration control --configuration atr-stop-2-0 --output-dir backtest_reports/sprint20/ema-round2
```

The first Fold 1 attempt after a power interruption failed because local PostgreSQL was offline. The existing `alphapilot-postgres` Docker volume was restarted without schema/data reset, and the command then passed. Fold 3 reused the configuration-identical 2025–2026 artifact.

## Tests and quality gates

- Focused backend after hardening: 48 passed (trade management, both Sprint 20 protocols, Strategy Lab gates, loss-control readiness, decisions, Copilot).
- Decision/action compatibility: 22 passed.
- Frontend floating-Copilot coverage proves automatic ticker attribution and correct display of the original Hebrew user text; assistant responses remain English/LTR. The existing Position Intelligence Copilot workflow remains covered.
- Final `backend/run_checks.ps1`: PASS — Ruff PASS, mypy PASS (170 source files), pytest 351 passed.
- Frontend: Vitest 16 files/75 tests PASS; ESLint PASS; TypeScript/Vite production build PASS.
- An earlier-stage real Edge/Playwright smoke used the then-visible context controls and captured Git-ignored `backend/backtest_reports/sprint20/ui-copilot-smoke.png`. Final browser acceptance superseded that interaction model: one unified visible chat, automatic AAPL entity resolution, unchanged Hebrew user text, and English/LTR grounded assistant output.
- The older Sprint 11D smoke was also attempted but timed out looking for its obsolete removed `Cash (USD)` field; it did not test Sprint 20. The focused Sprint 20 smoke supersedes it for this feature.

## Product status and limitations

The conversational UX is suitable for the existing read-only grounded use case. It does not calculate facts, mutate portfolios, recommend arbitrary boundaries, or execute orders. EMA has no approved protective-stop candidate and remains research-only for new BUY readiness. Micho's frozen numeric SMA150 completed-close loss control can satisfy decision readiness when authoritative current data exists, without being mislabeled as an intraday order. There is no broker connection or live order state.

Limitations: survivorship bias/current-constituent universe; `LEGACY_PARTIAL` snapshot provenance despite value reproducibility; fixed 5 bps cost; SPY benchmark limitations; daily OHLC path ambiguity; final-open positions marked to market; Micho unrealized-P&L and contributor dependence; local-provider language quality may vary; browser-only bounded conversation memory; no authentication/account persistence for Copilot history; and no live broker execution/readiness validation.

## Hardening acceptance summary

- English-only answers: implemented; Hebrew/mixed questions retain original user text and receive English LTR assistant answers.
- Direct factual answers: deterministic intent filtering limits provider context to relevant backend facts (average cost, quantity, entry/current price, P&L, monitoring, exit/loss control, trailing/target, paper, or navigation). Generic fact dumping is reduced; unavailable facts stay unavailable.
- Chat UX: distinct bubbles, animated three dots, fixed header/composer, inner message scroll only, no static history footer, automatic internal scope/entity resolution, missing-ticker clarification, and collapsible evidence.
- General help: canonical routes/purposes are backend facts; the endpoint is read-only and has no mutation/tool surface. Existing “Why this position?” and floating handoff remain.
- Micho: numeric current SMA150 boundary, exact completed-close trigger, active strategy-loss-control status, and `broker_stop_order=false` are backend-owned. Intraday touch alone remains non-triggering. Missing/invalid boundary cannot be actionable. No ATR stop or auto-rebuy was fabricated; normal BOTH re-entry remains.
- EMA Round 2: protocol path and closed candidates are documented above. Result is `NO_WINNER`; no candidate classification, profile promotion, or default change occurred.
- Hard safety: AI cannot calculate a boundary, React cannot calculate it, arbitrary fallback is impossible, and an actionable BUY cannot lack positive numeric loss-control evidence plus explicit trigger semantics.

## 2026-08-30 hardening and Round 2 final report

1. English-only answers: **YES**.
2. Hebrew questions receive English answers: **YES**; original user text is retained.
3. Specific questions receive direct answers: **YES**, enforced by direct-answer policy and intent-scoped facts.
4. Average-cost acceptance: **PASS**; only ticker and backend average cost are supplied for that intent.
5. Generic position dump: **materially reduced**; unrelated paper/monitoring facts are excluded.
6. Three-dot indicator: **YES**, an assistant-style animated pending bubble.
7. Outer scrollbar: **removed** with outer `overflow: hidden`.
8. Inner scrolling: **YES**, conversation history owns `overflow-y: auto`.
9. Unified chat routing: **YES**; GENERAL, PORTFOLIO, and POSITION are internal typed scopes, with automatic ticker resolution and missing-ticker clarification rather than a visible selector.
10. Navigation grounding: **YES**, from one canonical backend product-navigation map.
11. “Why this position?”: **preserved**, including its Ask AI handoff.
12. Numeric SMA150 boundary: **YES**, backend-owned current boundary.
13. Completed-close trigger: **preserved exactly**.
14. Intraday touch: **remains non-triggering** under frozen Micho semantics.
15. Micho loss-control readiness: **YES** when current positive SMA150 and explicit trigger evidence exist.
16. Automatic re-buy added: **NO**.
17. Normal future Micho re-entry: **preserved** through frozen BOTH rules and portfolio constraints.
18. Round 2 protocol: `docs/sprints/SPRINT20_EMA_STOP_RESEARCH_ROUND2_PROTOCOL.md`.
19. New hypothesis family: completed BUY signal-candle LOW structural invalidation; ATR2 is reference only.
20. Closed space: `control`, `atr-stop-2-0`, `signal-day-low-invalidation`.
21. Round 2 result: structural arm failed development turnover; ATR2 failed reused-validation drawdown.
22. Final Round 2 decision: **`NO_WINNER`**.
23. Candidate classification: not applicable; no candidate advanced to paper-forward status.
24. Default EMA profile changed: **NO**.
25. Arbitrary fallback possible: **NO**.
26. AI can calculate a boundary: **NO**.
27. React can calculate a boundary: **NO**; typed backend facts are display-only.
28. Actionable trade can lack numeric loss control: **NO**.
29. Backend gate: **PASS** — Ruff, formatting, mypy (170 files), pytest (351 passed).
30. Frontend gate: **PASS** — ESLint, 16 files/75 tests, TypeScript/Vite build.
31. Browser acceptance: **PASS** — unified General help, typing dots, automatic position resolution, unchanged Hebrew user text, and English/LTR assistant response.
32. Git status: branch `feature/conversational-copilot-risk-policy`; 30 tracked modified paths and 20 untracked status entries; no commit. Ignored reports are under `backend/backtest_reports/sprint20/`.
33. Recommended commit: `feat: unify grounded Copilot context and entity resolution`.

## Real Ollama Copilot reliability fix

### Root cause and failure attribution

The reported APA question `what is the avarge cost of a share that i bought?` exposed two coupled defects. The intent classifier did not recognize the real-world `avarge cost` typo, so an exact portfolio fact was misrouted to the generative `GENERAL` path. That path also imposed an unnecessarily brittle provider contract: Ollama had to generate the answer, grounding status, and exact server fact-reference identifiers. The API then rejected model-produced references that did not exactly match the filtered server evidence. The observed failure category was therefore `AI_RESPONSE_INVALID`, not provider unavailability: Ollama was configured as `qwen3:8b`, running, and reported `AVAILABLE` during reproduction. The old UI collapsed provider availability and response-validation failures into one generic message, which hid that distinction.

This was an application integration and response-contract defect, not an Ollama installation defect and not a research-data defect. The original invalid model field cannot be reconstructed from the old UI because the rejected payload was not safely retained, but the failing route and validation boundary are exact: typo misclassification sent the question to Ollama, and the server rejected the generated structured evidence contract.

### Implemented reliability boundary

Exact factual intents now bypass Ollama completely. Backend-owned deterministic rendering covers average cost (including `average cost`, `avg cost`, `avarge cost`, `cost basis per share`, and Hebrew equivalents), quantity, entry price, current completed-session price, market value, current unrealized P&L, monitoring status, stop/exit guidance, trailing-stop status, and profit-target status. Missing facts produce a controlled `FACT_UNAVAILABLE` answer; the service never fabricates zero or substitutes another fact.

Ollama remains in use for genuinely explanatory requests such as "Why am I holding APA?" and general navigation explanations. Its provider contract is deliberately small: `{ "answer": "..." }`. Grounding status, result status, and evidence references are owned and attached by the server, so model-generated identifiers can no longer corrupt the evidence contract. Deterministic responses identify provider `alphapilot` and model `deterministic-direct-answer-v1`; explanatory responses retain provider `ollama` and model `qwen3:8b`.

The API now returns distinct typed `AI_PROVIDER_UNAVAILABLE` (503) and `AI_RESPONSE_INVALID` (502) errors without exposing raw provider content or secrets. The UI preserves the user's question, presents a provider-specific recovery message, and offers Retry. An unavailable provider does not affect deterministic factual requests.

### Real acceptance evidence

Acceptance used the real current research portfolio and its actual APA position, the real FastAPI service, real Vite UI, Edge/Playwright, and the locally configured Ollama `qwen3:8b`; it did not use mocked provider output. The completed-session portfolio facts were average cost `$42.38`, 235 shares, current completed close `$42.53`, and unrealized P&L `+$35.25 (+0.35%)`.

- Exact typo question: PASS in API and browser, returning `Your average cost for APA is $42.38 per share.` through the deterministic provider path.
- Average-cost aliases and Hebrew UTF-8 question: PASS through the same deterministic path.
- Quantity, current price, and P&L questions: PASS without invoking Ollama.
- "Why am I holding APA?": PASS through real Ollama with server-owned evidence references.
- Stop/SELL question: PASS through deterministic backend facts; the existing EMA50 reference was `$38.48` and was not converted into an approved protective stop.
- Provider outage: PASS. With Ollama stopped, the typo average-cost question still returned 200; the explanatory question returned typed `AI_PROVIDER_UNAVAILABLE`, and the browser showed the recovery message and Retry control.
- Provider recovery: PASS. Ollama was restarted, status returned `AVAILABLE`, and the explanatory request succeeded again.
- Final real browser smoke: PASS in both provider-available and provider-unavailable modes. Ollama was restored and left available afterward.

### Reliability tests and final gates

- Focused Copilot backend suite: 19 passed.
- Frontend Copilot regression coverage includes typo-based factual success, no irrelevant paper-position dump, fact-unavailable handling, typed provider-unavailable and invalid-response messages, retained question, and successful Retry.
- Frontend final gate: ESLint PASS; Vitest 16 files / 75 tests PASS; TypeScript/Vite production build PASS.
- Backend final `run_checks.ps1`: Ruff and formatting PASS; mypy PASS across 170 source files; pytest 351 passed.

The reliability hardening was completed by Codex on top of the existing locally complete Sprint 20 implementation. Earlier Sprint 20 implementation and continuation work remains attributable as already documented, including the Antigravity continuation handoff; this final pass specifically owns the intent aliases, deterministic direct-answer layer, simplified provider contract, server-owned evidence, typed error/retry behavior, real Ollama/browser outage acceptance, and this report amendment. No stop-research artifact, research result, strategy rule, or default was changed.

Updated recommended commit message: `fix: make Copilot factual answers deterministic and resilient`.

## Unified Copilot Context Resolution

The final UX hardening removes the visible General / Portfolio / Position context
selector. AlphaPilot now exposes one conversation while preserving those three scopes
as typed internal backend concepts. The new read-only endpoint is
`POST /api/v1/ai/copilot/portfolio/{portfolio_id}/query`; its request contains the
question plus optional short-lived `active_ticker` and `pending_intent` session state.
Its response retains authoritative scope, ticker, intent, resolution status, and
server-owned evidence.

The deterministic pipeline is: intent detection, stored company/open-position entity
resolution, scope resolution, backend context assembly, then either direct rendering or
Ollama explanation. Tickers are matched case-insensitively only against safe stored
entities, normalized uppercase, and never delegated to Ollama. Reserved strategy/action
words such as SELL, HOLD, STOP, EMA, ATR, and AI are not treated as tickers. Exact stored
company names and unambiguous primary company names may also resolve an identity.
Multiple explicit tickers produce the one-position-at-a-time limitation rather than
silently choosing one.

Position questions without a resolvable ticker return deterministic
`CLARIFICATION_REQUIRED` with `Which ticker do you mean?` and do not call Ollama. The
browser retains that one pending intent, so a next message containing only `APA` resolves
the original request. Successful explicit resolution establishes one active ticker for
immediately relevant follow-ups. `What about FAST?` deterministically changes the active
entity; previous bubbles retain their original scope/ticker attribution. The state is
cleared after unrelated resolution where appropriate or by `Clear position context`.
Opening the global chat starts without a ticker; only the explicit Why-this-position
handoff may seed one.

Unknown tickers return a typed/product-safe identification failure. A stored company
without an open research position returns a separate known-but-not-held response and
never fabricates a zero quantity. General navigation questions and portfolio-wide value,
cash, count, and monitoring questions resolve without a ticker. Navigation and exact
financial facts are deterministic backend answers. Explanatory position questions use
Ollama only after successful ticker resolution, and the server still owns evidence IDs.

The header now shows only the product identity, read-only grounding statement, and an
optional `Currently discussing: TICKER` indicator. Chat history is preserved across
entity changes. A controlled textarea prevents clarification replies from concatenating
with the previous question. Auto-scroll runs after user/pending and response/error state
updates by setting only the `Copilot message history` container to its current
`scrollHeight`; the page and outer panel are never scrolled. Immediate (`auto`) behavior
was selected because real browser acceptance showed smooth scrolling could leave the
three-dot indicator temporarily below the viewport.

Focused backend Copilot tests: 29 passed. They cover explicit FAST and lowercase `fast`,
APA/Apple resolution, missing-ticker clarification, pending-intent continuation, active
ticker reuse/switching, multi-ticker limitation, reserved words, GENERAL and PORTFOLIO
routing, unknown versus known-not-held, deterministic-provider bypass, explanatory
provider use, and the typed unified API. Frontend regression coverage includes selector
removal, global open, FAST attribution, clarification with `APA` alone, APA follow-up,
switching to FAST without relabeling history, explicit Position Intelligence handoff,
provider error/retry, and inner-history auto-scroll for user, typing, answer,
clarification, and error states.

Final live Edge/Playwright acceptance used the real Vite UI, FastAPI backend, current
research portfolio, stored company/position data, and local Ollama. It passed:

- no visible context selector;
- `Where do I sync market data?` -> deterministic Data Management guidance;
- `How many shares do I own? FAST` -> actual stored 195-share FAST answer;
- cleared context plus `How many shares do I own?` -> clarification;
- `APA` alone -> actual stored 235-share APA answer;
- `What is my average cost?` -> APA `$42.38` follow-up;
- `What about FAST?` then average-cost follow-up -> FAST;
- a real `Why am I holding FAST?` Ollama explanation; and
- the typing indicator and final answer at the bottom of message history while window
  scroll and outer-panel scroll remained unchanged.

Final quality gates after this pass: backend Ruff/formatting PASS, mypy PASS across 170
source files, and pytest 351 passed; frontend ESLint PASS, Vitest 16 files / 75 tests
PASS, and TypeScript/Vite production build PASS. No strategy, ranking, sizing,
ExecutionReadiness, stop-research result, `NO_WINNER` conclusion, HYBRID 2%, or SMA150
financial semantics changed.

Updated recommended commit message:
`feat: unify grounded Copilot context and entity resolution`.

## Glossary / Definition Intent Hardening

The final Copilot semantic pass added a deterministic, server-owned `GLOSSARY` intent
for AlphaPilot terminology. Conceptual wording such as `What is stop loss?`,
`Do you know what is stop loss?`, `What does trailing stop mean?`, `What is EMA50?`,
and `What is ATR14?` now resolves in GENERAL scope without requiring or reusing a
ticker. Canonical definitions cover stop/loss-control concepts, strategy exit
references, targets, cost/P&L terms, EMA/SMA/ATR, and monitoring actions; Ollama is
not used to calculate or establish their meanings.

Definition intent takes precedence over active-entity reuse. With APA active, a plain
stop-loss definition remains general, while possessive wording such as `What is my
stop loss?` remains position-specific and safely uses APA. Without an explicit or
active ticker, the same possessive question asks `Which ticker do you mean?`.
`What is my stop loss for FAST?` and `Does FAST have a trailing stop?` retain FAST's
authoritative position facts. STOP, EMA/EMA50, and ATR/ATR14 are never treated as
ticker entities in definition questions.

The AlphaPilot stop-loss definition explicitly distinguishes an approved protective
stop, a deterministic strategy loss-control boundary, and a strategy exit reference.
It also states that Micho's completed daily close below SMA150 is not an intraday
broker stop order. This change introduced no mutation, provider-side financial
calculation, research change, or backtest rerun.

Focused Copilot validation passed 29 tests. The complete backend gate passed Ruff and
formatting, mypy across 170 source files, and all 351 pytest tests. The frontend gate
passed ESLint, all 75 Vitest tests across 16 files, and the production build. Real
Edge/Playwright acceptance against the running FastAPI/Vite application established APA,
asked `Do you know what is stop loss?`, verified the general definition contained no APA
position answer, then asked `What is my stop loss?` and received APA-specific guidance.
Both responses remained visible through the existing inner-history auto-scroll behavior.

## Recommendation

Do not activate an EMA protective stop and do not begin Sprint 21 automatically. Keep stop/trailing/profit defaults `NONE`; retain Micho's existing completed-close SMA150 exit as active strategy loss control. Review Sprint 20 evidence with the user. Any future EMA study must use a newly approved protocol rather than tuning these failed candidates.

## Git handoff

Branch: `feature/conversational-copilot-risk-policy`. The working tree intentionally contains 30 tracked modified paths and 20 untracked status entries, all local Sprint 20 work, with no commit. Git-ignored research artifacts under `backend/backtest_reports/sprint20/` are not listed by Git. Recommended commit message: `feat: unify grounded Copilot context and entity resolution`.
