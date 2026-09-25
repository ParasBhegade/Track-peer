.PHONY: up down restart logs psql redis test lint typecheck migrate rollback dev

# ========================
# Infrastructure
# ========================
up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

psql:
	docker compose exec postgres psql -U habittracker -d habittracker

redis:
	docker compose exec redis redis-cli

# ========================
# Backend development
# ========================
dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ========================
# Database migrations
# ========================
migrate:
	cd backend && alembic upgrade head

rollback:
	cd backend && alembic downgrade -1

migrate-reset:
	cd backend && alembic downgrade base

migrate-generate:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# ========================
# Quality
# ========================
lint:
	cd backend && python -m ruff check .

lint-fix:
	cd backend && python -m ruff check . --fix

typecheck:
	cd backend && python -m mypy .

# ========================
# Tests
# ========================
test:
	cd backend && python -m pytest -v

test-cov:
	cd backend && python -m pytest --cov=app --cov-report=term-missing
