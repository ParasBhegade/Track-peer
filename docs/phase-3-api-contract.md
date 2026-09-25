# Habit Tracker — Phase 3: API Contract + Implementation Kickoff

**Scope of this doc:** FR-1 (Auth), FR-2 (Profile), FR-3 (Habit Management) — i.e. proposal §17 build steps 1 and 2.
**Not in this doc:** occurrences/completion (FR-4), streaks, calendar, challenges, notifications, offline sync. Those get their own contract additions in later steps.
**Stack:** Expo (React Native) · FastAPI · PostgreSQL · Redis/Celery (wired later)

> Naming note: "Phase 3" here is the SDLC phase (contract + implementation start). "Build step 1/2" refers to the development order in proposal §17.

---

## 0. Review Findings — Gaps Between Phase 1/2 Docs and This Contract

Going through the requirements and the schema, these need fixing *before* we write the first migration. All are resolved in this doc; the migration in §5 includes them.

| # | Gap | Where | Resolution |
|---|---|---|---|
| 1 | `avatar` (FR-2.1) has no column | `users` | Add `avatar_url` (nullable). Upload flow deferred; MVP stores a URL only. |
| 2 | Optional `target` (FR-3.1) has no column | `habits` | Add `target` (text, nullable), e.g. "1 problem/day". |
| 3 | Preloaded habit sheets (FR-3.2) have no tables | schema | Add `habit_sheets` + `sheet_habits`, seeded from a JSON file. |
| 4 | Refresh tokens (FR-1.4) and password reset (FR-1.3) have no storage | schema | Add `refresh_tokens` + `password_reset_tokens` (hashed values only). |
| 5 | `habits.frequency` and `schedules.days_of_week` overlap | `habits` / `schedules` | `schedules.days_of_week` is the **source of truth**. `habits.frequency` is a denormalized label the server derives on every write. Clients never send inconsistent data. |
| 6 | `schedules.effective_from` is a `timestamp`, but occurrences are per **date** in the user's timezone | `schedules` | Change to `date` (user-local). Removes an entire class of timezone off-by-one bugs. FR-4.4's "edit timestamp" becomes "effective date". |
| 7 | Circular FK: `habits.source_challenge_id → challenges` and `challenges.habit_id → habits` | Phase 7 | Not needed now. When we get to challenges: create challenge with `habit_id` nullable, insert the habit, then set it — or make one FK `DEFERRABLE INITIALLY DEFERRED`. Column `source_challenge_id` is created now **without** the FK constraint; the constraint is added in the challenges migration. |
| 8 | No `created_at`/`updated_at` on `habits`, `users` | schema | Add both. Cheap now, painful later. |
| 9 | Nightly occurrence generation runs on server time, but "midnight" differs per user | Phase 2 checklist | Not this step, but flag now: run generation **hourly**, for users whose local date just rolled over (or generate 2 days ahead). Decide in build step 3. |
| 10 | Proposal lists 7 sheet categories, FR-3.2 lists 5 | docs | Seed the 5 in FR-3.2 for MVP; the other two are just more JSON later. |

---

## 1. API Conventions

| Topic | Rule |
|---|---|
| Base path | `/api/v1` |
| Format | JSON, `snake_case` fields, UTF-8 |
| Auth | `Authorization: Bearer <access_token>` on everything except `/auth/*` (unauthenticated ones listed in §2) |
| IDs | UUID v4 strings |
| Dates | `date` = `YYYY-MM-DD` (user-local). `time` = `HH:MM` 24h (user-local). `timestamp` = ISO-8601 UTC with `Z`. |
| Days of week | Integers, `0`=Mon … `6`=Sun (matches the `schedules.days_of_week` schema) |
| Pagination | Not needed for MVP (a user has tens of habits, not thousands). Revisit for challenge lists. |
| Idempotency | Mutating offline-capable endpoints (added in build step 3) will accept a client-generated `Idempotency-Key`. Not needed for auth/profile/habit CRUD. |
| Rate limiting | `/auth/login`, `/auth/register`, `/auth/password/forgot`: 5 req/min per IP + per email (Redis counter). |
| Versioning | Breaking changes → `/api/v2`. Additive changes (new optional fields) stay in v1. |

### Error format (all non-2xx)

```json
{
  "error": {
    "code": "validation_error",
    "message": "Human-readable summary",
    "details": [
      { "field": "days_of_week", "issue": "must contain at least one day" }
    ]
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `bad_request` | Malformed request |
| 401 | `invalid_credentials` | Wrong email/password |
| 401 | `token_expired` / `token_invalid` | Access token bad — client should try `/auth/refresh` once |
| 401 | `refresh_token_invalid` | Refresh failed — client must log out |
| 403 | `forbidden` | Authenticated but not allowed |
| 404 | `not_found` | Also used for other users' resources (don't leak existence) |
| 409 | `email_taken` | Register with an existing email |
| 409 | `conflict` | Other uniqueness / state conflicts |
| 422 | `validation_error` | Pydantic validation failure (FastAPI default remapped to this shape) |
| 429 | `rate_limited` | Includes `Retry-After` header |

---

## 2. Endpoint Summary

### 2.1 Auth (FR-1)

| Method | Path | Auth | Purpose | FR |
|---|---|---|---|---|
| POST | `/auth/register` | – | Email + password signup → returns user + tokens | 1.1 |
| POST | `/auth/login` | – | Email + password login → tokens | 1.1 |
| POST | `/auth/google` | – | Sign in / sign up with a Google **ID token** | 1.2 |
| POST | `/auth/google/link` | ✔ | Link Google to the current account | 1.5 |
| POST | `/auth/refresh` | – | Rotate refresh token → new access + refresh | 1.4 |
| POST | `/auth/logout` | – | Revoke the given refresh token | 1.4 |
| POST | `/auth/password/forgot` | – | Send reset email (always `202`, never reveals if email exists) | 1.3 |
| POST | `/auth/password/reset` | – | Set new password using emailed token | 1.3 |

### 2.2 Profile (FR-2)

| Method | Path | Auth | Purpose | FR |
|---|---|---|---|---|
| GET | `/users/me` | ✔ | Current user profile | 2.1 |
| PATCH | `/users/me` | ✔ | Update display name, avatar URL, timezone, goal | 2.1, 2.2 |

### 2.3 Habits (FR-3)

| Method | Path | Auth | Purpose | FR |
|---|---|---|---|---|
| GET | `/habits` | ✔ | List my habits (`?include_archived=false`) | 3.x |
| POST | `/habits` | ✔ | Create custom habit **with its first schedule** | 3.1 |
| GET | `/habits/{habit_id}` | ✔ | Habit detail incl. current + pending schedule | 3.x |
| PATCH | `/habits/{habit_id}` | ✔ | Edit non-schedule fields (name, description, target) | 3.x |
| PUT | `/habits/{habit_id}/schedule` | ✔ | Change schedule going forward (creates new version) | 3.3 |
| DELETE | `/habits/{habit_id}` | ✔ | Archive (soft delete) | 3.4 |
| POST | `/habits/{habit_id}/restore` | ✔ | Un-archive | 3.4 |
| GET | `/habit-sheets` | ✔ | List preloaded sheets (with their habits) | 3.2 |
| POST | `/habits/from-sheet` | ✔ | Create a habit from a sheet template, with optional overrides | 3.2 |

---

## 3. Key Payloads

### 3.1 Token response (register / login / google / refresh)

```json
{
  "user": { "...see User below..." },
  "tokens": {
    "access_token": "eyJ...",
    "refresh_token": "opaque-random-string",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

`/auth/refresh` returns only the `tokens` object.

### 3.2 `POST /auth/register`

```json
// request
{
  "email": "paras@example.com",
  "password": "at-least-8-chars",
  "display_name": "Paras",
  "timezone": "Asia/Kolkata"
}
```

- `timezone` is required on register (client auto-detects with `Intl.DateTimeFormat().resolvedOptions().timeZone`), validated against `zoneinfo.available_timezones()`.
- Errors: `409 email_taken`, `422 validation_error`.

### 3.3 `POST /auth/google`

```json
{ "id_token": "<Google ID token from expo-auth-session>", "timezone": "Asia/Kolkata" }
```

Backend verifies the ID token signature/audience with Google's public keys, then:
1. `google_oauth_id` matches a user → log in.
2. Else, verified email matches an existing user → **do not auto-link silently.** Return `409 conflict` with `details: [{issue: "account_exists_link_required"}]`; the client tells the user to log in with password and link from settings (`/auth/google/link`). Prevents account takeover via an unverified-email edge case.
3. Else create a new user (`password_hash = null`).

### 3.4 `User` object

```json
{
  "id": "uuid",
  "email": "paras@example.com",
  "display_name": "Paras",
  "avatar_url": null,
  "timezone": "Asia/Kolkata",
  "goal": "Become an ML Engineer",
  "has_password": true,
  "google_linked": false,
  "created_at": "2026-09-24T10:00:00Z"
}
```

### 3.5 `PATCH /users/me`

All fields optional; only sent fields change.

```json
{ "display_name": "Paras B", "avatar_url": "https://...", "timezone": "Asia/Kolkata", "goal": "Become an ML Engineer" }
```

Constraints: `display_name` 1–50 chars, `goal` ≤ 200 chars, `timezone` valid IANA name.

> ⚠️ Changing `timezone` affects how "today" is computed. For MVP the change takes effect from the **next** local day; travel-mid-streak handling stays deferred (proposal §7).

### 3.5 `Habit` object

```json
{
  "id": "uuid",
  "name": "DSA Practice",
  "description": "Solve at least one problem",
  "target": "1 problem/day",
  "frequency": "custom",
  "start_date": "2026-09-25",
  "is_shared_habit": false,
  "source_challenge_id": null,
  "archived_at": null,
  "schedule": {
    "days_of_week": [0, 1, 2, 3, 4, 5],
    "reminder_time": "20:00",
    "effective_from": "2026-09-25"
  },
  "pending_schedule": null,
  "created_at": "2026-09-24T10:05:00Z"
}
```

- `schedule` = the schedule effective **today** (user-local).
- `pending_schedule` = a future-dated schedule row, if the user has scheduled a change; otherwise `null`. Same shape as `schedule`.

### 3.6 `POST /habits`

```json
{
  "name": "DSA Practice",
  "description": "Solve at least one problem",
  "target": "1 problem/day",
  "frequency": "custom",
  "days_of_week": [0, 1, 2, 3, 4, 5],
  "start_date": "2026-09-25",
  "reminder_time": "20:00"
}
```

**Server rules (source of truth for validation):**

| Rule | Detail |
|---|---|
| `frequency = daily` | Server sets `days_of_week = [0..6]`; any client-sent days are ignored |
| `frequency = weekdays` | Server sets `[0,1,2,3,4]` |
| `frequency = custom` | `days_of_week` required, non-empty, unique, each 0–6, stored sorted |
| Label normalization | If a `custom` payload happens to be all 7 days → stored as `daily`; exactly Mon–Fri → `weekdays` |
| `start_date` | Must be ≥ today in the user's timezone (no back-dating in MVP — avoids fabricating history). Default: today |
| `reminder_time` | Optional, `HH:MM`, interpreted in user-local time |
| `name` | 1–80 chars, trimmed |
| Atomicity | Habit row + first `schedules` row (`effective_from = start_date`) inserted in **one transaction** |

Response: `201` + `Habit`.

### 3.7 `PUT /habits/{habit_id}/schedule` — the important one

```json
{
  "frequency": "custom",
  "days_of_week": [0, 1, 3],
  "reminder_time": "06:30",
  "effective_from": "2026-09-28"
}
```

This endpoint is what protects the **"past records never change"** rule (proposal §7, FR-3.3, FR-4.4).

**Behavior:**
1. `effective_from` defaults to **tomorrow** (user-local) and must be **> today**. (MVP: no same-day schedule edits — avoids racing with today's already-generated occurrence.)
2. If a schedule row with that exact `effective_from` already exists → **update it in place** (safe: it hasn't taken effect yet).
3. Otherwise → **insert** a new `schedules` row. Rows whose `effective_from <= today` are **never** mutated.
4. Delete only `pending`-status occurrences with `occurrence_date >= effective_from` for this habit (stale future placeholders); the generator recreates them from the new schedule. `completed` / `skipped` / `missed` rows are never touched.
5. Update `habits.frequency` label to match the schedule that's effective *today* (unchanged until the new one kicks in — recompute in the nightly job or lazily on read).
6. Response `200` + `Habit` (with the new row in `pending_schedule`).

Resolving "which schedule applies on date D":

```sql
SELECT * FROM schedules
WHERE habit_id = :habit_id AND effective_from <= :D
ORDER BY effective_from DESC
LIMIT 1;
```

### 3.8 Habit sheets

`GET /habit-sheets`

```json
{
  "sheets": [
    {
      "id": "uuid",
      "slug": "study",
      "name": "Study",
      "category": "study",
      "habits": [
        {
          "id": "uuid",
          "name": "DSA Practice",
          "description": null,
          "frequency": "custom",
          "days_of_week": [0, 1, 2, 3, 4, 5],
          "default_reminder_time": "20:00",
          "target": "1 problem/day"
        }
      ]
    }
  ]
}
```

`POST /habits/from-sheet`

```json
{
  "sheet_habit_id": "uuid",
  "start_date": "2026-09-25",
  "overrides": { "reminder_time": "19:00", "days_of_week": [0, 2, 4] }
}
```

Copies the template into a normal `habits` + `schedules` row — after that, the user's habit is fully independent of the sheet (editing the sheet later never changes anyone's habit). Response `201` + `Habit`.

---

## 4. OpenAPI 3.1 Spec (Contract Draft)

FastAPI generates this from the Pydantic models, but we're going **contract-first**: this is the agreed shape. The backend must match it; CI will diff the generated `openapi.json` against `docs/openapi.json` (see §7, task B10).

```yaml
openapi: 3.1.0
info:
  title: Habit Tracker API
  version: 1.0.0-draft.1
servers:
  - url: http://localhost:8000/api/v1
security:
  - bearerAuth: []

paths:
  /auth/register:
    post:
      tags: [Auth]
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/RegisterRequest' }
      responses:
        '201': { description: Created, content: { application/json: { schema: { $ref: '#/components/schemas/AuthResponse' } } } }
        '409': { $ref: '#/components/responses/Error' }
        '422': { $ref: '#/components/responses/Error' }
  /auth/login:
    post:
      tags: [Auth]
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/LoginRequest' }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/AuthResponse' } } } }
        '401': { $ref: '#/components/responses/Error' }
        '429': { $ref: '#/components/responses/Error' }
  /auth/google:
    post:
      tags: [Auth]
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/GoogleAuthRequest' }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/AuthResponse' } } } }
        '409': { $ref: '#/components/responses/Error' }
  /auth/google/link:
    post:
      tags: [Auth]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/GoogleLinkRequest' }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/User' } } } }
        '409': { $ref: '#/components/responses/Error' }
  /auth/refresh:
    post:
      tags: [Auth]
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/RefreshRequest' }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/Tokens' } } } }
        '401': { $ref: '#/components/responses/Error' }
  /auth/logout:
    post:
      tags: [Auth]
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/RefreshRequest' }
      responses:
        '204': { description: Logged out }
  /auth/password/forgot:
    post:
      tags: [Auth]
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [email]
              properties: { email: { type: string, format: email } }
      responses:
        '202': { description: Accepted (always, regardless of whether the email exists) }
  /auth/password/reset:
    post:
      tags: [Auth]
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [token, new_password]
              properties:
                token: { type: string }
                new_password: { type: string, minLength: 8, maxLength: 128 }
      responses:
        '204': { description: Password updated; all refresh tokens revoked }
        '400': { $ref: '#/components/responses/Error' }

  /users/me:
    get:
      tags: [Profile]
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/User' } } } }
    patch:
      tags: [Profile]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/UserUpdate' }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/User' } } } }
        '422': { $ref: '#/components/responses/Error' }

  /habits:
    get:
      tags: [Habits]
      parameters:
        - { name: include_archived, in: query, schema: { type: boolean, default: false } }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  habits: { type: array, items: { $ref: '#/components/schemas/Habit' } }
    post:
      tags: [Habits]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/HabitCreate' }
      responses:
        '201': { description: Created, content: { application/json: { schema: { $ref: '#/components/schemas/Habit' } } } }
        '422': { $ref: '#/components/responses/Error' }
  /habits/from-sheet:
    post:
      tags: [Habits]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/HabitFromSheet' }
      responses:
        '201': { description: Created, content: { application/json: { schema: { $ref: '#/components/schemas/Habit' } } } }
        '404': { $ref: '#/components/responses/Error' }
  /habits/{habit_id}:
    parameters:
      - { name: habit_id, in: path, required: true, schema: { type: string, format: uuid } }
    get:
      tags: [Habits]
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/Habit' } } } }
        '404': { $ref: '#/components/responses/Error' }
    patch:
      tags: [Habits]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/HabitUpdate' }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/Habit' } } } }
    delete:
      tags: [Habits]
      summary: Archive (soft delete)
      responses:
        '204': { description: Archived }
  /habits/{habit_id}/restore:
    parameters:
      - { name: habit_id, in: path, required: true, schema: { type: string, format: uuid } }
    post:
      tags: [Habits]
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/Habit' } } } }
  /habits/{habit_id}/schedule:
    parameters:
      - { name: habit_id, in: path, required: true, schema: { type: string, format: uuid } }
    put:
      tags: [Habits]
      summary: Change schedule going forward (never alters past records)
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ScheduleUpdate' }
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/Habit' } } } }
        '422': { $ref: '#/components/responses/Error' }
  /habit-sheets:
    get:
      tags: [Habit Sheets]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  sheets: { type: array, items: { $ref: '#/components/schemas/HabitSheet' } }

components:
  securitySchemes:
    bearerAuth: { type: http, scheme: bearer, bearerFormat: JWT }

  responses:
    Error:
      description: Error
      content:
        application/json:
          schema: { $ref: '#/components/schemas/ErrorResponse' }

  schemas:
    ErrorResponse:
      type: object
      required: [error]
      properties:
        error:
          type: object
          required: [code, message]
          properties:
            code: { type: string }
            message: { type: string }
            details:
              type: array
              items:
                type: object
                properties:
                  field: { type: string }
                  issue: { type: string }

    RegisterRequest:
      type: object
      required: [email, password, display_name, timezone]
      properties:
        email: { type: string, format: email }
        password: { type: string, minLength: 8, maxLength: 128 }
        display_name: { type: string, minLength: 1, maxLength: 50 }
        timezone: { type: string, example: Asia/Kolkata }
    LoginRequest:
      type: object
      required: [email, password]
      properties:
        email: { type: string, format: email }
        password: { type: string }
    GoogleAuthRequest:
      type: object
      required: [id_token]
      properties:
        id_token: { type: string }
        timezone: { type: string }
    GoogleLinkRequest:
      type: object
      required: [id_token]
      properties:
        id_token: { type: string }
    RefreshRequest:
      type: object
      required: [refresh_token]
      properties:
        refresh_token: { type: string }

    Tokens:
      type: object
      required: [access_token, refresh_token, token_type, expires_in]
      properties:
        access_token: { type: string }
        refresh_token: { type: string }
        token_type: { type: string, enum: [bearer] }
        expires_in: { type: integer, example: 900 }
    AuthResponse:
      type: object
      required: [user, tokens]
      properties:
        user: { $ref: '#/components/schemas/User' }
        tokens: { $ref: '#/components/schemas/Tokens' }

    User:
      type: object
      required: [id, email, display_name, timezone, has_password, google_linked, created_at]
      properties:
        id: { type: string, format: uuid }
        email: { type: string, format: email }
        display_name: { type: string }
        avatar_url: { type: [string, 'null'] }
        timezone: { type: string }
        goal: { type: [string, 'null'] }
        has_password: { type: boolean }
        google_linked: { type: boolean }
        created_at: { type: string, format: date-time }
    UserUpdate:
      type: object
      properties:
        display_name: { type: string, minLength: 1, maxLength: 50 }
        avatar_url: { type: [string, 'null'], format: uri }
        timezone: { type: string }
        goal: { type: [string, 'null'], maxLength: 200 }

    Frequency:
      type: string
      enum: [daily, weekdays, custom]
    DaysOfWeek:
      type: array
      minItems: 1
      maxItems: 7
      uniqueItems: true
      items: { type: integer, minimum: 0, maximum: 6 }
      description: 0=Mon .. 6=Sun
    Time:
      type: string
      pattern: '^([01]\d|2[0-3]):[0-5]\d$'
      example: '20:00'

    ScheduleView:
      type: object
      required: [days_of_week, effective_from]
      properties:
        days_of_week: { $ref: '#/components/schemas/DaysOfWeek' }
        reminder_time: { oneOf: [{ $ref: '#/components/schemas/Time' }, { type: 'null' }] }
        effective_from: { type: string, format: date }
    Habit:
      type: object
      required: [id, name, frequency, start_date, is_shared_habit, schedule, created_at]
      properties:
        id: { type: string, format: uuid }
        name: { type: string }
        description: { type: [string, 'null'] }
        target: { type: [string, 'null'] }
        frequency: { $ref: '#/components/schemas/Frequency' }
        start_date: { type: string, format: date }
        is_shared_habit: { type: boolean }
        source_challenge_id: { type: [string, 'null'], format: uuid }
        archived_at: { type: [string, 'null'], format: date-time }
        schedule: { $ref: '#/components/schemas/ScheduleView' }
        pending_schedule:
          oneOf: [{ $ref: '#/components/schemas/ScheduleView' }, { type: 'null' }]
        created_at: { type: string, format: date-time }
    HabitCreate:
      type: object
      required: [name, frequency]
      properties:
        name: { type: string, minLength: 1, maxLength: 80 }
        description: { type: [string, 'null'], maxLength: 500 }
        target: { type: [string, 'null'], maxLength: 100 }
        frequency: { $ref: '#/components/schemas/Frequency' }
        days_of_week:
          { $ref: '#/components/schemas/DaysOfWeek' }
          # required when frequency = custom; ignored otherwise
        start_date: { type: string, format: date, description: Defaults to today (user-local); must be >= today }
        reminder_time: { oneOf: [{ $ref: '#/components/schemas/Time' }, { type: 'null' }] }
    HabitUpdate:
      type: object
      properties:
        name: { type: string, minLength: 1, maxLength: 80 }
        description: { type: [string, 'null'], maxLength: 500 }
        target: { type: [string, 'null'], maxLength: 100 }
    ScheduleUpdate:
      type: object
      required: [frequency]
      properties:
        frequency: { $ref: '#/components/schemas/Frequency' }
        days_of_week: { $ref: '#/components/schemas/DaysOfWeek' }
        reminder_time: { oneOf: [{ $ref: '#/components/schemas/Time' }, { type: 'null' }] }
        effective_from: { type: string, format: date, description: Defaults to tomorrow (user-local); must be > today }

    HabitSheet:
      type: object
      properties:
        id: { type: string, format: uuid }
        slug: { type: string }
        name: { type: string }
        category: { type: string }
        habits:
          type: array
          items:
            type: object
            properties:
              id: { type: string, format: uuid }
              name: { type: string }
              description: { type: [string, 'null'] }
              frequency: { $ref: '#/components/schemas/Frequency' }
              days_of_week: { $ref: '#/components/schemas/DaysOfWeek' }
              default_reminder_time: { oneOf: [{ $ref: '#/components/schemas/Time' }, { type: 'null' }] }
              target: { type: [string, 'null'] }
    HabitFromSheet:
      type: object
      required: [sheet_habit_id]
      properties:
        sheet_habit_id: { type: string, format: uuid }
        start_date: { type: string, format: date }
        overrides:
          type: object
          properties:
            reminder_time: { $ref: '#/components/schemas/Time' }
            days_of_week: { $ref: '#/components/schemas/DaysOfWeek' }
```

---

## 5. Schema Changes (Migration `0001_initial`)

Everything in Phase 2 §2, plus the fixes from §0. Only the **deltas and new tables** are spelled out; unchanged columns stay as in Phase 2.

### Changes to existing tables

| Table | Change |
|---|---|
| `users` | + `avatar_url text null`, + `updated_at timestamptz not null default now()`. `email` stored **lowercased**; unique index on `lower(email)`. |
| `habits` | + `target text null`, + `created_at`, + `updated_at`. `source_challenge_id` created as plain `uuid null` (FK added in the challenges migration). |
| `schedules` | `effective_from` is `date` (was `timestamp`). Unique `(habit_id, effective_from)`. Check: `cardinality(days_of_week) BETWEEN 1 AND 7`. |
| `occurrences` | Not created in this step (build step 3). Migration `0003`. |

### New tables

```text
refresh_tokens
  id            uuid PK
  user_id       uuid FK → users ON DELETE CASCADE
  token_hash    text unique not null      -- SHA-256 of the opaque token; never store raw
  family_id     uuid not null             -- all rotations of one login share a family
  expires_at    timestamptz not null
  revoked_at    timestamptz null
  created_at    timestamptz default now()

password_reset_tokens
  id            uuid PK
  user_id       uuid FK → users ON DELETE CASCADE
  token_hash    text unique not null
  expires_at    timestamptz not null      -- 30 min
  used_at       timestamptz null

habit_sheets
  id            uuid PK
  slug          text unique not null
  name          text not null
  category      text not null
  sort_order    int default 0

sheet_habits
  id                    uuid PK
  sheet_id              uuid FK → habit_sheets ON DELETE CASCADE
  name                  text not null
  description           text null
  frequency             habit_frequency not null
  days_of_week          int[] not null
  default_reminder_time time null
  target                text null
  sort_order            int default 0
```

### Indexes

`habits(user_id) WHERE archived_at IS NULL`, `schedules(habit_id, effective_from DESC)`, `refresh_tokens(user_id)`, `refresh_tokens(family_id)`.

---

## 6. Auth Design Decisions

| Topic | Decision | Why |
|---|---|---|
| Password hashing | **argon2id** via `argon2-cffi` | NFR-2 allows bcrypt/argon2; argon2id is the current default recommendation |
| Access token | JWT (HS256 to start, `PyJWT`), 15 min, claims: `sub`, `iat`, `exp`, `jti` | NFR-2 |
| Refresh token | **Opaque random 256-bit string**, 7-day, stored **hashed** in `refresh_tokens` | Lets us revoke; JWT refresh tokens can't be revoked without a denylist |
| Rotation | Every `/auth/refresh` issues a new refresh token and revokes the old one | Limits stolen-token window |
| Reuse detection | If a **revoked** refresh token is presented → revoke the entire `family_id` → user must re-login | Standard refresh-token-theft mitigation |
| Mobile storage | `expo-secure-store` (Keychain/Keystore). **Never** AsyncStorage for tokens | Security |
| Google login (mobile) | `expo-auth-session` gets a Google **ID token** on-device → `POST /auth/google` → server verifies with `google-auth` | Backend never handles Google passwords/redirects |
| Password reset | 30-min single-use token emailed as a deep link (`habittracker://reset?token=...`); on success revoke **all** the user's refresh tokens | FR-1.3 |
| Email sending | Celery task (already in the architecture). Dev: console/Mailpit. Prod: SES or Resend | Off the request path |
| Email verification | **Not in MVP** (not in FR-1). Google-linked accounts are verified by Google. Revisit before public launch | Scope |
| User enumeration | `/auth/password/forgot` always `202`; login returns a generic `invalid_credentials` | Security |

---

## 7. Implementation Kickoff

### 7.1 Repo layout (NFR-6: independently deployable)

```text
habit-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, router mounting, error handlers
│   │   ├── core/
│   │   │   ├── config.py           # pydantic-settings, reads .env
│   │   │   ├── security.py         # argon2, JWT encode/decode, token hashing
│   │   │   ├── errors.py           # AppError + handlers → standard error shape
│   │   │   └── deps.py             # get_db, get_current_user
│   │   ├── db/
│   │   │   ├── base.py             # SQLAlchemy DeclarativeBase
│   │   │   └── session.py          # async engine + sessionmaker
│   │   ├── models/                 # users.py, habits.py, schedules.py, auth_tokens.py, sheets.py
│   │   ├── schemas/                # Pydantic request/response models (mirror §4)
│   │   ├── services/               # auth_service.py, habit_service.py, schedule_service.py
│   │   ├── api/v1/                 # auth.py, users.py, habits.py, habit_sheets.py
│   │   └── seeds/habit_sheets.json # preloaded sheets
│   ├── alembic/                    # migrations
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── mobile/                         # Expo app (expo-router)
├── docs/
│   ├── openapi.json                # committed snapshot = the contract
│   └── Phase1..3 docs
├── docker-compose.yml              # postgres, redis, mailpit
└── .github/workflows/ci.yml        # NFR-7
```

**Layering rule:** route handlers are thin (parse → call service → return schema). Business rules (schedule versioning, day resolution) live in `services/` so they're unit-testable without HTTP.

### 7.2 Backend dependencies

`fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]>=2`, `asyncpg`, `alembic`, `pydantic>=2`, `pydantic-settings`, `argon2-cffi`, `pyjwt`, `google-auth`, `email-validator`, `redis`, `celery`
Dev: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`, `testcontainers[postgres]` (or docker-compose'd test DB)

> Recommendation: SQLAlchemy 2.0 **async** + asyncpg — matches FastAPI's model and avoids blocking the event loop under load (Phase 2 scalability goals). If the team is more comfortable with sync, that's fine for MVP; just be consistent.

### 7.3 Key code skeletons

**Habit create validation (`schemas/habits.py`)**

```python
from datetime import date, time
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

class Frequency(str, Enum):
    daily = "daily"
    weekdays = "weekdays"
    custom = "custom"

ALL_DAYS = [0, 1, 2, 3, 4, 5, 6]
WEEKDAYS = [0, 1, 2, 3, 4]

class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    target: str | None = Field(default=None, max_length=100)
    frequency: Frequency
    days_of_week: list[int] | None = None
    start_date: date | None = None
    reminder_time: time | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v

    @model_validator(mode="after")
    def normalize_days(self):
        if self.frequency == Frequency.daily:
            self.days_of_week = ALL_DAYS
        elif self.frequency == Frequency.weekdays:
            self.days_of_week = WEEKDAYS
        else:  # custom
            days = self.days_of_week or []
            if not days or any(d < 0 or d > 6 for d in days):
                raise ValueError("days_of_week must contain values 0-6 for custom frequency")
            self.days_of_week = sorted(set(days))
            # label normalization
            if self.days_of_week == ALL_DAYS:
                self.frequency = Frequency.daily
            elif self.days_of_week == WEEKDAYS:
                self.frequency = Frequency.weekdays
        return self
```

**Schedule versioning (`services/schedule_service.py`)**

```python
async def change_schedule(db, user, habit, payload) -> Habit:
    today = local_today(user.timezone)              # zoneinfo, user-local date
    effective_from = payload.effective_from or today + timedelta(days=1)
    if effective_from <= today:
        raise AppError(422, "validation_error", "effective_from must be after today")

    existing = await get_schedule_row(db, habit.id, effective_from)
    if existing:                                    # not yet in effect -> safe to edit
        existing.days_of_week = payload.days_of_week
        existing.reminder_time = payload.reminder_time
    else:
        db.add(Schedule(habit_id=habit.id, days_of_week=payload.days_of_week,
                        reminder_time=payload.reminder_time,
                        effective_from=effective_from))

    # drop stale FUTURE placeholders only; never touch completed/skipped/missed
    await delete_pending_occurrences(db, habit.id, from_date=effective_from)
    await db.commit()
    return await load_habit_with_schedules(db, habit.id, today)
```

**Schedule lookup for any date (used later by the occurrence generator)**

```python
def schedule_for(schedules: list[Schedule], d: date) -> Schedule | None:
    eligible = [s for s in schedules if s.effective_from <= d]
    return max(eligible, key=lambda s: s.effective_from, default=None)
```

### 7.4 Task breakdown

**Backend (1–2 devs)**

| ID | Task | Depends on | Done when |
|---|---|---|---|
| B1 | Repo scaffold, `docker-compose.yml` (Postgres, Redis, Mailpit), config, `/health`, ruff+mypy, CI skeleton (NFR-7) | – | `docker compose up` + `pytest` green in CI |
| B2 | SQLAlchemy models + Alembic `0001_initial` (schema from §5) | B1 | `alembic upgrade head` / `downgrade base` both work on empty DB |
| B3 | Error handling (`AppError`, validation remap) + `get_current_user` dependency | B1 | Error shape in §1 verified by test |
| B4 | Register / login / refresh / logout + rotation & reuse detection | B2, B3 | Auth test matrix in §8 passes |
| B5 | `GET/PATCH /users/me` + timezone validation | B4 | Bad tz → 422; goal/display name persisted |
| B6 | Habit CRUD (`POST/GET/PATCH/DELETE/restore`) incl. first-schedule transaction | B5 | Habit + schedule row atomic; other user's habit → 404 |
| B7 | `PUT /habits/{id}/schedule` + versioning rules | B6 | Schedule-history tests in §8 pass |
| B8 | Habit sheets seed + `GET /habit-sheets` + `POST /habits/from-sheet` | B6 | 5 sheets seeded idempotently |
| B9 | Google sign-in + link + password reset (email via Celery/Mailpit) | B4 | Link/409 flows tested with a mocked Google verifier |
| B10 | CI check: regenerate `openapi.json`, fail on diff vs `docs/openapi.json` | B4+ | Contract drift breaks the build |

**Mobile (1–2 devs)** — can start on day 1 without waiting for the backend:

| ID | Task | Done when |
|---|---|---|
| M1 | Expo app (expo-router, TypeScript), theme, navigation shell for MVP screens (proposal §16) | App runs on device/emulator with empty screens |
| M2 | Generate typed client from `docs/openapi.json` (`openapi-typescript` + `openapi-fetch`) | `npm run gen:api` produces types; CI checks they're current |
| M3 | Mock server from the OpenAPI file (Prism: `prism mock docs/openapi.json`) | Mobile can build against the contract before backend exists |
| M4 | Auth screens: Splash → Login/Register, secure-store token handling, auto-refresh interceptor (retry once on `token_expired`) | Cold start restores session; refresh failure logs out |
| M5 | Profile setup (display name, timezone auto-detect, goal) | Matches FR-2 |
| M6 | Habit setup screens: sheet browser → add habit; custom habit form (day picker, time picker, target) | Creates habit against mock, then real backend |

### 7.5 Suggested order of attack (small team)

```text
Week 1   B1 B2 B3        │ M1 M2 M3
Week 2   B4 B5           │ M4 M5
Week 3   B6 B7 B8        │ M6
Week 4   B9 B10 + hardening, integration pass: mobile ↔ real backend
```

Rough estimate for a 2-person team; adjust once real velocity is known.

---

## 8. Test Plan (this step)

**Auth**
- Register → 201; duplicate email (case-insensitive) → 409; weak password → 422; invalid timezone → 422
- Login: wrong password and unknown email return the **same** `invalid_credentials`
- Access token expiry → `token_expired`; refresh works; old refresh token rejected after rotation
- **Reuse detection:** replay a rotated refresh token → whole family revoked, next legit refresh also fails
- Password reset: token single-use, expires at 30 min, revokes all sessions
- Google: existing email w/o link → 409 `account_exists_link_required`; link then login works

**Profile**
- PATCH only touches supplied fields; `goal` > 200 chars → 422

**Habits**
- Create `daily` / `weekdays` / `custom` → correct `days_of_week`; custom with `[]` or `[7]` → 422
- `start_date` in the past (user-local) → 422; timezone edge case: user in `Pacific/Kiritimati` (UTC+14) vs server UTC around midnight → "today" resolves by **user's** zone
- Habit + schedule are created atomically (force a failure on schedule insert → no orphan habit)
- User A cannot read/edit/archive User B's habit → 404
- Archive hides from default list, `include_archived=true` shows it, restore works

**Schedule versioning (protects proposal §7)**
- Given schedule Mon/Wed/Fri effective Sep 1; change to Mon/Tue/Thu effective Sep 28 → `schedule_for(Sep 20)` still returns Mon/Wed/Fri, `schedule_for(Sep 28)` returns Mon/Tue/Thu
- Second edit with the same `effective_from` updates the row (no duplicate)
- `effective_from <= today` → 422
- (Once occurrences exist, build step 3) completed rows before `effective_from` are unchanged after an edit — add as a regression test then

---

## 9. Decisions

| # | Question | Status | Outcome / Recommendation |
|---|---|---|---|
| D1 | Allow back-dated `start_date`? | ✅ **Decided** | **No.** Prevents fabricating `MISSED` history and skewing streaks. |
| D2 | Allow same-day schedule edits? | ✅ **Decided** | **No** — earliest effective date is tomorrow. Simplifies the race with today's occurrence. |
| D3 | Email verification on signup? | Open | Recommend deferring; add before public launch. |
| D4 | Avatar upload vs URL | Open | Recommend URL-only now; upload (S3/R2 presigned URL) later. |
| D5 | Async vs sync SQLAlchemy | ✅ **Decided** | **Async** (SQLAlchemy 2.0 + asyncpg; see §7.2). |
| D6 | Occurrence generation cadence (hourly by user-tz vs 2-days-ahead) | Open | Decide at the start of build step 3; both work with the schema as designed. |
| D7 | Should archiving a habit also cancel its future `pending` occurrences? | Open | Recommend yes — same delete-pending-only rule as schedule edits. |

---

## 10. What's Next

**Build step 3 — Daily Occurrence + Completion Tracking** (proposal §17 Phase 3, FR-4): add `occurrences` table (migration `0003`), the generator job, `GET /today`, `PUT /occurrences/{id}` (complete/skip), and the idempotency + offline-sync contract. That's where the "critical reliability scenario" (proposal §19) first becomes testable end-to-end.

---

## 11. Decision Log

Single place to record decisions and which docs they touched. Add a row whenever a decision changes a doc.

| Date | ID | Decision | Rationale | Docs updated |
|---|---|---|---|---|
| 2026-09-24 | D1 | No back-dated `start_date`; must be ≥ today in the user's timezone | Avoids fabricating `MISSED` history; keeps streaks and completion % honest | Phase 1 (FR-3.1), Phase 2 (`habits.start_date`), Proposal (§4.2), Phase 3 (§3.6, §9) |
| 2026-09-24 | D2 | No same-day schedule edits; `effective_from` ≥ tomorrow (user-local date) | Removes the race with today's already-generated occurrence; protects "past never changes" | Phase 1 (FR-3.3, FR-4.4), Phase 2 (`schedules`), Proposal (§7), Phase 3 (§3.7, §9) |
| 2026-09-24 | D5 | Async SQLAlchemy 2.0 + asyncpg + Alembic | Matches FastAPI's async model; fits the Phase 2 scalability goals | Phase 1 (stack line), Phase 2 (§3 pooling note), Proposal (§13), Phase 3 (§7.2, §9) |
| 2026-09-24 | – | Phase 2 schema aligned with the Phase 3 migration (avatar, target, timestamps, auth-token and habit-sheet tables, `effective_from` as `date`, `days_of_week` as source of truth) | Phase 2 must match the real migration | Phase 2 (§2, §3) |

Still open: D3, D4, D6, D7 (see §9).

