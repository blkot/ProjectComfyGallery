.PHONY: audit backup bootstrap check dev down image-audit logs migrate production test

audit:
	uvx pip-audit --local
	pnpm audit --prod --audit-level high --registry=https://registry.npmjs.org

bootstrap:
	uv sync --all-packages
	pnpm install --frozen-lockfile=false

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest
	pnpm check
	pnpm test

dev:
	docker compose up --build

production:
	docker compose -f compose.yaml -f compose.production.yaml up -d --build

backup:
	docker compose -f compose.yaml -f compose.production.yaml run --rm --no-deps backup run

down:
	docker compose down

image-audit:
	sh deploy/operations/security-scan.sh

logs:
	docker compose logs -f

migrate:
	uv run --package comfy-gallery-core alembic -c packages/py/core/alembic.ini upgrade head

test:
	uv run pytest
	pnpm test
