#!/usr/bin/env bash
set -e
python scripts/prepare_dev_config.py
python scripts/dev_backend.py &
python scripts/dev_simulator.py --profile normal_pass &
wait
