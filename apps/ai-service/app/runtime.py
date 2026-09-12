from __future__ import annotations

import os


def should_enable_reload(env: dict[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    return values.get("UVICORN_RELOAD", "").strip() == "1"
