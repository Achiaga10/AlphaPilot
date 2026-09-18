# Sprint 29 — Operational Notifications & Escalation

Status: implemented locally, validated, not committed or pushed.

## Outcome

Sprint 29 adds persistent, deterministic operational email delivery on top of Sprint
28 incidents. It adds no trading capability. Operations remains the incident authority;
notification code cannot create a trade decision, modify Forward economics, mutate a
broker account, or call Alpaca. EMAIL is the sole external channel.

The implementation consists of a durable logical notification outbox, immutable
delivery-attempt audit, a single-operator preference singleton, deterministic rendering,
an SMTP provider adapter, a separate one-minute scheduler, bounded retry/backoff, a
committed crash-recovery lease, typed APIs, and a compact Dashboard delivery surface.

## Authority and policy

The policy reads only persisted Sprint 28 incident facts, lifecycle, severity,
single-operator preferences and the fixed reminder interval. News and AI are absent.

- INFO: no email.
- Actionable WARNING: one initial email. The set is Forward failure/staleness/cycle
  failure; market-data stale/missing/sync failure; broker sync failed/stale/
  misconfigured; overdue external action; required manual exit; partial external SELL;
  ambiguous broker match; warning broker conflict; and position quantity drift.
- CRITICAL: one immediate email for every CRITICAL incident except the notification
  subsystem's own incidents. While still OPEN it may create one reminder per configured
  interval, default 3,600 seconds.
- ACKNOWLEDGED: the incident remains active, but pending and future reminders are
  cancelled/suppressed. It is not treated as resolved.
- RESOLVED: one recovery email only when an earlier incident/reminder notification was
  actually DELIVERED and recovery preference remains enabled. Pending stale incident
  notifications are cancelled.
- `EXTERNAL_BUY_ACTION_UPCOMING`: in-app only.
- `MANUAL_EXIT_ACTION_REQUIRED`: one WARNING email.
- `MANUAL_EXIT_ACTION_OVERDUE`: immediate CRITICAL email and eligible reminders.

When delivery is enabled after an incident is already active, the worker reconciles it
once through the original OPENED identity. Repeated Operations evaluation does not spam.

## Persistence and delivery

Migration `3a3f0c993c27` descends from `c28a0f1b2d3e` and creates:

- `notifications`: one logical rendered outbox item with incident/event link, channel,
  status, kind, priority, transition, generation, recipient, content, unique dedup key,
  optional completed session, schedule, attempt summary, provider reference and lease.
- `notification_delivery_attempts`: immutable per-attempt number, UTC start/completion,
  delivered/transient/permanent result, sanitized failure category, provider reference
  and duration.
- `notification_preferences`: exactly one `DEFAULT_OPERATOR` profile with global/email,
  WARNING, CRITICAL, recovery and daily-summary flags plus recipient.

Statuses are `PENDING`, `DELIVERING`, `DELIVERED`, `RETRY_PENDING`, `FAILED` and
`CANCELLED`. Incident logical keys are
`incident:{incident_id}:{transition}:{generation}:EMAIL`. Initial, resolution and each
escalation have their own transition/generation; reminder generations increase. Daily
summary identity is `daily:{completed_session}:EMAIL:{recipient_hash}`. TEST uses a
random request identity.

Each worker transaction selects one due row with PostgreSQL `FOR UPDATE SKIP LOCKED`,
sets `DELIVERING`, increments the attempt, writes a unique lease token and commits a
five-minute lease before provider I/O. Success or failure is finalized only by the
lease owner. An expired lease is claimable after restart. Two workers therefore make
one normal provider call per claim. SMTP is not transactionally exactly once: if SMTP
accepts the message and the process dies before the delivered commit, lease recovery
may send a duplicate.

Transient delay after attempts one through four is 60, 300, 900 and 1,800 seconds;
attempt five ends FAILED. Authentication, incomplete configuration and recipient
rejection are permanent immediately. Manual retry changes FAILED to RETRY_PENDING and
uses the same claim/provider/audit path. Provider exceptions are reduced to TIMEOUT,
AUTHENTICATION, CONNECTION, RECIPIENT_REJECTED, CONFIGURATION or PROVIDER_ERROR.

## Configuration and security

Defaults are disabled:

```text
NOTIFICATIONS_ENABLED=false
NOTIFICATION_EMAIL_ENABLED=false
NOTIFICATION_EMAIL_TO=
NOTIFICATION_WORKER_INTERVAL_SECONDS=60
NOTIFICATION_CRITICAL_REMINDER_SECONDS=3600
NOTIFICATION_MAX_ATTEMPTS=5
NOTIFICATION_DELIVERY_LEASE_SECONDS=300
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
SMTP_TIMEOUT_SECONDS=15
NOTIFICATION_FROM_EMAIL=
```

SMTP host/user/password/TLS/sender are never persisted or exposed. The recipient is an
operator preference with the environment recipient as an optional backend default.
Email content uses selected structured incident facts only; it does not dump raw
exceptions, credentials, authorization data or arbitrary provider payloads. Broker-
related messages visibly show PAPER or LIVE. LIVE messages include `LIVE ACCOUNT
OBSERVATION — read-only broker evidence` and never claim live trading is active.

Subjects are deterministic, for example:

- `[AlphaPilot][CRITICAL] Manual exit overdue — HAL`
- `[AlphaPilot][WARNING] Forward engine stale`
- `[AlphaPilot][RECOVERED] Broker sync restored`

Manual-exit body text includes ticker, SELL, shares, expected session and reason where
available, plus: `Manual broker SELL action required` and `AlphaPilot has not submitted,
cancelled, or executed a broker order.`

## API and UI

Endpoints:

- `GET /api/v1/notifications/status`
- `GET /api/v1/notifications`
- `GET /api/v1/notifications/{id}`
- `GET /api/v1/notifications/preferences`
- `PUT /api/v1/notifications/preferences`
- `POST /api/v1/notifications/{id}/retry`
- `POST /api/v1/notifications/test`

No DELETE exists. Status exposes enabled, email enabled, configured, worker running,
queue depth, pending count, failed count, last delivery and sanitized last error. The
Operations Center displays those facts, preference editing, explicit TEST queuing,
recent immutable history and incident delivery state (`NOT_ELIGIBLE`,
`SUPPRESSED_BY_PREFERENCE`, `PENDING`, `DELIVERED`, `FAILED`). Delivered never means
resolved. SMTP settings and broker/trading controls are absent.

## Daily summary

The optional daily email is disabled by default. It reuses Sprint 28's backend Daily
Operations Summary and its authoritative latest completed trading session. It contains
overall health/counts, Forward equity/open positions, manual BUY/SELL and overdue
counts, broker sync health, conflicts and position drift. Unique session/recipient/
channel identity means repeated workers and Saturday/Sunday without a new completed
session create nothing new.

## Notification health and recursion

Operations can surface `NOTIFICATION_DELIVERY_FAILED`, `NOTIFICATION_QUEUE_STALE` and
`NOTIFICATION_MISCONFIGURED`. Their source domain is `NOTIFICATION`; policy excludes
that entire domain from external delivery, so SMTP failure cannot email about itself.
SMTP failure is contained and does not block Forward, broker sync, Operations or APIs.

## Validation

- Baseline: backend 715 tests; frontend 109 tests across 20 files.
- Focused backend: 39 notification/Operations/API/scheduler tests passed after final
  acknowledgement/backfill hardening.
- Full backend: Ruff PASS, format PASS, mypy PASS across 227 source files, 734 tests PASS.
- Focused frontend: 5 Operations Center tests PASS.
- Full frontend: lint PASS, 111 tests across 20 files PASS.
- Production build: PASS (117 modules transformed).
- Migration on `TEST_DATABASE_URL`: current `c28a0f1b2d3e`; upgrade to
  `3a3f0c993c27`; constraints/focused tests; downgrade to `c28a0f1b2d3e`; re-upgrade;
  `alembic check` reported no new operations.
- Browser: PASS with real FastAPI, real Vite, Edge/Playwright, isolated TEST database
  and FakeNotificationProvider. Covered disabled state, enabling preferences, CRITICAL,
  WARNING, INFO ineligibility, manual exit, overdue reminder, acknowledgement,
  recovery, daily summary, transient recovery, permanent failure, TEST delivery,
  history and absence of broker controls.
- Browser financial safety: an acceptance-only middleware rejected all non-notification
  mutations; final protected-table audit found zero ResearchPortfolio, Paper, Forward
  and broker rows.
- Optional real SMTP smoke: `NOT_RUN_NOT_CONFIGURED`; this is not a failure.

Test-suite hygiene was deliberate. No test file or test was deleted or consolidated;
all prior meaningful coverage was retained. Nineteen backend tests and two frontend
tests were added. There are no new skips/xfails and no weakened assertions.

## Required final report — 78 answers

1. Sprint name: Sprint 29 — Operational Notifications & Escalation.
2. Automatic trading added: NO.
3. Can notifications submit Alpaca orders: NO.
4. Can notifications change Micho: NO.
5. Can notifications change Forward state: NO.
6. External channels: EMAIL only, through SMTP.
7. Statuses: PENDING, DELIVERING, DELIVERED, RETRY_PENDING, FAILED, CANCELLED.
8. Persistence: logical outbox + immutable attempt audit + singleton operator preference.
9. Migration: `3a3f0c993c27`, descending from `c28a0f1b2d3e`.
10. Dedup identity: incident ID + transition + generation + EMAIL; daily summary uses
    recipient hash + EMAIL + completed session.
11. Incident policy: deterministic OPENED/escalation/RESOLVED transitions plus timed
    CRITICAL reminders; no polling-based repeated warning emails.
12. INFO: no email.
13. WARNING: one email only for the frozen actionable-warning set.
14. CRITICAL: immediate email for every non-notification-subsystem CRITICAL and reminders
    while OPEN.
15. Reminder default: 3,600 seconds.
16. Acknowledgement: keeps incident active and cancels/suppresses reminders.
17. Resolution: one recovery only after a prior delivered external notification.
18. Upcoming BUY: in-app only, no default email.
19. Manual exit required: WARNING email with explicit manual SELL wording.
20. Overdue exit: immediate CRITICAL, reminder eligible, never claims execution.
21. Processing: separate one-minute scheduler, committed claim, provider I/O, audited
    finalize; never SMTP inside the incident transaction.
22. Multi-worker claim: PostgreSQL `FOR UPDATE SKIP LOCKED` plus committed lease token.
23. Crash recovery: expired DELIVERING lease becomes claimable; application row remains.
24. Backoff: 60, 300, 900, 1,800 seconds.
25. Maximum attempts: five automatic attempts.
26. Permanent failure: sanitized category and immediate FAILED without app crash.
27. Recursion: `NOTIFICATION` source incidents are always in-app only.
28. SMTP fields: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS,
    SMTP_TIMEOUT_SECONDS, NOTIFICATION_FROM_EMAIL; enable/default recipient/worker policy
    fields are listed above.
29. SMTP credentials frontend-visible: NO.
30. Secrets persisted: NO.
31. Recipient model: one `DEFAULT_OPERATOR` preference; persisted optional recipient,
    with backend environment recipient fallback; no row means no email.
32. Daily scheduling: once after an authoritative newly completed trading session exists
    and Operations facts are available.
33. Summary dedup: recipient hash + EMAIL + completed trading session.
34. Weekend duplicates: NO.
35. Health fields: enabled, email_enabled, configured, worker_running, queue_depth,
    pending_count, failed_count, last_delivery_at, last_error.
36. SMTP failure affects Forward: NO.
37. SMTP failure affects broker sync: NO.
38. News involved: NO.
39. Micho semantics changed: NO.
40. EMA20 semantics changed: NO.
41. Forward semantics changed: NO.
42. Alpaca still read-only: YES.
43. Broker mutation: NO.
44. Critical example: `[AlphaPilot][CRITICAL] Manual exit overdue — HAL`, with manual
    action and no-order-submitted wording.
45. Exit-required example: WARNING email for APA SELL, 10 shares, manual action required.
46. Reminder example: unresolved HAL critical creates generation 1 after 3,600 seconds.
47. Acknowledgement example: HAL becomes ACKNOWLEDGED; later intervals create no reminder.
48. Recovery example: delivered broker-sync warning resolves and emits one RECOVERED email.
49. Retry example: two transient failures at +1m/+5m, third attempt delivers with all
    attempt audit retained.
50. Summary example: session 2026-09-16 includes health, Forward equity, actions, broker,
    conflicts and drift exactly once.
51. Effectively-once limitation: SMTP acceptance cannot share the database transaction;
    a crash after acceptance and before commit can theoretically duplicate a retry.
52. Focused backend: 39 passed.
53. Full backend: Ruff/format PASS, mypy 227 files PASS, 734 tests PASS.
54. Focused frontend: 5 passed.
55. Full frontend: lint PASS, 111 tests/20 files PASS.
56. Build: PASS, 117 modules transformed.
57. Browser: PASS with real FastAPI/Vite/Edge, TEST DB and fake provider; protected
    financial-domain audit PASS.
58. Optional SMTP smoke: NOT_RUN_NOT_CONFIGURED.
59. Migration required: YES.
60. Development DB migrated: NO.
61. ResearchPortfolio mutated: NO.
62. Paper mutated: NO.
63. Forward economic state mutated: NO.
64. Current broker state mutated: NO.
65. Test-suite hygiene performed: YES.
66. Deleted/consolidated tests: none; replacement coverage not applicable.
67. Backend count: 715 before, 734 after.
68. Frontend count: 109 before, 111 after; test files remain 20.
69. New skips/xfails: NO.
70. Assertions weakened: NO.
71. Files created: migration; notification model/provider/schema/service/scheduler/routes;
    API/service/scheduler tests; three controlled backend browser scripts; frontend
    browser smoke; this report.
72. Files modified: configuration/env example, model/router/lifespan registration,
    Operations model/schema/service/tests, CORS, test DB cleanup, frontend API/types/
    hooks/component/styles/fixtures/tests/package scripts, and continuity docs.
73. Git branch/HEAD: `research/ema20-loss-control` at
    `ed859f1d219913090d5d318fa3fa8f267ad71839`.
74. Git status: uncommitted Sprint 29 modified and untracked files; nothing staged.
75. Commit: NO.
76. Push: NO.
77. Known limitations: SMTP availability and delay; no mathematical exactly-once receipt;
    crash-window duplicate possible; unread email; single operator; EMAIL only; periodic
    read-only broker facts; health is not profitability; no autonomous trading.
78. Recommended next step: user reviews the diff/report, publishes Sprint 29 through the
    normal Git/PR flow, then follows the deployment runbook below. Do not start Sprint 30.

## User-run deployment runbook

1. Review all Sprint 29 files and this report. Create the user-owned commit/branch/PR;
   do not deploy an unreviewed working tree.
2. On the deployment host, pull the approved clean `main` and verify its HEAD and clean
   status.
3. Verify the intended database target without printing credentials. Confirm it is not
   a test/development mix-up.
4. Take and verify a recoverable PostgreSQL backup.
5. From `backend`, run `uv run alembic current`, confirm the expected pre-revision, then
   run `uv run alembic upgrade head` and verify `3a3f0c993c27`.
6. Configure the notification enable flags, SMTP host/port/user/password/TLS/timeout,
   sender and optional default recipient locally. Never paste secrets into Git or UI.
7. Start/restart backend and frontend services. Confirm Operations and notification
   schedulers are running and all other service health remains normal.
8. In Operations Center, configure the single-operator recipient/preferences. Start
   with the intended WARNING/CRITICAL/recovery policy; enable daily summary only if wanted.
9. Inspect `/api/v1/notifications/status`: enabled/configured/worker_running, queue,
   failed count, last delivery and sanitized last error.
10. Explicitly click `Send test email`; verify exactly one TEST message and its DELIVERED
    audit before relying on operational email.
11. Inspect active/resolved incidents and notification history. Confirm delivery state
    is not mistaken for incident resolution.
12. Confirm there are still no Alpaca submit/cancel/replace/close endpoints or UI broker
    controls. Sprint 29 is alerting only.

## Known limitations and stop condition

Email depends on SMTP and can be delayed or unread. External receipt is not exactly once;
the provider-accepted/pre-commit crash window can duplicate. The model is single operator,
EMAIL only—no SMS, Telegram, WhatsApp or mobile push. Broker observation remains periodic
and read-only. Operational health does not prove strategy profitability. Alerts never
execute trades and no autonomous trading exists.

Sprint 30 was not started.
