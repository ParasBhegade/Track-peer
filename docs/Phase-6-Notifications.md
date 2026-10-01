# Habit Tracker — Phase 6: Notifications (Local Reminders)

**Scope:** FR-8.1 (habit reminders), proposal §5, §17 step 6  
**Depends on:** Phase 3 (habits + versioned schedules with `reminder_time`), Phase 4 (occurrences, Today screen), Phase 5 (verified, pushed; Alembic head `bd8da8c4ac34`)  
**Status:** Final Specification — decisions D16–D22 frozen  
**Next Phase:** Phase 7 — Challenges

---

## 0. Purpose

Remind the user, on their device, when a scheduled habit is due.

This phase is mostly mobile. Backend work is one read-only endpoint that computes what should be scheduled, so the device never re-implements schedule resolution.

Core rule:

> **Schedules and occurrences remain the source of truth. Notifications are a derived, disposable projection of them.**

The set of scheduled device notifications can be thrown away and rebuilt at any time from server data. Nothing about a notification is ever authoritative.

---

# 0.1 Phase 5 Carry-Forward Context — IMPORTANT

The following Phase 5 decisions and implementation outcomes are already finalized and MUST NOT be reopened during Phase 6.

### D10 — SKIPPED streak semantics

**SKIPPED is neutral.**

- `COMPLETED → SKIPPED → COMPLETED` continues one continuous streak.
- `MISSED` breaks the streak.
- The Phase 5 implementation was corrected to this behavior.
- A Phase 5 regression test was added and proven against the old buggy implementation:
  - reverted/buggy implementation → test FAIL
  - corrected implementation → test PASS
- Do NOT reinterpret, revert, or redesign D10 during Phase 6.
- Phase 6 must not modify streak/statistics semantics.

### Phase 5 completion state

Phase 5 was completed, audited, committed, and pushed to `main`.

Alembic head:

`bd8da8c4ac34`

Phase 6 must preserve all Phase 4/5 occurrence, streak, statistics, calendar, and status semantics.

### Existing Phase 4/5 findings discovered during Phase 6 kickoff

Any discrepancy discovered during Phase 6 implementation must first be classified as:

1. Phase 6 blocker/prerequisite
2. Phase 6 implementation requirement
3. Pre-existing Phase 4/5 issue to record separately
4. Future-phase issue

Do NOT silently expand Phase 6 to repair unrelated historical behavior.

---

# 1. Scope

## In scope

- Local scheduled reminders via `expo-notifications`
- Notification permission handling
- Server-computed reminder plan
- Idempotent device-side reconcile
- Complete/skip → cancel today's reminder; undo → restore if future
- Cleanup on logout, archive, schedule edit, reminder removal
- Notification tap → Today
- Physical-device verification

## Explicitly out of scope

- Remote push (FCM/APNs), Expo push tokens, backend token storage
- Missed-habit reminders, streak warnings, daily summaries
- Challenge/social notifications
- Snooze/action buttons
- Background fetch/tasks for refill
- Per-habit settings beyond `reminder_time`
- New tables or migrations
- Changes to occurrence generation, status, streak, or statistics logic

**Alembic must remain at `bd8da8c4ac34`.**

---

# 2. Decisions to Freeze

| # | Decision |
|---|---|
| D16 | **Dated one-off triggers in a rolling window** |
| D17 | **Backend `GET /reminders/plan` computes the plan using the shared schedule resolver** |
| D18 | **Ask permission contextually on first save with `reminder_time`, never at launch/login** |
| D19 | **Complete/skip cancels today's reminder; undo restores it if its time has not passed** |
| D20 | **Schedule the soonest ≤60 reminders globally across all habits** |
| D21 | **Title = habit name; body = fixed short string; no streak/percentage data** |
| D22 | **Fire at device local wall-clock time; occurrence boundaries still use stored user timezone** |

The rolling-window limitation is accepted. Background refill is out of scope.

---

# 3. Architecture

```text
Habit → Schedule version (reminder_time, effective_from)
             ↓
    shared schedule resolver
             ↓
    GET /reminders/plan?from=&to=
             ↓
    mobile reconcile()
             ↓
    expo-notifications
             ↓
    tap → Today
```

Nothing flows back from a notification to the server.

---

# 4. Backend — GET /reminders/plan

## 4.1 Request

```text
GET /api/v1/reminders/plan?from=YYYY-MM-DD&to=YYYY-MM-DD
```

- `from` defaults to user's local today.
- `to` defaults to `from + 13 days`.
- Inclusive maximum: 14 days.
- Larger range → 400.
- `from` before local today → 400.
- Authenticated-user scoped only.
- No habit ID parameter.

## 4.2 Response

```json
{
  "timezone": "Asia/Kolkata",
  "from": "2026-09-28",
  "to": "2026-10-11",
  "reminders": [
    {
      "notification_id": "habit:3f2a…:2026-09-28",
      "habit_id": "3f2a…",
      "habit_name": "Read 20 pages",
      "occurrence_date": "2026-09-28",
      "reminder_time": "20:00"
    }
  ]
}
```

Sort by:

```text
(occurrence_date, reminder_time, habit_id)
```

Deterministic ID:

```text
habit:{habit_id}:{occurrence_date}
```

## 4.3 Inclusion rules

A `(habit, date)` appears only when:

1. Habit is not archived.
2. `date >= habit.start_date`.
3. Shared `schedule_for(habit, date)` says it is scheduled.
4. Applicable schedule has non-null `reminder_time`.
5. If today's occurrence exists, it is `PENDING`.

`COMPLETED`, `SKIPPED`, and `MISSED` are excluded.

The plan must never create, generate, or mutate occurrences.

---

# 5. B25 — Shared Schedule Resolver — HARD GATE

Before implementing the reminder plan:

1. Inspect all existing schedule-resolution logic.
2. Identify the authoritative Phase 3 behavior:
   - latest schedule version with `effective_from <= target_date`
   - preserve historical schedule semantics
   - preserve future schedule semantics
3. Extract that resolution rule into one pure function operating on already-loaded schedule versions.
4. Make `schedule_for()` delegate to it.
5. Make `/reminders/plan` use it.
6. Do not create a second resolver.

Required matrix test:

```text
habits × dates × schedule versions

plan-derived scheduled/unscheduled result
        ==
schedule_for(habit, date)
```

If historical/local resolver copies disagree:

- Do not silently redesign Phase 3/4/5 behavior.
- Classify the discrepancy first.
- Only change behavior if required for safe shared-resolver extraction.
- Add a regression test for any necessary behavior change.
- Report the exact change.

---

# 6. Backend Performance

The plan must avoid N+1 queries.

Required:

- Habits + relevant schedule versions loaded in a bounded number of queries.
- Today's occurrence statuses loaded in one query.
- Resolver operates in memory.
- Query-count test proves query count is independent of habit count/window length.

---

# 7. Validation / Errors

| Case | Response |
|---|---|
| Unauthenticated | 401 |
| `to < from` | 400 |
| Range > 14 days | 400 |
| `from < local today` | 400 |
| Malformed date | 400 |
| Habit not owned | Not applicable; no habit ID accepted |

---

# 8. Mobile Notification Service

Create three separable pieces under `src/notifications/`.

## 8.1 Permissions

Responsible for:

- Get status
- Request permission
- Open OS settings

## 8.2 `planToTriggers(plan, now, deviceTz)`

Pure function:

1. Combine date + reminder time in device timezone.
2. Drop `fireAt <= now`.
3. Sort soonest-first.
4. Truncate globally to 60.
5. Return `{id, fireAt, title, body, data}`.

No API calls or scheduler calls.

## 8.3 `reconcile()`

**The only function allowed to schedule or cancel habit notifications.**

Flow:

```text
permission check
      ↓
GET /reminders/plan
      ↓
planToTriggers()
      ↓
getAllScheduledNotificationsAsync()
      ↓
filter habit:* notifications
      ↓
cancel(existing - desired)
      ↓
schedule(desired - existing)
```

Intersection is untouched.

Second identical reconcile must produce zero scheduler operations.

---

# 9. Reconcile Serialization — HARD REQUIREMENT

Overlapping reconciles must not interleave.

Required behavior:

```text
reconcile A starts
       ↓
reconcile B requested
       ↓
A completes
       ↓
exactly one follow-up reconcile B
```

Use a single in-flight promise or equivalent.

Test that overlapping calls produce no interleaving and exactly one queued follow-up.

---

# 10. Notification Payload

```text
title: <habit_name>
body: "Time for your habit."
data:
  {
    habit_id,
    occurrence_date,
    screen: "today"
  }

identifier:
  habit:{habit_id}:{occurrence_date}
```

Keep the body in one constant.

Android notification channel must exist before the first schedule call.

---

# 11. Global 60-Notification Rule

The limit applies across **all habits**:

```text
all desired reminders
        ↓
sort by fire time
        ↓
take earliest 60
```

Never 60 per habit.

Test with >60 reminders and verify:
- scheduled set is capped at 60;
- earliest reminders are retained;
- latest reminders are dropped.

---

# 12. Reconcile Trigger Points

| Trigger | Action |
|---|---|
| App start / foreground | Reconcile |
| Habit create with reminder | Reconcile |
| Schedule/reminder edit | Reconcile |
| Archive | Reconcile |
| Restore | Reconcile |
| Complete | Reconcile |
| Skip | Reconcile |
| Undo | Reconcile |
| Permission granted | Reconcile |
| Logout | Cancel all `habit:` notifications |
| Login | Fresh reconcile |

All calls use the serialized reconcile mechanism.

---

# 13. Permission UX

No permission prompt at launch or login.

On first save of a habit with `reminder_time`:

```text
save
 ↓
short in-app explanation
 ↓
OS permission prompt
```

Granted → reconcile immediately.

Denied:
- habit still saves;
- tracking remains usable;
- show non-blocking notice;
- provide settings action.

If permission is later revoked, foreground reconcile returns `no_permission` and the same notice is shown.

---

# 14. Notification Tap — M17

Tap must open the existing **Today** screen.

Requirements:

- cold-start tap;
- warm/background tap;
- never mark complete;
- use existing navigation;
- no new screen.

---

# 15. Authentication Prerequisite

Before relying on foreground reconciliation, inspect the current mobile authentication implementation.

Verify:

- access-token persistence;
- access-token expiry behavior;
- refresh-token flow;
- authenticated API behavior after access-token expiry.

If the current client truly has no persistence/refresh and foreground reconciliation can receive 401 after token expiry:

- treat it as a Phase 6 prerequisite/blocker;
- do not hide 401s inside notification code;
- do not create a fake workaround;
- report the exact auth gap before M16/M17.

---

# 16. Existing Phase 4/5 Findings — Classification

### Rollover catch-up

If Celery rollover can miss a user's local midnight when the worker is unavailable:

**Do not change occurrence generation in Phase 6.**

Record as a pre-existing Phase 4 operational issue unless Phase 4 is explicitly reopened.

### Historical idempotency

If delayed duplicate idempotency keys after complete → undo are not recognized:

**Do not redesign occurrence idempotency in Phase 6.**

Record for future offline-sync work.

### Calendar/date rendering

Existing Phase 5 issues such as null percentages or timezone date parsing must be classified first.

Only fix them in Phase 6 if they directly block Phase 6 acceptance.

---

# 17. Expo Runtime Kickoff Gate

Before M13, verify against the **current Expo SDK documentation**:

1. `expo-notifications` support in Expo Go.
2. What requires a Development Build.
3. Whether M18 requires a Development Build.
4. Android requirements affecting notification timing.

Record the result before proceeding.

---

# 18. Backend Tests

Required:

1. Daily habit with reminder.
2. Weekday-limited habit.
3. `reminder_time = null`.
4. Archived habit.
5. Future `start_date`.
6. Schedule-version regression.
7. Today completed excluded.
8. Undo to pending returns reminder.
9. Today skipped excluded.
10. Non-UTC timezone.
11. 15-day range → 400.
12. `to < from` → 400.
13. `from < local today` → 400.
14. Malformed dates → 400.
15. Ownership isolation.
16. Deterministic identical requests.
17. Resolver equivalence matrix.
18. Bounded query count.
19. Read-only occurrence behavior.
20. Existing Phase 4/5 suite remains green.

---

# 19. Mobile Unit Tests

Required:

1. `planToTriggers` drops `fireAt <= now`.
2. Global 60 limit.
3. Earliest reminders retained.
4. Device-timezone date/time combination.
5. DST boundary.
6. Deterministic IDs.
7. Cancel extras.
8. Schedule missing.
9. Leave intersection untouched.
10. Second identical reconcile makes zero scheduler calls.
11. `no_permission` makes zero scheduler calls.
12. Concurrent reconcile calls serialize.
13. Logout cancels every `habit:` notification and no unrelated notification.
14. Authenticated plan fetch returning 401 is handled through the existing auth layer, not swallowed by notification code.

---

# 20. Physical Device Verification — M18

Use a real device and record actual evidence.

1. Create reminder 2–3 minutes ahead.
2. Permission explainer appears.
3. Grant permission.
4. Notification fires at expected minute with habit name.
5. Tap from lock screen with app killed → Today.
6. Repeat with app backgrounded.
7. Complete before firing → no notification.
8. Undo while future → notification restored.
9. Edit reminder for tomorrow → today unchanged.
10. Archive habit → reminder removed.
11. Deny permission → habit saves, notice appears, settings action works.
12. Grant permission from settings and return → reminders reconcile without restart.
13. Logout → no reminders remain.
14. Login as another user → only their reminders exist.
15. Create 10+ habits/multiple reminders → scheduled set ≤60.
16. Verify soonest reminders retained.
17. Android: document delivery timing/inexact-alarm behavior and exact-alarm requirements if applicable.

---

# 21. Task Breakdown

## Backend

### B25 — Shared Resolver
- Extract pure resolver.
- `schedule_for()` delegates.
- Reminder plan uses it.
- Resolver-equivalence tests.
- Preserve Phase 3 behavior.

### B26 — Reminder Plan
Implement:

```text
GET /api/v1/reminders/plan
```

with validation, inclusion, ownership, determinism, timezone, and read-only behavior.

### B27 — Verification
- Backend tests.
- `docs/openapi.json`.
- OpenAPI drift check.
- Full existing suite.

## Mobile

### M13
- `expo-notifications`.
- Android channel.
- Foreground handling.

### M14
- Permissions.
- Contextual UX.
- Denied state.
- Settings deep link.

### M15
- `planToTriggers()`.
- Unit tests.
- `reconcile()`.
- Serialization.
- Global 60 limit.

### M16
Wire reconciliation to:
- habit creation;
- schedule/reminder edits;
- archive/restore;
- complete/skip/undo;
- login/logout.

### M17
Notification tap → Today.

### M18
Physical-device verification and evidence.

---

# 22. Implementation Order

```text
Kickoff / Expo runtime verification
        ↓
Authentication prerequisite verification
        ↓
B25 — shared resolver
        ↓
B26 — reminder plan
        ↓
B27 — backend tests + OpenAPI
        ↓
M13 + M14
        ↓
M15 — pure trigger logic + reconcile
        ↓
M16 — application wiring
        ↓
M17 — tap handling
        ↓
M18 — physical device
        ↓
Phase 6 audit
```

Do not start M16/M17 until the reminder plan and authentication prerequisite are verified.

---

# 23. Data Integrity Rules

1. Notifications never create, modify, or delete occurrences, schedules, or habits.
2. The plan is computed from server schedules.
3. The device never independently resolves schedules.
4. Scheduled notifications are rebuildable from the plan.
5. `reconcile()` is the only scheduler owner.
6. Complete/skip suppresses today's reminder.
7. Undo restores it if its time is still ahead.
8. Tomorrow-effective schedule edits do not change today's reminder.
9. Logout leaves zero `habit:` notifications.
10. Denied permission never blocks habit creation/tracking.
11. No Phase 4/5 semantics change.
12. D10 remains: **SKIPPED is neutral; MISSED breaks streaks.**

---

# 24. Acceptance Scenario

```text
1. Create recurring habit with reminder.
2. Contextual permission prompt appears.
3. Grant permission.
4. Reminder plan returns next 14 days.
5. Device schedules desired reminders, capped at 60.
6. Reminder fires.
7. Tap notification.
8. Today opens.
9. Complete before reminder.
10. Reminder cancels.
11. Undo while future.
12. Reminder restores.
13. Edit reminder effective tomorrow.
14. Today's reminder remains unchanged.
15. Tomorrow uses new time.
16. Archive habit.
17. Its reminders are removed.
18. Logout.
19. No habit:* reminders remain.
20. Login as another user.
21. Only new user's reminders exist.
22. Deny notification permission.
23. Habit still saves and tracking works.
24. Enable permission in OS settings.
25. Return to app.
26. Reminders reconcile without restart.
27. Backend tests, Ruff, Mypy, OpenAPI drift clean.
28. Alembic remains at bd8da8c4ac34.
```

---

# 25. Completion Criteria

Phase 6 is complete only when:

- `GET /reminders/plan` implemented/tested.
- `docs/openapi.json` updated and drift check clean.
- `schedule_for()` and reminder plan share one resolver.
- Resolver-equivalence matrix passes.
- No N+1 query behavior.
- Mobile reconcile is idempotent and serialized.
- Global 60 limit tested.
- Permission UX works.
- Complete/skip/undo behavior works.
- Logout isolation works.
- Notification tap works cold and warm.
- Authentication prerequisite is verified.
- All physical-device checks are executed with evidence.
- No migration created.
- Alembic remains at `bd8da8c4ac34`.
- No Phase 4/5 behavior changed.
- Full backend suite is green.
- No remote push during Phase 6 implementation.
- No FCM/APNs.
- No Phase 7 work.
- Local commit(s) only.
- Separate audit pass occurs before remote push.

---

# 26. Explicit Out-of-Scope Reminder

Do NOT implement:

- FCM/APNs
- Expo push tokens
- Backend push-token storage
- Missed-habit reminders
- Streak warnings
- Daily summaries
- Challenge/social notifications
- Snooze/action buttons
- Background refill
- New tables
- New migrations
- New occurrence-generation logic
- New streak/statistics logic
- Phase 7 Challenges/Rooms

---

## Next Phase

**Phase 7 — Challenges and Rooms**

Phase 7 begins only after Phase 6 is separately audited and accepted.
