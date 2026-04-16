# Query Service

The query service will:
- Receive Input (`customer_id` and other query string parameters)
- Load query templates and format with inputs
- Run queries
- Return results as `dict`

## Service Structure

Code location - @layers/supsim/python/supsim/query_service

### Classes

| Class | Purpose | Methods |
| --- | --- |
| `Query` | represents a query string with database query execution context | `execute()` |
| `QueryBuilder` | take tenant and connection context and generates queries from templates, returns `Query` | `build_movement_metrics()`, `build_stock_summary_query()`, etc. |