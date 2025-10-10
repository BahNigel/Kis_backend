# KIS — Django Project

This repository contains an industry-style Django project layout designed for clarity, testability, and deployability.

Below you will find an explanation of the folder structure, what each file and directory is for, and how to perform common development tasks (creating apps, migrations, running locally, using Docker, running tests, and deployment notes).

---

## Quick start (development)

1. Copy `.env.example` to `.env` and fill in required values (DATABASE_URL, SECRET_KEY, etc.).
2. Create a virtual environment and install dependencies (or use the provided Docker setup):

```bash
python -m venv .env
source .venv/bin/activate
pip install -r requirements/dev.txt   # or pip install -r requirements/base.txt
```

3. Run database migrations and start the development server:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

If using Docker (recommended for parity with production):

```bash
docker-compose up --build
```

---

## Repository layout

```
kis/
├─ manage.py
├─ config/                          # Django config & entrypoints
│  ├─ settings/
│  │  ├─ base.py
│  │  ├─ local.py
│  │  ├─ production.py
│  │  └─ __init__.py
│  ├─ urls.py
│  ├─ asgi.py
│  └─ wsgi.py
├─ apps/                            # Domain apps (create here)
│  └─ __init__.py
├─ common/                          # Shared helpers: pagination, permissions...
│  ├─ pagination.py
│  ├─ permissions.py
│  ├─ exceptions.py
│  ├─ middleware.py
│  └─ __init__.py
├─ docs/                            # API guides, OpenAPI, ADRs
│  └─ decisions/
├─ scripts/                         # Useful scripts (seed, manage wrappers)
├─ tests/                           # Integration/e2e tests
├─ requirements/                     # base/dev/prod requirements files
├─ .env.example
├─ Dockerfile
├─ docker-compose.yml
├─ pyproject.toml
└─ README.md
```

### Top-level files

* **manage.py** — Django CLI entrypoint. Use it to run `makemigrations`, `migrate`, `runserver`, `test`, `createsuperuser`, etc.

* **.env.example** — Example environment variables. Copy to `.env` (excluded from VCS) and provide real values locally/CI.

* **Dockerfile** — Image for production (or local parity). Designed to run your app with a WSGI/ASGI server (e.g. gunicorn, uvicorn).

* **docker-compose.yml** — Local development containers (web, db, cache, worker). Use to spin up an environment identical to production dependencies.

* **pyproject.toml** — Project metadata, development tooling configuration (black, isort, pre-commit, etc.) — keep dependencies and dev tooling declared here when applicable.

* **requirements/** — pin and separate installation constraints: `base.txt`, `dev.txt`, `prod.txt` or equivalent. Use pinned versions for deterministic installs in CI.

---

## `config/` — Django configuration and entrypoints

This directory centralizes Django settings and WSGI/ASGI entrypoints.

* **config/settings/base.py** — The canonical baseline settings. Contains settings that are environment-agnostic: `INSTALLED_APPS`, `MIDDLEWARE`, `TEMPLATES`, shared logging configuration, common defaults.

* **config/settings/local.py** — Local/developer overrides for debugging, local DB, console logging, etc. This gets used when working on your machine.

* **config/settings/production.py** — Production overrides (SECURE settings, different database, caching, Sentry integration, WhiteNoise/static handling, etc.).

* **config/urls.py** — Project URL router. Import app-level routers here or mount API routers for OpenAPI.

* **config/asgi.py** — ASGI entrypoint. If you use async features or channels, this is used by `uvicorn`/`daphne`.

* **config/wsgi.py** — WSGI entrypoint used by `gunicorn` for synchronous production deployments.

**Pattern note:** Use `DJANGO_SETTINGS_MODULE=config.settings.local` for local development and `config.settings.production` in production. Consider using a small `config/settings/__init__.py` that loads `base.py` and overlays the requested profile.

---

## `apps/` — Domain applications

Place all Django apps (business/domain logic) here. Keeping apps inside a top-level `apps` package avoids import collisions and makes the project structure clearer.

To create a new app:

```bash
cd kis
python manage.py startapp --template=/dev/null --name=__init__.py my_app apps/my_app
```

(Alternatively) simple flow:

```bash
python manage.py startapp my_app apps/my_app
# Move generated app into the apps/ package if Django created it at the top level
```

Then add the app to `config/settings/base.py` in `INSTALLED_APPS` (prefer full dotted path — e.g. `apps.my_app.apps.MyAppConfig`).

Recommended app structure inside `apps/<app>`:

```
apps/my_app/
├─ migrations/
├─ admin.py
├─ apps.py
├─ models.py
├─ views.py
├─ serializers.py   # if DRF
├─ urls.py
├─ services.py      # business logic
├─ tasks.py         # background tasks (celery/ff)
├─ tests/           # unit + small integration tests
└─ __init__.py
```

**Notes:**

* Use `apps.my_app.apps.MyAppConfig` to register app name and verbose name.
* Keep views thin — prefer services for complex logic so they can be tested in isolation.

---

## `common/` — Shared utilities

This package contains reusable bits used across apps:

* **pagination.py** — project-wide pagination policies (DRF paginators or helpers for cursor pagination).
* **permissions.py** — common permission classes and helpers.
* **exceptions.py** — app-level or API exception types and mapping to HTTP responses.
* **middleware.py** — custom middleware used across environments (request id, logging correlation, metrics).

Place other cross-cutting utilities (auth helpers, mixins, custom fields) here.

---

## `docs/` — Documentation and ADRs

Keep API guides, OpenAPI specs, architecture decision records (`docs/decisions/`), and any documented operational runbooks here.

---

## `scripts/` — Helpful scripts

Utility scripts such as database seeding, local DB setup, combined commands, or maintenance scripts. Keep scripts idempotent and well-documented.

Example:

```bash
# scripts/seed_db.sh
python manage.py loaddata fixtures/initial_data.json
```

---

## `tests/` — Integration / E2E tests

Project-level tests that exercise the whole stack (database, HTTP endpoints). Unit tests ideally live within each app in `apps/<app>/tests/` while broader tests go into this `tests/` directory.

Run tests with:

```bash
pytest -q
# or
python manage.py test
```

---

## Common developer tasks

### Creating a new app

1. Create the app in the `apps/` package:

```bash
python manage.py startapp my_app apps/my_app
```

2. Add `apps.my_app.apps.MyAppConfig` to `INSTALLED_APPS` in `config/settings/base.py`.
3. Create basic `urls.py` under `apps/my_app/` and include it in `config/urls.py`.
4. Add migrations (if you added models):

```bash
python manage.py makemigrations my_app
python manage.py migrate
```

### Making & applying migrations

* Create migrations for all changed apps:

```bash
python manage.py makemigrations        # inspects all apps and creates migrations for modified models
```

* Apply migrations to the configured database:

```bash
python manage.py migrate
```

* Create a named migration (helpful for manual control):

```bash
python manage.py makemigrations --name add_foo_field my_app
```

* Show migration status:

```bash
python manage.py showmigrations
```

### Running the dev server

```bash
python manage.py runserver 0.0.0.0:8000
```

When using Docker:

```bash
docker-compose up --build
# or for just the web service
docker-compose up --build web
```

### Creating a superuser

```bash
python manage.py createsuperuser
```

### Collecting static files (for production)

```bash
python manage.py collectstatic --noinput
```

---

## Docker & deployment notes

* The `Dockerfile` should build a minimal image with pinned dependencies, copy the code, collect static files (or defer to build step), and run the app with `gunicorn` (sync) or `uvicorn` (async). Keep secrets out of images and use environment variables instead.

* `docker-compose.yml` provides a local composition for services such as Postgres, Redis, Celery worker, and your web container. Use it for local integration tests and development parity.

* Use environment-specific settings modules (`local` vs `production`) and make `DJANGO_SETTINGS_MODULE` configurable via environment variable.

* Configure healthchecks, readiness/liveness endpoints, and proper logging to stdout/stderr so container orchestrators can capture logs.

---

## Testing & CI

* Use `pytest` with `pytest-django` for comfortable testing. Keep unit tests fast and focused; integration tests can run in CI using a Postgres service container.

* Run linters (flake8/ruff), formatters (black/isort), and type checks (mypy) in CI. Consider gating merges on passing tests and quality checks.

---

## Logging, monitoring & error reporting

* Centralize logging configuration in `config/settings/base.py`. Send structured logs (JSON) to stdout so logging collectors can parse them.

* Integrate Sentry (or similar) in `production.py` for error aggregation.

* Add request identifiers and correlation IDs in `common/middleware.py` to help trace requests across services.

---

## Security & secret management

* Never commit `.env` or production settings. Use a secrets manager in production (Vault, AWS Secrets Manager, etc.).

* Enable Django security settings in `production.py` (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`).

---

## Helpful tips & best practices

* Keep apps small and focused. Prefer multiple smaller apps over a single monolithic app with unrelated models.
* Keep views thin and push business logic into `services.py` or domain services.
* Version and pin third-party dependencies in production.
* Use feature flags for risky deploys and gradual rollouts.

---

## Where to add project-specific documentation

* API samples, OpenAPI schema and usage examples go in `docs/`.
* Architecture decisions and rationale belong in `docs/decisions/` as ADRs.

---

If you want, I can generate a `CONTRIBUTING.md`, `Makefile` for common dev tasks, or an opinionated `Dockerfile` / `docker-compose.yml` tuned for this layout.
