import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.persistence import resolve_database_path


def main() -> int:
    path = resolve_database_path(os.getenv("FLOWMATE_DB_PATH", "data/flowmate_demo.db"))
    if "demo" not in path.name:
        print(f"Refusing to reset non-demo database: {path}")
        return 2
    if path.exists():
        path.unlink()
        print(f"Removed {path}")
    else:
        print(f"No demo database found at {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
