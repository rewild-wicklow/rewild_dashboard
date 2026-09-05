from pathlib import Path
import json
import re
import shutil

# NWW - work-around - git prooject is called rewild_dashboard - fix this fn to handle either
# def find_project_root(project_name="rewild_dashboard"):
def find_project_root(project_name="rewild"):
    current = Path(__file__).resolve()

    for parent in [current] + list(current.parents):
        if parent.name == project_name:
            return parent

    raise RuntimeError(
        f"Could not find project root '{project_name}'. "
        "Make sure this script is located somewhere inside the project."
    )

ROOT_DIR = find_project_root()

EXPORT_DIR = ROOT_DIR / "src" / "assets" / "qgis-map"
INDEX = EXPORT_DIR / "index.html"
# ---------------------------------------------------------------------
# 0. Copy custom SVG marker files into qgis2web markers folder
# ---------------------------------------------------------------------

SOURCE_MARKERS_DIR = EXPORT_DIR.parent / "markers"
TARGET_MARKERS_DIR = EXPORT_DIR / "markers"

TARGET_MARKERS_DIR.mkdir(exist_ok=True)

for svg_path in SOURCE_MARKERS_DIR.glob("*.svg"):
    target_path = TARGET_MARKERS_DIR / svg_path.name
    shutil.copy2(svg_path, target_path)
    print(f"Copied {svg_path.name} -> {target_path}")


# ---------------------------------------------------------------------
# Continue on the journey
# ---------------------------------------------------------------------

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
        "attribution": '<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>',
        "max_zoom": 19,
    },
    "voyager": {
        "file": "index-voyager.html",
        "label": "Carto Voyager",
        "url": "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        "attribution": "© OpenStreetMap contributors © CARTO",
        "max_zoom": 20,
        "add_topography_overlay": True,
    },
    "positron": {
        "file": "index-positron.html",
        "label": "Carto Positron",
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "attribution": "© OpenStreetMap contributors © CARTO",
        "max_zoom": 20,
    },
    "topo": {
        "file": "index-topo.html",
        "label": "OpenTopoMap",
        "url": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "attribution": "Map data © OpenStreetMap contributors, SRTM | Map style © OpenTopoMap",
        "max_zoom": 17,
    },
    "imagery": {
        "file": "index-imagery.html",
        "label": "Esri World Imagery",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Tiles © Esri",
        "max_zoom": 19,
    },
}

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

def patch_safe_highlight_function(html: str) -> str:
    """
    Replace qgis2web's generated highlightFeature() function when present.

    Some qgis2web exports do not generate highlightFeature() at all. In that
    case there is nothing to patch, so the function returns the HTML unchanged.

    A small brace-matching parser is used instead of depending on whichever
    variable or block happens to follow the generated function. This makes the
    replacement tolerant of formatting changes between qgis2web versions.
    """

    safe_highlight_function = """
        var highlightLayer;

        function highlightFeature(e) {
            highlightLayer = e.target;

            /*
             * A Leaflet marker does not have setStyle().
             * A polygon or line does.
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

    function_match = re.search(
        r"function\s+highlightFeature\s*\(\s*e\s*\)\s*\{",
        html,
    )

    if not function_match:
        print(
            "Safe hover highlight function not present in this export; "
            "skipping replacement"
        )
        return html

    function_start = function_match.start()
    opening_brace = html.find("{", function_match.start(), function_match.end())

    depth = 0
    function_end = None
    quote = None
    escaped = False
    index = opening_brace

    while index < len(html):
        character = html[index]

        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
        else:
            if character in ("'", '"', "`"):
                quote = character
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    function_end = index + 1
                    break

        index += 1

    if function_end is None:
        raise RuntimeError(
            "Found highlightFeature(), but could not locate its closing brace."
        )

    # Include a preceding generated `var highlightLayer;` declaration when it
    # immediately belongs to this function, avoiding duplicate declarations.
    prefix = html[:function_start]
    declaration_match = re.search(
        r"var\s+highlightLayer\s*;\s*$",
        prefix,
    )

    replacement_start = (
        declaration_match.start()
        if declaration_match
        else function_start
    )

    html = (
        html[:replacement_start]
        + safe_highlight_function
        + html[function_end:]
    )

    print("Updated safe hover highlight function: 1 replacement(s)")
    return html

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
                max-width: 360px;
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

def add_parent_message_bridge(
    html: str,
    sites_layer: str,
    plantings_layer: str,
) -> str:
    """
    Send selected site or planting properties from the qgis2web iframe
    to the surrounding Dash page.
    """

    site_click_code = """
            layer.on('click', function() {
                var message = {
                    source: 'rewild-qgis-map',
                    featureType: 'site',
                    properties: feature.properties,
                    sentAt: Date.now()
                };

                console.log(
                    'Sending site selection to Dash:',
                    message
                );

                /*
                 * Update the Dash Store directly. postMessage() by itself
                 * does not change a dcc.Store unless the parent page has a
                 * separate message listener. Because this iframe is served
                 * by the same Dash application, set_props() is the most
                 * reliable bridge.
                 */
                try {
                    if (
                        window.parent
                        && window.parent.dash_clientside
                        && typeof window.parent.dash_clientside.set_props
                            === 'function'
                    ) {
                        window.parent.dash_clientside.set_props(
                            'selected-map-feature',
                            {data: message}
                        );
                    }
                } catch (error) {
                    console.warn(
                        'Could not update the Dash feature store directly:',
                        error
                    );
                }

                /* Retain postMessage as a compatibility fallback. */
                window.parent.postMessage(
                    message,
                    '*'
                );
            });
"""

    planting_click_code = """
            layer.on('click', function() {
                var message = {
                    source: 'rewild-qgis-map',
                    featureType: 'planting',
                    properties: feature.properties,
                    sentAt: Date.now()
                };

                console.log(
                    'Sending planting selection to Dash:',
                    message
                );

                window.parent.postMessage(
                    message,
                    '*'
                );
            });
"""

    site_pattern = re.compile(
        rf"""
        (
            function\s+pop_{re.escape(sites_layer)}
            \(feature,\s*layer\)\s*\{{
        )
        """,
        re.VERBOSE,
    )

    html, site_count = site_pattern.subn(
        lambda match: (
            match.group(1)
            + "\n"
            + site_click_code
        ),
        html,
        count=1,
    )

    planting_pattern = re.compile(
        rf"""
        (
            function\s+pop_{re.escape(plantings_layer)}
            \(feature,\s*layer\)\s*\{{
        )
        """,
        re.VERBOSE,
    )

    html, planting_count = planting_pattern.subn(
        lambda match: (
            match.group(1)
            + "\n"
            + planting_click_code
        ),
        html,
        count=1,
    )

    print(
        f"Added site message bridge: "
        f"{site_count} replacement(s)"
    )

    print(
        f"Added planting message bridge: "
        f"{planting_count} replacement(s)"
    )

    if site_count == 0:
        raise RuntimeError(
            f"Could not add message bridge to {sites_layer}"
        )

    if planting_count == 0:
        raise RuntimeError(
            f"Could not add message bridge to {plantings_layer}"
        )

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
# Keep nested planting polygons clickable and highlightable
# =========================================================================

def patch_planting_panes(
    html: str,
    plantings_layer: str,
) -> str:
    """
    Put each planting protection type in its own Leaflet pane.

    This prevents a large outer polygon, such as an area of tubes, from
    intercepting hover and click events intended for a smaller polygon
    located inside it.

    Drawing order, from lowest to highest:
        unprotected
        tubes
        cages
        exclosure
    """

    pane_names = {
        "unprotected": "pane_planting_unprotected",
        "tubes": "pane_planting_tubes",
        "cages": "pane_planting_cages",
        "exclosure": "pane_planting_exclosure",
    }

    pane_code = f"""
        /*
         * Separate panes ensure smaller nested planting polygons remain
         * clickable even when they sit inside a larger planting polygon.
         */
        map.createPane('{pane_names["unprotected"]}');
        map.getPane('{pane_names["unprotected"]}').style.zIndex = 404;
        map.getPane('{pane_names["unprotected"]}').style['mix-blend-mode'] = 'normal';

        map.createPane('{pane_names["tubes"]}');
        map.getPane('{pane_names["tubes"]}').style.zIndex = 405;
        map.getPane('{pane_names["tubes"]}').style['mix-blend-mode'] = 'normal';

        map.createPane('{pane_names["cages"]}');
        map.getPane('{pane_names["cages"]}').style.zIndex = 406;
        map.getPane('{pane_names["cages"]}').style['mix-blend-mode'] = 'normal';

        map.createPane('{pane_names["exclosure"]}');
        map.getPane('{pane_names["exclosure"]}').style.zIndex = 407;
        map.getPane('{pane_names["exclosure"]}').style['mix-blend-mode'] = 'normal';
"""

    style_function = f"""
        function style_{plantings_layer}_0(feature) {{
            var protection = String(
                (feature.properties || {{}})['Protection'] || ''
            ).trim().toLowerCase();

            switch (protection) {{
                case 'exclosure':
                    return {{
                        pane: '{pane_names["exclosure"]}',
                        opacity: 1,
                        color: 'rgba(229,129,14,1.0)',
                        dashArray: '',
                        lineCap: 'round',
                        lineJoin: 'round',
                        weight: 2.0,
                        fillColor: 'rgba(229,129,14,1.0)',
                        fillOpacity: 0,
                        interactive: true
                    }};

                case 'cages':
                    return {{
                        pane: '{pane_names["cages"]}',
                        opacity: 1,
                        color: 'rgba(172,253,81,1.0)',
                        dashArray: '8.0,4.0',
                        lineCap: 'round',
                        lineJoin: 'round',
                        weight: 2.0,
                        fillColor: 'rgba(172,253,81,1.0)',
                        fillOpacity: 0,
                        interactive: true
                    }};

                case 'tubes':
                    return {{
                        pane: '{pane_names["tubes"]}',
                        opacity: 1,
                        color: 'rgba(141,90,153,1.0)',
                        dashArray: '8.0,4.0',
                        lineCap: 'round',
                        lineJoin: 'round',
                        weight: 2.0,
                        fillColor: 'rgba(141,90,153,1.0)',
                        fillOpacity: 0,
                        interactive: true
                    }};

                case 'unprotected':
                default:
                    return {{
                        pane: '{pane_names["unprotected"]}',
                        opacity: 1,
                        color: 'rgba(137,137,137,1.0)',
                        dashArray: '8.0,4.0',
                        lineCap: 'round',
                        lineJoin: 'round',
                        weight: 2.0,
                        fillColor: 'rgba(137,137,137,1.0)',
                        fillOpacity: 0,
                        interactive: true
                    }};
            }}
        }}
"""

    # Replace the generated style function and the single generated pane.
    style_and_pane_pattern = re.compile(
        rf"""
        \s*
        function\s+style_{re.escape(plantings_layer)}_0
        \(feature\)\s*\{{
            .*?
        \}}

        \s*
        map\.createPane\('pane_{re.escape(plantings_layer)}'\);
        \s*
        map\.getPane\('pane_{re.escape(plantings_layer)}'\)
            \.style\.zIndex\s*=\s*\d+\s*;
        \s*
        map\.getPane\('pane_{re.escape(plantings_layer)}'\)
            \.style\[['"]mix-blend-mode['"]\]\s*=\s*['"]normal['"]\s*;
        """,
        re.DOTALL | re.VERBOSE,
    )

    html, style_count = style_and_pane_pattern.subn(
        "\n" + style_function + "\n" + pane_code,
        html,
        count=1,
    )

    print(
        f"Added protection-specific panes for {plantings_layer}: "
        f"{style_count} replacement(s)"
    )

    if style_count == 0:
        raise RuntimeError(
            f"Could not replace the style function and pane for "
            f"{plantings_layer}."
        )

    # Remove the shared pane from the GeoJSON constructor. A shared pane here
    # can override the pane returned by the feature style function.
    layer_constructor_pattern = re.compile(
        rf"""
        (
            var\s+layer_{re.escape(plantings_layer)}
            \s*=\s*new\s+L\.geoJson
            \(
                json_{re.escape(plantings_layer)},
                \s*\{{
                .*?
                layerName:\s*['"]layer_{re.escape(plantings_layer)}['"],
        )
        \s*
        pane:\s*['"]pane_{re.escape(plantings_layer)}['"],
        """,
        re.DOTALL | re.VERBOSE,
    )

    html, pane_count = layer_constructor_pattern.subn(
        r"\1",
        html,
        count=1,
    )

    print(
        f"Removed shared GeoJSON pane from {plantings_layer}: "
        f"{pane_count} replacement(s)"
    )

    if pane_count == 0:
        raise RuntimeError(
            f"Could not remove the shared pane from layer_{plantings_layer}."
        )

    return html


def style_leaflet_legend(html: str) -> str:
    css = """
    <style id="rewild-legend-styles">

    /* Overall legend */
    .leaflet-control-layers {
        font-size: 13px;
        margin-top: 1px !important;
    }

    /* Legend contents */
    .leaflet-control-layers-list {
        font-size: 13px;
    }
    
    /* Layer names */
    .leaflet-control-layers label {
        font-size: 13px;
    }

    /* Nested tree entries */
    .leaflet-layerstree-header-name,
    .leaflet-layerstree-node-label {
        font-size: 12px !important;
    }

    /* Legend icons */
    .leaflet-control-layers img {
        width: 14px !important;
        height: 14px !important;
        margin-right: 4px;
        vertical-align: middle;
    }

    /* Checkboxes */
    .leaflet-control-layers-selector {
        transform: scale(0.85);
        margin-right: 4px;
    }


    .leaflet-control-layers-expanded {
        width: 255px;
    }

    /* Reduce spacing */
    .leaflet-control-layers-overlays label {
        margin-bottom: 3px;
    }

    </style>
    """

    return html.replace("</head>", css + "\n</head>", 1)

# =========================================================================
# Keep planting selection lightweight
# =========================================================================

def disable_planting_detail_popup(
    html: str,
    plantings_layer: str,
) -> str:
    """
    Prevent qgis2web's full planting popup from opening.

    The lightweight hover tooltip remains available. Clicking a planting:
    - sends the planting data to the parent Dash page;
    - keeps/reopens the lightweight tooltip;
    - scrolls the parent page to the detail panel below the map.
    """

    function_pattern = re.compile(
        rf"""
        (
            function\s+pop_{re.escape(plantings_layer)}
            \(feature,\s*layer\)\s*\{{
        )
        (?P<body>.*?)
        (
            \n\s*\}}
            \n
            \s*function\s+style_{re.escape(plantings_layer)}_0
        )
        """,
        re.DOTALL | re.VERBOSE,
    )

    match = function_pattern.search(html)

    if not match:
        raise RuntimeError(
            f"Could not find pop_{plantings_layer}(feature, layer)."
        )

    body = match.group("body")

    # Remove only the qgis2web popup binding inside the planting function.
    body, bind_count = re.subn(
        r"""
        \s*
        layer\.on\(
            ['"]popupopen['"],
            \s*
            function\(e\)\s*\{
                .*?
            \}
        \);
        \s*
        layer\.bindPopup\(
            content,
            \s*
            \{\s*maxHeight:\s*400\s*\}
        \);
        """,
        "\n",
        body,
        count=1,
        flags=re.DOTALL | re.VERBOSE,
    )

    if bind_count == 0:
        # Fallback for slightly different qgis2web formatting.
        body, bind_count = re.subn(
            r"""
            \s*
            layer\.bindPopup\(
                content,
                \s*
                \{\s*maxHeight:\s*400\s*\}
            \);
            """,
            "\n",
            body,
            count=1,
            flags=re.DOTALL | re.VERBOSE,
        )

    print(
        f"Removed full planting popup binding from {plantings_layer}: "
        f"{bind_count} replacement(s)"
    )

    if bind_count == 0:
        raise RuntimeError(
            f"Could not remove the popup binding from {plantings_layer}."
        )

    # Enhance the planting click handler that was added by
    # add_parent_message_bridge().
    click_pattern = re.compile(
        r"""
        layer\.on\(
            ['"]click['"],
            \s*
            function\(\)\s*\{
                \s*
                var\s+message\s*=\s*\{
                    \s*
                    source:\s*['"]rewild-qgis-map['"],
                    \s*
                    featureType:\s*['"]planting['"],
                    \s*
                    properties:\s*feature\.properties,
                    \s*
                    sentAt:\s*Date\.now\(\)
                \s*
                \};
                .*?
                window\.parent\.postMessage\(
                    \s*
                    message,
                    \s*
                    ['"]\*['"]
                \s*
                \);
            \s*
            \}
        \);
        """,
        re.DOTALL | re.VERBOSE,
    )

    enhanced_click = """
            layer.on('click', function() {
                var message = {
                    source: 'rewild-qgis-map',
                    featureType: 'planting',
                    properties: feature.properties,
                    sentAt: Date.now()
                };

                /*
                 * Keep the compact planting tooltip visible instead of
                 * opening qgis2web's full table popup.
                 */
                if (typeof layer.closePopup === 'function') {
                    layer.closePopup();
                }

                if (typeof layer.openTooltip === 'function') {
                    layer.openTooltip();
                }

                console.log(
                    'Sending planting selection to Dash:',
                    message
                );

                /*
                 * Send the selected properties directly into the Dash
                 * dcc.Store so the detailed panel callback runs.
                 */
                try {
                    if (
                        window.parent
                        && window.parent.dash_clientside
                        && typeof window.parent.dash_clientside.set_props
                            === 'function'
                    ) {
                        window.parent.dash_clientside.set_props(
                            'selected-map-feature',
                            {data: message}
                        );
                    }
                } catch (error) {
                    console.warn(
                        'Could not update the Dash feature store directly:',
                        error
                    );
                }

                /* Retain postMessage as a compatibility fallback. */
                window.parent.postMessage(
                    message,
                    '*'
                );

                /*
                 * The map iframe and Dash page are served from the same
                 * application, so scroll directly to the detail panel.
                 * The postMessage fallback also lets parent-side code handle
                 * this later if the hosting arrangement changes.
                 */
                window.parent.postMessage(
                    {
                        source: 'rewild-qgis-map',
                        action: 'scroll-to-project-details'
                    },
                    '*'
                );

                window.setTimeout(
                    function() {
                        try {
                            var detailPanel =
                                window.parent.document.getElementById(
                                    'project-detail-panel'
                                );

                            if (detailPanel) {
                                detailPanel.scrollIntoView({
                                    behavior: 'smooth',
                                    block: 'start'
                                });
                            }
                        } catch (error) {
                            console.warn(
                                'Could not scroll parent page to details:',
                                error
                            );
                        }
                    },
                    100
                );
            });
"""

    body, click_count = click_pattern.subn(
        enhanced_click,
        body,
        count=1,
    )

    print(
        f"Updated lightweight planting click behaviour: "
        f"{click_count} replacement(s)"
    )

    if click_count == 0:
        raise RuntimeError(
            "Could not find the generated planting click handler. "
            "Make sure disable_planting_detail_popup() runs after "
            "add_parent_message_bridge()."
        )

    replacement = (
        match.group(1)
        + body
        + match.group(3)
    )

    return (
        html[:match.start()]
        + replacement
        + html[match.end():]
    )


def patch_map_layout_and_initial_view(html: str) -> str:
    """
    Make the Leaflet map fill its iframe and force a stable County Wicklow
    starting extent.

    This handles both qgis2web map declarations:
      - exports containing `var crs = ...`
      - ordinary Leaflet exports containing only `var map = ...`

    It also disables leaflet-hash restoration. Otherwise a URL fragment such
    as `#18/53.18/-6.27` can override fitBounds() and reopen the map extremely
    zoomed in.
    """

    responsive_css = """
        <style id="rewild-responsive-map">
            html,
            body {
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                overflow: hidden;
            }

            #map {
                width: 100% !important;
                height: 100% !important;
                min-height: 100%;
                margin: 0;
                padding: 0;
            }
        </style>
"""

    # Remove qgis2web's fixed pixel dimensions, regardless of the numbers.
    html, fixed_css_count = re.subn(
        r"""
        <style>\s*
        \#map\s*\{\s*
            width:\s*[^;]+;\s*
            height:\s*[^;]+;\s*
        \}\s*
        </style>
        """,
        responsive_css,
        html,
        count=1,
        flags=re.DOTALL | re.VERBOSE,
    )

    if fixed_css_count == 0:
        if "</head>" not in html:
            raise RuntimeError("Could not find </head> to add responsive map CSS.")

        html = html.replace(
            "</head>",
            responsive_css + "\n    </head>",
            1,
        )

    print(
        "Made map responsive: "
        f"{fixed_css_count if fixed_css_count else 1} patch(es)"
    )

    map_block = """
        var map = L.map('map', {
            zoomControl: false,
            maxZoom: 20,
            minZoom: 1
        });

        var rewildInitialBounds = L.latLngBounds(
            [52.64062730567451, -7.0611765937028785],
            [53.282235869183104, -5.799805104021357]
        );

        map.fitBounds(rewildInitialBounds, {
            padding: [24, 24],
            animate: false
        });
"""

    # Match the map declaration itself. Do not require a preceding CRS block.
    map_pattern = re.compile(
        r"""
        var\s+map\s*=\s*L\.map\(
            ['"]map['"],
            \s*\{
                .*?
            \}
        \)
        \s*
        (?:\.fitBounds\(
            .*?
        \))?
        \s*;
        """,
        re.DOTALL | re.VERBOSE,
    )

    html, map_count = map_pattern.subn(
        map_block,
        html,
        count=1,
    )

    print(
        "Replaced initial Leaflet map extent: "
        f"{map_count} replacement(s)"
    )

    if map_count == 0:
        raise RuntimeError(
            "Could not find the generated `var map = L.map(...)` block."
        )

    # Leaflet-hash can restore an old zoom/centre from the address fragment
    # after fitBounds(), making the map look as though the extent patch failed.
    html, hash_count = re.subn(
        r"\s*var\s+hash\s*=\s*new\s+L\.Hash\(map\)\s*;",
        """
        /*
         * Do not restore a previous map zoom from the URL hash.
         * Clear any stale qgis2web map fragment without reloading the page.
         */
        if (window.location.hash) {
            window.history.replaceState(
                null,
                document.title,
                window.location.pathname + window.location.search
            );
        }
""",
        html,
        count=1,
    )

    print(
        "Disabled stale URL-hash zoom restoration: "
        f"{hash_count} replacement(s)"
    )

    resize_code = """
        /*
         * Leaflet may initialise before the iframe has its final dimensions.
         * Recalculate the map size and reapply the overview after layout.
         */
        function resetRewildMapView() {
            map.invalidateSize(false);
            map.fitBounds(rewildInitialBounds, {
                padding: [24, 24],
                animate: false
            });
        }

        window.addEventListener('load', function() {
            window.setTimeout(resetRewildMapView, 0);
            window.setTimeout(resetRewildMapView, 150);
            window.setTimeout(resetRewildMapView, 500);
        });

        window.addEventListener('resize', function() {
            map.invalidateSize(false);
        });
"""

    insertion_point = "map.attributionControl.setPrefix"

    if insertion_point not in html:
        raise RuntimeError(
            "Could not find the attribution-control insertion point."
        )

    html = html.replace(
        insertion_point,
        resize_code + "\n        " + insertion_point,
        1,
    )

    print("Added iframe resize and initial-view reset")

    return html

def remove_qgis2web_label_engine(html: str) -> str:
    """
    Remove only qgis2web's labelgun-based permanent-label system.

    This deliberately preserves:
    - overlaysTree
    - L.control.layers.tree(...)
    - lay.addTo(map)
    - the visible map legend/layer selector
    """

    # ---------------------------------------------------------------
    # 1. Remove only the three label-engine script tags
    # ---------------------------------------------------------------
    scripts = (
        "rbush.min.js",
        "labelgun.min.js",
        "labels.js",
    )

    for script_name in scripts:
        pattern = re.compile(
            rf"""
            \s*
            <script
                \s+
                src=["']js/{re.escape(script_name)}["']
            ></script>
            """,
            re.VERBOSE,
        )

        html, count = pattern.subn("", html)

        print(
            f"Removed {script_name}: "
            f"{count} replacement(s)"
        )

    # ---------------------------------------------------------------
    # 2. Remove layer label-registration blocks individually
    #
    # Typical qgis2web output:
    #
    # var i = 0;
    # layer_Sites_2.eachLayer(function(layer) {
    #     labels.push(layer);
    #     totalMarkers += 1;
    #     layer.added = true;
    #     addLabel(layer, i);
    #     i++;
    # });
    # ---------------------------------------------------------------
    registration_pattern = re.compile(
        r"""
        \s*
        var\s+i\s*=\s*0\s*;
        \s*
        layer_[A-Za-z0-9_]+
        \.eachLayer
        \(
            function\s*
            \(\s*layer\s*\)
            \s*
            \{
                (?:
                    (?!\}\s*\);)
                    .
                )*?
                addLabel
                \(
                    \s*layer\s*,
                    \s*i\s*
                \)
                \s*;
                (?:
                    (?!\}\s*\);)
                    .
                )*?
            \}
        \);
        """,
        re.DOTALL | re.VERBOSE,
    )

    html, registration_count = registration_pattern.subn(
        "",
        html,
    )

    print(
        "Removed label registration blocks: "
        f"{registration_count} replacement(s)"
    )

    # ---------------------------------------------------------------
    # 3. Neutralize resetLabels instead of deleting surrounding blocks
    #
    # This is safer than matching entire map.on(...) handlers because those
    # handlers can sit close to the legend code in qgis2web exports.
    # ---------------------------------------------------------------
    html, reset_count = re.subn(
        r"""
        resetLabels
        \(
            \s*
            \[
                .*?
            \]
            \s*
        \)
        \s*;
        """,
        "/* qgis2web label reset removed */",
        html,
        flags=re.DOTALL | re.VERBOSE,
    )

    print(
        "Neutralized resetLabels calls: "
        f"{reset_count} replacement(s)"
    )

    # ---------------------------------------------------------------
    # 4. Validate that the legend survived
    # ---------------------------------------------------------------
    required_legend_fragments = (
        "var overlaysTree =",
        "L.control.layers.tree",
        "lay.addTo(map)",
    )

    missing = [
        fragment
        for fragment in required_legend_fragments
        if fragment not in html
    ]

    if missing:
        raise RuntimeError(
            "The label patch unexpectedly damaged the map legend. "
            "Missing: "
            + ", ".join(missing)
        )

    print("Verified that the map legend remains intact")

    return html


# =========================================================================
# Disable interaction and popups for all background/reference layers
# =========================================================================

def disable_non_project_layer_popups(
    html: str,
    allowed_layers: set[str],
) -> str:
    """
    Keep only Sites and Plantings interactive.

    For every other qgis2web GeoJSON layer this patch:
    - removes its generated ``onEachFeature: pop_<layer>`` hook, so no popup
      is bound;
    - changes the GeoJSON constructor to ``interactive: false``;
    - changes any generated style return values to ``interactive: false``.

    Making reference polygons non-interactive also prevents County Wicklow,
    the national park, and future background layers from intercepting clicks
    intended for Sites or Plantings. The layers remain visible and can still
    be switched on and off in the legend.
    """

    all_layers = set(re.findall(
        r"var\s+layer_([A-Za-z0-9_]+)\s*=\s*new\s+L\.geoJson",
        html,
    ))

    disabled_layers = sorted(all_layers - set(allowed_layers))

    for layer_name in disabled_layers:
        # Remove the callback that binds the qgis2web popup.
        html, popup_count = re.subn(
            rf"\s*onEachFeature:\s*pop_{re.escape(layer_name)},",
            "",
            html,
            count=1,
        )

        # Make the GeoJSON layer itself ignore pointer events.
        constructor_pattern = re.compile(
            rf"(var\s+layer_{re.escape(layer_name)}\s*=\s*new\s+"
            rf"L\.geoJson\(.*?\{{)(.*?)(\n\s*\}}\);)",
            re.DOTALL,
        )

        constructor_match = constructor_pattern.search(html)
        constructor_count = 0

        if constructor_match:
            constructor_body = constructor_match.group(2)
            constructor_body, constructor_count = re.subn(
                r"interactive:\s*true",
                "interactive: false",
                constructor_body,
                count=1,
            )

            html = (
                html[:constructor_match.start()]
                + constructor_match.group(1)
                + constructor_body
                + constructor_match.group(3)
                + html[constructor_match.end():]
            )

        # Also update all style branches belonging to this layer.
        style_pattern = re.compile(
            rf"(function\s+style_{re.escape(layer_name)}(?:_[0-9]+)?"
            rf"\s*\([^)]*\)\s*\{{.*?)(?=\n\s*map\.createPane"
            rf"\('pane_{re.escape(layer_name)}'\);)",
            re.DOTALL,
        )

        def disable_style_interaction(match: re.Match) -> str:
            return re.sub(
                r"interactive:\s*true",
                "interactive: false",
                match.group(1),
            )

        html, style_count = style_pattern.subn(
            disable_style_interaction,
            html,
            count=1,
        )

        print(
            f"Disabled popup/interactions for {layer_name}: "
            f"popup hook={popup_count}, constructor={constructor_count}, "
            f"style block={style_count}"
        )

    return html

# =========================================================================
# Public-site privacy and compact site popup
# =========================================================================

def sanitize_public_sites_data(export_dir: Path, sites_layer: str) -> None:
    """Remove private/internal attributes from browser-delivered site data."""
    data_path = export_dir / "data" / f"{sites_layer}.js"
    if not data_path.exists():
        raise RuntimeError(f"Could not find public site data file: {data_path}")

    source = data_path.read_text(encoding="utf-8")
    prefix_match = re.match(
        rf"\s*var\s+json_{re.escape(sites_layer)}\s*=\s*",
        source,
    )
    if not prefix_match:
        raise RuntimeError(f"Could not parse {data_path.name}.")

    json_text = source[prefix_match.end():].strip()
    if json_text.endswith(";"):
        json_text = json_text[:-1].rstrip()
    collection = json.loads(json_text)

    safe_fields = (
        "Name", "Description", "Local Group", "Date of First Activity",
        "Management Type", "Activity Type", "last_visited",
        "display_name", "Rewild Site Code",
    )
    private_count = 0

    for feature in collection.get("features", []):
        properties = feature.get("properties") or {}
        is_private = str(properties.get("Local Group") or "").strip().casefold() == "private landowner"
        sanitized = {
            key: properties.get(key)
            for key in safe_fields
            if properties.get(key) not in (None, "")
        }

        if is_private:
            private_count += 1
            public_code = (
                properties.get("display_name")
                or properties.get("Rewild Site Code")
                or "Private restoration site"
            )
            activity = str(properties.get("Activity Type") or "habitat restoration").strip().lower()
            sanitized.update({
                "Name": public_code,
                "display_name": public_code,
                "Local Group": "Private land",
                "Description": (
                    f"A privately hosted {activity} project supported by "
                    "ReWild Wicklow. Exact access and landowner details are not published."
                ),
            })

        feature["properties"] = sanitized

    output = (
        f"var json_{sites_layer} = "
        + json.dumps(collection, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    data_path.write_text(output, encoding="utf-8")
    print(
        f"Sanitized {data_path.name}: "
        f"{len(collection.get('features', []))} site(s), "
        f"{private_count} private site(s) anonymized"
    )


def replace_site_detail_popup(html: str, sites_layer: str) -> str:
    """Replace qgis2web's long attribute table with a compact public card."""
    popup_code = r'''

            var publicSite = feature.properties || {};
            var publicSiteName = escapeHoverText(
                publicSite['display_name'] || publicSite['Name'] || 'ReWild Wicklow site'
            );
            var publicActivity = titleCaseHoverText(publicSite['Activity Type']);
            var publicDescription = escapeHoverText(publicSite['Description']);
            var publicPartner = escapeHoverText(publicSite['Local Group']);
            var publicFirstActivity = formatHoverDate(publicSite['Date of First Activity']);
            var publicLastVisited = formatHoverDate(publicSite['last_visited']);

            var publicPopupContent =
                '<div class="rw-site-popup">' +
                    '<div class="rw-site-popup-kicker">ReWild Wicklow site</div>' +
                    '<div class="rw-site-popup-title">' + publicSiteName + '</div>' +
                    (publicActivity ? '<div class="rw-site-popup-tag">' + escapeHoverText(publicActivity) + '</div>' : '') +
                    (publicDescription ? '<div class="rw-site-popup-description">' + publicDescription + '</div>' : '') +
                    '<div class="rw-site-popup-grid">' +
                        (publicPartner ? '<div><span>Working with</span>' + publicPartner + '</div>' : '') +
                        (publicFirstActivity ? '<div><span>Active since</span>' + publicFirstActivity + '</div>' : '') +
                        (publicLastVisited ? '<div><span>Latest visit</span>' + publicLastVisited + '</div>' : '') +
                    '</div>' +
                    '<div class="rw-site-popup-note">Private contact, access and land records are not shown.</div>' +
                '</div>';

            layer.unbindPopup();
            layer.bindPopup(publicPopupContent, {
                maxWidth: 340,
                minWidth: 250,
                className: 'rw-site-leaflet-popup'
            });
'''
    pattern = re.compile(
        rf"(function\s+pop_{re.escape(sites_layer)}\(feature,\s*layer\)\s*\{{)"
        rf"(.*?)(\n\s*\}}\n\s*function\s+style_{re.escape(sites_layer)}_0)",
        re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        raise RuntimeError(f"Could not find pop_{sites_layer}(feature, layer).")

    return (
        html[:match.start()] + match.group(1) + match.group(2) + popup_code
        + match.group(3) + html[match.end():]
    )


def add_site_popup_css(html: str) -> str:
    css = r'''
        <style id="rewild-site-popup-styles">
            .rw-site-leaflet-popup .leaflet-popup-content-wrapper {
                border-radius: 14px;
                border: 1px solid #dce7d8;
                box-shadow: 0 12px 32px rgba(47, 74, 42, 0.22);
            }
            .rw-site-leaflet-popup .leaflet-popup-content { margin: 0; width: 350px !important; }
            .rw-site-popup { 
                width: 340px;
                box-sizing: border-box;
                padding: 18px 20px;
                color: #42563d;
                font-family: Arial, Helvetica, sans-serif;
                line-height: 1.5;
            }
            .rw-site-popup-kicker { margin-bottom: 3px; color: #82907d; font-size: 10px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; }
            .rw-site-popup-title { color: #35552f; font-size: 18px; font-weight: 750; line-height: 1.2; }
            .rw-site-popup-tag { display: inline-block; margin-top: 8px; padding: 4px 8px; border-radius: 999px; background: #edf4e9; color: #587050; font-size: 11px; font-weight: 700; }
            .rw-site-popup-description { margin-top: 11px; font-size: 13px; white-space: pre-line; }
            .rw-site-popup-grid { display: grid; gap: 7px; margin-top: 13px; padding-top: 11px; border-top: 1px solid #e5ece2; font-size: 12px; }
            .rw-site-popup-grid div { display: grid; grid-template-columns: 105px 1fr; gap: 8px; }
            .rw-site-popup-grid span { color: #7b8d76; font-weight: 700; }
            .rw-site-popup-note { margin-top: 12px; color: #81907d; font-size: 10.5px; font-style: italic; }
        </style>
'''
    if "</head>" not in html:
        raise RuntimeError("Could not find </head> for site popup CSS.")
    return html.replace("</head>", css + "\n    </head>", 1)

def patch_common(original_html: str) -> tuple[str, str]:
    html = original_html

    sites_match = re.search(r"markers/Sites_(\d+)\.svg", html)
    if not sites_match:
        raise RuntimeError("Could not find markers/Sites_<number>.svg in index.html")

    sites_id = sites_match.group(1)
    sites_layer = f"Sites_{sites_id}"
    print(f"Detected Sites layer: {sites_layer}")

    html = patch_map_layout_and_initial_view(html)

    html = re.sub(
        r"function style_WicklowMountainsNationalPark_1_0\(\) \{.*?\n\s*\}",
        """function style_WicklowMountainsNationalPark_1_0() {
            return {
                pane: 'pane_WicklowMountainsNationalPark_1',
                opacity: 1,
                color: 'rgba(80,150,80,1.0)',
                weight: 2,
                fillOpacity: 0,
                interactive: false,
            }
        """,
        html,
        flags=re.S,
    )

    html = re.sub(
        r"function style_CountyWicklow_2_0\(\) \{.*?\n\s*\}",
        """function style_CountyWicklow_2_0() {
            return {
                pane: 'pane_CountyWicklow_2',
                opacity: 1,
                color: 'rgba(159,203,152,1.0)',
                weight: 2,
                fillOpacity: 0,
                interactive: false,
            }
        """,
        html,
        flags=re.S,
    )

    js_icon_map = "{\n" + ",\n".join(
        f"                '{key}': '{value}'"
        for key, value in SITE_ICON_MAP.items()
    ) + "\n            }"

    new_style_function = f"""
        function style_{sites_layer}_0(feature) {{
            var managementType = String(feature.properties['Management Type'] || '').trim().toLowerCase();

            var iconFile = {js_icon_map}[managementType] || 'tree_purple.svg';

            return {{
                pane: 'pane_{sites_layer}',
                rotationAngle: 0.0,
                rotationOrigin: 'center center',
                icon: L.icon({{
                    iconUrl: 'markers/' + iconFile,
                    iconSize: [19.0, 19.0],
                    iconAnchor: [9.5, 9.5],
                    popupAnchor: [0, -9.5]
                }}),
                interactive: true,
            }};
        }}
"""

    html, n = re.subn(
        rf"\s*function style_{sites_layer}_0\(feature\) \{{.*?\n\s*map\.createPane\('pane_{sites_layer}'\);",
        new_style_function + f"\n        map.createPane('pane_{sites_layer}');",
        html,
        flags=re.S,
    )
    print(f"Updated {sites_layer} style function: {n} replacement(s)")

    for label, svg in LEGEND_ICON_MAP.items():
        pattern = rf'<img src="legend/{sites_layer}_[^"]*"\s*/></td><td>{re.escape(label)}</td>'
        replacement = rf'<img src="markers/{svg}" style="width:19px;height:19px;" /></td><td>{label}</td>'
        html, n = re.subn(pattern, replacement, html)
        print(f"Updated legend icon for {label}: {n} replacement(s)")

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
        

    print("\n--- Disabling background-layer popups ---")

    html = disable_non_project_layer_popups(
        html,
        {layers["sites"], layers["plantings"]},
    )

    print("\n--- Removing qgis2web label engine ---")

    html = remove_qgis2web_label_engine(html)

    print("\n--- Patching planting layer order ---")

    html = patch_planting_panes(
        html,
        layers["plantings"],
    )

    print("\n--- Patching hover interactions ---")

    html = patch_safe_highlight_function(html)

    # html = add_iframe_scroll_bridge(html) # was added bc i was dumb but might be useful later

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

    html = add_parent_message_bridge(
        html,
        layers["sites"],
        layers["plantings"],
    )

    html = replace_site_detail_popup(html, layers["sites"])
    html = add_site_popup_css(html)

    html = disable_planting_detail_popup(
        html,
        layers["plantings"],
    )

    html = keep_plantings_visible(
        html,
        layers["plantings"],
    )

    html = style_leaflet_legend(html)

    html = add_hover_css(html)

    return html, sites_layer, layers



def apply_basemap(html: str, basemap: dict, layers: dict) -> str:
    label = basemap["label"]
    url = basemap["url"]
    attribution = basemap["attribution"]
    max_zoom = basemap["max_zoom"]
    add_topography_overlay = basemap.get("add_topography_overlay", False)

    # Remove the basemap created by qgis2web
    html = re.sub(
        r"\s*map\.createPane\('pane_[A-Za-z0-9_]+Basemap_0'\);.*?map\.addLayer\(layer_[A-Za-z0-9_]+Basemap_0\);",
        "",
        html,
        flags=re.S,
    )

    html = re.sub(
        r"\s*map\.createPane\('pane_OSMStandard_0'\);.*?map\.addLayer\(layer_OSMStandard_0\);",
        "",
        html,
        flags=re.S,
    )

    # Define chosen basemap
    basemap_js = f"""
        map.createPane('pane_Basemap_0');
        map.getPane('pane_Basemap_0').style.zIndex = 200;

        var layer_Basemap_0 = L.tileLayer('{url}', {{
            pane: 'pane_Basemap_0',
            opacity: 1.0,
            attribution: '{attribution}',
            minZoom: 1,
            maxZoom: {max_zoom},
            minNativeZoom: 0,
            maxNativeZoom: {max_zoom}
        }});

        map.addLayer(layer_Basemap_0);
"""

    if add_topography_overlay:
        basemap_js += """
        map.createPane('pane_Topography_0');
        map.getPane('pane_Topography_0').style.zIndex = 250;

        var layer_Topography_0 = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
            pane: 'pane_Topography_0',
            opacity: 0.38,
            attribution: 'Map data © OpenStreetMap contributors, SRTM | Map style © OpenTopoMap',
            minZoom: 1,
            maxZoom: 17,
            minNativeZoom: 0,
            maxNativeZoom: 17
        });
"""

    html = html.replace(
        "var bounds_group = new L.featureGroup([]);",
        "var bounds_group = new L.featureGroup([]);\n" + basemap_js,
    )

    # Remove old basemap entries from the layer selector
    html = re.sub(
        r"\s*\{label:\s*[\"'][^\"']*(OSM Standard|Carto Voyager|Carto Positron|OpenTopoMap|Esri World Imagery|Topographic Overlay)[^\"']*[\"'],\s*layer:\s*layer_[A-Za-z0-9_]+\},?",
        "",
        html,
    )

    # Add basemap to the layer selector
    
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



original_html = INDEX.read_text(encoding="utf-8")
common_html, sites_layer, layers = patch_common(original_html)

# Remove private/internal values from the browser-delivered dataset itself.
sanitize_public_sites_data(EXPORT_DIR, layers["sites"])


for key, basemap in BASEMAPS.items():
    output_html = apply_basemap(common_html, basemap, layers)
    output_path = EXPORT_DIR / basemap["file"]
    output_path.write_text(output_html, encoding="utf-8")
    print(f"Created {output_path}")

print("Done. Original index.html was not overwritten.")