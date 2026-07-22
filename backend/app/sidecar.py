from __future__ import annotations

import asyncio
import ipaddress
import os
import sys

import uvicorn


def _loopback_host() -> str:
    host = os.getenv("CHASSIS_BACKEND_HOST", "127.0.0.1").strip()
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError
    except ValueError as exc:
        raise RuntimeError("packaged sidecar may bind only to a numeric loopback address") from exc
    return host


async def serve() -> None:
    # Import after the launcher has populated all resource/data environment paths.
    from app.main import app
    from app.sidecar_runtime import bind_server, clear_server

    port = int(os.getenv("CHASSIS_BACKEND_PORT", "0"))
    if not 1 <= port <= 65535:
        raise RuntimeError("CHASSIS_BACKEND_PORT must be an allocated port between 1 and 65535")
    config = uvicorn.Config(
        app,
        host=_loopback_host(),
        port=port,
        access_log=False,
        log_level=os.getenv("CHASSIS_LOG_LEVEL", "info").lower(),
        server_header=False,
        date_header=False,
    )
    server = uvicorn.Server(config)
    bind_server(server)
    try:
        await server.serve()
    finally:
        clear_server()


def main() -> None:
    if "--self-test" in sys.argv:
        import cantools  # noqa: F401
        import docx  # noqa: F401
        import fitz  # noqa: F401
        import reportlab  # noqa: F401

        print("sidecar-self-test:ok")
        return
    asyncio.run(serve())


if __name__ == "__main__":
    main()
