"""
爬虫状态追踪 (最近一次执行的结果)
"""
from __future__ import annotations
from datetime import datetime
from threading import Lock

_state: dict = {
    "last_run": None,
    "results": {},
    "errors": [],
}
_lock = Lock()


def update(results: dict, errors: list[str] | None = None) -> None:
    with _lock:
        _state["last_run"] = datetime.utcnow().isoformat()
        _state["results"] = results
        _state["errors"] = errors or []


def get_status() -> dict:
    with _lock:
        return {
            "last_run": _state["last_run"],
            "results": _state["results"],
            "errors": list(_state["errors"]),
        }
