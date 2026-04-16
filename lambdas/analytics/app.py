import json
from typing import Any

from supsim.query_service import QueryBuilder


def _json_response(status_code: int, body: Any) -> dict:

    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def stock_summary(event: dict, context: object) -> dict:

    customer_id = event["pathParameters"]["customer_id"]
    query = QueryBuilder(customer_id).build_stock_summary_query()
    rows = query.execute()

    return _json_response(200, rows)


def customer_summary(event: dict, context: object) -> dict:

    customer_id = event["pathParameters"]["customer_id"]
    query = QueryBuilder(customer_id).build_customer_summary_query()
    rows = query.execute()

    return _json_response(200, rows)


def movement_metrics(event: dict, context: object) -> dict:

    customer_id = event["pathParameters"]["customer_id"]
    stock_code = event["pathParameters"]["stock_code"]
    query = QueryBuilder(customer_id).build_movement_metrics_query(stock_code)
    rows = query.execute()
    
    return _json_response(200, rows)
