from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.configuration.models import ProductionConfiguration, SignedConfigurationPackage, sign_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign a validated chassis production configuration")
    parser.add_argument("input", type=Path, help="ProductionConfiguration JSON file")
    parser.add_argument("output", type=Path, help="Destination signed package JSON file")
    parser.add_argument("--issuer", required=True, help="Named administrator or provisioning process")
    args = parser.parse_args()

    key = os.getenv("CHASSIS_CONFIG_SIGNING_KEY", "")
    if len(key) < 32:
        raise SystemExit("CHASSIS_CONFIG_SIGNING_KEY must be injected locally and contain at least 32 characters")
    configuration = ProductionConfiguration.model_validate_json(args.input.read_text(encoding="utf-8"))
    unsigned = SignedConfigurationPackage(
        package_id=uuid4(),
        issued_at=datetime.now(timezone.utc),
        issuer=args.issuer,
        configuration=configuration,
        signature="0" * 64,
    )
    package = unsigned.model_copy(update={"signature": sign_package(unsigned, key)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(package.model_dump_json(indent=2), encoding="utf-8")
    print(f"signed package written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
