from __future__ import annotations

from typing import Any

from supsim.utils.response import success_response


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return success_response({"status": "ok"})
