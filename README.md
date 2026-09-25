# Habit Tracker

A mobile-first habit tracking and peer accountability platform.

**Stack:** React Native (Expo) · FastAPI · PostgreSQL · Redis

---

## Quickstart

### 1. Start infrastructure

```bash
cp .env.example .env
docker compose up -d
```

This starts:

| Service    | Port  | Purpose              |
|------------|-------|----------------------|
| PostgreSQL | 5432  | Primary database     |
| Redis      | 6379  | Cache / job broker   |
| Mailpit    | 8025  | Dev email UI         |
| Mailpit    | 1025  | Dev SMTP             |

### 2. Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -e ".[dev]"

cp .env.example .env
alembic upgrade head

uvicorn app.main:app --reload
```

### 3. Verify

```
GET http://localhost:8000/api/v1/health
```

### 4. Run tests

```bash
cd backend
pytest -v
```

### 5. Lint & type check

```bash
cd backend
ruff check .
mypy .
```

---

## Repository Layout

```
habit-tracker/
├── .github/workflows/ci.yml    # CI: lint + typecheck + tests
├── docker-compose.yml           # PostgreSQL, Redis, Mailpit
├── Makefile                     # Common dev commands
├── docs/
│   ├── phase-0-proposal.md
│   ├── phase-1-requirements.md
│   ├── phase-2-system-design.md
│   ├── phase-3-api-contract.md
│   ├── openapi.json
│   └── design/brief.md
├── backend/
│   ├── app/                     # FastAPI application
│   │   ├── main.py
│   │   ├── core/                # Config, security, errors, deps
│   │   ├── db/                  # Engine, session, base model
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic request/response
│   │   ├── services/            # Business logic
│   │   └── api/v1/              # Route handlers
│   ├── alembic/                 # Migrations
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
└── mobile/                      # Expo app (future)
```

---

## Documentation

- [Phase 0 — Proposal](docs/phase-0-proposal.md)
- [Phase 1 — Requirements](docs/phase-1-requirements.md)
- [Phase 2 — System Design](docs/phase-2-system-design.md)
- [Phase 3 — API Contract](docs/phase-3-api-contract.md)
- [Design Brief](docs/design/brief.md)
