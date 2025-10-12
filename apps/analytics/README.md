## Integration notes & extension points

1. **Streaming & scalability**: replace EventStream DB ingestion with Kafka or AWS Kinesis for high throughput. Use materialized views for dashboard widgets.
2. **Predictive models**: build a microservice (FastAPI) wrapping scikit-learn / Prophet / Torch models and call via Celery.
3. **Multi-tenant**: ensure row-level isolation by scoping queries via `org_id`/`partner_id` or use separate schemas per tenant.
4. **Settings & feature flags**: consider launching a sidecar service for feature evaluation (low-latency), cache flags in Redis, and add SDKs for client-side evaluation.
5. **Security**: encrypt sensitive setting values, restrict dashboard sharing, and provide audit logs for setting changes.
6. **Dashboards**: store widget queries as SQL or JSON DSL and render client-side. Use precomputed aggregates for heavy widgets.

---

## How to wire the app quickly

1. Copy the files into `analytics/`.
2. Add `'analytics.apps.AnalyticsConfig'` to `INSTALLED_APPS`.
3. Run `python manage.py makemigrations analytics` and `migrate`.
4. Start the server and visit `/api/schema/` and the Swagger UI to explore the API.
5. Hook Celery to run async tasks.