# Habit Tracker Application — MVP Proposal

## 1. Overview

The proposed application is a habit tracking and social accountability platform designed to help users build, maintain, and monitor habits consistently.

The application will not be limited to a web platform. The long-term target is a proper **mobile application**, with a backend and database supporting authentication, habit management, daily tracking, reminders, challenges, leaderboards, streaks, and calendar-based history.

For the initial stage, this document only proposes the idea, product scope, core logic, and technical direction. The complete SDLC — requirements, architecture, database design, UI/UX, implementation, testing, deployment, and maintenance — will be addressed in later phases.

---

## 2. Core Idea

The application allows a user to:

1. Create an account or log in.
2. Complete basic profile information.
3. Define their personal goal.
4. Use the goal as part of their profile bio.
5. Select preloaded habit sheets or create custom habits.
6. Create schedules and reminders for individual habits.
7. Track each habit on a daily basis.
8. View weekly, monthly, and daily progress.
9. Maintain and track streaks.
10. Create or join peer challenge rooms.
11. Compete with peers through a leaderboard.
12. Encourage and motivate other participants through social challenge progress.

The application should combine **personal habit tracking** with **peer accountability and healthy competition**.

---

## 3. Proposed User Flow

### Step 1 — Authentication

When the user opens the application:

- New user → Create Account
- Existing user → Login

Basic authentication and account security will be handled by the backend.

### Step 2 — Profile Setup

The user provides the required information.

The application also asks:

> **What is your main goal?**

Examples:

- Improve fitness
- Prepare for exams
- Learn programming
- Build a consistent study routine
- Improve productivity

This goal becomes part of the user's profile and can act as their personal bio.

Example:

> **Goal:** Become an ML Engineer

---

## 4. Habit Setup

After profile setup, the user can choose between two approaches.

### 4.1 Preloaded Habit Sheets

The application can provide ready-made collections of habits.

Possible categories:

- Fitness
- Study
- Productivity
- Health
- Personal Development
- Reading
- Skill Development

Example:

### Study Sheet

- DSA Practice
- Read for 30 minutes
- Revise today's topics
- Solve 5 problems

### Fitness Sheet

- Gym
- 10,000 steps
- Drink sufficient water
- Stretching

These are starting templates and can be customized by the user.

### 4.2 Custom Habits

The user can create their own habit.

Possible fields:

- Habit name
- Description
- Frequency
- Selected days
- Start date
- Reminder time
- Optional target

Example:

```text
Habit: DSA Practice
Frequency: Monday–Saturday
Reminder: 8:00 PM
Target: 1 problem/day
```

> **MVP rule:** the start date must be today or later (in the user's local timezone). Back-dating is not supported, so tracking history only begins from the day a habit is created — this avoids fabricating `MISSED` records for days the user never had the habit.

---

# 5. Habit Scheduling and Notifications

Each habit should have its own schedule.

The application should support:

- Specific days
- Daily habits
- Selected weekdays
- Start date
- Reminder time
- Future notification support

Example:

```text
Gym
Monday / Wednesday / Friday
6:00 AM
```

The notification system should remind the user when a scheduled habit is due.

Future versions can add:

- Missed habit reminders
- Streak warnings
- Daily summaries
- Challenge notifications
- Social activity notifications

---

# 6. Individual Habit Tracking

This is the **core functionality of the application**.

The user should be able to open the application and immediately see their habits for the current day.

Example:

```text
Today's Habits

✓ DSA Practice
○ Gym
○ Reading
✓ Water

Today's Progress
████████░░ 80%
```

The system must record the status of each scheduled habit occurrence.

Possible states:

```text
PENDING
COMPLETED
SKIPPED
MISSED
```

The exact status model can be finalized during the database and system-design phase.

---

# 7. Core Tracking Logic

The most important technical requirement is:

> **Daily tracking must remain accurate and consistent.**

The application must not rely only on a current counter such as:

```text
currentStreak = 7
```

Instead, the underlying daily completion history should be preserved.

A conceptual model is:

```text
Habit
   ↓
Schedule
   ↓
Daily Occurrence
   ↓
Completion Status
```

Example:

```text
Habit: DSA Practice

21 Sep → COMPLETED
22 Sep → COMPLETED
23 Sep → MISSED
24 Sep → COMPLETED
```

This historical record should support:

- Calendar history
- Streak calculation
- Completion percentage
- Weekly statistics
- Monthly statistics
- Challenge scoring
- Future analytics

### Timezone Rule

Each user has a stored timezone (captured at signup, editable in settings). A "day" for occurrence generation and streak calculation is midnight-to-midnight in **the user's own local timezone**, not server/UTC time. All timestamps are stored in UTC and converted at read/write time using the stored offset — this keeps a habit marked "done" at 11:50 PM local from bleeding into the wrong day if the server is in a different zone. Travel across timezones mid-streak is an edge case deferred to post-MVP (documented, not solved, here).

### Important Rule

**Past tracking records should not unexpectedly change when a user modifies their future habit schedule.**

For example:

If a user changes:

```text
Monday / Wednesday / Friday
```

to:

```text
Monday / Tuesday / Thursday
```

their previous completion history should remain intact.

Schedule changes apply **from the next day onward** (MVP: no same-day schedule edits).

---

# 8. Streak System

The application should support:

- Current streak
- Longest streak
- Total completed occurrences
- Completion percentage
- Weekly consistency
- Monthly consistency

Streaks should be derived from actual completion history rather than being treated as the only source of truth.

Example:

```text
Monday     ✓
Tuesday    ✓
Wednesday  ✓
Thursday   ✗
Friday     ✓
```

The current streak after Friday should be:

```text
1 day
```

not 4 days.

The exact streak rules will be formally defined during the system-design and testing phases.

---

# 9. Calendar Tracking

The application should provide proper calendar-based tracking.

### Monthly View

Users should be able to see their overall consistency throughout the month.

### Weekly View

Users can see their habits and completion status across a week.

### Daily View

Selecting a specific date should show the habits scheduled for that date and their recorded status.

Example:

```text
24 September

✓ DSA Practice
✓ Gym
✗ Reading
✓ Water

Daily Completion: 75%
```

The calendar should be based on the same underlying tracking records used by the habit system.

There should not be separate tracking logic for the calendar.

---

# 10. Peer Tracking and Challenges

A major feature of the application is social accountability.

### 10.1 MVP Model — Single Shared Habit per Challenge

For the first version, a challenge defines **one canonical habit** that every member tracks identically. This keeps scoring simple and fair — everyone is completing the exact same thing, so a percentage-based leaderboard is directly comparable.

One user creates a challenge room by defining the shared habit and duration.

Example:

```text
Challenge:
30 Day DSA Grind

Shared Habit:
Solve 1 DSA problem/day

Duration:
30 Days

Members:
10
```

The creator receives a room/challenge code.

Other users join using that code and get the shared habit automatically added to their own habit list for the challenge duration. Their daily completion of that shared habit is what feeds the challenge leaderboard.

Example:

```text
Challenge Code:
X7K92P
```

### 10.2 Future Option — Custom Habit Matching

Not part of the MVP. Later, a challenge creator could allow members to track a *personal* habit that maps to the challenge's theme instead of the exact shared habit (e.g. one member does "Gym," another does "Yoga," both count toward a "Fitness Challenge"). This needs an explicit, transparent scoring rule (e.g. "any 1 completion/day counts") decided at challenge-creation time, since it complicates fairness. Deferred until the single-shared-habit model is proven.

---

# 11. Peer Leaderboard

The challenge can include a leaderboard to encourage consistency and friendly competition.

Example:

```text
30 Day DSA Grind

Ezio       87%
Rahul      81%
Aman       73%
```

Since every member tracks the same shared habit (§10.1), the leaderboard formula for the MVP is:

```text
Completion % = (Days completed) / (Days elapsed since joining) × 100
```

Ranked descending by Completion %, tie-broken by longest current streak, then by earliest join time.

This is exploit-resistant by construction — there's no separate "streak score" to game, and no cross-habit weighting to argue about, because everyone is doing the identical occurrence. Alternate metrics (raw completions, consistency scores) are deferred to post-MVP once custom habit matching (§10.2) is introduced and cross-habit normalization actually becomes necessary.

---

# 12. Motivation and Social Features

The peer system can later support lightweight social interactions.

Examples:

- Challenge progress
- Completion notifications
- Encouragement messages
- Reactions
- Milestones
- Streak achievements

The initial MVP should avoid unnecessary social complexity.

The main purpose is:

> **Accountability + consistency + healthy competition.**

---

# 13. Proposed Mobile Application Direction

The application should be developed as a proper mobile application rather than only as a traditional web platform.

### Proposed Frontend

**React Native + Expo**

Reasons:

- Android and iOS support from one codebase
- Good fit for mobile-first development
- Notification support
- Suitable for an MVP
- React ecosystem knowledge can be reused

### Proposed Backend

**FastAPI** (with SQLAlchemy 2.0 async + asyncpg + Alembic for database access and migrations)

Reasons:

- Python-based
- Strong API development capabilities
- Good fit for future data/ML functionality
- Clean separation between mobile application and backend

### Proposed Database

**PostgreSQL**

PostgreSQL is proposed because the application contains strongly related entities such as:

```text
Users
  ↓
Habits
  ↓
Schedules
  ↓
Daily Records
  ↓
Challenges
  ↓
Challenge Members
  ↓
Challenge Records
```

A relational database can provide useful constraints and transaction support for maintaining tracking consistency.

### Proposed Notifications

Initially:

**Expo Notifications**

Future implementation can use platform-specific notification infrastructure such as FCM/APNs where appropriate.

---

# 14. High-Level Architecture

```text
                 MOBILE APPLICATION
                  React Native / Expo
                         │
                         ▼
                     REST API
                      FastAPI
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
         PostgreSQL    Authentication  Notifications
             │
             ▼
      Habit Tracking Engine
             │
        ┌────┴─────┐
        ▼          ▼
     Streaks    Challenges
                   │
                   ▼
               Leaderboard
```

This is only a proposed high-level direction. Detailed architecture will be created during the SDLC/system-design phase.

---

# 15. Offline-First Consideration

Because this is a mobile habit application, offline tracking should be considered early.

A user may want to mark a habit as complete when they have poor or no internet connectivity.

Ideally:

```text
User marks habit complete
          ↓
Local application state
          ↓
User continues using app
          ↓
Internet becomes available
          ↓
Sync with backend
          ↓
Server confirms record
```

This should prevent the application from becoming unusable simply because the network is temporarily unavailable.

Offline synchronization and conflict handling can be designed in detail later.

---

# 16. Proposed MVP Screens

The initial MVP can start with a limited number of screens.

### 1. Splash / Onboarding

Introduces the application.

### 2. Login / Register

Authentication.

### 3. Profile Setup

- Basic information
- Goal
- Profile bio

### 4. Habit Setup

- Preloaded habit sheets
- Custom habit creation

### 5. Home / Today

Main daily tracking screen.

### 6. Calendar

- Daily
- Weekly
- Monthly tracking

### 7. Challenges

- Create challenge
- Join challenge
- View challenge progress
- Leaderboard

### 8. Profile / Statistics

- Goal
- Current streak
- Longest streak
- Completion rate
- Total completions
- Habit statistics

---

# 17. Recommended Development Priority

The application should be developed in a logical order.

```text
Phase 1
Authentication + Profile
        ↓
Phase 2
Habit Creation + Scheduling
        ↓
Phase 3
Daily Occurrence + Completion Tracking
        ↓
Phase 4
Calendar + History
        ↓
Phase 5
Streak Engine + Statistics
        ↓
Phase 6
Notifications
        ↓
Phase 7
Challenges + Rooms
        ↓
Phase 8
Leaderboards
        ↓
Phase 9
Offline Sync + Conflict Handling
        ↓
Phase 10
UI Polish + Gamification
```

The order may change during detailed planning.

---

# 18. Core Product Principle

The application should follow one primary principle:

> **Tracking accuracy comes before gamification.**

The application must first reliably answer:

- What habits were scheduled?
- What was completed?
- What was missed?
- What happened on a particular date?
- What is the user's current streak?
- What is their historical completion rate?

Only after this foundation is reliable should features such as leaderboards, achievements, social interactions, animations, and gamification be built on top of it.

---

# 19. Critical Reliability Scenario

Before considering the core MVP tracking system complete, the following flow should work correctly:

```text
Create Habit
      ↓
Set Schedule
      ↓
Habit appears on Today
      ↓
Mark Completed
      ↓
Close Application
      ↓
Reopen Application
      ↓
Correct status is displayed
      ↓
Next day is generated correctly
      ↓
Streak is calculated correctly
      ↓
Calendar shows correct historical record
```

This scenario should eventually become one of the application's most important integration tests.

---

# 20. Initial MVP Scope

### Included

- User authentication
- User profile
- Goal/profile bio
- Preloaded habit sheets
- Custom habits
- Habit schedules
- Daily habit tracking
- Notifications/reminders
- Calendar
- Streaks
- Individual statistics
- Peer challenge rooms
- Join/create challenge
- Challenge leaderboard

### Not a priority for the first version

- Complex AI features
- Advanced social networking
- Public user discovery
- Complex reward economy
- Excessive gamification
- Advanced recommendation systems
- Large-scale analytics

These can be considered after the core habit-tracking system is stable.

---

# 21. Future Possibilities

The architecture should leave room for future additions such as:

- AI-based habit recommendations
- Personalized habit plans
- Habit difficulty adjustment
- Productivity insights
- Behavioral analytics
- Smart reminder timing
- AI coaching
- Achievement systems
- Advanced challenge types
- Friend/follower systems
- Cross-device synchronization
- Web dashboard
- Advanced analytics

These are **future possibilities**, not part of the initial MVP requirement.

---

# 22. Conclusion

The proposed application is a **mobile-first habit tracking and peer accountability platform**.

Its core consists of:

```text
Personal Goals
      +
Habit Management
      +
Reliable Daily Tracking
      +
Calendar History
      +
Streaks
      +
Peer Challenges
      +
Leaderboards
```

The most important engineering requirement is the reliability of the underlying daily tracking system. All higher-level features — streaks, calendars, statistics, challenges, and leaderboards — should depend on a consistent source of truth for habit occurrences and completion records.

This document represents the **initial product proposal and technical direction only**.

The next stage will be to take this idea through the complete **Software Development Life Cycle (SDLC)**, including detailed requirements, functional/non-functional requirements, use cases, system architecture, database schema, API design, UI/UX planning, implementation strategy, testing, deployment, and maintenance.

