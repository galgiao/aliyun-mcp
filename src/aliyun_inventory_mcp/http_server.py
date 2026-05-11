from __future__ import annotations

import json
import os
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from aliyun_inventory_mcp.server import get_aliyun_inventory


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _json_error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "aliyun-inventory-http"})


async def inventory(request: Request) -> JSONResponse:
    try:
        payload: dict[str, Any] = await request.json()
    except json.JSONDecodeError:
        return _json_error("Invalid JSON request body.", 400)

    if not isinstance(payload, dict):
        return _json_error("Request body must be a JSON object.", 400)

    try:
        result = get_aliyun_inventory(**payload)
    except TypeError as exc:
        return _json_error(f"Invalid request parameter: {exc}", 400)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        return _json_error(str(exc), 500)

    return JSONResponse(result)


app = Starlette(
    debug=os.getenv("ALIYUN_HTTP_DEBUG", "").lower() in {"1", "true", "yes", "on"},
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/inventory", inventory, methods=["POST"]),
    ],
)


def main() -> None:
    uvicorn.run(
        "aliyun_inventory_mcp.http_server:app",
        host=os.getenv("ALIYUN_HTTP_HOST", "0.0.0.0"),
        port=_env_int("ALIYUN_HTTP_PORT", 8001),
        reload=os.getenv("ALIYUN_HTTP_RELOAD", "").lower() in {"1", "true", "yes", "on"},
    )


if __name__ == "__main__":
    main()
