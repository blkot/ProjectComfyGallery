.PHONY: audit backup bootstrap check dev dev-admin dev-bootstrap dev-check \
	dev-infra dev-infra-down dev-logs dev-migrate dev-ready dev-status down \
	image-audit logs migrate milestone nas-deploy nas-registry-login production test

DEV_ENV ?= .env.development
DEV_COMPOSE = docker compose --env-file $(DEV_ENV) -f compose.development.yaml

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

dev: dev-ready
	./deploy/development/start.sh

dev-bootstrap:
	./deploy/development/bootstrap.sh

dev-infra: dev-bootstrap
	$(DEV_COMPOSE) up -d --wait

dev-migrate:
	./deploy/development/with-env.sh \
		uv run --package comfy-gallery-core \
		alembic -c packages/py/core/alembic.ini upgrade head

dev-admin:
	./deploy/development/with-env.sh \
		uv run --package comfy-gallery-core \
		python -m comfy_gallery_core.cli create-admin --if-missing

dev-ready: dev-infra dev-migrate dev-admin
	@echo "Local infrastructure is ready. Run 'make dev' to start the application."

dev-status:
	$(DEV_COMPOSE) ps

dev-logs:
	$(DEV_COMPOSE) logs -f

dev-infra-down:
	$(DEV_COMPOSE) down

dev-check:
	$(MAKE) check

milestone:
	./deploy/operations/create-milestone.sh $(RELEASE_VERSION)

nas-registry-login:
	./deploy/operations/login-ghcr-xanta.sh

nas-deploy:
	@test -n "$(RELEASE_VERSION)" || \
		(echo "Usage: make nas-deploy RELEASE_VERSION=x.y.z" >&2; exit 1)
	./deploy/operations/deploy-xanta-release.sh $(RELEASE_VERSION)

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
