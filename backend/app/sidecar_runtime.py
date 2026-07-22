from __future__ import annotations

import threading
from typing import Protocol


class _UvicornServer(Protocol):
    should_exit: bool


_lock = threading.Lock()
_server: _UvicornServer | None = None


def bind_server(server: _UvicornServer) -> None:
    """Register the embedded server without exposing it through the public API."""
    global _server
    with _lock:
        _server = server


def request_shutdown() -> bool:
    """Ask uvicorn to run FastAPI shutdown hooks and then leave its event loop."""
    with _lock:
        if _server is None:
            return False
        _server.should_exit = True
        return True


def clear_server() -> None:
    global _server
    with _lock:
        _server = None
