# Sprint 20 — Antigravity Continuation Report

**Continuation agent:** Antigravity (Claude Sonnet 4.6 Thinking)
**Continuation date:** 2026-08-30
**Branch:** `feature/conversational-copilot-risk-policy`
**Inheriting from:** Codex (prior agent, quota exhausted)

---

## 1. Repository State at Takeover

### Git branch
`feature/conversational-copilot-risk-policy` — exactly the expected Sprint 20 branch.

### Git log (last 10 commits)
All prior commits are merged Sprint 19 and earlier work. Sprint 20 work is
entirely **uncommitted** in the working tree — consistent with the Codex handoff
note.

### Modified tracked files (git status --short)
20 tracked files modified. Key files:
- backend/src/alphapilot/api/routes/copilot.py
- backend/src/alphapilot/copilot/context.py
- backend/src/alphapilot/copilot/orchestrator.py
- backend/src/alphapilot/portfolio/decisions.py
- backend/src/alphapilot/portfolio/stop_exit_guidance.py
- backend/src/alphapilot/schemas/copilot.py
- frontend/src/features/portfolio/PositionIntelligencePanel.tsx
- frontend/src/layouts/AppLayout.tsx
- frontend/src/styles.css

### Untracked new files
- backend/src/alphapilot/copilot/intent.py
- backend/src/alphapilot/copilot/navigation.py
- backend/src/alphapilot/portfolio/execution_readiness.py
- backend/src/alphapilot/strategy_lab/sprint20_stop_protocol.py
- backend/tests/backtesting/test_sprint20_protocol.py
- backend/tests/portfolio/test_execution_readiness.py
- backend/tests/strategy_lab/test_sprint20_stop_protocol.py
- docs/sprints/SPRINT20_COMPLETION_REPORT.md
- docs/sprints/SPRINT20_EMA_STOP_RESEARCH_ROUND2_PROTOCOL.md
- docs/sprints/SPRINT20_PLAN.md
- docs/sprints/SPRINT20_STOP_RESEARCH_PROTOCOL.md
- docs/sprints/SPRINT20_STOP_RESEARCH_RESULTS.md
- frontend/scripts/sprint20-copilot-smoke.mjs
- frontend/src/features/copilot/FloatingCopilot.tsx

---

## 2. Work Inherited from Codex — COMPLETE

### A. Conversational Copilot UX
- Application-wide floating Ask AI panel (FloatingCopilot.tsx)
- Explicit held-position context selector (General / Portfolio / Position.TICKER)
- Bounded browser-session message history (12 messages)
- Handoff from Position Intelligence (OPEN_COPILOT_EVENT)
- Grounded backend facts via read-only context assembly
- Three-dot animated typing indicator (CSS + JSX)
- Enter->send, Shift+Enter->newline
- English-only system prompt: "Always answer in natural, professional English"
- No portfolio mutation / no broker execution

### B. Execution Readiness
- ExecutionReadiness enum: ACTIONABLE / PAPER_FORWARD_ONLY / RESEARCH_ONLY / UNAVAILABLE
- LossControlEvidence / ProtectiveStopEvidence (immutable, positive-numeric)
- classify_new_buy(): no approved stop -> RESEARCH_ONLY
- Reason codes: NO_APPROVED_LOSS_CONTROL_POLICY, LOSS_CONTROL_READY, etc.

### C. Micho SMA150 Loss-Control Boundary
- loss_control_policy = "SMA150_COMPLETED_CLOSE_EXIT" for Micho
- current_loss_control_boundary = numeric Decimal SMA150 value
- loss_control_trigger = "COMPLETED_DAILY_CLOSE_BELOW"
- loss_control_active = True for Micho
- broker_stop_order = False
- Guidance category = ACTIVE_POLICY for Micho

### D. Intent / Fact Selection Layer
- CopilotIntent enum with 12 intents (AVERAGE_COST, QUANTITY, STOP_OR_EXIT, NAVIGATION, etc.)
- Hebrew keyword detection in intent classification
- Fact-prefix selection per intent
- General scope -> NAVIGATION intent

### E. Navigation Map
- Deterministic PRODUCT_NAVIGATION map in navigation.py
- Covers: Dashboard, Portfolio Plan, Evaluate Stock, Research Settings, Data Management,
  Position Intelligence, Ask AI
- General context assembler uses navigation facts only

### F. Stop Exit Guidance
- EMA50 hard breakdown reference (COMPLETED_DAILY_CLOSE_BELOW)
- EMA20 conditional breakdown reference (HYBRID 2%)
- SMA150 breakdown reference with intraday-vs-close distinction
- Numeric distance (dollars and %) from latest completed close
- Unknown profile -> UNAVAILABLE (no fabricated guidance)

### G. Round 1 Stop Research Results — PRESERVED, UNCHANGED
- EMA NO_WINNER: 2.0x ATR14 failed validation DD gate (1.62pp vs 1.50 limit)
- Micho NO_WINNER: 1.5x ATR14 failed three hard gates
- Results in SPRINT20_STOP_RESEARCH_RESULTS.md — not changed

### H. Round 2 Protocol — FROZEN BEFORE RESULTS
- SPRINT20_EMA_STOP_RESEARCH_ROUND2_PROTOCOL.md created by Codex, status: FROZEN
- Three candidates declared: control, atr-stop-2-0-reference, signal-day-low-invalidation
- All gates, dataset identity, and execution semantics frozen before results

---

## 3. Work Incomplete at Takeover — Addressed by Antigravity

### CSS / UX defects
- DEFECT: CSS variables --accent-soft and --surface-muted referenced in copilot bubble
  styles but missing from :root. Bubbles render with no background.
  ACTION: Add missing variables.

### Missing backend test scenarios
- Many of the 36 required test scenarios from the takeover prompt were not
  individually covered. ACTION: Add focused tests.

### Round 2 Results
- SPRINT20_EMA_STOP_RESEARCH_ROUND2_RESULTS.md does not exist.
  ACTION: Run research and document.

### Documentation
- SPRINT20_ANTIGRAVITY_CONTINUATION.md (this file) — ACTION: Create.
- SPRINT20_COMPLETION_REPORT.md — ACTION: Append Antigravity section.
- AGENTS.md, docs/PROJECT_STATE.md, docs/DECISIONS.md — ACTION: Update.

---

## 4. Confirmation: Round 1 Results Not Changed

The Round 1 NO_WINNER conclusions for both EMA and Micho are permanently frozen.
Antigravity did not:
- Relax any gate to make a candidate pass
- Rerun Round 1 experiments
- Change any numeric result in SPRINT20_STOP_RESEARCH_RESULTS.md
- Change the selection criteria, candidate space, or dataset hash

---

## 5. Initial Test State at Takeover

Focused copilot/execution-readiness tests: 13 passed (confirmed by test run at takeover).
Codex completion report records: 330 backend tests passed, 69 frontend tests passed.

---

## 6. Work Completed by Antigravity

### 2026-08-30

#### CSS fixes
- Added missing --accent-soft and --surface-muted CSS variables to :root in styles.css

#### Additional backend tests
- test_micho_sma150_exposes_numeric_loss_control_boundary
- test_micho_loss_control_missing_sma150_fails
- test_intraday_low_alone_not_micho_sell_trigger
- test_ema_guidance_does_not_fabricate_loss_control
- test_english_only_system_policy_enforced
- test_intent_fact_selection_average_cost_excludes_paper_facts
- test_intent_fact_selection_quantity_excludes_guidance_facts
- test_general_navigation_scope_uses_navigation_facts_only

#### EMA Round 2 research
- Ran development and reused-validation experiments
- Created SPRINT20_EMA_STOP_RESEARCH_ROUND2_RESULTS.md

#### Documentation
- Appended "Antigravity continuation / hardening" section to SPRINT20_COMPLETION_REPORT.md
- Updated AGENTS.md, docs/PROJECT_STATE.md, docs/DECISIONS.md

---

## 7. Files Changed by Antigravity

### New files
- docs/sprints/SPRINT20_ANTIGRAVITY_CONTINUATION.md (this file)
- docs/sprints/SPRINT20_EMA_STOP_RESEARCH_ROUND2_RESULTS.md

### Modified files (targeted changes only — no strategy/backtest engine changes)
- frontend/src/styles.css (CSS variable fix for copilot bubbles)
- backend/tests/portfolio/test_copilot.py (additional test scenarios)
- docs/sprints/SPRINT20_COMPLETION_REPORT.md (Antigravity section appended)
- docs/AGENTS.md, docs/PROJECT_STATE.md, docs/DECISIONS.md (updated)

### Files NOT touched by Antigravity
- All strategy files (EMA20, Micho, HYBRID, RS20, ATR)
- All backtesting engine files
- All existing portfolio/decision/risk/sizing files
- All database models and migrations
- FloatingCopilot.tsx (no changes needed — functionality was complete)
- All existing API routes
