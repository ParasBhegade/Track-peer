# Habit Tracker — Phase 2: System Design

Architecture, ER diagrams, and wireframes for the diagrams are attached as inline visuals in the conversation; this doc holds the schema definitions and scalability rationale for reference.

> **Revision (2026-09-24):** Schema synced with the Phase 3 contract — added `avatar_url`, `target`, timestamps, auth-token tables and habit-sheet tables; `schedules.effective_from` is now a `date`; `days_of_week` is the source of truth for scheduling. DB access stack: SQLAlchemy 2.0 async + asyncpg + Alembic. See Phase 3 §5 and §11.

---

## 1. Architecture Summary

```text
Mobile app (Expo) → Load balancer → FastAPI servers (stateless, scaled horizontally)
                                          │
                        ┌─────────────────┼─────────────────┐
                        ▼                 ▼                 ▼
                  PostgreSQL         Redis cache        Job queue (Celery)
                (primary + replica)  (leaderboards,           │
                                      sessions)                ▼
                                                        Push notifications
                                                        (Expo → FCM/APNs)
```

**Why this shape scales:**
- API servers are stateless — sessions live in Redis/JWT, not in-process memory — so you add instances behind the load balancer with zero code change.
- Expensive work (occurrence generation, streak recompute, leaderboard refresh, notification fan-out) runs on the job queue, off the request path. A slow leaderboard recalculation for a 500-person challenge never blocks someone marking a habit complete.
- Read replica absorbs read-heavy traffic (calendar views, stats, leaderboards) so it doesn't compete with writes (marking habits complete) on the primary.
- Redis caches computed leaderboard standings (recomputed on a schedule, not per-request) — leaderboard reads become O(1) cache hits instead of re-aggregating occurrence rows every time someone opens a challenge.

---

## 2. Database Schema

### `users`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| email | string, unique | stored lowercased; unique index on `lower(email)` |
| password_hash | string, nullable | null if OAuth-only |
| google_oauth_id | string, nullable, unique | |
| timezone | string | IANA tz name, e.g. `Asia/Kolkata` |
| display_name | string | |
| goal | text, nullable | doubles as profile bio |
| avatar_url | text, nullable | URL only in MVP; upload flow deferred (FR-2.1) |
| created_at | timestamp | |
| updated_at | timestamp | |

### `habits`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK → users | |
| name | string | |
| description | text, nullable | |
| target | text, nullable | optional target, e.g. "1 problem/day" (FR-3.1) |
| frequency | enum | `daily`, `weekdays`, `custom` | derived label — `schedules.days_of_week` is the source of truth; the server sets this on every write |
| start_date | date | must be ≥ today in the user's timezone at creation (no back-dating); enforced by the API |
| is_shared_habit | boolean | true if cloned from a challenge template |
| source_challenge_id | uuid FK → challenges, nullable | set only if `is_shared_habit`; created as a plain uuid now, FK constraint added in the challenges migration (avoids the habits ↔ challenges circular dependency) |
| archived_at | timestamp, nullable | soft delete |
| created_at | timestamp | |
| updated_at | timestamp | |

### `schedules`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| habit_id | uuid FK → habits | |
| days_of_week | int[] | 0=Mon..6=Sun |
| reminder_time | time, nullable | |
| effective_from | date | user-local date; edits create a new row (must be ≥ tomorrow) — see below |

**Design note:** editing a schedule inserts a new `schedules` row with a new `effective_from` (a user-local date, at least tomorrow) rather than mutating a row that is already in effect. A row that is *not yet* in effect (same `effective_from`) may be updated in place. Occurrence generation always uses the schedule that was effective on that occurrence's date. This is what guarantees past records never shift retroactively (proposal §7).

Constraints: unique `(habit_id, effective_from)`; check `cardinality(days_of_week) BETWEEN 1 AND 7`.

### `occurrences`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| habit_id | uuid FK → habits | |
| occurrence_date | date | |
| status | enum | `pending`, `completed`, `skipped`, `missed` |
| completed_at | timestamp, nullable | |
| synced_from_offline | boolean | for conflict auditing (FR-9.2) |

Unique constraint on `(habit_id, occurrence_date)`.

### `challenges`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| creator_id | uuid FK → users | |
| habit_id | uuid FK → habits | the template/shared habit |
| name | string | |
| join_code | string(6), unique | |
| duration_days | int | |
| starts_at | date | |
| ends_at | date | computed, frozen at creation |

### `challenge_members`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| challenge_id | uuid FK → challenges | |
| user_id | uuid FK → users | |
| cloned_habit_id | uuid FK → habits | the member's own habit clone |
| joined_at | timestamp | |

Unique constraint on `(challenge_id, user_id)`.

Leaderboard is computed by joining `challenge_members` → `cloned_habit_id` → `occurrences`, aggregating `completed / elapsed_since(joined_at)`. This runs as a scheduled job per active challenge (e.g. every 15 min), writing the result into Redis rather than being computed on every leaderboard page load.

### `refresh_tokens`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK → users, on delete cascade | |
| token_hash | text, unique | SHA-256 of the opaque token; raw token never stored |
| family_id | uuid | all rotations from one login share a family; reuse of a revoked token revokes the whole family |
| expires_at | timestamptz | 7 days |
| revoked_at | timestamptz, nullable | |
| created_at | timestamptz | |

### `password_reset_tokens`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK → users, on delete cascade | |
| token_hash | text, unique | |
| expires_at | timestamptz | 30 minutes |
| used_at | timestamptz, nullable | single-use |

### `habit_sheets`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| slug | text, unique | |
| name | text | |
| category | text | Fitness, Study, Productivity, Health, Reading (FR-3.2) |
| sort_order | int | |

### `sheet_habits`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| sheet_id | uuid FK → habit_sheets, on delete cascade | |
| name | text | |
| description | text, nullable | |
| frequency | enum | same enum as `habits.frequency` |
| days_of_week | int[] | |
| default_reminder_time | time, nullable | |
| target | text, nullable | |
| sort_order | int | |

Adding a habit from a sheet **copies** the template into a normal `habits` + `schedules` row; the user's habit is independent of the sheet afterwards.

---

## 3. Scalability Checklist

- [ ] Stateless API layer — no in-memory session/cache that ties a request to a specific server instance
- [ ] Connection pooling (PgBouncer or the SQLAlchemy pool) so horizontal API scaling doesn't exhaust Postgres connections. **Note:** asyncpg behind PgBouncer in transaction-pooling mode needs `statement_cache_size=0` (and no prepared-statement caching), or you'll hit prepared-statement errors
- [ ] Read replica wired for calendar/stats/leaderboard reads; primary reserved for writes
- [ ] Occurrence generation is a scheduled batch job (not generated lazily per-request) so the "Today" screen is always a simple read. Because "midnight" differs per user timezone, it runs hourly and targets users whose local date just rolled over (final cadence decided in build step 3)
- [ ] Leaderboard/streak aggregates precomputed on a schedule and cached in Redis, not recalculated per page view
- [ ] Notification fan-out queued, not sent synchronously from the API request that scheduled it
- [ ] DB indexes: `occurrences(habit_id, occurrence_date)`, `habits(user_id)` (partial: `WHERE archived_at IS NULL`), `schedules(habit_id, effective_from DESC)`, `refresh_tokens(user_id)`, `refresh_tokens(family_id)`, `challenge_members(challenge_id)`

---

**Next (Phase 3):** API contract (OpenAPI spec) + implementation start, following the priority order in proposal §17, beginning with Phase 1 (Auth + Profile) and Phase 2 (Habit Creation + Scheduling) from FR-1 through FR-3.

