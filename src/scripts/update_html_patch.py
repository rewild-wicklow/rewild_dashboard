from pathlib import Path
import re
import shutil


# =========================================================================
# 1. Paths
# =========================================================================
#
# qgis2web produces index.html in this directory.
#
# We read that original file, apply our patches, and create files such as:
#
#   index-voyager.html
#   index-osm.html
#   index-topo.html
#
# The original index.html is not overwritten.
# =========================================================================

EXPORT_DIR = Path(
    "/Users/noellelaw/Desktop/2026-SUMMER/rewild/src/assets/qgis-map"
)

INDEX = EXPORT_DIR / "index.html"

SOURCE_MARKERS_DIR = EXPORT_DIR.parent / "markers"
TARGET_MARKERS_DIR = EXPORT_DIR / "markers"


# =========================================================================
# 2. Configuration
# =========================================================================

SITE_ICON_MAP = {
    "regular": "tree_red.svg",
    "sporadic": "tree_yellow.svg",
    "annual": "tree_light_blue.svg",
    "never": "tree_gray.svg",
    "": "tree_purple.svg",
    "null": "tree_purple.svg",
    "undefined": "tree_purple.svg",
}


LEGEND_ICON_MAP = {
    "Regular visits from RW": "tree_red.svg",
    "Sporadic visits from RW, Monitored locally": "tree_yellow.svg",
    "Annual visit from RW, Maintained Locally": "tree_light_blue.svg",
    "No visits required": "tree_gray.svg",
    "Undetermined": "tree_purple.svg",
}


BASEMAPS = {
    "osm": {
        "file": "index-osm.html",
        "label": "OSM Standard",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": (
            '<a href="https://www.openstreetmap.org/copyright">'
            "© OpenStreetMap contributors</a>"
        ),
        "max_zoom": 19,
    },

    "voyager": {
        "file": "index-voyager.html",
        "label": "Carto Voyager",
        "url": (
            "https://{s}.basemaps.cartocdn.com/"
            "rastertiles/voyager/{z}/{x}/{y}{r}.png"
        ),
        "attribution": "© OpenStreetMap contributors © CARTO",
        "max_zoom": 20,
        "add_topography_overlay": True,
    },

    "positron": {
        "file": "index-positron.html",
        "label": "Carto Positron",
        "url": (
            "https://{s}.basemaps.cartocdn.com/"
            "light_all/{z}/{x}/{y}{r}.png"
        ),
        "attribution": "© OpenStreetMap contributors © CARTO",
        "max_zoom": 20,
    },

    "topo": {
        "file": "index-topo.html",
        "label": "OpenTopoMap",
        "url": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "attribution": (
            "Map data © OpenStreetMap contributors, SRTM | "
            "Map style © OpenTopoMap"
        ),
        "max_zoom": 17,
    },

    "imagery": {
        "file": "index-imagery.html",
        "label": "Esri World Imagery",
        "url": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ),
        "attribution": "Tiles © Esri",
        "max_zoom": 19,
    },
}


# =========================================================================
# 3. Copy the custom tree markers
# =========================================================================

def copy_custom_markers() -> None:
    """
    Copy all custom SVG files from:

        assets/markers

    into:

        assets/qgis-map/markers

    qgis2web may recreate the qgis-map export directory, so this is repeated
    each time the patch script runs.
    """

    TARGET_MARKERS_DIR.mkdir(parents=True, exist_ok=True)

    copied_count = 0

    for svg_path in SOURCE_MARKERS_DIR.glob("*.svg"):
        target_path = TARGET_MARKERS_DIR / svg_path.name

        shutil.copy2(svg_path, target_path)

        copied_count += 1
        print(f"Copied marker: {svg_path.name}")

    if copied_count == 0:
        print(
            "WARNING: No SVG marker files were found in "
            f"{SOURCE_MARKERS_DIR}"
        )


# =========================================================================
# 4. Detect qgis2web layer names
# =========================================================================
#
# qgis2web may change these numbers between exports:
#
#   Sites_2
#   Sites_3
#   Plantings_3
#   Plantings_4
#
# Therefore, we detect the current number rather than hard-coding it.
# =========================================================================

def detect_layer(html: str, base_name: str) -> str:
    """
    Find a qgis2web data file reference such as:

        data/Sites_2.js

    and return:

        Sites_2
    """

    pattern = rf'data/{re.escape(base_name)}_(\d+)\.js'

    match = re.search(pattern, html)

    if not match:
        raise RuntimeError(
            f"Could not find data/{base_name}_<number>.js in index.html"
        )

    layer_name = f"{base_name}_{match.group(1)}"

    print(f"Detected layer: {layer_name}")

    return layer_name


# =========================================================================
# 5. Replace the projected qgis2web map
# =========================================================================

def patch_map_definition(html: str) -> str:
    """
    Some qgis2web exports create a projected Leaflet CRS.

    Since the exported GeoJSON coordinates are longitude/latitude, this patch
    replaces that projected map definition with a normal Leaflet map.
    """

    standard_map_block = """
        var map = L.map('map', {
            zoomControl: false,
            maxZoom: 20,
            minZoom: 1
        }).fitBounds([
            [52.64062730567451, -7.0611765937028785],
            [53.282235869183104, -5.799805104021357]
        ]);
"""

    projected_map_pattern = re.compile(
        r"""
        \s*
        var\s+crs\s*=\s*new\s+L\.Proj\.CRS
        \(.*?\};
        \s*
        var\s+map\s*=\s*L\.map
        \('map',\s*\{.*?\}\)
        \.fitBounds
        \(\[\[.*?\]\]\);
        """,
        re.DOTALL | re.VERBOSE,
    )

    html, count = projected_map_pattern.subn(
        standard_map_block,
        html,
        count=1,
    )

    if count == 0:
        print(
            "Map CRS replacement: 0 replacements "
            "(the export may already use a normal Leaflet map)"
        )
    else:
        print("Map CRS replacement: 1 replacement")

    return html


# =========================================================================
# 6. Style the county and national park boundary layers
# =========================================================================

def replace_polygon_style(
    html: str,
    layer_name: str,
    color: str,
) -> str:
    """
    Replace a qgis2web polygon style function.

    These background boundary layers remain non-interactive so they do not
    block the mouse from reaching sites and planting polygons.
    """

    style_function = f"""
        function style_{layer_name}_0() {{
            return {{
                pane: 'pane_{layer_name}',
                opacity: 1,
                color: '{color}',
                dashArray: '',
                lineCap: 'round',
                lineJoin: 'round',
                weight: 2,
                fillOpacity: 0,
                interactive: false,
            }};
        }}
"""

    pattern = re.compile(
        rf"""
        function\s+style_{re.escape(layer_name)}_0
        \(\)\s*\{{
        .*?
        (?=
            map\.createPane
            \('pane_{re.escape(layer_name)}'\)
        )
        """,
        re.DOTALL | re.VERBOSE,
    )

    html, count = pattern.subn(
        style_function + "\n        ",
        html,
        count=1,
    )

    print(
        f"Updated style for {layer_name}: "
        f"{count} replacement(s)"
    )

    return html


# =========================================================================
# 7. Replace the site symbols with custom tree icons
# =========================================================================

def patch_site_icons(
    html: str,
    sites_layer: str,
) -> str:
    """
    Replace the automatically generated qgis2web marker style with our
    management-type tree icons.
    """

    javascript_icon_map = "{\n" + ",\n".join(
        f"                '{key}': '{value}'"
        for key, value in SITE_ICON_MAP.items()
    ) + "\n            }"

    style_function = f"""
        function style_{sites_layer}_0(feature) {{
            var managementType = String(
                feature.properties['Management Type'] || ''
            ).trim().toLowerCase();

            var iconFile = {javascript_icon_map}[managementType]
                || 'tree_purple.svg';

            return {{
                pane: 'pane_{sites_layer}',
                rotationAngle: 0.0,
                rotationOrigin: 'center center',

                icon: L.icon({{
                    iconUrl: 'markers/' + iconFile,
                    iconSize: [19.0, 19.0],
                    iconAnchor: [9.5, 9.5],
                    popupAnchor: [0, -9.5],
                    tooltipAnchor: [0, -10]
                }}),

                interactive: true,
            }};
        }}
"""

    pattern = re.compile(
        rf"""
        \s*
        function\s+style_{re.escape(sites_layer)}_0
        \(feature\)\s*\{{
        .*?
        (?=
            map\.createPane
            \('pane_{re.escape(sites_layer)}'\)
        )
        """,
        re.DOTALL | re.VERBOSE,
    )

    html, count = pattern.subn(
        style_function + "\n        ",
        html,
        count=1,
    )

    print(
        f"Updated {sites_layer} marker style: "
        f"{count} replacement(s)"
    )

    if count == 0:
        raise RuntimeError(
            f"Could not replace the style function for {sites_layer}"
        )

    return html


# =========================================================================
# 8. Replace the site legend icons
# =========================================================================

def patch_site_legend(
    html: str,
    sites_layer: str,
) -> str:
    """
    Replace qgis2web's generated site legend symbols with the matching
    custom tree SVG files.
    """

    for label, svg_filename in LEGEND_ICON_MAP.items():
        pattern = re.compile(
            rf"""
            <img
            \s+src="legend/{re.escape(sites_layer)}_[^"]*"
            \s*/>
            </td>
            <td>{re.escape(label)}</td>
            """,
            re.VERBOSE,
        )

        replacement = (
            f'<img src="markers/{svg_filename}" '
            'style="width:19px;height:19px;" />'
            f"</td><td>{label}</td>"
        )

        html, count = pattern.subn(
            replacement,
            html,
            count=1,
        )

        print(
            f"Updated legend icon for '{label}': "
            f"{count} replacement(s)"
        )

    return html


# =========================================================================
# 9. Fix qgis2web's hover highlight function
# =========================================================================
#
# Why this matters:
#
# Planting polygons have a setStyle() method.
# Standard Leaflet markers do not.
#
# The original qgis2web hover function tries to call setStyle() on both.
# When it reaches a tree marker, JavaScript throws an error and the site
# tooltip never opens.
#
# This replacement checks whether setStyle() exists before calling it.
#
# It also removes openPopup() from hover. Full popups will still open when a
# feature is clicked.
# =========================================================================

def patch_safe_highlight_function(html: str) -> str:
    """
    Replace qgis2web's original highlightFeature() function.

    Why this is necessary:
    - Planting polygons support layer.setStyle().
    - Tree markers do not support layer.setStyle().
    - The original qgis2web function calls setStyle() for every feature.
    - That causes a JavaScript error when hovering over a tree marker.

    This replacement:
    - highlights polygons safely;
    - leaves markers alone;
    - does not open the full popup on hover;
    - allows the lightweight tooltip to appear instead.
    """

    safe_highlight_function = """
        var highlightLayer;

        function highlightFeature(e) {
            highlightLayer = e.target;

            /*
             * A Leaflet marker does not have setStyle().
             * A polygon or line does.
             *
             * If this feature is a marker, stop here. Its tooltip can still
             * open normally.
             */
            if (
                typeof highlightLayer.setStyle !== 'function'
                || !highlightLayer.feature
                || !highlightLayer.feature.geometry
            ) {
                return;
            }

            var geometryType =
                highlightLayer.feature.geometry.type;

            if (
                geometryType === 'LineString'
                || geometryType === 'MultiLineString'
            ) {
                highlightLayer.setStyle({
                    color: 'rgba(255, 255, 0, 1.0)'
                });
            } else if (
                geometryType === 'Polygon'
                || geometryType === 'MultiPolygon'
            ) {
                highlightLayer.setStyle({
                    fillColor: 'rgba(255, 255, 0, 1.0)',
                    fillOpacity: 0.30
                });
            }
        }
"""

    # The original function may be followed by either:
    #
    #     var crs = ...
    #
    # or:
    #
    #     var map = ...
    #
    # depending on how qgis2web exported the project.
    pattern = re.compile(
        r"""
        var\s+highlightLayer\s*;

        \s*

        function\s+highlightFeature\s*
        \(\s*e\s*\)
        \s*
        \{
            .*?
        \}

        (?=
            \s*
            var\s+(?:crs|map)\s*=
        )
        """,
        re.DOTALL | re.VERBOSE,
    )

    html, count = pattern.subn(
        safe_highlight_function,
        html,
        count=1,
    )

    print(
        "Updated safe hover highlight function: "
        f"{count} replacement(s)"
    )

    if count == 0:
        raise RuntimeError(
            "Could not replace highlightFeature(). "
            "The function exists, but its generated structure may have "
            "changed. Search index.html for 'function highlightFeature'."
        )

    return html


# =========================================================================
# 10. Remove qgis2web's automatically generated permanent labels
# =========================================================================
#
# Near the bottom of the export, qgis2web adds code similar to:
#
#   layer.bindTooltip(..., {
#       permanent: true,
#       className: 'css_Sites_2'
#   });
#
# We remove those labels before adding our own hover cards.
#
# If we did not remove them, the later bindTooltip() call could replace the
# richer tooltip added inside pop_Sites_2().
# =========================================================================

def remove_generated_tooltip(
    html: str,
    layer_name: str,
) -> str:
    pattern = re.compile(
        rf"""
        layer\.bindTooltip
        \(
            .*?
            className:\s*
            ['"]css_{re.escape(layer_name)}['"]
            .*?
        \);
        """,
        re.DOTALL | re.VERBOSE,
    )

    html, count = pattern.subn(
        "",
        html,
        count=1,
    )

    print(
        f"Removed generated tooltip for {layer_name}: "
        f"{count} replacement(s)"
    )

    return html


# =========================================================================
# 11. Add reusable JavaScript helpers
# =========================================================================

def add_hover_javascript_helpers(html: str) -> str:
    """
    Add helper functions used by both site and planting hover cards.

    escapeHoverText() prevents text such as '<' or '&' from being interpreted
    as HTML.

    formatHoverDate() converts:

        2026-04-11

    into:

        11 April 2026
    """

    helper_code = """
        function escapeHoverText(value) {
            if (value === null || value === undefined) {
                return '';
            }

            return String(value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function formatHoverDate(value) {
            if (!value) {
                return '';
            }

            var parts = String(value).split('-');

            if (parts.length !== 3) {
                return escapeHoverText(value);
            }

            var date = new Date(
                Number(parts[0]),
                Number(parts[1]) - 1,
                Number(parts[2])
            );

            if (isNaN(date.getTime())) {
                return escapeHoverText(value);
            }

            return date.toLocaleDateString(
                'en-IE',
                {
                    day: 'numeric',
                    month: 'long',
                    year: 'numeric'
                }
            );
        }

        function titleCaseHoverText(value) {
            if (!value) {
                return '';
            }

            return String(value)
                .replace(/[-_]/g, ' ')
                .replace(
                    /\\b\\w/g,
                    function(letter) {
                        return letter.toUpperCase();
                    }
                );
        }
"""

    insertion_point = "var title = new L.Control"

    if insertion_point not in html:
        raise RuntimeError(
            "Could not find the map title control insertion point"
        )

    html = html.replace(
        insertion_point,
        helper_code + "\n        " + insertion_point,
        1,
    )

    print("Added shared hover JavaScript helpers")

    return html


# =========================================================================
# 12. Add the site hover card
# =========================================================================
#
# This code is inserted at the beginning of:
#
#   function pop_Sites_2(feature, layer) {
#
# The original click popup remains below it.
# =========================================================================

def add_site_hover(
    html: str,
    sites_layer: str,
) -> str:
    site_hover_code = """
            var siteProperties = feature.properties || {};

            var siteName = escapeHoverText(
                siteProperties['Name'] || 'Unnamed site'
            );

            var siteActivity = titleCaseHoverText(
                siteProperties['Activity Type']
            );

            var managementType = String(
                siteProperties['Management Type'] || ''
            ).trim().toLowerCase();

            var managementLabels = {
                regular: 'Regular visits from ReWild Wicklow',
                sporadic: 'Sporadic visits; monitored locally',
                annual: 'Annual visit; maintained locally',
                never: 'No visits required'
            };

            var siteManagement = escapeHoverText(
                managementLabels[managementType]
                || 'Management schedule undetermined'
            );

            var siteLocalGroup = escapeHoverText(
                siteProperties['Local Group']
            );

            var siteLastVisited = formatHoverDate(
                siteProperties['last_visited']
            );

            var siteHoverContent =
                '<div class="rw-hover-card">' +

                    '<div class="rw-hover-title">' +
                        siteName +
                    '</div>' +

                    (
                        siteActivity
                            ? '<div class="rw-hover-row">' +
                                '<span class="rw-hover-label">' +
                                    'Activity' +
                                '</span>' +
                                '<span>' +
                                    escapeHoverText(siteActivity) +
                                '</span>' +
                              '</div>'
                            : ''
                    ) +

                    '<div class="rw-hover-row">' +
                        '<span class="rw-hover-label">' +
                            'Management' +
                        '</span>' +
                        '<span>' +
                            siteManagement +
                        '</span>' +
                    '</div>' +

                    (
                        siteLocalGroup
                            ? '<div class="rw-hover-row">' +
                                '<span class="rw-hover-label">' +
                                    'Local group' +
                                '</span>' +
                                '<span>' +
                                    siteLocalGroup +
                                '</span>' +
                              '</div>'
                            : ''
                    ) +

                    (
                        siteLastVisited
                            ? '<div class="rw-hover-row">' +
                                '<span class="rw-hover-label">' +
                                    'Last visited' +
                                '</span>' +
                                '<span>' +
                                    siteLastVisited +
                                '</span>' +
                              '</div>'
                            : ''
                    ) +

                    '<div class="rw-hover-hint">' +
                        'Click for full details' +
                    '</div>' +

                '</div>';

            layer.bindTooltip(
                siteHoverContent,
                {
                    permanent: false,
                    direction: 'top',
                    offset: [0, -12],
                    opacity: 0.98,
                    className: 'rw-hover-tooltip'
                }
            );
"""

    pattern = re.compile(
        rf"""
        function\s+pop_{re.escape(sites_layer)}
        \(feature,\s*layer\)\s*\{{
        """,
        re.VERBOSE,
    )

    def add_code_after_function(match: re.Match) -> str:
        return match.group(0) + "\n" + site_hover_code

    html, count = pattern.subn(
        add_code_after_function,
        html,
        count=1,
    )

    print(
        f"Added hover card to {sites_layer}: "
        f"{count} replacement(s)"
    )

    if count == 0:
        raise RuntimeError(
            f"Could not find pop_{sites_layer}(feature, layer)"
        )

    return html


# =========================================================================
# 13. Add the planting hover card
# =========================================================================

def add_planting_hover(
    html: str,
    plantings_layer: str,
) -> str:
    planting_hover_code = """
            var plantingProperties = feature.properties || {};

            var plantingName = escapeHoverText(
                plantingProperties['Name'] || 'Unnamed planting'
            );

            var plantingProtection = titleCaseHoverText(
                plantingProperties['Protection']
            );

            var plantingLastVisited = formatHoverDate(
                plantingProperties['last_visited']
            );

            var plantingHoverContent =
                '<div class="rw-hover-card">' +

                    '<div class="rw-hover-title">' +
                        plantingName +
                    '</div>' +

                    (
                        plantingProtection
                            ? '<div class="rw-hover-row">' +
                                '<span class="rw-hover-label">' +
                                    'Protection' +
                                '</span>' +
                                '<span>' +
                                    escapeHoverText(
                                        plantingProtection
                                    ) +
                                '</span>' +
                              '</div>'
                            : ''
                    ) +

                    (
                        plantingLastVisited
                            ? '<div class="rw-hover-row">' +
                                '<span class="rw-hover-label">' +
                                    'Last visited' +
                                '</span>' +
                                '<span>' +
                                    plantingLastVisited +
                                '</span>' +
                              '</div>'
                            : ''
                    ) +

                    '<div class="rw-hover-hint">' +
                        'Click for full details' +
                    '</div>' +

                '</div>';

            layer.bindTooltip(
                plantingHoverContent,
                {
                    permanent: false,
                    sticky: true,
                    direction: 'top',
                    opacity: 0.98,
                    className: 'rw-hover-tooltip'
                }
            );
"""

    pattern = re.compile(
        rf"""
        function\s+pop_{re.escape(plantings_layer)}
        \(feature,\s*layer\)\s*\{{
        """,
        re.VERBOSE,
    )

    def add_code_after_function(match: re.Match) -> str:
        return match.group(0) + "\n" + planting_hover_code

    html, count = pattern.subn(
        add_code_after_function,
        html,
        count=1,
    )

    print(
        f"Added hover card to {plantings_layer}: "
        f"{count} replacement(s)"
    )

    if count == 0:
        raise RuntimeError(
            f"Could not find pop_{plantings_layer}(feature, layer)"
        )

    return html


# =========================================================================
# 14. Keep planting borders visible at all zoom levels
# =========================================================================
#
# qgis2web currently adds code such as:
#
#   if (map.getZoom() >= 13 && map.getZoom() <= 19) {
#       map.addLayer(layer_Plantings_3);
#   } else {
#       map.removeLayer(layer_Plantings_3);
#   }
#
# That is why the planting boundary disappears after scrolling too far.
#
# The lightest patch is to replace each removeLayer command with addLayer.
# =========================================================================

def keep_plantings_visible(
    html: str,
    plantings_layer: str,
) -> str:
    remove_command = (
        f"map.removeLayer(layer_{plantings_layer});"
    )

    add_command = (
        f"map.addLayer(layer_{plantings_layer});"
    )

    count = html.count(remove_command)

    html = html.replace(
        remove_command,
        add_command,
    )

    print(
        f"Disabled zoom-based removal for {plantings_layer}: "
        f"{count} replacement(s)"
    )

    return html


# =========================================================================
# 15. Add hover-card CSS inside the iframe
# =========================================================================
#
# Important:
#
# The main Dash assets/style.css file cannot style elements inside an iframe.
# The iframe contains a separate HTML document.
#
# Therefore, the tooltip CSS must be inserted into each generated map HTML.
# =========================================================================

def add_hover_css(html: str) -> str:
    hover_css = """
        <style>
            .rw-hover-tooltip {
                padding: 0;
                border: 1px solid #d4e2d0;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.98);
                color: #405b39;
                box-shadow:
                    0 4px 14px
                    rgba(44, 72, 40, 0.18);
                font-family:
                    Arial,
                    Helvetica,
                    sans-serif;
            }

            .rw-hover-tooltip::before {
                border-top-color:
                    rgba(255, 255, 255, 0.98);
            }

            .rw-hover-card {
                box-sizing: border-box;
                min-width: 210px;
                max-width: 290px;
                padding: 10px 12px;
                line-height: 1.35;
            }

            .rw-hover-title {
                margin-bottom: 7px;
                color: #35552f;
                font-size: 15px;
                font-weight: 700;
            }

            .rw-hover-row {
                display: grid;
                grid-template-columns: 82px 1fr;
                gap: 7px;
                margin-top: 4px;
                font-size: 12px;
            }

            .rw-hover-label {
                color: #6e8567;
                font-weight: 600;
            }

            .rw-hover-hint {
                margin-top: 8px;
                padding-top: 7px;
                border-top: 1px solid #e5ece2;
                color: #788a73;
                font-size: 11px;
                font-style: italic;
            }
        </style>
"""

    if "</head>" not in html:
        raise RuntimeError(
            "Could not find </head> in the exported HTML"
        )

    html = html.replace(
        "</head>",
        hover_css + "\n    </head>",
        1,
    )

    print("Added hover-card CSS")

    return html

def add_iframe_scroll_bridge(html: str) -> str:
    """
    Allow normal mouse-wheel scrolling over the map to scroll the outer
    Dash page.

    Leaflet normally captures wheel events for map zooming. Because the map
    is inside an iframe, those events do not reach the parent page.

    Behaviour after this patch:
    - Normal wheel/trackpad scrolling scrolls the Dash page.
    - Ctrl/Command + wheel zooms the Leaflet map.
    """

    scroll_bridge_js = """
        /*
         * Normal scrolling should move the parent Dash page.
         * Ctrl/Command + scrolling remains available for map zooming.
         */
        map.scrollWheelZoom.disable();

        document.addEventListener(
            'wheel',
            function(event) {
                var wantsMapZoom =
                    event.ctrlKey || event.metaKey;

                if (wantsMapZoom) {
                    /*
                     * Temporarily enable Leaflet wheel zoom.
                     */
                    map.scrollWheelZoom.enable();

                    window.clearTimeout(
                        window.rewildWheelZoomTimeout
                    );

                    window.rewildWheelZoomTimeout =
                        window.setTimeout(
                            function() {
                                map.scrollWheelZoom.disable();
                            },
                            250
                        );

                    return;
                }

                /*
                 * Stop the iframe from consuming the wheel event and ask
                 * the parent Dash page to scroll instead.
                 */
                event.preventDefault();

                window.parent.postMessage(
                    {
                        source: 'rewild-qgis-map',
                        action: 'scroll-parent',
                        deltaX: event.deltaX,
                        deltaY: event.deltaY
                    },
                    '*'
                );
            },
            {
                passive: false
            }
        );
"""

    insertion_point = "var hash = new L.Hash(map);"

    if insertion_point not in html:
        raise RuntimeError(
            "Could not find 'var hash = new L.Hash(map);' "
            "for the iframe scroll bridge."
        )

    html = html.replace(
        insertion_point,
        insertion_point + "\n" + scroll_bridge_js,
        1,
    )

    print("Added iframe-to-parent scrolling bridge")

    return html

# =========================================================================
# 16. Apply all shared patches
# =========================================================================

def patch_common(
    original_html: str,
) -> tuple[str, dict[str, str]]:
    html = original_html

    print("\n--- Detecting qgis2web layers ---")

    layers = {
        "sites": detect_layer(
            html,
            "Sites",
        ),
        "plantings": detect_layer(
            html,
            "Plantings",
        ),
        "county": detect_layer(
            html,
            "CountyWicklow",
        ),
        "national_park": detect_layer(
            html,
            "WicklowMountainsNationalPark",
        ),
    }

    print("\n--- Patching the map ---")

    html = patch_map_definition(html)

    html = add_iframe_scroll_bridge(html)

    html = replace_polygon_style(
        html,
        layers["national_park"],
        "rgba(80,150,80,1.0)",
    )

    html = replace_polygon_style(
        html,
        layers["county"],
        "rgba(159,203,152,1.0)",
    )

    html = patch_site_icons(
        html,
        layers["sites"],
    )

    html = patch_site_legend(
        html,
        layers["sites"],
    )

    print("\n--- Patching hover interactions ---")

    html = patch_safe_highlight_function(html)

    html = remove_generated_tooltip(
        html,
        layers["sites"],
    )

    html = remove_generated_tooltip(
        html,
        layers["plantings"],
    )

    html = add_hover_javascript_helpers(html)

    html = add_site_hover(
        html,
        layers["sites"],
    )

    html = add_planting_hover(
        html,
        layers["plantings"],
    )

    html = keep_plantings_visible(
        html,
        layers["plantings"],
    )

    html = add_hover_css(html)

    return html, layers


# =========================================================================
# 17. Apply a particular basemap
# =========================================================================

def apply_basemap(
    html: str,
    basemap: dict,
    layers: dict[str, str],
) -> str:
    label = basemap["label"]
    url = basemap["url"]
    attribution = basemap["attribution"]
    max_zoom = basemap["max_zoom"]

    add_topography_overlay = basemap.get(
        "add_topography_overlay",
        False,
    )

    # -----------------------------------------------------------------
    # Remove the basemap created by qgis2web
    # -----------------------------------------------------------------

    html = re.sub(
        r"""
        \s*
        map\.createPane
        \('pane_[A-Za-z0-9_]+Basemap_0'\);
        .*?
        map\.addLayer
        \(layer_[A-Za-z0-9_]+Basemap_0\);
        """,
        "",
        html,
        flags=re.DOTALL | re.VERBOSE,
    )

    html = re.sub(
        r"""
        \s*
        map\.createPane
        \('pane_OSMStandard_0'\);
        .*?
        map\.addLayer
        \(layer_OSMStandard_0\);
        """,
        "",
        html,
        flags=re.DOTALL | re.VERBOSE,
    )

    # -----------------------------------------------------------------
    # Define our chosen basemap
    # -----------------------------------------------------------------

    basemap_javascript = f"""
        map.createPane('pane_Basemap_0');
        map.getPane('pane_Basemap_0').style.zIndex = 200;

        var layer_Basemap_0 = L.tileLayer(
            '{url}',
            {{
                pane: 'pane_Basemap_0',
                opacity: 1.0,
                attribution: '{attribution}',
                minZoom: 1,
                maxZoom: {max_zoom},
                minNativeZoom: 0,
                maxNativeZoom: {max_zoom}
            }}
        );

        map.addLayer(layer_Basemap_0);
"""

    if add_topography_overlay:
        basemap_javascript += """
        map.createPane('pane_Topography_0');

        map.getPane(
            'pane_Topography_0'
        ).style.zIndex = 250;

        var layer_Topography_0 = L.tileLayer(
            'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
            {
                pane: 'pane_Topography_0',
                opacity: 0.38,
                attribution:
                    'Map data © OpenStreetMap contributors, SRTM | ' +
                    'Map style © OpenTopoMap',
                minZoom: 1,
                maxZoom: 17,
                minNativeZoom: 0,
                maxNativeZoom: 17
            }
        );
"""

    insertion_point = (
        "var bounds_group = new L.featureGroup([]);"
    )

    if insertion_point not in html:
        raise RuntimeError(
            "Could not find bounds_group in the exported HTML"
        )

    html = html.replace(
        insertion_point,
        insertion_point + "\n" + basemap_javascript,
        1,
    )

    # -----------------------------------------------------------------
    # Remove old basemap entries from the layer selector
    # -----------------------------------------------------------------

    html = re.sub(
        r"""
        \s*
        \{
            label:\s*
            ["']
            [^"']*
            (
                OSM\ Standard
                |
                Carto\ Voyager
                |
                Carto\ Positron
                |
                OpenTopoMap
                |
                Esri\ World\ Imagery
                |
                Topographic\ Overlay
            )
            [^"']*
            ["'],
            \s*
            layer:\s*
            layer_[A-Za-z0-9_]+
        \},
        ?
        """,
        "",
        html,
        flags=re.VERBOSE,
    )

    # -----------------------------------------------------------------
    # Add our basemap to the layer selector
    # -----------------------------------------------------------------

    layer_entries = (
        f"            {{label: '{label}', "
        "layer: layer_Basemap_0},\n"
    )

    if add_topography_overlay:
        layer_entries += (
            "            {label: 'Topographic Overlay', "
            "layer: layer_Topography_0},\n"
        )

    national_park_layer = layers["national_park"]

    national_park_entry_pattern = re.compile(
        rf"""
        (
            \{{
                label:\s*
                '<img
                \s+src="legend/{re.escape(national_park_layer)}\.png"
                \s*/>
                \s*
                Wicklow\ Mountains\ National\ Park',
                \s*
                layer:\s*
                layer_{re.escape(national_park_layer)}
            \}},
        )
        """,
        re.VERBOSE,
    )

    html, count = national_park_entry_pattern.subn(
        lambda match: (
            match.group(1)
            + "\n"
            + layer_entries
        ),
        html,
        count=1,
    )

    print(
        f"Added '{label}' to layer selector: "
        f"{count} replacement(s)"
    )

    if count == 0:
        print(
            "WARNING: The basemap was created, but its layer-selector "
            "entry may not have been inserted."
        )

    return html


# =========================================================================
# 18. Run the patch
# =========================================================================

def main() -> None:
    print("Starting qgis2web patch process\n")

    if not INDEX.exists():
        raise FileNotFoundError(
            f"The qgis2web export was not found:\n{INDEX}"
        )

    copy_custom_markers()

    print(f"\nReading original export: {INDEX}")

    original_html = INDEX.read_text(
        encoding="utf-8",
    )

    common_html, layers = patch_common(
        original_html,
    )

    print("\n--- Creating basemap versions ---")

    for basemap_key, basemap in BASEMAPS.items():
        output_html = apply_basemap(
            common_html,
            basemap,
            layers,
        )

        output_path = (
            EXPORT_DIR
            / basemap["file"]
        )

        output_path.write_text(
            output_html,
            encoding="utf-8",
        )

        print(
            f"Created {basemap_key}: "
            f"{output_path.name}"
        )

    print(
        "\nDone. Original index.html was not overwritten."
    )


if __name__ == "__main__":
    main()