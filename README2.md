# KIS — Accounts & Identity (Django)

This repository is a modular, production-minded Django service implementing an Accounts & Identity domain.

## Layout
- `config/` - Django settings (base/local/production), ASGI/WGSI, URLs
- `apps/` - application modules (accounts lives in `apps/accounts`)
- `common/` - shared helpers (pagination, permissions, middleware)
- `requirements/` - requirements bundles
- `Dockerfile`, `docker-compose.yml` - containers for local/deploy
- `.env.example` - environment variables

## Quickstart (local)
1. Create venv: `python -m venv .venv && source .venv/bin/activate`
2. Install: `pip install -r requirements/base.txt`
3. Copy env: `cp .env.example .env` and adjust values
4. Migrate: `python manage.py migrate`
5. Create superuser: `python manage.py createsuperuser`
6. Run: `python manage.py runserver`

## Notes & Next Steps
- Add the rest of UML models (AIAccess, FeatureFlag, GDPRRequest, etc.) by following patterns in `apps/accounts/models.py`.
- Integrate Celery tasks for background jobs (billing webhooks, export generation).
- Implement robust quota enforcement (use Redis counters for atomicity).
- Add OpenAPI docs via `drf-spectacular`. Visit `/api/schema/` and `/api/docs/`.
