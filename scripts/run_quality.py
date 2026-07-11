from __future__ import annotations

"""Run isolated backend and simulator quality suites from the project root."""

import argparse
import json
import os
from pathlib import Path
import random
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]


def find_udp_port_base() -> int:
    for _ in range(100):
        base = random.randrange(20_000, 50_000)
        sockets: list[socket.socket] = []
        try:
            for offset in (0, 1, 100, 101):
                item = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                item.bind(("127.0.0.1", base + offset))
                sockets.append(item)
            return base
        except OSError:
            continue
        finally:
            for item in sockets:
                item.close()
    raise RuntimeError("could not reserve an isolated UDP port range")


def python_executable() -> Path:
    candidate = ROOT / "backend" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return candidate if candidate.exists() else Path(sys.executable)


def run(command: Sequence[str], env: dict[str, str]) -> int:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("backend", "simulator", "all"), default="all")
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument("--keep-artifacts", action="store_true")
    parser.add_argument("--artifact-dir", type=Path, help="persist coverage and manifest in this directory")
    args = parser.parse_args()

    artifact_root = args.artifact_dir.resolve() if args.artifact_dir else Path(tempfile.mkdtemp(prefix="chassis-eol-quality-"))
    artifact_root.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        {
            "CHASSIS_RUNTIME_PROFILE": "test",
            "CHASSIS_DATA_DIR": str(artifact_root / "data"),
            "CHASSIS_TEST_ROOT": str(artifact_root),
            "CHASSIS_TEST_PORT_BASE": str(find_udp_port_base()),
            "PYTHONPATH": os.pathsep.join((str(ROOT / "backend"), str(ROOT / "simulator"), environment.get("PYTHONPATH", ""))),
        }
    )
    python = str(python_executable())
    results: dict[str, int] = {}
    try:
        if args.suite in {"backend", "all"}:
            command = [python, "-m", "pytest", "backend/tests", "-q"]
            if args.coverage:
                command.extend(
                    [
                        "--cov=app",
                        "--cov-report=term-missing",
                        f"--cov-report=json:{artifact_root / 'backend-coverage.json'}",
                        "--cov-fail-under=60",
                    ]
                )
            results["backend"] = run(command, environment)
        if args.suite in {"simulator", "all"}:
            command = [python, "-m", "pytest", "simulator/tests", "-q"]
            if args.coverage:
                command.extend(
                    [
                        "--cov=can_frame_simulator",
                        "--cov-report=term-missing",
                        f"--cov-report=json:{artifact_root / 'simulator-coverage.json'}",
                        "--cov-fail-under=40",
                    ]
                )
            results["simulator"] = run(command, environment)
        manifest = {
            "profile": "test",
            "data_dir": str(artifact_root / "data"),
            "udp_port_base": environment["CHASSIS_TEST_PORT_BASE"],
            "results": results,
        }
        (artifact_root / "quality-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, indent=2), flush=True)
        return 0 if all(code == 0 for code in results.values()) else 1
    finally:
        if not args.keep_artifacts and not args.artifact_dir:
            shutil.rmtree(artifact_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
