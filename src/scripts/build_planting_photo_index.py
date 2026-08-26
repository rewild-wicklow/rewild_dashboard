#!/usr/bin/env python3
"""
Build a JavaScript photo index for planting progress.

The script reads a qgis2web Plantings_*.js file, scans a planting-photo folder and a visit-photo folder, copies the images into the qgis-map/images folder, matches images to planting names, extracts dates and photo types, and writes a JS file beside the Plantings JS file.

Uses only the Python standard library.

Example:
    python build_planting_photo_index.py \
        "/path/to/Plantings_3.js" \
        "/path/to/planting-photos" \
        "/path/to/visit-photos"

Output:
    /path/to/qgis-map/data/planting_photo_index.js
    /path/to/qgis-map/images/planting-photos/...
    /path/to/qgis-map/images/visit-photos/...
"""

from __future__ import annotations

import argparse
import json
import shutil
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".heic"
}

# Add exceptional filename fragments here when automatic matching is not enough.
# The key is a normalized filename/site fragment; the value must exactly match
# a "Name" value in Plantings_*.js.
ALIASES: dict[str, str] = {
    # Example:
    # "rewildlargeexclosure": "An Óige Knockree - ReWild Large Exclosure",
}


@dataclass(frozen=True)
class Planting:
    name: str
    photo: str | None
    first_planted: str | None
    last_visited: str | None


def normalize(value: str) -> str:
    """Lowercase, remove accents, and keep only letters and numbers."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def load_qgis_js(path: Path) -> dict[str, Any]:
    """Read `var something = {...}` as JSON."""
    text = path.read_text(encoding="utf-8-sig")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Could not find a JSON object in {path}")
    return json.loads(text[start : end + 1])


def extract_plantings(data: dict[str, Any]) -> list[Planting]:
    results: list[Planting] = []
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        name = str(props.get("Name") or "").strip()
        if not name:
            continue
        photo = props.get("Photo")
        results.append(
            Planting(
                name=name,
                photo=str(photo).strip() if photo else None,
                first_planted=props.get("First Planted"),
                last_visited=props.get("last_visited"),
            )
        )
    return results


def iter_images(folder: Path) -> Iterable[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"Photo folder does not exist: {folder}")
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def infer_photo_type(filename: str, default_type: str) -> str:
    lower = filename.lower()
    prefix_map = {
        "maintenance": "maintenance",
        "observation": "observation",
        "visit": "visit",
        "monitoring": "monitoring",
        "growth": "growth",
        "planting": "planting",
        "plantings": "planting",
    }
    for prefix, photo_type in prefix_map.items():
        if re.match(rf"^{re.escape(prefix)}[-_ ]", lower):
            return photo_type
    return default_type


def extract_date(filename: str) -> str | None:
    """
    Recognize:
      260729172900       -> 2026-07-29
      20260613_101432    -> 2026-06-13
      2026-07-29         -> 2026-07-29
    """
    stem = Path(filename).stem

    patterns = [
        (r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)", "%Y%m%d"),
        (r"(?<!\d)(\d{2})([01]\d)([0-3]\d)(?:\d{6})?(?!\d)", "%y%m%d"),
    ]

    for pattern, fmt in patterns:
        for match in re.finditer(pattern, stem):
            compact = "".join(match.groups())
            try:
                return datetime.strptime(compact, fmt).date().isoformat()
            except ValueError:
                continue
    return None


def filename_name_fragment(filename: str) -> str:
    """Remove type prefixes, dates, camera prefixes, and separators."""
    stem = Path(filename).stem

    stem = re.sub(
        r"^(maintenance|observation|visit|monitoring|growth|plantings?|photo)[-_ ]+",
        "",
        stem,
        flags=re.IGNORECASE,
    )

    # Remove common camera-generated prefixes only when they occur at the start.
    stem = re.sub(r"^(IMG|JPEG|PXL|Screenshot)[-_ ]+", "", stem, flags=re.IGNORECASE)

    # Remove YYYYMMDD, YYMMDDHHMMSS, and related trailing timestamps.
    stem = re.sub(r"[-_ ]+20\d{6}(?:[-_ ]?\d{6,9})?$", "", stem)
    stem = re.sub(r"[-_ ]+\d{12,14}$", "", stem)
    stem = re.sub(r"[-_ ]+\d{6}$", "", stem)

    return stem.strip("-_ ")


def match_planting(
    image: Path,
    plantings: list[Planting],
    exact_photo_lookup: dict[str, Planting],
) -> tuple[Planting | None, str, float]:
    """
    Matching priority:
      1. Exact `Photo` basename from Plantings JS
      2. Manual ALIASES entry
      3. Exact normalized planting name
      4. One normalized name contains the other
      5. Fuzzy string comparison
    """
    basename_key = image.name.casefold()
    if basename_key in exact_photo_lookup:
        return exact_photo_lookup[basename_key], "photo_field", 1.0

    fragment = filename_name_fragment(image.name)
    fragment_norm = normalize(fragment)

    if not fragment_norm:
        return None, "unmatched", 0.0

    alias_target = ALIASES.get(fragment_norm)
    if alias_target:
        for planting in plantings:
            if planting.name == alias_target:
                return planting, "alias", 1.0

    normalized = [(planting, normalize(planting.name)) for planting in plantings]

    for planting, planting_norm in normalized:
        if fragment_norm == planting_norm:
            return planting, "exact_name", 1.0

    containment_matches: list[tuple[float, Planting]] = []
    for planting, planting_norm in normalized:
        shorter = min(len(fragment_norm), len(planting_norm))
        if shorter >= 8 and (
            fragment_norm in planting_norm or planting_norm in fragment_norm
        ):
            ratio = shorter / max(len(fragment_norm), len(planting_norm))
            containment_matches.append((ratio, planting))

    if containment_matches:
        containment_matches.sort(key=lambda item: item[0], reverse=True)
        best_ratio, best_planting = containment_matches[0]
        # A lower threshold is useful for filenames that omit a site prefix,
        # e.g. ReWildLargeExclosure vs An Óige Knockree - ReWild Large Exclosure.
        if best_ratio >= 0.42:
            return best_planting, "contained_name", round(best_ratio, 3)

    scored: list[tuple[float, Planting]] = []
    for planting, planting_norm in normalized:
        score = SequenceMatcher(None, fragment_norm, planting_norm).ratio()
        scored.append((score, planting))
    scored.sort(key=lambda item: item[0], reverse=True)

    best_score, best_planting = scored[0]
    if best_score >= 0.68:
        return best_planting, "fuzzy_name", round(best_score, 3)

    return None, "unmatched", round(best_score, 3)


def copy_images_to_qgis_map(source_folder: Path, destination_folder: Path, qgis_map_dir: Path) -> list[tuple[Path, str]]:
    """Copy images into qgis-map/images and return source plus browser path."""
    copied = []
    destination_folder.mkdir(parents=True, exist_ok=True)

    for image in iter_images(source_folder):
        relative_path = image.relative_to(source_folder)
        destination = destination_folder / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, destination)
        copied.append((image, destination.relative_to(qgis_map_dir).as_posix()))

    return copied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a JS index connecting planting and visit photos to Plantings_*.js."
    )
    parser.add_argument("plantings_js", type=Path)
    parser.add_argument("planting_photos", type=Path)
    parser.add_argument("visit_photos", type=Path)
    parser.add_argument(
        "--qgis-map-dir",
        type=Path,
        default=None,
        help=(
            "Destination qgis-map folder. By default this is inferred when "
            "Plantings JS is inside qgis-map/data/."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JS path. Default: planting_photo_index.js beside Plantings JS.",
    )
    parser.add_argument(
        "--include-unmatched",
        action="store_true",
        help="Include unmatched files in the JS output under `unmatched`.",
    )
    args = parser.parse_args()

    plantings_js = args.plantings_js.resolve()
    output_path = (
        args.output.resolve()
        if args.output
        else plantings_js.parent / "planting_photo_index.js"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.qgis_map_dir:
        qgis_map_dir = args.qgis_map_dir.resolve()
    elif plantings_js.parent.name.lower() == "data":
        qgis_map_dir = plantings_js.parent.parent
    else:
        raise ValueError(
            "Could not infer qgis-map directory. Supply --qgis-map-dir."
        )

    planting_destination = qgis_map_dir / "images" / "planting-photos"
    visit_destination = qgis_map_dir / "images" / "visit-photos"

    copied_inputs = [
        (copy_images_to_qgis_map(
            args.planting_photos.resolve(), planting_destination, qgis_map_dir
        ), "planting"),
        (copy_images_to_qgis_map(
            args.visit_photos.resolve(), visit_destination, qgis_map_dir
        ), "visit"),
    ]

    data = load_qgis_js(plantings_js)
    plantings = extract_plantings(data)
    exact_photo_lookup = {
        Path(planting.photo).name.casefold(): planting
        for planting in plantings
        if planting.photo
    }

    records: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()

    for copied_images, default_type in copied_inputs:
        for image, web_path in copied_images:
            resolved = image.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            planting, method, score = match_planting(
                image, plantings, exact_photo_lookup
            )
            photo_type = infer_photo_type(image.name, default_type)
            date = extract_date(image.name)

            if planting is None:
                unmatched.append(
                    {
                        "image_path": web_path,
                        "source_filename": image.name,
                        "photo_type": photo_type,
                        "date": date,
                        "name_fragment": filename_name_fragment(image.name),
                        "best_match_score": score,
                    }
                )
                continue

            # For a primary planting photo with no date in its filename, fall
            # back to the mapped planting's first-planted date.
            if date is None and photo_type == "planting":
                date = planting.first_planted

            records.append(
                {
                    "planting_site_name": planting.name,
                    "image_path": web_path,
                    "photo_type": photo_type,
                    "date": date,
                    "source_filename": image.name,
                    "match_method": method,
                    "match_score": score,
                }
            )

    records.sort(
        key=lambda record: (
            record["planting_site_name"].casefold(),
            record["date"] or "9999-12-31",
            record["photo_type"],
            record["source_filename"].casefold(),
        )
    )

    payload: dict[str, Any] = {
        "generated_from": plantings_js.name,
        "records": records,
    }
    if args.include_unmatched:
        payload["unmatched"] = unmatched

    js = (
        "// Generated by build_planting_photo_index.py\n"
        "var planting_photo_index = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n"
    )
    output_path.write_text(js, encoding="utf-8")

    print(f"Copied photos into: {qgis_map_dir / 'images'}")
    print(f"Wrote: {output_path}")
    print(f"Matched images: {len(records)}")
    print(f"Unmatched images: {len(unmatched)}")
    if unmatched:
        print("\nUnmatched files:")
        for item in unmatched:
            print(f"  - {item['source_filename']}")


if __name__ == "__main__":
    main()
