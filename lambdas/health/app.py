import json
import os
from datetime import datetime, timezone


def lambda_handler(event: dict, context: object) -> dict:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": os.environ.get("ENVIRONMENT", "unknown"),
        }),
    }
