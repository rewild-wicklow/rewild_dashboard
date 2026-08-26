from pathlib import Path
import geopandas as gpd

DATA_DIR = Path("/Users/noellelaw/Desktop/2026-SUMMER/rewild/data/20260609/external-data")
ASSETS_DIR = Path("/Users/noellelaw/Desktop/2026-SUMMER/rewild/src/assets")
ASSETS_DIR.mkdir(exist_ok=True)

layers = {
    "rewild_sites": "WOL-Rewild-Provisional-Sites-260603.gpkg",
    "wicklow_boundary": "wicklow-boundary-20m.gpkg",
    "national_park": "wicklow-national-park-boundary-10m.gpkg",
    "sac": "sac-2026-wicklow-clipped-10m.gpkg",
    "spa": "spa-2026-wicklow-20m.gpkg",
    "nature_reserves": "nature-reserves-wicklow-20m.gpkg",
}

for name, filename in layers.items():
    path = DATA_DIR / filename
    gdf = gpd.read_file(path, engine="pyogrio")

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    out_path = ASSETS_DIR / f"{name}.geojson"
    gdf.to_file(out_path, driver="GeoJSON")
    print(f"Saved {out_path}")