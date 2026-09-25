# Habit Tracker — Phase 1: Requirements Document

**Team:** 2–4 devs · **Goal:** Ship a real, usable product · **Stack:** React Native (Expo) + FastAPI + PostgreSQL (SQLAlchemy 2.0 async + asyncpg + Alembic)

> **Revision (2026-09-24):** FR-3.1, FR-3.3 and FR-4.4 updated to reflect Phase 3 decisions — no back-dated start dates, schedule edits effective from the next local day, async SQLAlchemy. See Phase 3 §11 (Decision Log).

---

## 1. User Roles

| Role | Description |
|---|---|
| **User** | Standard account — habits, streaks, challenges |
| **Challenge Creator** | A User who created a challenge room (has delete/edit rights on that room only) |
| *(No admin/moderator role in MVP — deferred)* |

---

## 2. Functional Requirements

### FR-1 — Authentication
- FR-1.1: User can register with email + password
- FR-1.2: User can register/login via Google OAuth
- FR-1.3: Password reset via email link
- FR-1.4: JWT-based session (access + refresh token)
- FR-1.5: Email uniqueness enforced; OAuth account can be linked to an existing email/password account

### FR-2 — Profile
- FR-2.1: User sets display name, avatar (optional), timezone (auto-detected, editable)
- FR-2.2: User sets a "Goal" (free text, doubles as bio)

### FR-3 — Habit Management
- FR-3.1: User can create a custom habit (name, description, frequency, days, start date, reminder time, optional target). Start date must be today or later in the user's local timezone — no back-dating in MVP, so history only begins from the day a habit is created
- FR-3.2: User can select from preloaded habit sheets (Fitness, Study, Productivity, Health, Reading) and add individual habits from them
- FR-3.3: User can edit a habit's future schedule without altering past completion records (see FR-4.4). Edits take effect from the next local day at the earliest; same-day schedule edits are not supported in MVP
- FR-3.4: User can archive/delete a habit (soft delete — history retained)

### FR-4 — Daily Tracking
- FR-4.1: System generates a daily occurrence per active habit per scheduled day, in the user's local timezone
- FR-4.2: User can mark an occurrence: `COMPLETED`, `SKIPPED`, or leave as `PENDING` → `MISSED` after day ends
- FR-4.3: "Today" screen shows all of today's occurrences with live completion %
- FR-4.4: A schedule edit takes effect from its `effective_from` date (user-local, ≥ tomorrow). Only `PENDING` occurrences on or after that date are regenerated; `COMPLETED` / `SKIPPED` / `MISSED` records are never modified

### FR-5 — Streaks & Stats
- FR-5.1: Current streak = consecutive `COMPLETED` days up to and including yesterday/today, recalculated from occurrence history (never stored as a bare counter)
- FR-5.2: Longest streak, total completions, completion % (weekly/monthly/all-time) computed per habit and account-wide

### FR-6 — Calendar
- FR-6.1: Daily / Weekly / Monthly views, all reading from the same occurrence table as FR-4/FR-5 (no separate calendar data model)

### FR-7 — Challenges
- FR-7.1: User creates a challenge: name, shared habit definition, duration, generates a join code
- FR-7.2: User joins via code → shared habit auto-added to their habit list for challenge duration
- FR-7.3: Leaderboard: `completed_days / elapsed_days × 100`, tie-break by current streak then join time
- FR-7.4: Challenge auto-ends at duration expiry; leaderboard freezes

### FR-8 — Notifications
- FR-8.1: Local push reminder at each habit's scheduled time (Expo Notifications)
- FR-8.2: *(Deferred: missed-habit/streak-warning pushes — post-MVP)*

### FR-9 — Offline
- FR-9.1: Marking a habit complete works offline; queued and synced on reconnect
- FR-9.2: Conflict rule: server record wins if a conflicting completion already exists for that occurrence (simple last-write-loses-to-server for MVP; proper merge deferred)

---

## 3. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | API p95 response time < 300ms for read endpoints under normal load |
| NFR-2 | Passwords hashed with bcrypt/argon2; JWTs short-lived (≤15min access, 7-day refresh) |
| NFR-3 | PostgreSQL with foreign-key constraints enforcing habit → schedule → occurrence integrity |
| NFR-4 | App must remain usable (read + local-write) with zero connectivity |
| NFR-5 | Timezone-correct day boundaries per user (§7 of proposal) |
| NFR-6 | Codebase split: `mobile/` (Expo) and `backend/` (FastAPI), independently deployable |
| NFR-7 | CI runs lint + tests on PR (GitHub Actions, free tier is enough for a 2–4 person team) |

---

## 4. Out of Scope for MVP
Custom-habit challenge matching, AI features, follower/friend graph, advanced analytics, missed/streak-warning push notifications, public discovery — all listed in proposal §20/§21, unchanged.

---

## 5. Suggested Team Split (2–4 devs)
- **Backend (1–2):** FastAPI, PostgreSQL schema, auth, occurrence/streak engine, challenge logic
- **Mobile (1–2):** Expo app, screens (§16 of proposal), offline queue, notifications
- Shared: API contract (OpenAPI spec from FastAPI) is the integration boundary — agree on it before Phase 3 starts

---

**Next (Phase 2):** System architecture + ER diagram / DB schema, derived directly from FR-3 through FR-7.

