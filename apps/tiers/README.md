## Integration notes

1. Use a billing provider (Stripe/Braintree) in production; keep webhooks for subscription lifecycle and reconcile via `reconcile_subscription`.
2. Cache entitlement/plan feature lookups in Redis for low-latency enforcement.
3. Enforce usage quota checks in middleware or a service layer before allowing actions (e.g., decrement usage quotas atomically).
4. Consider separate read models or materialized views for high-traffic quota/usage counters.
5. Encrypt sensitive billing identifiers and never store raw card data.

---

If you'd like, I can:
- Add example OpenAPI/Swagger security schemes (Stripe webhook secrets, OAuth2) into schema.
- Provide Docker Compose + Stripe emulator + Celery config.
- Implement atomic quota check helpers and middleware.
