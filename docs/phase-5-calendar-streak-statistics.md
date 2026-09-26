**# Habit Tracker — Phase 5: Calendar, Streaks & Statistics**

**\*\*Scope:\*\*** FR-5 (Streaks & Statistics), FR-6 (Calendar)  

**\*\*Depends on:\*\*** Phase 4 Daily Tracking Engine  

**\*\*Status:\*\*** Specification / Ready for implementation after decision freeze  

**\*\*Next Phase:\*\*** Phase 6 — Notifications

\---

**## 0. Purpose**

Phase 5 introduces the read and aggregation layer on top of the Phase 4 \`occurrences\` system.

This phase implements:

\- Calendar views and calendar summaries

\- Current streaks

\- Longest streaks

\- Completion statistics

\- Habit-level statistics

\- Account-level statistics

\- Mobile Calendar screen

\- Mobile Habit Details / Progress History

\- Mobile Statistics screen

The fundamental architectural rule is:

*>* **\*\*The** \`occurrences\` **table remains the authoritative source of tracking history.\*\***

Calendar, streak, and statistics functionality must derive their meaning from occurrence history.

Cached aggregate fields may be used to improve read performance, but they are **\*\*derived accelerators, never the source of truth\*\***.

This phase does **\*\*not\*\*** create a separate calendar data model and does **\*\*not\*\*** create or mutate occurrence rows as part of calendar/stats reads.

\---

**# 1. Scope**

**## 1.1 Functional Requirements**

**### FR-5 — Streaks & Statistics**

The system shall provide:

\- Current streak

\- Longest streak

\- Total completed occurrences

\- Weekly completion percentage

\- Monthly completion percentage

\- Habit-level statistics

\- Account-wide statistics

All statistics must be derived from actual occurrence history.

**### FR-6 — Calendar**

The system shall provide:

\- Daily occurrence history

\- Weekly occurrence history

\- Monthly calendar view

\- Monthly completion heatmap/summary

\- Day-level drill-down

\- Historical tracking information

The calendar must use the same \`occurrences\` data used by the tracking engine.

There must be **\*\*no separate calendar tracking logic\*\***.

\---

**# 2. Architectural Principles**

**## 2.1 Occurrences Are the Source of Truth**

\`\`\`text

Habit

  ↓

Schedule Version

  ↓

Occurrence

  ↓

Status

  ↓

Calendar / Streak / Statistics

\`\`\`

The authoritative historical record is:

\`\`\`text

occurrences

\`\`\`

Cached fields on \`habits\` are derived values only.

If a cached value ever disagrees with occurrence history, occurrence history wins and the cached value must be repairable/recalculable.

\---

**## 2.2 Phase 5 Does Not Generate Occurrences**

Occurrence generation remains a Phase 4 responsibility.

Phase 5:

\- reads existing occurrences;

\- aggregates existing occurrences;

\- calculates streaks from existing occurrences;

\- calculates statistics from existing occurrences;

\- updates cached aggregate fields only as part of an occurrence status mutation.

Phase 5 must **\*\*not\*\*** independently generate daily occurrences.

\---

**## 2.3 Phase 5 Does Not Mutate Historical Occurrences**

Calendar and statistics endpoints are read-only with respect to occurrences.

They must never:

\- mark an occurrence completed;

\- mark an occurrence skipped;

\- mark an occurrence missed;

\- create an occurrence;

\- delete an occurrence.

Occurrence mutation remains exclusively within the Phase 4 occurrence-status API and its established transaction/idempotency flow.

\---

**# 3. Decisions**

The following decisions must be frozen before implementation.

\---

**## D10 — Does SKIPPED Break a Streak?**

**### Decision**

**\*\*Yes.\*\***

Only \`COMPLETED\` extends a streak.

The rules are:

\| Status | Streak effect |

\|---|---|

\| \`COMPLETED\` | Extends streak |

\| \`PENDING\` for today | Does not currently break streak |

\| \`SKIPPED\` | Breaks streak |

\| \`MISSED\` | Breaks streak |

A future occurrence is not considered part of the current streak.

\---

**# 4. D11 — Streak Unit for Non-Daily Habits**

**### Decision**

For habits that are not scheduled every calendar day, streaks are based on:

*>* **\*\*Consecutive scheduled occurrences.\*\***

Not consecutive calendar days.

Example:

\`\`\`text

Schedule:

Monday / Wednesday / Friday

Monday     COMPLETED

Wednesday  COMPLETED

Friday     COMPLETED

\`\`\`

This represents a streak of:

\`\`\`text

3 scheduled occurrences

\`\`\`

Tuesday and Thursday do not break the streak because those dates were not scheduled occurrences.

**## 4.1 Schedule-Version Rule**

Historical streak calculation must respect the schedule version that applied to each historical date.

For every historical occurrence date:

\`\`\`text

schedule_for(habit_id, occurrence_date)

\`\`\`

must be used to determine the applicable schedule.

A later schedule edit must **\*\*never retroactively change the historical meaning of previous occurrences\*\***.

\---

**# 5. D12 — Completion Percentage Denominator**

Completion percentage is based on **\*\*scheduled occurrences\*\***, not calendar days.

For any requested period:

\`\`\`text

completion_percentage =

    completed_occurrences

    ---------------------

    scheduled_occurrences

\`\`\`

Where:

\`\`\`text

scheduled_occurrences =

    COMPLETED

  + PENDING

  + SKIPPED

  + MISSED

\`\`\`

Future occurrences outside the requested period are excluded.

Example:

\`\`\`text

Scheduled: 10

Completed: 7

Skipped:   1

Missed:    1

Pending:   1

\`\`\`

Therefore:

\`\`\`text

7 / 10 = 70%

\`\`\`

\---

**# 6. D13 — Archived Habits and History**

Archived habits retain their historical tracking records.

Therefore:

\- Historical occurrences remain in the database.

\- Historical calendar views may include archived habits.

\- Historical statistics may include completed occurrences belonging to archived habits where explicitly requested.

\- Archive does not rewrite historical records.

\- Archive does not generate future occurrences.

Future tracking for an archived habit remains disabled according to Phase 4 behavior.

**## 6.1 Historical vs Future Rule**

**### Historical**

Include archived habit occurrences.

**### Future**

Archived habits do not contribute new scheduled occurrences.

\---

**# 7. D14 — Statistics Period Boundaries**

All period calculations use the user's IANA timezone.

**## Weekly**

Week:

\`\`\`text

Monday → Sunday

\`\`\`

For "weekly to date":

\`\`\`text

Monday → user's local today

\`\`\`

Future days are excluded.

**## Monthly**

Month:

\`\`\`text

1st day → last day of calendar month

\`\`\`

For "monthly to date":

\`\`\`text

1st day → user's local today

\`\`\`

Future days are excluded.

**## 7.1 Timezone Requirement**

Period boundaries must be calculated using the user's local timezone.

The system must not use UTC calendar boundaries for user-facing statistics.

\---

**# 8. D15 — Statistics Storage Strategy**

Cached fields are allowed only where they can be maintained correctly.

The Phase 5 schema will contain:

\`\`\`text

current_streak

total_completions

\`\`\`

\`longest_streak\` will **\*\*not\*\*** be stored as a monotonic cached value.

**### Storage decision**

\| Metric | Storage |

\|---|---|

\| Current streak | Cached |

\| Total completions | Cached |

\| Longest streak | Computed from occurrences |

\| Weekly completion % | Computed from occurrences |

\| Monthly completion % | Computed from occurrences |

\| Calendar summary | Computed from occurrences |

\| Account statistics | Aggregated from authoritative data |

\---

**# 9. Schema Changes**

Migration:

\`\`\`text

0004_streaks_and_stats

\`\`\`

Add to \`habits\`:

\| Column | Type | Default | Purpose |

\|---|---|---:|---|

\| \`current_streak\` | integer | \`0\` | Cached current streak |

\| \`total_completions\` | integer | \`0\` | Cached completed-occurrence count |

Constraints:

\`\`\`text

current_streak >= 0

total_completions >= 0

\`\`\`

No new calendar table is required.

No streak-history table is required.

No statistics table is required.

\---

**# 10. Migration Backfill**

Phase 4 may already contain occurrence data when migration \`0004\` executes.

Therefore the migration must **\*\*backfill existing data\*\***.

**## 10.1** \`total_completions\`

For each habit:

\`\`\`text

total_completions =

    COUNT(occurrences WHERE status = COMPLETED)

\`\`\`

**## 10.2** \`current_streak\`

After adding the fields, existing habits must have their current streak calculated from existing occurrence history using the Phase 5 streak rules.

The migration must not simply initialize all existing habits to zero if occurrence history already exists.

**## 10.3 Migration Safety**

The migration must:

\- preserve existing occurrence data;

\- not modify occurrence statuses;

\- not create/delete occurrences;

\- leave Alembic at the new head;

\- pass existing migration tests.

\---

**# 11. Current Streak Engine**

Function:

\`\`\`python

recalculate_streak(db, habit) -> None

\`\`\`

The calculation must use the user's local date.

The algorithm walks backward through scheduled occurrences.

\`\`\`text

streak = 0

date = most recent scheduled occurrence

       at or before user's local today

while scheduled occurrence exists:

    occurrence = occurrence for date

    if occurrence.status == COMPLETED:

        streak += 1

    elif occurrence.status == PENDING and date == today:

        # Today is still open.

        # It does not break the existing streak.

        continue to previous scheduled occurrence

    else:

        # SKIPPED or MISSED

        break

    date = previous scheduled occurrence

\`\`\`

The resulting value becomes:

\`\`\`text

habit.current_streak = streak

\`\`\`

\---

**# 12. Current Streak Boundary**

Today's pending occurrence does not immediately destroy the streak.

Example:

\`\`\`text

Monday     COMPLETED

Tuesday    COMPLETED

Wednesday  PENDING

\`\`\`

Current streak:

\`\`\`text

2

\`\`\`

If Wednesday becomes \`COMPLETED\`, current streak becomes \`3\`.

If Wednesday becomes \`SKIPPED\` or \`MISSED\`, current streak becomes \`0\`.

\---

**# 13. No Arbitrary Streak Lookback Limit**

The implementation must not use an arbitrary correctness-breaking cap such as:

\`\`\`text

730 occurrences

\`\`\`

A cap could cause a long-running habit to report an incorrect streak.

Instead:

\- use indexed occurrence data;

\- use efficient scheduled-occurrence queries;

\- optimize only if actual profiling demonstrates a performance problem.

Any future optimization must preserve exact results.

\---

**# 14. Longest Streak**

\`longest_streak\` is **\*\*not stored on the habit\*\***.

It is calculated from historical occurrence data.

The calculation must identify the longest sequence of consecutive scheduled occurrences where every occurrence is:

\`\`\`text

COMPLETED

\`\`\`

\`SKIPPED\` and \`MISSED\` break the sequence.

A current-day \`PENDING\` occurrence does not create a completed streak segment.

Historical schedule versions must be respected.

\---

**# 15. Total Completions**

\`total_completions\` is a cached count representing:

\`\`\`text

COUNT(all occurrences for this habit

      whose status is COMPLETED)

\`\`\`

It includes historical completed occurrences.

\---

**# 16. Total Completion Update Rules**

When an occurrence changes status:

**###** \`PENDING → COMPLETED\`

\`\`\`text

total_completions += 1

\`\`\`

**###** \`SKIPPED → COMPLETED\`

\`\`\`text

total_completions += 1

\`\`\`

**###** \`COMPLETED → PENDING\`

\`\`\`text

total_completions -= 1

\`\`\`

**###** \`COMPLETED → SKIPPED\`

\`\`\`text

total_completions -= 1

\`\`\`

**###** \`COMPLETED → COMPLETED\`

No change.

**###** \`PENDING → SKIPPED\`

No change.

**###** \`SKIPPED → PENDING\`

No change.

The valid transitions remain governed by the Phase 4 occurrence API.

\---

**# 17. Transactional Consistency**

Occurrence status mutation and cached aggregate updates must happen inside the same database transaction.

\`\`\`text

BEGIN

update occurrence

update total_completions

recalculate current_streak

COMMIT

\`\`\`

If any operation fails:

\`\`\`text

ROLLBACK

\`\`\`

No partial state may persist.

The occurrence remains the authoritative state.

\---

**# 18. Idempotency Compatibility**

Phase 5 must preserve Phase 4 occurrence idempotency behavior.

A repeated request using the same \`Idempotency-Key\` must not:

\- increment \`total_completions\` twice;

\- decrement it twice;

\- produce duplicate effects;

\- create inconsistent cached state.

\---

**# 19. Calendar**

Phase 4 already provides:

\`\`\`text

GET /occurrences?from=&to=

\`\`\`

This remains the detailed day/week history endpoint.

Phase 5 adds:

\`\`\`text

GET /calendar/summary?year=&month=

\`\`\`

\---

**# 20. Calendar Summary**

The endpoint returns one entry for **\*\*every calendar day in the requested month\*\***.

Example:

\`\`\`json

{

  "days": [

    {

      "date": "2026-09-01",

      "scheduled": 0,

      "completed": 0,

      "percent": null

    },

    {

      "date": "2026-09-02",

      "scheduled": 3,

      "completed": 2,

      "percent": 67

    },

    {

      "date": "2026-09-03",

      "scheduled": 3,

      "completed": 3,

      "percent": 100

    }

  ]

}

\`\`\`

Rules:

\`\`\`text

scheduled = number of scheduled occurrences

completed = number of COMPLETED occurrences

percent   = completed / scheduled × 100

\`\`\`

Use round-half-up.

If \`scheduled == 0\`, then:

\`\`\`text

percent = null

\`\`\`

not \`0\`.

\---

**# 21. Calendar Query Requirements**

The summary query must:

\- group by \`occurrence_date\`;

\- restrict results to the requested month;

\- enforce user ownership;

\- include historical occurrences of archived habits;

\- avoid N+1 queries.

The endpoint must return all calendar days, including days with no occurrence rows.

The implementation may use a database date series or equivalent application-level zero-fill after a single aggregate query.

There must be **\*\*no per-day database query loop\*\***.

\---

**# 22. Calendar Archived-Habit Rule**

Archived habits remain visible in historical calendar data.

However:

\- archived habits do not produce new future occurrences;

\- historical occurrence rows remain queryable;

\- calendar summary includes those historical rows.

The query must not simply exclude archived habits globally.

\---

**# 23. Calendar Day Detail**

The existing Phase 4 endpoint remains the source for detailed day data:

\`\`\`text

GET /occurrences?from=&to=

\`\`\`

The mobile calendar may request:

\`\`\`text

from = selected date

to   = selected date

\`\`\`

No new day-detail tracking model is required.

\---

**# 24. Calendar Weekly View**

The weekly calendar view uses:

\`\`\`text

GET /occurrences?from=&to=

\`\`\`

The backend does not need a separate weekly calendar table.

The mobile layer groups returned occurrences by local date.

\---

**# 25. Calendar Monthly View**

The monthly calendar screen uses:

\`\`\`text

GET /calendar/summary

\`\`\`

for the heatmap/overview.

A selected day uses:

\`\`\`text

GET /occurrences?from=&to=

\`\`\`

for detailed occurrences.

\---

**# 26. Habit Statistics**

Endpoint:

\`\`\`text

GET /habits/{id}/stats

\`\`\`

Example:

\`\`\`json

{

  "current_streak": 12,

  "longest_streak": 31,

  "total_completions": 84,

  "weekly_completion_percent": 86,

  "monthly_completion_percent": 78

}

\`\`\`

Definitions:

\- \`current_streak\`: cached current consecutive scheduled-occurrence streak.

\- \`longest_streak\`: computed from occurrence history.

\- \`total_completions\`: cached lifetime completed-occurrence count.

\- \`weekly_completion_percent\`: current local week to date.

\- \`monthly_completion_percent\`: current local month to date.

\---

**# 27. Statistics Rounding**

All completion percentages use:

\`\`\`text

round-half-up

\`\`\`

matching the Phase 4 \`/today\` convention.

If the denominator is zero:

\`\`\`text

percent = null

\`\`\`

\---

**# 28. Account Statistics**

Endpoint:

\`\`\`text

GET /stats/overview

\`\`\`

Example:

\`\`\`json

{

  "total_active_habits": 5,

  "weekly_completion_percent": 82,

  "best_current_streak": 12,

  "total_lifetime_completions": 246

}

\`\`\`

Definitions:

**###** \`total_active_habits\`

Number of non-archived habits belonging to the authenticated user.

**###** \`weekly_completion_percent\`

Calculated as:

\`\`\`text

sum(completed occurrences)

\--------------------------

sum(scheduled occurrences)

\`\`\`

It is **\*\*not\*\*** the average of habit percentages.

**###** \`best_current_streak\`

\`\`\`text

MAX(current_streak)

\`\`\`

among the user's active habits.

This is not the longest historical streak.

**###** \`total_lifetime_completions\`

Total completed occurrences across the user's habits.

Historical completed occurrences belonging to archived habits remain part of lifetime completion history.

\---

**# 29. User Ownership**

All Phase 5 endpoints must enforce authenticated-user ownership.

A user must never retrieve:

\- another user's calendar;

\- another user's occurrences;

\- another user's habit statistics;

\- another user's account statistics.

Existing Phase 4 ownership rules remain applicable.

\---

**# 30. API Validation**

**## Calendar**

Validate:

\`\`\`text

year

month

\`\`\`

with appropriate calendar bounds.

Invalid month:

\`\`\`text

400

\`\`\`

or the project's established validation response.

**## Habit Statistics**

If the habit does not belong to the authenticated user:

\`\`\`text

404

\`\`\`

consistent with the existing habit ownership behavior.

\---

**# 31. Performance Requirements**

Phase 5 must avoid unnecessary query amplification.

**### Calendar**

Must not perform one database query per calendar day.

**### Statistics**

Must use bounded period queries for weekly/monthly percentages.

**### Streak**

Must use indexed occurrence data.

**### Longest Streak**

Must calculate from historical occurrence data without an arbitrary correctness cap.

Optimization should be based on measured performance.

\---

**# 32. Required Database Indexes**

Phase 5 should reuse Phase 4 occurrence indexes wherever possible.

Relevant access patterns include:

\`\`\`text

habit_id + occurrence_date

\`\`\`

and:

\`\`\`text

occurrence_date

\`\`\`

where necessary for calendar/account aggregation.

Additional indexes must be justified by actual Phase 5 query patterns.

\---

**# 33. Backend Task Breakdown**

**## B19 — Migration and Aggregate Fields**

Implement:

\- migration \`0004_streaks_and_stats\`;

\- \`current_streak\`;

\- \`total_completions\`;

\- constraints/defaults;

\- migration backfill;

\- initial current-streak calculation.

**## B20 — Streak Engine**

Implement:

\- current streak;

\- longest streak;

\- scheduled-occurrence traversal;

\- schedule-version-aware historical traversal;

\- D10;

\- D11;

\- transaction integration.

**## B21 — Calendar**

Implement:

\`\`\`text

GET /calendar/summary

\`\`\`

and integrate with:

\`\`\`text

GET /occurrences

\`\`\`

for detailed calendar views.

**## B22 — Habit Statistics**

Implement:

\`\`\`text

GET /habits/{id}/stats

\`\`\`

including:

\- current streak;

\- longest streak;

\- total completions;

\- weekly completion percentage;

\- monthly completion percentage.

**## B23 — Account Statistics**

Implement:

\`\`\`text

GET /stats/overview

\`\`\`

including:

\- active habit count;

\- account-wide weekly completion;

\- best current streak;

\- lifetime completions.

**## B24 — Backend Regression and Integration Tests**

Implement comprehensive Phase 5 tests.

\---

**# 34. Mobile Task Breakdown**

**## M9 — Calendar Screen**

Implement the monthly calendar screen.

Data:

\`\`\`text

GET /calendar/summary

\`\`\`

Features:

\- month navigation;

\- day completion indicators;

\- empty/no-scheduled-day state;

\- selected-day detail;

\- day-level occurrence history.

Use:

\`\`\`text

GET /occurrences?from=&to=

\`\`\`

for selected-day detail.

**## M10 — Habit Details & Progress History**

Implement the Habit Details / Progress History screen.

Display:

\- current streak;

\- longest streak;

\- total completions;

\- weekly completion;

\- monthly completion;

\- historical progress.

Reuse the approved Stitch design where applicable.

**## M11 — Statistics Screen**

Implement the Statistics screen.

Data source:

\`\`\`text

GET /stats/overview

\`\`\`

Display:

\- active habits;

\- weekly completion;

\- best current streak;

\- lifetime completions.

**## M12 — Mobile Streak Regression**

Verify:

\`\`\`text

Complete

↓

streak increases

↓

Undo

↓

streak returns to correct value

\`\`\`

No manual refresh should be required.

\---

**# 35. Test Plan**

Phase 5 must include unit, integration, and API-level tests where appropriate.

**## 35.1 D10 — SKIPPED Breaks Streak**

\`\`\`text

Day 1 COMPLETED

Day 2 COMPLETED

Day 3 SKIPPED

\`\`\`

Expected:

\`\`\`text

current_streak = 0

\`\`\`

**## 35.2 MISSED Breaks Streak**

\`\`\`text

Day 1 COMPLETED

Day 2 COMPLETED

Day 3 MISSED

\`\`\`

Expected:

\`\`\`text

current_streak = 0

\`\`\`

**## 35.3 Today's Pending Occurrence**

\`\`\`text

Day 1 COMPLETED

Day 2 COMPLETED

Day 3 PENDING

\`\`\`

Expected:

\`\`\`text

current_streak = 2

\`\`\`

**## 35.4 D11 — Non-Daily Habit**

Schedule:

\`\`\`text

Monday / Wednesday / Friday

\`\`\`

Occurrences:

\`\`\`text

Monday     COMPLETED

Wednesday  COMPLETED

Friday     COMPLETED

\`\`\`

Expected:

\`\`\`text

current_streak = 3

\`\`\`

Tuesday and Thursday must not break the streak.

\---

**# 36. Schedule-Version Regression**

Test:

\`\`\`text

Old schedule:

Monday / Wednesday / Friday

Historical occurrences:

Monday     COMPLETED

Wednesday  COMPLETED

New schedule:

Tuesday / Thursday / Saturday

\`\`\`

Historical streak calculations must continue respecting the old schedule for historical dates.

\---

**# 37. Undo Regression**

Test:

\`\`\`text

COMPLETED

↓

streak increases

↓

UNDO

↓

streak recalculated

\`\`\`

The result must equal actual occurrence history.

\---

**# 38. Redo Regression**

Test:

\`\`\`text

COMPLETED

↓

UNDO

↓

COMPLETED

\`\`\`

Expected:

\- correct \`total_completions\`;

\- correct \`current_streak\`;

\- no duplicate increment;

\- no stale cached value.

\---

**# 39. Total Completion Counter Tests**

Cover:

\`\`\`text

PENDING → COMPLETED

COMPLETED → PENDING

SKIPPED → COMPLETED

COMPLETED → SKIPPED

\`\`\`

Ensure the cached counter exactly matches authoritative occurrence history.

\---

**# 40. Idempotency Tests**

Repeated completion request with the same idempotency key must not increment \`total_completions\` twice.

Repeated undo request must not decrement twice.

Conflicting idempotency keys must preserve Phase 4 behavior.

\---

**# 41. Longest Streak Tests**

Test:

\`\`\`text

COMPLETED

COMPLETED

COMPLETED

SKIPPED

COMPLETED

COMPLETED

\`\`\`

Expected:

\`\`\`text

longest_streak = 3

\`\`\`

Then undo one of the historical completions and ensure the calculated longest streak changes accordingly.

This protects against an incorrect monotonic-cache implementation.

\---

**# 42. Weekly Statistics Tests**

Test:

\- Monday boundary;

\- Sunday boundary;

\- today inclusion;

\- future-day exclusion;

\- zero scheduled occurrences;

\- mixed completed/skipped/missed/pending;

\- non-daily schedules.

\---

**# 43. Monthly Statistics Tests**

Test:

\- first day of month;

\- last day of month;

\- month transition;

\- future dates;

\- zero scheduled occurrences;

\- timezone boundary;

\- non-daily schedules.

\---

**# 44. Timezone Boundary Test**

Create a user whose local date differs from UTC.

Verify:

\`\`\`text

weekly statistics

monthly statistics

calendar summary

\`\`\`

use the user's local date boundaries.

\---

**# 45. Calendar Tests**

Verify:

\- every day of requested month is returned;

\- days without occurrences return \`scheduled = 0\`;

\- zero-scheduled days return \`percent = null\`;

\- completed counts are correct;

\- percentages use round-half-up;

\- archived historical habits remain included;

\- ownership is enforced;

\- no N+1 query pattern is introduced.

\---

**# 46. Archived Habit Tests**

Create a habit with historical occurrences.

Archive it.

Verify:

\- historical calendar still contains its occurrences;

\- historical statistics can still use its completed records where applicable;

\- no future occurrences are generated;

\- active-habit count excludes it.

\---

**# 47. Account Statistics Tests**

Verify:

\`\`\`text

total_active_habits

weekly_completion_percent

best_current_streak

total_lifetime_completions

\`\`\`

Use multiple habits with different denominators.

Specifically test that combined weekly percentage is weighted by total scheduled occurrences rather than averaging habit percentages.

\---

**# 48. Query Count Test**

The calendar summary must not execute one database query per calendar day.

Test the endpoint with query instrumentation and assert that the implementation uses an aggregate strategy rather than an N+1 loop.

\---

**# 49. API Contract**

Phase 5 must update:

\`\`\`text

docs/openapi.json

\`\`\`

with:

\`\`\`text

GET /calendar/summary

GET /habits/{id}/stats

GET /stats/overview

\`\`\`

Add all request/response schemas.

The canonical OpenAPI file must remain synchronized with the generated FastAPI schema.

Existing OpenAPI drift CI must continue to pass.

\---

**# 50. Mobile API Layer**

Add typed API functions for:

\`\`\`text

getCalendarSummary()

getHabitStats()

getStatsOverview()

\`\`\`

The mobile layer must use the existing authenticated API client.

Do not duplicate authentication/token logic.

\---

**# 51. Error Handling**

Phase 5 endpoints must follow existing project API error conventions.

Handle:

\- unauthorized access;

\- invalid dates;

\- invalid month;

\- missing habit;

\- non-owned habit;

\- database failures.

The mobile UI must provide appropriate loading, empty, and error states.

\---

**# 52. Explicitly Out of Scope**

The following are **\*\*not part of Phase 5\*\***:

\- Challenges

\- Challenge rooms

\- Peer tracking

\- Leaderboards

\- Cross-user statistics

\- Social rankings

\- Notifications

\- Reminder scheduling

\- Push notifications

\- Expo Notifications implementation

\- Gamification beyond streak/statistics display

\- New occurrence-generation logic

\- New occurrence status types

No:

\`\`\`text

challenges

challenge_members

leaderboards

\`\`\`

tables should be introduced in Phase 5.

These belong to later phases.

\---

**# 53. Data Integrity Rules**

The following rules are mandatory:

1\. \`occurrences\` remains the source of truth.

2\. Cached counters must never become independent tracking state.

3\. Historical occurrences must not be rewritten to make statistics convenient.

4\. Schedule changes must not rewrite historical schedule semantics.

5\. Archive must not destroy historical occurrence data.

6\. Streak calculations must respect the user's local timezone.

7\. Non-daily streaks operate on scheduled occurrences.

8\. \`SKIPPED\` breaks a streak.

9\. \`MISSED\` breaks a streak.

10\. Today's \`PENDING\` occurrence does not break the current streak.

11\. Future occurrences do not contribute to current/period statistics.

12\. Historical statistics must remain reproducible from occurrence history.

\---

**# 54. Source-of-Truth Recovery**

Because cached fields are derived values, the system should make it possible to repair them from occurrence history.

At minimum, the backend must have reusable service logic capable of recalculating:

\`\`\`text

current_streak

total_completions

\`\`\`

from authoritative occurrence data.

A future maintenance/reconciliation command may use these services to detect and repair drift.

A dedicated reconciliation CLI is **\*\*not required in Phase 5\*\*** unless implementation discovers a concrete need.

\---

**# 55. Verification Checklist**

**## Backend**

\- [ ] Migration \`0004\` created

\- [ ] Migration backfills existing data

\- [ ] \`current_streak\` implemented

\- [ ] \`total_completions\` implemented

\- [ ] longest streak calculation implemented

\- [ ] schedule-version-aware streak logic implemented

\- [ ] D10 implemented

\- [ ] D11 implemented

\- [ ] D12 implemented

\- [ ] D13 implemented

\- [ ] D14 implemented

\- [ ] D15 implemented

\- [ ] \`/calendar/summary\` implemented

\- [ ] \`/habits/{id}/stats\` implemented

\- [ ] \`/stats/overview\` implemented

\- [ ] transaction integrity verified

\- [ ] idempotency preserved

\- [ ] ownership verified

\- [ ] OpenAPI updated

**## Tests**

\- [ ] full backend test suite passes

\- [ ] D10 test passes

\- [ ] D11 test passes

\- [ ] schedule-version regression passes

\- [ ] undo/redo tests pass

\- [ ] longest-streak historical recalculation passes

\- [ ] timezone tests pass

\- [ ] calendar tests pass

\- [ ] archived-habit tests pass

\- [ ] account-statistics tests pass

\- [ ] query-count/N+1 test passes

\- [ ] OpenAPI drift test passes

**## Quality**

\- [ ] Ruff clean

\- [ ] Mypy clean

\- [ ] Alembic at head

\- [ ] no temporary debug files

\- [ ] no Phase 6 implementation

\- [ ] working tree reviewed before commit

**## Mobile**

\- [ ] Calendar screen implemented

\- [ ] Month navigation works

\- [ ] Day detail works

\- [ ] Habit statistics displayed

\- [ ] Statistics screen implemented

\- [ ] streak updates without manual refresh

\- [ ] loading states work

\- [ ] empty states work

\- [ ] error states work

\- [ ] physical-device verification completed

\---

**# 56. Acceptance Scenario**

The following end-to-end scenario must pass before Phase 5 is closed.

\`\`\`text

1\. Create a habit.

2\. Configure a recurring schedule.

3\. Phase 4 generates today's occurrence.

4\. Open Calendar.

5\. Today's occurrence is visible.

6\. Mark the occurrence COMPLETED.

7\. Current streak updates.

8\. Total completions updates.

9\. Calendar summary shows the completion.

10\. Habit statistics show the updated values.

11\. Account statistics reflect the completion.

12\. Undo the completion.

13\. Current streak recalculates correctly.

14\. Total completions decrements correctly.

15\. Calendar summary reflects the undo.

16\. Re-complete the occurrence.

17\. Values return to the correct state.

18\. Cross a local timezone day boundary.

19\. Verify weekly/monthly statistics use the user's local date.

20\. Verify a non-daily habit counts consecutive scheduled occurrences.

21\. Verify SKIPPED breaks the streak.

22\. Archive a habit.

23\. Verify historical calendar data remains available.

24\. Verify archived habit is excluded from active-habit statistics.

\`\`\`

\---

**# 57. Phase 5 Completion Criteria**

Phase 5 is complete only when:

\`\`\`text

Occurrences

    ↓

Calendar

    ↓

Streak Engine

    ↓

Habit Statistics

    ↓

Account Statistics

\`\`\`

all operate from the same authoritative occurrence history.

The implementation must preserve:

\- historical correctness;

\- timezone correctness;

\- schedule-version correctness;

\- idempotency;

\- transaction atomicity;

\- ownership isolation;

\- API contract integrity.

No Phase 6 work should be included in the Phase 5 implementation.

\---

**# 58. Phase 5 Implementation Clarifications**

The following rules are authoritative implementation constraints for Phase 5:

1\. **\*\*Occurrence history remains the source of truth.\*\***

   \`current_streak\`, \`longest_streak\`, and \`total_completions\` are derived

   cached fields only. They must always be recoverable by recalculating from

   occurrence history.

2\. **\*\*Every occurrence status change recalculates all three cached fields.\*\***

   \`current_streak\`, \`longest_streak\`, and \`total_completions\` are recalculated

   together and persisted in the same transaction as the triggering status

   change. No status transition is exempt — do not attempt to classify some

   transitions as "streak-relevant" and others as not; that judgment call is

   itself the source of bugs (e.g. a transition that looks like a pure

   completion-count change may still break a streak).

3\. **\*\***\`longest_streak\` **must never be incrementally bumped.\*\***

   The implementation must not use \`max(old_value, new_value)\`. A historical

   undo or status correction must be able to reduce the cached longest streak.

4\. **\*\*Streak traversal is over scheduled occurrences, not calendar days.\*\***

   Non-scheduled calendar days do not break a streak. Historical scheduled

   status must be resolved using \`schedule_for(habit_id, occurrence_date)\` so

   later schedule versions cannot reinterpret historical occurrences.

5\. \*\*Backward history traversal must be paginated, with two distinct stopping

   conditions:\*\*

   **\*\*5a.** \`current_streak\` **stops at the first break.\*\***

   Fetch scheduled occurrences in pages, most recent first. Stop as soon as

   a page contains a streak-breaking occurrence — no need to look further

   back once the current run has ended.

   **\*\*5b.** \`longest_streak\` **has no early-stop condition.\*\***

    Every page must be scanned. Pages may be processed oldest to newest or

    newest to oldest, provided the complete scheduled-occurrence history is

    examined. A streak-breaking occurrence resets the running counter but does

    NOT end the scan — there may be a longer completed run elsewhere in the

    habit's history. Pagination only bounds memory per fetch; it must never be

    used to bound the total amount of history scanned.

    Do not apply 5a's early-stop logic to the \`longest_streak\` calculation —

    doing so can silently miss a longer historical run and report an incorrect

    maximum.

6\. **\*\*Archived habits remain historically visible.\*\***

   Archived occurrences remain available to calendar/history and lifetime

   statistics. Archived habits are excluded from current-period account

   statistics whose scope is explicitly limited to active habits.

7\. **\*\*Cached aggregate fields are never authoritative.\*\***

   If cached values become inconsistent with occurrence history, the

   occurrence history must be used to reconstruct the correct values.

These rules take precedence over implementation shortcuts that would violate

tracking correctness, historical accuracy, or recovery from cached-state

corruption.

**# 59. Phase 6**

After Phase 5 is fully verified and committed:

*>* **\*\*Phase 6 — Notifications\*\***

Scope:

\- local scheduled reminders;

\- Expo Notifications;

\- reminder scheduling based on existing habit schedules;

\- notification permission handling;

\- notification lifecycle management.

Phase 6 depends on the existing:

\`\`\`text

Habits

Schedules

Occurrence Engine

\`\`\`

and does not require changes to the Phase 5 calendar/streak/statistics architecture.