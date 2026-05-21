.PHONY: dev infra backend frontend stop clean

# ── Development ──────────────────────────────────────

dev: infra backend frontend  ## Start everything in development mode

infra:  ## Start Docker infrastructure (PostgreSQL, Redis, Qdrant)
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 3
	@docker compose ps

backend:  ## Start Python backend
	cd backend && poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
	@echo "Backend started on http://localhost:8000"

frontend:  ## Start Tauri desktop app in dev mode
	cd desktop && pnpm tauri dev

# ── Infrastructure ───────────────────────────────────

infra-up:  ## Start infrastructure only
	docker compose up -d

infra-down:  ## Stop infrastructure
	docker compose down

infra-reset:  ## Reset infrastructure (destroys all data)
	docker compose down -v
	docker compose up -d

# ── Database ─────────────────────────────────────────

db-migrate:  ## Run database migrations
	cd backend && poetry run alembic upgrade head

db-revision:  ## Create a new migration (usage: make db-revision msg="add users table")
	cd backend && poetry run alembic revision --autogenerate -m "$(msg)"

# ── Testing ──────────────────────────────────────────

test:  ## Run Python tests
	cd backend && poetry run pytest -v

lint:  ## Run linter
	cd backend && poetry run ruff check .

format:  ## Format Python code
	cd backend && poetry run ruff format .

# ── Cleanup ──────────────────────────────────────────

stop:  ## Stop all services
	-pkill -f "uvicorn app.main" 2>/dev/null || true
	docker compose down

clean: stop  ## Clean all build artifacts
	rm -rf desktop/src-tauri/target
	rm -rf desktop/node_modules
	rm -rf desktop/dist
	rm -rf media/*

# ── Help ─────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
