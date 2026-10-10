"""Regenerate the curated agency reference from the cached CEMS ZIP.

Run ``uv run --locked --group processing python scripts/prepare_ahr_flood_extent.py``.
The original ZIP is retrieved by ``floodbeacon.sources.ingest_case`` and remains
ignored under data/raw/ahr-2021. This command performs no network or DB writes.
"""

import json
from pathlib import Path

from floodbeacon.regional_flood import prepare_flood_extent


if __name__ == "__main__":
    print(json.dumps(prepare_flood_extent(
        Path("data"), Path("src/floodbeacon/static/imagery/ahr-region")
    ), indent=2))
