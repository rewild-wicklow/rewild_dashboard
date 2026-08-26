# Troubleshooting

## Conda environment will not create

Make sure Conda is installed and available in the terminal:

```bash
conda --version
```

Then retry:

```bash
conda env create -f rewild_environment.yml
```

If the `rewild` environment already exists, update it instead:

```bash
conda env update -n rewild -f rewild_environment.yml --prune
```

## `ModuleNotFoundError` when running the app

Activate the project environment first:

```bash
conda activate rewild
python src/app.py
```

## qgis2web export fails with a geometry error

In qgis2web **Layers and Groups**, deselect **Nature Reserves** under **External Datasets** and export again.

## `update_html_export.py` cannot find a layer

The patch script detects qgis2web layer files such as `Sites_3.js` and `Plantings_3.js`. Check that the new export contains the expected layers in:

```text
src/assets/qgis-map/data/
```

If QGIS/qgis2web renamed or omitted a layer, fix the export before running the patch script.

## `update_html_export.py` cannot find `index.html`

The qgis2web export must be named exactly:

```text
src/assets/qgis-map/
```

and it must contain `index.html`.

## Custom site markers disappear after a new export

This is expected until the patch script is run. The source marker SVGs live in:

```text
src/assets/markers/
```

Run:

```bash
python src/scripts/update_html_export.py
```

## Photos are missing

Re-run `build_planting_photo_index.py` using the current Mergin Maps `planting-photos` and `visit-photos` folders. Check its terminal summary for unmatched images.

Also confirm that these folders were generated:

```text
src/assets/qgis-map/images/planting-photos/
src/assets/qgis-map/images/visit-photos/
```

and that this file exists:

```text
src/assets/qgis-map/data/planting_photo_index.js
```

## The wrong `Plantings_*.js` filename is in a command

qgis2web may change the numeric suffix on each export. Look in:

```text
src/assets/qgis-map/data/
```

and use the current `Plantings_<number>.js` filename when running the photo-index script.

## Map behavior breaks after a qgis2web export

Always run:

```bash
python src/scripts/update_html_export.py
```

after replacing `src/assets/qgis-map/`. The raw qgis2web export does not contain all dashboard-specific behavior.

## Before committing an updated map

Run the dashboard locally and verify the map, detail panel, photos, timeline, legend, and public/private field behavior. Avoid relying only on a successful script exit.
