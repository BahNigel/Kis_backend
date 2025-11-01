# KIS - Notifications Django App (Advanced)

This app provides a feature-rich in-app notification system with extensibility for multi-channel delivery tracking and advanced personalization. It is intentionally scoped to avoid external push provider code — you can integrate your custom push server later (Node.js or other).

Features included:
- Notification templates with basic token rendering
- In-app notification model with actions, snooze, expiry, deduplication
- Notification rules for per-user suppression, quiet hours, and channel preferences
- Delivery tracking per channel with retry/backoff (Celery tasks)
- Digest aggregation for batched emails or in-app digests
- Utilities for signing webhooks, quiet-hours checks, and basic rate-limiting

Quick start:
1. Add `notifications` to INSTALLED_APPS.
2. Ensure `rest_framework` and `celery` (if used) are configured.
3. Include `notifications.urls` into your project's URL conf: `path("api/", include("notifications.urls"))`.
4. Run `python manage.py makemigrations notifications` and `python manage.py migrate`.

Security & production notes:
- Replace the naive template renderer with Jinja2 or Django templates for safety.
- Integrate Email/SMS/Webhook providers in the `process_notification_delivery` task.
- Respect user locale and timezone when checking quiet hours.
- Store secrets (webhook signing key) in environment variables.
- Integrate ML-based personalization in `personalization_score` and suppression logic.

Extensions I can provide next:
- Full integration examples for Email & SMS providers (sendgrid/twilio) without Node.js.
- Frontend components (React) for in-app notification center and real-time updates (websockets).
- Rate-limiting & throttling rules per user & global with Redis-backed counters.
- A production-ready templating engine and sandbox for user-editable templates.