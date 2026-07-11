from pathlib import Path
for path in ["data", "data/reports", "data/logs"]:
    Path(path).mkdir(parents=True, exist_ok=True)
print("development data directories ready")
