# KIS - Events Django App (Advanced)

This app provides a comprehensive and extensible events system designed to integrate with your existing `account` and `content` apps.

Quick start:
1. Add `events` to INSTALLED_APPS.
2. Ensure `rest_framework` and `django_celery_results` (if using Celery) are configured.
3. Include `events.urls` in your project's urls: `path("api/", include("events.urls"))`.
4. Run `python manage.py makemigrations events` and `python manage.py migrate`.

Notes & advanced extensions:
- Services and tasks are intentionally lightweight placeholders — integrate your payment provider, blockchain provider, and ML pipelines in `services.py` and `tasks.py`.
- Security: verify webhooks using `utils.sign_payload` and add additional checks for check-in devices.
- Seat allocation: build allocation algorithms using `Seat`, `SeatMap` and `Ticket` relationships.
- Hybrid streaming: integrate with a media service and record `HybridStream.playback_url`.

