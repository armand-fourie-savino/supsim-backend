# API Conventions

The below document clarifies requirements for infrastructure and code for creating APIs.

- One HttpApi to be used by all lambda create in @stacks/api_stack.py
- One lambda per service (analytics, organisations)
- Keep lambda handlers clean:
    - received request and gather context
    - hand off to service (in lambda layer)
    - return response
- Use /python-patterns for skill for python code formatting and standards

## Routing

All routes except for system health checks should contain a customer ID in the route:

Example:
```python
    "{BASE_URL}/{customer_id}/movement_metrics"
```

## Endpoints

| Route | Methods | Lambda Handler |
| --- | --- | --- |
| `{customer_id}/stock_summary` | `GET` | `analytics.app.stock_summary` |
| `{customer_id}/customer_summary` | `GET` | `analytics.app.customer_summary` |
| `{customer_id}/movement_metrics/{stock_code}` | `GET` | `analytics.app.movement_metrics` |
