import json
from pathlib import Path


def load_qgis2web_features(file_path):
    """Load features from a qgis2web JavaScript-wrapped GeoJSON file."""
    try:
        raw_content = Path(file_path).read_text(encoding="utf-8")

        json_start = raw_content.find("{")
        json_end = raw_content.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            return []

        data = json.loads(
            raw_content[json_start:json_end]
        )

        return data.get("features", [])

    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"Could not load QGIS data from {file_path}: {exc}"
        )
        return []