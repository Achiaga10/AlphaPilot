# AlphaPilot Sprint 14 Plan — Strategy-Specific Configuration Profiles

## 1. Goal

Make the backend the authoritative source for each strategy's frozen research
configuration. The normal Portfolio Plan workflow will accept a strategy and
selection policy, resolve a versioned strategy profile, and return that profile
with every plan so the UI can explain exactly what was applied.

## 2. Scope

- Add an immutable, deterministic backend profile registry and resolver.
- Add a typed read endpoint for all strategy profiles.
- Resolve profiles in the high-level `POST /api/v1/portfolio/plan` workflow.
- Include profile identity/version/configuration in plan responses and plan IDs.
- Bind stateless plan actions to the profile that produced the plan.
- Remove sizing and strategy-rule authority from the normal frontend request.
- Render backend-provided profile facts in Portfolio Plan and Settings.
- Preserve old browser draft data while ignoring its obsolete sizing field.

## 3. Non-goals

- No new strategy, entry, exit, stop, profit, ranking, sizing, or risk research.
- No parameter tuning or validation experiment.
- No changes to strategy factory defaults, Scanner behavior, T+1 execution,
  completed-session filtering, or Sprint 13 research-data semantics.
- No broker integration, authenticated persistence, or durable plan storage.
- No Sprint 15 Strategy Lab implementation.

## 4. Backend Profile Architecture

`strategy/profile.py` will own frozen dataclasses/enums and a deterministic
registry keyed by `StrategyName`. A strict resolver will return the exact
immutable profile or raise a stable unknown-profile error. Pydantic response
schemas will serialize these domain objects without exposing mutable registry
state.

The normal path becomes:

`PortfolioPlanRequest -> profile resolver -> explicit PortfolioDecisionOrchestrator -> PortfolioDecisionPlan`.

The existing lower-level `POST /portfolio/decisions` remains explicitly
configurable for research and compatibility.

## 5. Frozen Profile Definitions

### EMA20 Pullback

- profile ID/version: `ema20-pullback-v1` / `1`
- classification: `PROMISING_RESEARCH_BASELINE`
- entry: existing EMA20 Pullback reclaim logic
- selection: user-selectable; recommended `relative-strength-20`
- sizing: `equal-slot`
- strategy exit: `HYBRID`, frozen threshold `2%`
- default protective stop: `NONE`
- default profit management: `NONE`
- informational research-only stop candidate: static `3 × ATR14`

### Micho 150

- profile ID/version: `micho-150-v1` / `1`
- classification: `PROMISING_RESEARCH_BASELINE`
- entry: Micho V1 `BOTH`
- selection: user-selectable; recommended `relative-strength-20`
- sizing: `atr-volatility-normalized`
- strategy exit: existing close below SMA150
- default protective stop: `NONE`
- default profit management: `NONE`
- informational research-only stop candidate: static `1.5 × ATR14`

Global `PortfolioRiskConfig` remains separate and unchanged. No
strategy-specific global risk parameters will be invented.

## 6. Authority and Compatibility Rules

- Normal clients choose strategy and selection policy only.
- Profile-owned sizing, EMA exit/threshold, and Micho entry mode are not accepted
  as normal request authority.
- The explicit lower-level orchestration/decision interfaces remain available.
- Existing strategy factory defaults and Scanner behavior remain unchanged.
- Legacy `alphapilot.plan-draft.v1` values retain cash, positions, strategy,
  selection, date, and ticker scope; any stored sizing value is ignored.

## 7. Plan Identity and Stateless Action Safety

The plan fingerprint will include the authoritative profile ID, version, and
resolved configuration. Plan responses and action requests will carry profile
identity. Preview/apply will reject profile/sizing mismatches before changing
the browser research portfolio. This remains stateless validation rather than
durable server-side plan storage.

## 8. API Contract

- `GET /api/v1/portfolio/strategy-profiles` returns typed ordered profile facts.
- `POST /api/v1/portfolio/plan` accepts high-level inputs and returns the
  resolved profile alongside the existing typed plan.
- Existing plan action endpoints receive and validate profile identity.
- `POST /api/v1/portfolio/decisions` remains the explicit research interface.

## 9. Frontend Contract

- Remove `sizingPolicy` from `PlanDraft` and the normal plan request.
- Remove the sizing selector and the client-owned classification table.
- Load profiles through the typed API/query layer with runtime validation.
- Show the selected backend profile near the Plan configuration.
- Show all backend profiles and global risk defaults on Settings.
- Continue rendering generated plans and actions from response-owned sizing.
- Evaluate Stock uses the same profile-driven high-level request while retaining
  strict target identity and latest-request-wins behavior.

## 10. Testing Requirements

Backend focused coverage will verify deterministic registry order, exact EMA
and Micho facts, strict unknown handling, profile endpoint serialization,
profile-owned high-level plan configuration, absence of normal overrides,
lower-level compatibility, response identity, fingerprint versioning, action
mismatch rejection, and existing Plan/Scanner/Evaluate/session behavior.

Frontend focused coverage will verify typed profile loading and malformed-data
guards, no sizing selector/request authority, exact profile displays, Settings
API ownership, legacy draft migration, response-owned downstream sizing,
profile-bound actions, Evaluate identity behavior, and stale-plan semantics.

## 11. Validation

Run focused backend and frontend tests throughout. Final gates:

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1

cd ..\frontend
npm run lint
npm test -- --run
npm run build
```

Then restart the real local backend/frontend and manually verify both strategy
profiles, plan generation, action preview/apply, Evaluate Stock, legacy local
storage, and no broker execution or external provider dependency.

## 12. Completion Criteria

Sprint 14 is complete when the backend registry is authoritative, the normal UI
cannot choose sizing or override strategy rules, plans/actions are bound to a
versioned profile, both typed APIs and all regression gates pass, browser
acceptance passes, continuity/reporting are complete, and Sprint 15 has not
started.
