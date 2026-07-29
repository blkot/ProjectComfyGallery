from __future__ import annotations

import json
from pathlib import Path

from comfy_gallery_api.main import app


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    destination = repository_root / "doc" / "interfaces" / "openapi.json"
    destination.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
