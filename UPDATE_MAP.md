# Updating the Dashboard Map

Use this process when the Mergin Maps project has new site data, planting data, visits, or photographs.

## 1. Download the latest Mergin Maps project

Log in to Mergin Maps and download/sync the most recent ReWild Wicklow project to your computer.

The downloaded project should include `projects.qgz` and the associated project data. Keep track of the paths to its `planting-photos` and `visit-photos` folders; they are used later.

## 2. Open the project in QGIS

Install QGIS if necessary, then open:

```text
projects.qgz
```

Confirm that the expected layers load before exporting.

## 3. Install qgis2web

In QGIS, open the plugin manager and install **qgis2web** if it is not already installed.

The qgis2web **Create web map** button should then appear in the QGIS toolbar.

## 4. Export the web map

Open qgis2web and use the existing layer selection unless there is a reason to change it.

Under **Export**:

1. Set the export location to:

   ```text
   <rewild repository>/src/assets
   ```

2. Select **Leaflet** as the export format.
3. Export the map.

### If export fails with a geometry error

Return to **Layers and Groups**, find **Nature Reserves** under **External Datasets**, deselect it, and export again.

## 5. Rename the export

qgis2web creates a new export folder. Rename that folder to:

```text
qgis-map
```

The final path must be:

```text
src/assets/qgis-map/
```

If an older `qgis-map` folder already exists, replace it with the new export. The custom source markers are stored separately in `src/assets/markers/` and will be copied back in by the patch script.

## 6. Rebuild the planting photo index

The photo-index script copies planting and visit photos into the qgis2web export and creates `planting_photo_index.js`.

First, find the newly exported Plantings file. It will be inside:

```text
src/assets/qgis-map/data/
```

and will have a name such as `Plantings_3.js`. The number can change between qgis2web exports.

Run the following from the repository root, replacing the three example paths with the current ones:

```bash
python src/scripts/build_planting_photo_index.py \
  src/assets/qgis-map/data/Plantings_3.js \
  /path/to/mergin-project/planting-photos \
  /path/to/mergin-project/visit-photos
```

The script creates/updates:

```text
src/assets/qgis-map/data/planting_photo_index.js
src/assets/qgis-map/images/planting-photos/
src/assets/qgis-map/images/visit-photos/
```

Check the terminal output for unmatched images. If a filename cannot be matched automatically, add an exception to the `ALIASES` dictionary near the top of `build_planting_photo_index.py` and run it again.

## 7. Patch the qgis2web export

From the repository root:

```bash
python src/scripts/update_html_export.py
```

This script applies the dashboard-specific changes to the generated qgis2web files, including custom markers, basemaps, pop-up/interaction behavior, and other map styling/behavior that is not preserved by a standard qgis2web export.

The script expects the export at:

```text
src/assets/qgis-map/
```

and the reusable marker SVGs at:

```text
src/assets/markers/
```

## 8. Run and check the dashboard

Start the app:

```bash
python src/app.py
```

Check at minimum:

- the Project Map loads;
- site markers use the expected colors;
- planting areas can be selected;
- the detail panel updates after a map selection;
- tree-type icons display;
- planting and visit photos display;
- the timeline loads;
- the map legend is visible;
- no private/internal fields appear in public pop-ups.

If something is wrong, see `docs/TROUBLESHOOTING.md` before changing the generated qgis2web files manually.
