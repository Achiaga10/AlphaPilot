# Approved BUY End-to-End Hotfix

Date: 2026-09-09  
Status: implemented locally; all code and controlled browser gates pass  
Scope: Micho 150 and EMA20 Pullback operational planning only

## Root cause

The shared News gate had an explicit advisory allow-list containing EMA20 Pullback
but not Micho. Consequently, an otherwise deterministic, actionable Micho BUY could
still be refreshed, assessed and replaced by `SKIP/NOT_ACTIONABLE` because of adverse,
missing, stale or unavailable News. EMA20 already preserved its deterministic tuple.

The backend's approval invariant and frontend filtering were otherwise correct:
approval is `final_action=BUY && is_final_actionable=true`. The remaining UI defect
was presentational: the primary badge rendered `BUY`, not the required unambiguous
`APPROVED BUY` label.

## Implementation

- Added both enum and profile-ID forms of Micho to the shared advisory authority rule.
- Both supported strategies now attach persisted News context without automatic News
  refresh. Assessment/provider/parse errors become `UNAVAILABLE` advisory metadata.
- Advisory application preserves decision, allocation, loss-control, final-action,
  terminal-reason and actionability fields exactly. It cannot create a SELL or exit.
- The primary decision badge now says `APPROVED BUY` only when the canonical backend
  invariant is true. A non-actionable allocation continues to say `Candidate allocation`.
- Product copy now describes News as advisory for both strategies.
- News providers, persisted articles/observations/classifications, explicit bounded
  refresh, historical plans and all deterministic strategy gates remain intact.

No strategy rule, threshold, sizing rule, loss-control policy, historical result or
research classification changed. No fallback BUY or stop was introduced.

## Deterministic acceptance coverage

Backend coverage proves for both strategies that:

- adverse, unavailable, stale, partial, rate-limited, never-refreshed and hard-event
  News cannot override an otherwise approved BUY;
- News exceptions cannot interrupt a Plan;
- News cannot create or override HOLD/SELL/EXIT_REQUIRED;
- positive News cannot bypass entry safety, exclusions, portfolio constraints or
  missing approved numeric loss control;
- Profile and Plan routes succeed with all News providers unconfigured;
- a technically valid Micho candidate becomes approved when every legitimate gate
  passes; a synthetic test-only EMA candidate does likewise when an approved numeric
  boundary is explicitly injected at the test boundary.

Frontend coverage proves the same canonical invariant drives the approved tab, count,
action button, allocation label and primary `APPROVED BUY` badge for both strategies.

## Real read-only root-cause snapshot

Request: current S&P 500 universe, relative-strength-20 selection, requested
2026-09-09; backend completed session 2026-09-08. Current ResearchPortfolio revision
25 had no open positions. The snapshot performed Plan generation only.

### Micho 150

- Requested: 502; evaluated: 500. FDXF and HONA had insufficient history and did not
  enter the technical-BUY funnel.
- Technical BUYs: 19.
- Approved BUYs: 10 — BG, EQIX, ES, FRT, GLW, KHC, MDLZ, VMRK, VRT, WMB.
- First blockers among technical BUYs: held 0; exclusion 0; freshness 0; strategy
  safety 0; portfolio 9; allocation 0; loss control 0; other 0.
- Portfolio/ranking-capacity blockers: AMAT, D, DLR, GEV, HST, KLAC, PWR, SPG, WRB.
- News-blocked: 0.

### EMA20 Pullback

- Requested/evaluated: 502/502.
- Technical BUYs: 50.
- Approved BUYs: 0.
- First blockers: held 0; exclusion 0; freshness/entry-revalidation unavailable 5;
  entry safety 15; portfolio 0; allocation 0; loss control 30; other 0.
- Entry revalidation unavailable: CME, JNJ, REGN, RSG, SOLV.
- Entry too extended above EMA20: BKR, BNY, C, CVNA, HPE, LITE, LYB, MDT, MRK,
  OKE, STT, TRGP, WFC, WMB, XOM.
- Loss-control unavailable: AES, AMP, AMT, APH, BRK.B, CAH, CMCSA, CMG, COR, CPRT,
  CRWD, DG, ELV, EQT, EXE, GEN, GILD, IFF, IVZ, MCK, MS, MSFT, NOW, NUE, PFE, T,
  TECH, TGT, TSCO, WBD.
- News-blocked: 0.

The EMA result is evidence that the absence of an approved production loss-control
policy remains authoritative: every one of the 30 candidates that passed current
entry geometry ended at `LOSS_CONTROL_UNAVAILABLE` with
`NO_APPROVED_LOSS_CONTROL_POLICY`. The other 20 stopped earlier, so loss control was
not allowed to hide their first blocker.

## Verification

- Focused backend: 64 passed.
- Full Portfolio backend: 198 passed.
- Full backend: Ruff/format passed; mypy passed across 199 source files; 645 tests
  passed.
- Focused frontend: 27 passed.
- Full frontend: lint passed; 98 tests passed; production build passed.
- Controlled real Edge acceptance: PASS for both profiles. Backend/UI approved counts
  reconciled, Micho rendered `APPROVED BUY`, EMA rendered its typed blockers, News was
  advisory, News provider calls were zero, and Portfolio/Paper state signatures were
  unchanged. No broker action occurred.

## Required answers

1. Can News block Micho BUY? No.
2. Can News block EMA20 BUY? No.
3. Can News prevent Profile generation? No, for either strategy.
4. Can News prevent Portfolio Plan generation? No, for either strategy.
5. Is approved BUY computed from final action plus final actionability? Yes.
6. Can an all-gates-passed Micho candidate become approved? Yes.
7. Can an all-gates-passed EMA candidate with approved loss control become approved?
   Yes; proved only through an explicitly synthetic test boundary because production
   has no approved EMA loss-control policy.
8. Are strategy rules unchanged? Yes.
9. Was News infrastructure or data deleted? No.
10. Was loss-control safety bypassed? No.
11. Was any hardcoded/fallback BUY behavior added? No.
12. Real Micho technical/approved counts: 19/10.
13. Real EMA20 technical/approved counts: 50/0.
14. News-blocked count: 0 for both.
15. Migration required or created: no.
16. Production/Paper/broker mutation: no.

Development stops after this report and the project-pause handoff. Sprint 25 was not
started.
