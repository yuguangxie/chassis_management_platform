import atexit
import os
import random
import secrets
import shutil
import socket
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PROJECT))

import pytest


def _find_udp_port_base() -> int:
    for _ in range(100):
        base = random.randrange(20_000, 50_000)
        sockets: list[socket.socket] = []
        try:
            for offset in (0, 1, 100, 101):
                candidate = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                candidate.bind(("127.0.0.1", base + offset))
                sockets.append(candidate)
            return base
        except OSError:
            pass
        finally:
            for candidate in sockets:
                candidate.close()
    raise RuntimeError("unable to allocate an isolated UDP port range for backend tests")


_owns_test_root = "CHASSIS_TEST_ROOT" not in os.environ
TEST_ROOT = Path(os.environ.setdefault("CHASSIS_TEST_ROOT", tempfile.mkdtemp(prefix="chassis-eol-tests-")))
os.environ.setdefault("CHASSIS_RUNTIME_PROFILE", "test")
os.environ.setdefault("CHASSIS_DATA_DIR", str(TEST_ROOT / "data"))
os.environ.setdefault("CHASSIS_TEST_PORT_BASE", str(_find_udp_port_base()))
os.environ.setdefault("CHASSIS_CONFIG_SIGNING_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("CHASSIS_ACTIVE_CONFIG_PATH", str(TEST_ROOT / "data" / "config" / "active-package.json"))
if _owns_test_root:
    atexit.register(lambda: shutil.rmtree(TEST_ROOT, ignore_errors=True))

from app.security.auth import Role
from app.services.app_state import state

state.auth.install_token("test-viewer-token", "test-viewer", Role.VIEWER)
state.auth.install_token("test-operator-token", "test-operator", Role.OPERATOR)
state.auth.install_token("test-engineer-token", "test-engineer", Role.ENGINEER)
state.auth.install_token("test-admin-token", "test-admin", Role.ADMIN)


@pytest.fixture
def auth_headers():
    def make(role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer test-{role}-token"}

    return make
