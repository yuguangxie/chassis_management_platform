python scripts/prepare_dev_config.py
Start-Process python -ArgumentList 'scripts/dev_backend.py'
Start-Process python -ArgumentList 'scripts/dev_simulator.py --profile normal_pass'
