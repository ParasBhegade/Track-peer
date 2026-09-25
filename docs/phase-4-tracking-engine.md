# Habit Tracker — Phase 4: Core Tracking Engine (Daily Occurrences + Completion)

**Scope of this doc:** FR-4 (Daily Tracking) — proposal §17 build step 3. This is the
single most important phase in the product per proposal §18: "Tracking accuracy
comes before gamification." Every later phase (calendar, streaks, stats,
challenges, leaderboards) reads from what's built here.

**Not in this doc:** streak calculation (Phase 5), calendar views (Phase 5),
statistics (Phase 5), notifications (Phase 6), challenges/leaderboard (Phase 7),
offline queue/sync UI (Phase 8), mobile screens beyond a minimal Today screen.

**Depends on:** Phase 3 (habits, schedules, `schedule_for(date)` resolution) —
done.

---

## 0. What "done" looks like

The proposal's own acceptance test (§19) is the definition of done for this
phase:

```text
Create Habit → Set Schedule → Habit appears on Today → Mark Completed →
Close app → Reopen → Correct status shown → Next day generated correctly →
(Streak — Phase 5) → Calendar shows correct record (Phase 5)
```

For this phase specifically: an automated test runs "Create → Schedule →
appears on Today → Mark Completed → next day generated correctly" end-to-end,
using a frozen clock and at least one non-UTC user (e.g. `Asia/Kolkata`).
Streak/calendar assertions are added once Phase 5 exists — for now the test
just needs to prove the occurrence record is correct.

---

## 1. Decisions Locked for This Phase

These resolve the open items from Phase 3 §9 that specifically block this
phase. Recorded here and should be copied into the Phase 3 Decision Log
(§11) once implemented.

| # | Question | Decision | Why |
|---|---|---|---|
| D6 | Occurrence generation cadence | **Hourly, targeting users whose local date just rolled over** (not nightly, not 2-days-ahead) | "Nightly" assumes one global midnight, which doesn't exist across timezones. Generating 2 days ahead risks showing occurrences before their schedule's `effective_from`. Hourly-by-tz keeps "Today" always fresh within an hour of local midnight, which is acceptable latency for a habit app. |
| D7 | Does archiving cancel future `pending` occurrences? | **Yes** — same delete-pending-only rule as a schedule edit (Phase 3 §3.7 step 4): only `pending` rows with `occurrence_date >= today` are deleted; anything `completed`/`skipped`/`missed` is untouched. | Consistency with the schedule-edit rule; an archived habit shouldn't keep generating future "Today" items. |
| D8 (new) | Missed rollover timing | **At local midnight**, no grace window, as part of the same hourly job that generates the next day | A grace window adds a second timing rule to test and explain; MVP keeps one clock event per user per day. Revisit post-MVP if user feedback wants a grace period. |
| D9 (new) | Can a user un-complete or complete a past day? | **Undo allowed only for today's occurrences. Past days (`occurrence_date < today`) are locked** — no completing, skipping, or un-completing. | Matches "past tracking records should not unexpectedly change" (proposal §7) — extending that principle from schedule edits to direct edits of history. |
| D10 (new) | Does `SKIPPED` break a streak? | **Not decided here — flagged for Phase 5.** This phase only needs to store the state correctly; streak semantics don't affect the occurrence schema. | Keeps this phase's scope to tracking, not streak logic. |
| D11 (new) | Streak unit for non-daily habits (calendar days vs. scheduled occurrences) | **Not decided here — flagged for Phase 5**, same reasoning as D10. | ditto |

---

## 2. Schema — Migration `0003_occurrences`

Matches Phase 2 §2 `occurrences`, unchanged from that draft:

```text
occurrences
  id                    uuid PK
  habit_id              uuid FK → habits, on delete cascade
  occurrence_date       date not null            -- user-local date, not UTC
  status                occurrence_status not null default 'pending'
                        -- enum: pending | completed | skipped | missed
  completed_at          timestamptz null
  synced_from_offline    boolean not null default false   -- FR-9.2 auditing;
                                                           -- offline QUEUE
                                                           -- itself is Phase 8,
                                                           -- but this column
                                                           -- exists now so
                                                           -- Phase 8 doesn't
                                                           -- need a migration
  idempotency_key       text null                -- see §5
  created_at            timestamptz not null default now()
  updated_at            timestamptz not null default now()
```

**Constraints:**
- Unique `(habit_id, occurrence_date)` — the generator's `ON CONFLICT DO
  NOTHING` relies on this.
- Unique `(habit_id, idempotency_key) WHERE idempotency_key IS NOT NULL` —
  lets a client safely retry a completion call.
- FK `habit_id → habits(id) ON DELETE CASCADE` — archiving a habit is a soft
  delete (doesn't touch occurrences), but a hard delete (not exposed via API
  in MVP, only used in tests/admin tooling) cascades cleanly.

**Indexes:**
- `occurrences(habit_id, occurrence_date)` (already listed in Phase 2's
  scalability checklist — this migration is what actually creates it)
- `occurrences(occurrence_date, status) WHERE status = 'pending'` — supports
  the rollover job's "find all pending rows whose date has passed" query
  without a full table scan as data grows.

---

## 3. The Generator

### 3.1 What it does, in order, once per run

For each user whose **local date just changed** (i.e. current UTC time,
converted to that user's `timezone`, has crossed a date boundary within the
last hour):

1. **Roll over yesterday:** `UPDATE occurrences SET status = 'missed' WHERE
   status = 'pending' AND occurrence_date = <user's yesterday>` — but only
   for occurrences belonging to this user's non-archived habits.
2. **Generate today:** for every non-archived habit belonging to this user
   where `habit.start_date <= today`:
   - resolve `schedule_for(today)` (Phase 3 §3.8 lookup — the schedule row
     with the latest `effective_from <= today`)
   - if `today`'s weekday (0=Mon..6=Sun) is in that schedule's
     `days_of_week`, `INSERT ... ON CONFLICT (habit_id, occurrence_date) DO
     NOTHING` a `pending` row for today.
3. Both steps are idempotent — running the job twice for the same user/hour
   changes nothing on the second run. This matters because "hourly, for
   users whose local date just changed" is not a perfectly precise
   partition (clock drift, job overlap, retries), so idempotency is the
   safety net, not the schedule.

### 3.2 Why this needs to be a query, not a loop over all users

At even a few thousand users, "loop over every user and check their
timezone" is wasteful. The actual query:

```sql
SELECT id, timezone FROM users
WHERE EXTRACT(HOUR FROM (now() AT TIME ZONE timezone)) = 0;
```

— i.e. find users where it's currently between midnight and 1 AM in their
own timezone, right now. Run this query at the top of every hour; the result
set is exactly the users who need rollover + generation this run. This scales
independently of total user count (assuming reasonable timezone spread) and
requires no per-user scheduling infrastructure — just a Celery Beat entry
that fires hourly.

### 3.3 Where it lives

Celery task `tasks.occurrence_rollover_and_generate`, scheduled via Celery
Beat at `0 * * * *` (top of every hour). Reuses `schedule_for()` from Phase
3's `schedule_service.py` — no duplicate logic.

### 3.4 Habit-create and schedule-edit hooks

A brand-new habit or an edited schedule shouldn't wait up to an hour to show
up on Today. So, synchronously (in the same request, same transaction) as:

- `POST /habits` — after creating the habit + first schedule, immediately
  generate today's occurrence if `start_date <= today` and today matches
  the schedule.
- `PUT /habits/{id}/schedule` — if the edit's `effective_from` is tomorrow
  (the common case, since same-day edits are blocked by D2), nothing
  changes for *today's* occurrence. No immediate generation needed here;
  tomorrow's hourly run picks it up naturally.
- `DELETE /habits/{id}` (archive) — per D7, delete future `pending`
  occurrences (`occurrence_date >= today`) synchronously in the same
  request.

This keeps the hourly job as the source of truth for steady-state operation,
while these three request paths handle the "don't make the user wait"
cases.

---

## 4. Endpoints

| Method | Path | Purpose | FR |
|---|---|---|---|
| GET | `/today` | Today's occurrences for the current user, plus a progress summary | 4.3 |
| GET | `/occurrences?habit_id=&from=&to=` | Range query (calendar in Phase 5 reuses this; `habit_id` optional) | 4.1, 6.1 |
| PUT | `/occurrences/{id}` | Mark `completed` or `skipped`, or revert to `pending` (today only) | 4.2 |

No `POST /occurrences` — occurrences are never created by the client, only
by the generator (§3). This is deliberate: it prevents a client from
inventing occurrences for dates/habits that were never scheduled.

### 4.1 `GET /today`

```json
{
  "date": "2026-09-25",
  "occurrences": [
    {
      "id": "uuid",
      "habit_id": "uuid",
      "habit_name": "DSA Practice",
      "occurrence_date": "2026-09-25",
      "status": "pending",
      "completed_at": null,
      "reminder_time": "20:00"
    }
  ],
  "progress": { "completed": 4, "total": 6, "percent": 67 }
}
```

- `date` and every `occurrence_date` are the caller's **local** today,
  derived from `users.timezone` — never server/UTC "today."
- `progress` counts `completed` against all non-`missed` scheduled items for
  today (i.e. `completed / (completed + pending + skipped)`); `missed` can
  only apply to past days by definition, so it never appears in today's
  denominator.
- `reminder_time` is denormalized from the habit's current schedule so the
  mobile Today screen doesn't need a second round-trip.

### 4.2 `GET /occurrences`

```
GET /occurrences?from=2026-09-01&to=2026-09-25&habit_id=<uuid optional>
```

```json
{
  "occurrences": [
    { "id": "uuid", "habit_id": "uuid", "habit_name": "DSA Practice",
      "occurrence_date": "2026-09-24", "status": "completed",
      "completed_at": "2026-09-24T14:32:00Z" }
  ]
}
```

- `from`/`to` required, inclusive, max range 92 days (roughly a quarter —
  generous for a monthly calendar view, cheap enough to not need pagination
  yet).
- Ownership enforced via the habit's `user_id`; no cross-user leakage.
- `habit_id` omitted → all of the user's habits in range. This is what
  Phase 5's calendar will call.

### 4.3 `PUT /occurrences/{id}`

```json
// request
{ "status": "completed" }
```

Headers: `Idempotency-Key: <client-generated UUID>` — **required** on this
endpoint (see §5).

```json
// response 200
{
  "id": "uuid",
  "habit_id": "uuid",
  "occurrence_date": "2026-09-25",
  "status": "completed",
  "completed_at": "2026-09-25T14:32:11Z"
}
```

**Rules (D9):**
- Allowed `status` values in the request: `completed`, `skipped`, `pending`
  (the last one is "undo").
- Only occurrences where `occurrence_date == today` (user-local) may be
  modified. `occurrence_date < today` → `403 forbidden` with a message like
  "past occurrences are locked." `occurrence_date > today` shouldn't exist
  (the generator never creates future rows beyond today), so this case is a
  `404`.
- Setting `completed` stamps `completed_at = now()` (UTC). Setting `pending`
  or `skipped` clears `completed_at`.
- Ownership: not-your-habit → `404` (same rule as Phase 3, §1 error table).

---

## 5. Idempotency Design

Offline retry and flaky-network double-taps are the two real failure modes
this guards against (full offline **queueing** is Phase 8, but the server
contract for safe retries needs to exist now, since `PUT /occurrences/{id}`
is exactly the kind of call a client will retry blindly).

**Mechanism:**
1. Client generates a UUID once per user action (not per HTTP attempt) and
   sends it as `Idempotency-Key`.
2. Server checks `occurrences` for a row with the same `(habit_id,
   idempotency_key)`. If found and the stored request matches the new one →
   return the previously-computed response unchanged (don't re-stamp
   `completed_at`).
3. If found but the request *differs* (e.g. same key, different `status`) →
   `409 conflict` — this indicates a client bug (reusing a key for a
   different action), not a network retry.
4. If not found → process normally, store the key on the row.

This is deliberately simple (store-on-the-row) rather than a separate
idempotency-keys table, because occurrences are 1:1 with the action being
retried — there's no need for a generic cross-endpoint idempotency store in
this phase.

---

## 6. OpenAPI Additions

Append to `docs/openapi.json` (paths + schemas only — full file omitted
here for brevity; merge into the existing document from Phase 3):

```yaml
paths:
  /today:
    get:
      tags: [Occurrences]
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/TodayResponse' } } } }
  /occurrences:
    get:
      tags: [Occurrences]
      parameters:
        - { name: from, in: query, required: true, schema: { type: string, format: date } }
        - { name: to, in: query, required: true, schema: { type: string, format: date } }
        - { name: habit_id, in: query, required: false, schema: { type: string, format: uuid } }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/OccurrenceListResponse' } } } }
        '422': { $ref: '#/components/responses/Error' }
  /occurrences/{occurrence_id}:
    parameters:
      - { name: occurrence_id, in: path, required: true, schema: { type: string, format: uuid } }
    put:
      tags: [Occurrences]
      parameters:
        - { name: Idempotency-Key, in: header, required: true, schema: { type: string, format: uuid } }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/OccurrenceUpdate' }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/Occurrence' } } } }
        '403': { $ref: '#/components/responses/Error' }
        '404': { $ref: '#/components/responses/Error' }
        '409': { $ref: '#/components/responses/Error' }

components:
  schemas:
    OccurrenceStatus:
      type: string
      enum: [pending, completed, skipped, missed]
    Occurrence:
      type: object
      required: [id, habit_id, occurrence_date, status]
      properties:
        id: { type: string, format: uuid }
        habit_id: { type: string, format: uuid }
        habit_name: { type: string }
        occurrence_date: { type: string, format: date }
        status: { $ref: '#/components/schemas/OccurrenceStatus' }
        completed_at: { type: [string, 'null'], format: date-time }
        reminder_time: { type: [string, 'null'] }
    TodayResponse:
      type: object
      required: [date, occurrences, progress]
      properties:
        date: { type: string, format: date }
        occurrences: { type: array, items: { $ref: '#/components/schemas/Occurrence' } }
        progress:
          type: object
          required: [completed, total, percent]
          properties:
            completed: { type: integer }
            total: { type: integer }
            percent: { type: integer }
    OccurrenceListResponse:
      type: object
      properties:
        occurrences: { type: array, items: { $ref: '#/components/schemas/Occurrence' } }
    OccurrenceUpdate:
      type: object
      required: [status]
      properties:
        status: { type: string, enum: [completed, skipped, pending] }
```

---

## 7. Implementation Task Breakdown

| ID | Task | Depends on | Done when |
|---|---|---|---|
| B11 | Migration `0003_occurrences` (§2) | Phase 3 done | `alembic upgrade head`/`downgrade` both clean |
| B12 | `occurrence_service.py`: `schedule_for()` reuse, rollover query, generation query, both idempotent | B11 | Unit tests: running generation twice for the same user/day produces exactly one row per scheduled habit |
| B13 | Celery task + Beat schedule (hourly, §3.2 query) | B12 | Task runs against a seeded multi-timezone fixture and produces correct rows for each |
| B14 | Hook generation into `POST /habits` and archive-cascade into `DELETE /habits/{id}` (§3.4, D7) | B12, Phase 3 habit endpoints | Creating a habit today with today in its schedule shows it on `/today` immediately, no wait for the hourly job |
| B15 | `GET /today` | B12 | Matches §4.1 exactly, including progress math |
| B16 | `GET /occurrences` range query | B11 | Range > 92 days → 422; ownership enforced |
| B17 | `PUT /occurrences/{id}` incl. idempotency (§5) and past-day lock (D9) | B15 | Test matrix in §8 passes |
| B18 | OpenAPI reconciliation (append §6, regenerate, diff against Phase 3's CI check) | B15–B17 | CI drift check (Phase 3 B10) still passes |

**Mobile (parallel):**

| ID | Task | Done when |
|---|---|---|
| M7 | Today screen: fetch `/today`, render progress block + habit cards (pending/completed/skipped/missed per the Stitch brief) | Matches design brief §12–13 |
| M8 | Mark-complete/skip interaction: optimistic UI update, `PUT /occurrences/{id}` with a client-generated `Idempotency-Key`, rollback on error | Tapping "MARK COMPLETE" flips the card instantly; a forced network failure reverts it with a visible error, per brief §31 |

---

## 8. Test Plan

**Generation & rollover**
- Habit scheduled Mon/Wed/Fri, `start_date` = today (Monday, user-local) →
  today's occurrence exists, `pending`.
- Same habit, `start_date` = tomorrow → no occurrence generated today.
- Running the generation job twice in the same hour for the same user →
  still exactly one row per habit per day (idempotency).
- User in `Pacific/Kiritimati` (UTC+14) and a user in `Pacific/Niue`
  (UTC-11) at the same real-world instant → each rolls over/generates on
  their *own* midnight, not the server's.
- Yesterday's `pending` row → `missed` after rollover; a `completed` row
  from yesterday is untouched by the same job run.
- Archiving a habit today deletes today's still-`pending` occurrence but
  leaves yesterday's `completed` row alone (D7).

**`GET /today`**
- Progress percent matches `completed / (completed+pending+skipped)`,
  rounded consistently (define and test the rounding rule, e.g.
  round-half-up).
- Empty state (no habits scheduled today) → `occurrences: []`,
  `progress: {completed: 0, total: 0, percent: 0}`, not a division-by-zero
  error.

**`PUT /occurrences/{id}`**
- Mark `completed` → `completed_at` set; mark `pending` again (undo) →
  `completed_at` cleared.
- Same request replayed with the same `Idempotency-Key` → identical
  response, `completed_at` unchanged (not re-stamped to a later time).
- Same `Idempotency-Key`, different `status` in the body → `409`.
- Attempt to modify an occurrence with `occurrence_date` = yesterday →
  `403`.
- Not-your-habit's occurrence → `404`.
- Missing `Idempotency-Key` header → `422` (or `400`, per whatever the
  existing error-shape convention uses for a missing required header —
  confirm against Phase 3's `AppError` handling and be consistent).

**Critical reliability scenario (proposal §19, this phase's slice)**
- End-to-end: create habit → schedule → appears on `/today` → mark
  completed → (simulate app restart: fresh GET) → status still
  `completed` → advance the frozen clock one user-local day → run the
  generation job → tomorrow's occurrence exists as `pending`, today's stays
  `completed`.

---

## 9. Open Items Carried Forward

| # | Item | Owner phase |
|---|---|---|
| D10 | Does `SKIPPED` break a streak? | Phase 5 |
| D11 | Streak unit — calendar days vs. scheduled occurrences | Phase 5 |
| — | Full offline queue (client-side pending-actions store, sync-on-reconnect, `synced_from_offline` actually being set to `true` by a sync path rather than just existing as a column) | Phase 8 |
| — | Grace window for missed rollover (currently: none, D8) — revisit if user feedback asks for it | Post-MVP |

---

## 10. What's Next

**Phase 5 — Calendar + Streak Engine + Statistics** (proposal §17 steps 4–5,
FR-5/FR-6): streak calculation from occurrence history (resolving D10/D11
first), daily/weekly/monthly calendar views built on `GET /occurrences`
(§4.2 above — no new tracking data model, per proposal §9's "no separate
tracking logic for the calendar" rule), and account-wide + per-habit
statistics.