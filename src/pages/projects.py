import json
from datetime import datetime
from pathlib import Path

import dash
from dash import Input, Output, callback, dcc, html
import pandas as pd
import plotly.graph_objects as go
from pathlib import PurePosixPath


dash.register_page(__name__, path="/projects")


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
MANAGEMENT_LABELS = {
    "regular": "Regular visits from ReWild Wicklow",
    "sporadic": "Sporadic visits from ReWild Wicklow; monitored locally",
    "annual": "Annual visit from ReWild Wicklow; maintained locally",
    "never": "No visits required",
}

TIMELINE_PLANTINGS_FILE = Path("src/assets/qgis-map/data/Plantings_3.js")

PHOTO_INDEX_FILE = Path("src/assets/qgis-map/data/planting_photo_index.js")


# This is the browser URL corresponding to PHOTO_INDEX_FILE.parent.
PHOTO_INDEX_URL_BASE = ""

TREE_MARKERS_PATH = "/assets/markers"

PHOTO_TYPE_ORDER = {
    "planting": 0,
    "growth": 1,
    "observation": 2,
    "visit": 3,
    "maintenance": 4,
    "monitoring": 5,
}

TREE_SPECIES = {
    "alder": {
        "label": "Alder",
        "filename": "alder.png",
    },
    "birch": {
        "label": "Birch",
        "filename": "birch.png",
    },
    "blackthorn": {
        "label": "Blackthorn",
        "filename": "blackthorn.png",
    },
    "crab-apple": {
        "label": "Crab Apple",
        "filename": "crab-apple.png",
    },
    "guelder-rose": {
        "label": "Guelder-Rose",
        "filename": "guelder-rose.png",
    },
    "hawthorn": {
        "label": "Hawthorn",
        "filename": "hawthorn.png",
    },
    "hazel": {
        "label": "Hazel",
        "filename": "hazel.png",
    },
    "holly": {
        "label": "Holly",
        "filename": "holly.png",
    },
    "oak": {
        "label": "Oak",
        "filename": "oak.png",
    },
    "rowan": {
        "label": "Rowan",
        "filename": "rowan.png",
    },
    "scots-pine": {
        "label": "Scots Pine",
        "filename": "scots-pine.png",
    },
    "wild-cherry": {
        "label": "Wild Cherry",
        "filename": "wild-cherry.png",
    },
    "willow": {
        "label": "Willow",
        "filename": "willow.png",
    },
}

PHOTO_TYPE_LABELS = {
    "planting": "Planting",
    "maintenance": "Maintenance",
    "observation": "Observation",
    "visit": "Visit",
    "monitoring": "Monitoring",
    "growth": "Growth update",
}

# ---------------------------------------------------------------------
# Data loading and timeline preparation
# ---------------------------------------------------------------------
def load_qgis2web_features(file_path):
    """Load features from a qgis2web JavaScript-wrapped GeoJSON file."""
    try:
        raw_content = Path(file_path).read_text(encoding="utf-8")
        json_start = raw_content.find("{")
        json_end = raw_content.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            return []

        data = json.loads(raw_content[json_start:json_end])
        return data.get("features", [])
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not load timeline data from {file_path}: {exc}")
        return []

def load_photo_index(file_path):
    """Load records from the generated planting_photo_index.js file."""
    try:
        raw_content = Path(file_path).read_text(encoding="utf-8")

        json_start = raw_content.find("{")
        json_end = raw_content.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            return []

        data = json.loads(raw_content[json_start:json_end])
        return data.get("records", [])

    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not load photo index from {file_path}: {exc}")
        return []
    
def photo_record_src(record):
    """
    Convert an indexed path such as:

        data/20260802/visit-photos/photo.jpg

    into:

        /assets/qgis-map/data/20260802/visit-photos/photo.jpg
    """
    image_path = (
        str(record.get("image_path") or "")
        .replace("\\", "/")
        .strip()
        .lstrip("/")
    )

    if not image_path:
        return None

    if image_path.startswith(("http://", "https://")):
        return image_path

    return f"/assets/qgis-map/{image_path}"

def build_timeline_events(features):
    """Create one timeline row for every recorded planting and visit date."""
    events = []

    for feature in features:
        properties = feature.get("properties") or {}
        planting_name = properties.get("Name") or "Unnamed planting"
        site_id = properties.get("Site")

        for field_name, event_label in (
            ("First Planted", "First Planted"),
            ("last_visited", "Latest Visit"),
        ):
            raw_date = properties.get(field_name)
            parsed_date = pd.to_datetime(raw_date, errors="coerce")

            if pd.isna(parsed_date):
                continue

            events.append(
                {
                    "Date": parsed_date,
                    "Event": event_label,
                    "Planting": planting_name,
                    "Site": site_id,
                }
            )

    if not events:
        return pd.DataFrame(columns=["Date", "Event", "Planting", "Site"])

    return pd.DataFrame(events).sort_values("Date").reset_index(drop=True)


PLANTING_FEATURES = load_qgis2web_features(TIMELINE_PLANTINGS_FILE)
TIMELINE_EVENTS = build_timeline_events(PLANTING_FEATURES)


def make_work_timeline(selected_properties):
    """Show all recorded work and highlight the selected planting's dates."""
    if TIMELINE_EVENTS.empty:
        return html.P(
            "No dated planting or maintenance records are available.",
            className="timeline-empty-message",
        )

    selected_name = str(selected_properties.get("Name") or "").strip()
    selected_site = str(selected_properties.get("Site") or "").strip()

    events = TIMELINE_EVENTS.copy()
    events["Selected"] = events["Planting"].astype(str).str.strip().eq(selected_name)

    timeline_start = pd.Timestamp(events["Date"].min().year, 1, 1)
    timeline_end   = pd.Timestamp(events["Date"].max().year + 1, 1, 1)

    # Site ID is a useful fallback if the feature name changes slightly.
    if selected_site:
        name_matches = events["Selected"]
        site_matches = events["Site"].astype(str).str.strip().eq(selected_site)
        events["Selected"] = name_matches | (
            site_matches
            & events["Date"].isin(
                pd.to_datetime(
                    [
                        selected_properties.get("First Planted"),
                        selected_properties.get("last_visited"),
                    ],
                    errors="coerce",
                )
            )
        )

    other_events = events.loc[~events["Selected"]]
    selected_events = events.loc[events["Selected"]]

    fig = go.Figure()

    # The horizontal spine behind the points.
    fig.add_shape(
        type="line",
        x0=timeline_start,
        x1=timeline_end,
        y0=0,
        y1=0,
        line={"color": "#b7c7b2", "width": 3},
        layer="below",
    )

    fig.add_trace(
        go.Scatter(
            x=other_events["Date"],
            y=[0] * len(other_events),
            mode="markers",
            name="ReWild Plantings",
            marker={
                "size": 9,
                "color": "#b9c5b5",
                "line": {"width": 1, "color": "#ffffff"},
            },
            customdata=other_events[["Planting", "Event"]].to_numpy(),
            hovertemplate=(
                "<span style='font-size:11px;color:#a06489;'>"
                "%{customdata[1]}</span>"
                "<br>"
                "<b style='font-size:12px;'>%{customdata[0]}</b>"
                "<br>"
                "<span style='color:#71806d;'>"
                "%{x|%-d %B %Y}</span>"
                "<extra></extra>"
            ),
        )
    )

    if not selected_events.empty:

        fig.add_trace(
            go.Scatter(
                x=selected_events["Date"],
                y=[0] * len(selected_events),
                mode="markers",
                name="Selected Planting",
                marker={
                    "size": 9,
                    "color": "#b573a2",
                    "symbol": "diamond",
                    "line": {"width": 1, "color": "#ffffff"},
                },
                text=selected_events["Event"],
                textposition="top center",
                textfont={"size": 10, "color": "#3f5f38"},
                customdata=selected_events[["Planting", "Event"]].to_numpy(),
                hovertemplate=(
                    "<span style='font-size:11px;color:#a06489;'>"
                    "SELECTED PLANTING · %{customdata[1]}</span>"
                    "<br>"
                    "<b style='font-size:12px;'>%{customdata[0]}</b>"
                    "<br>"
                    "<span style='color:#71806d;'>"
                    "%{x|%-d %B %Y}</span>"
                    "<extra></extra>"
                ),
            )
        )

        selected_records = selected_events.to_dict("records")

        for index, event in enumerate(selected_records):
            event_name = event["Event"]

            # Push the two labels away from one another.
            if event_name == "First Planted":
                xanchor = "right"
                xshift = -8
            elif event_name == "Latest Visit":
                xanchor = "left"
                xshift = 8
            else:
                xanchor = "center"
                xshift = 0

            fig.add_annotation(
                x=event["Date"],
                y=0,
                text=event_name,
                showarrow=False,
                xanchor=xanchor,
                yanchor="bottom",
                xshift=xshift,
                yshift=12,
                font={
                    "size": 10,
                    "color": "#3f5f38",
                },
            )

    fig.update_layout(
        height=265,
        margin={"l": 25, "r": 25, "t": 55, "b": 25},

        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",

        hovermode="closest",

        # Dragging the graph now moves left and right.
        dragmode="pan",

        showlegend=True,

        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.08,
            "xanchor": "left",
            "x": 0,
            "font": {
                "size": 12,
                "color": "#52644d",
            },
        },

        # Controls the appearance of every hover popup.
        hoverlabel={
            "bgcolor": "#fff8f9",
            "bordercolor": "#d7a8c4",
            "font": {
                "family": "Arial, Helvetica, sans-serif",
                "size": 13,
                "color": "#42563d",
            },
            "align": "left",
            "namelength": -1,
        },

        xaxis={
            "title": None,
            "showgrid": False,
            "zeroline": False,
            "showline": False,

            "range": [timeline_start, timeline_end],

            "tickformat": "%Y",
            "dtick": "M12",

            "tickfont": {
                "size": 13,
                "color": "#52644d",
            },

            "ticks": "outside",
            "ticklen": 5,
            "tickwidth": 1,
            "tickcolor": "#9bad95",

            # Allows dragging and zooming.
            "fixedrange": False,
            "automargin": True,

            # Gives the user a draggable window below the timeline.
            "rangeslider": {
                "visible": True,
                "thickness": 0.16,
                "bgcolor": "#edf4e8",
                "bordercolor": "#d3e0cf",
                "borderwidth": 1,
            },

            # Handy preset time windows.
            "rangeselector": {
                "x": 1,
                "xanchor": "right",
                "y": 1.18,
                "yanchor": "top",
                "bgcolor": "#ffffff",
                "bordercolor": "#d6e2d1",
                "borderwidth": 1,
                "font": {
                    "size": 11,
                    "color": "#52644d",
                },
                "buttons": [
                    {
                        "count": 1,
                        "label": "1 year",
                        "step": "year",
                        "stepmode": "backward",
                    },
                    {
                        "count": 3,
                        "label": "3 years",
                        "step": "year",
                        "stepmode": "backward",
                    },
                    {
                        "label": "All",
                        "step": "all",
                    },
                ],
            },
        },

        yaxis={
            "visible": False,
            "range": [-0.08, 0.35],
            "fixedrange": True,
        },
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H4(
                                "ReWild Planting Timeline",
                                className="project-timeline-title",
                            ),
                            html.P(
                                "Explore planting and volunteer activity over time.",
                                className="project-timeline-description",
                            ),
                        ]
                    ),
                ],
                className="project-timeline-heading",
            ),

            dcc.Graph(
                figure=fig,
                config={
                    "displayModeBar": False,
                    "responsive": True,
                    "scrollZoom": True,
                    "displaylogo": False,
                },
                className="project-timeline-graph",
            ),

            html.Div(
                [
                    html.Span("↔", className="timeline-help-icon"),
                    html.Span(
                        "Drag to explore · scroll to zoom · double-click to reset",
                        className="timeline-help-text",
                    ),
                ],
                className="timeline-help",
            ),
        ],
        className="project-timeline",
    )


# ---------------------------------------------------------------------
# Photographic progress trail for a planting
# ---------------------------------------------------------------------
def get_planting_photo_records(planting_name):
    """Return all indexed photos belonging to one planting."""
    normalized_name = str(planting_name or "").strip().casefold()

    records = [
        record
        for record in PLANTING_PHOTO_RECORDS
        if str(
            record.get("planting_site_name") or ""
        ).strip().casefold() == normalized_name
    ]

    def sort_key(record):
        raw_date = record.get("date")
        parsed_date = pd.to_datetime(raw_date, errors="coerce")

        if pd.isna(parsed_date):
            parsed_date = pd.Timestamp.max

        photo_type = (
            str(record.get("photo_type") or "")
            .strip()
            .lower()
        )

        return (
            parsed_date,
            PHOTO_TYPE_ORDER.get(photo_type, 999),
        )

    return sorted(records, key=sort_key)


def render_photo_progress_story(planting_name):
    """
    Render a horizontal, chronological photographic story for one planting.
    """
    records = get_planting_photo_records(planting_name)

    if not records:
        return html.Div(
            [
                html.Div("Photo story", className="photo-story-eyebrow"),
                html.P(
                    "No photographic visits have been linked to this "
                    "planting yet.",
                    className="photo-story-empty",
                ),
            ],
            className="planting-photo-story planting-photo-story-empty",
        )

    dated_records = [
        record for record in records if record.get("date")
    ]

    latest_record = dated_records[-1] if dated_records else records[-1]

    cards = []

    for index, record in enumerate(records):
        photo_type = str(
            record.get("photo_type") or "visit"
        ).strip().lower()

        type_label = PHOTO_TYPE_LABELS.get(
            photo_type,
            format_text(photo_type) or "Visit",
        )

        image_src = photo_record_src(record)
        raw_date = record.get("date")
        is_latest = record is latest_record

        if not image_src:
            continue
        print(f"Rendering photo record for {planting_name}: {image_src} ({raw_date})")
        cards.append(
            html.Article(
                [
                    html.Div(
                        [
                            html.Img(
                                src=image_src,
                                alt=(
                                    f"{type_label} photograph of "
                                    f"{planting_name}"
                                ),
                                className="photo-story-image",
                            ),
                            (
                                html.Span(
                                    "Latest",
                                    className="photo-story-latest-badge",
                                )
                                if is_latest
                                else None
                            ),
                        ],
                        className="photo-story-image-wrap",
                    ),
                    html.Div(
                        [
                            html.Div(
                                format_date(raw_date) or "Date not recorded",
                                className="photo-story-date",
                            ),
                            html.Div(
                                (
                                    "First Planted"
                                    if photo_type == "planting"
                                    else type_label
                                ),
                                className="photo-story-card-title",
                            ),
                        ],
                        className="photo-story-card-copy",
                    ),
                ],
                className=(
                    "photo-story-card "
                    + (
                        "photo-story-card-latest"
                        if is_latest
                        else ""
                    )
                ),
            )
        )

    if not cards:
        return None

    return html.Section(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "Planting Photo Library",
                                className="photo-story-eyebrow",
                            ),
                            html.H4(
                                "Planting and Maintenance Progress",
                                className="photo-story-heading",
                            ),
                            html.P(
                                (
                                    f"{len(cards)} recorded images"
                                ),
                                className="photo-story-description",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Span(
                                "←",
                                className="photo-story-scroll-arrow",
                            ),
                            html.Span("Scroll to see more"),
                            html.Span(
                                "→",
                                className="photo-story-scroll-arrow",
                            ),
                        ],
                        className="photo-story-scroll-hint",
                    ),
                ],
                className="photo-story-header",
            ),
            html.Div(
                cards,
                className="photo-story-track",
                role="list",
                **{"aria-label": f"Photographic history of {planting_name}"},
            ),
        ],
        className="planting-photo-story",
    )

# ---------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------
def display_value(value, fallback="Not recorded"):
    if value is None:
        return fallback

    value = str(value).strip()
    return value or fallback


def detail_row(label, value):
    if value is None or str(value).strip() == "":
        return None

    return html.Div(
        [
            html.Div(label, className="project-detail-label"),
            html.Div(value, className="project-detail-value"),
        ],
        className="project-detail-row",
    )


def format_text(value):
    if value is None:
        return None

    return (
        str(value)
        .replace("-", " ")
        .replace("_", " ")
        .strip()
        .title()
    )


def format_boolean(value):
    if value is None:
        return None

    normalized = str(value).strip().lower()

    if normalized in {"true", "yes", "1"}:
        return "Yes"

    if normalized in {"false", "no", "0"}:
        return "No"

    return format_text(value)


def format_date(value):
    if not value:
        return None

    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d")
        return parsed.strftime("%-d %B %Y")
    except ValueError:
        return str(value)


def clean_qgis_photo_filename(filename):
    return (
        str(filename)
        .replace("\\", "_")
        .replace("/", "_")
        .replace(":", "_")
        .strip()
    )

def parse_species_planted(value):
    """
    Convert QGIS/PostgreSQL-style species arrays into a clean list.

    Supported examples:
        {"alder","birch","oak"}
        {alder,birch,oak}
        {"scots-pine"}
    """
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        raw_species = value
    else:
        cleaned = str(value).strip()

        if not cleaned:
            return []

        # Remove the surrounding PostgreSQL array braces.
        if cleaned.startswith("{") and cleaned.endswith("}"):
            cleaned = cleaned[1:-1]

        raw_species = cleaned.split(",")

    species = []

    for item in raw_species:
        normalized = (
            str(item)
            .strip()
            .strip('"')
            .strip("'")
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )

        if normalized and normalized not in species:
            species.append(normalized)

    return species


def render_species_icons(species_value):
    species = parse_species_planted(species_value)

    if not species:
        return None

    icons = []

    for species_key in species:
        species_info = TREE_SPECIES.get(species_key)

        if not species_info:
            continue

        label = species_info["label"]
        image_src = (
            f"{TREE_MARKERS_PATH}/{species_info['filename']}"
        )

        icons.append(
            html.Img(
                src=image_src,
                alt=label,
                title=label,
                className="planting-species-image",
            )
        )

    if not icons:
        return None

    return html.Div(
        [
            html.Div(
                "Trees Planted",
                className="planting-species-heading",
            ),
            html.Div(
                icons,
                className="planting-species-list",
            ),
        ],
        className="planting-species-section",
    )

#Load the planting photo index for use in the project detail panel.
PLANTING_PHOTO_RECORDS = load_photo_index(PHOTO_INDEX_FILE)

# ---------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------
layout = html.Div(
    [
        # -------------------------------------------------------------
        # Compact page introduction
        # -------------------------------------------------------------
        html.Section(
            [
                html.Div(
                    [
                        html.Div(
                            "Explore ReWild Wicklow’s work",
                            className="projects-eyebrow",
                        ),
                        html.H1(
                            "Project Map",
                            className="projects-hero-title",
                        ),
                        html.P(
                            "Select a site or planting area to find out more details and "
                            "recorded volunteer visits.",
                            className="projects-hero-description",
                        ),
                    ],
                    className="projects-hero-copy",
                ),

                html.Div(
                    [
                        html.Span(
                            "↓",
                            className="projects-guide-arrow",
                        ),
                        html.Span(
                            "Choose a site or planting area",
                            className="projects-guide-text",
                        ),
                    ],
                    className="projects-guide-pill",
                ),
            ],
            className="projects-hero",
        ),

        # -------------------------------------------------------------
        # Map section
        # -------------------------------------------------------------
        html.Section(
            [


                html.Div(
                    [
                        html.Div(
                            html.Iframe(
                                src="/assets/qgis-map/index-voyager.html",
                                id="qgis-map-frame",
                                className="qgis-map-frame",
                            ),
                            className="qgis-map-wrapper",
                        ),

                        html.Div(
                            [
                                html.Div(
                                    "HOW TO EXPLORE:",
                                    className="projects-map-note-label",
                                ),
                                html.P(
                                    "Hover over a tree marker to view a project "
                                    "site, or select a planting area "
                                    "to see more detailed planting records.",
                                    className="projects-map-note-text",
                                ),
                            ],
                            className="projects-map-note",
                        ),
                    ],
                    className="projects-map-card",
                ),
            ],
            className="projects-map-section",
        ),

        # Hidden communication elements
        dcc.Input(
            id="selected-map-feature-json",
            type="text",
            value="",
            style={"display": "none"},
        ),
        dcc.Store(
            id="selected-map-feature",
            data=None,
            storage_type="memory",
        ),

        # -------------------------------------------------------------
        # Selected project information
        # -------------------------------------------------------------
        html.Section(
            [
                

                html.Div(
                    [
                        html.H3("Select a project on the map"),
                        html.P(
                            "The selected planting or site will appear here "
                            "with its photographs, timeline and recorded details."
                        ),
                    ],
                    id="project-detail-panel",
                    className=(
                        "project-detail-panel "
                        "project-detail-empty"
                    ),
                ),
            ],
            className="projects-detail-section",
        ),
    ],
    className="projects-page",
)


# ---------------------------------------------------------------------
# Server-side rendering callback
# ---------------------------------------------------------------------
@callback(
    Output("project-detail-panel", "children"),
    Output("project-detail-panel", "className"),
    Output("selected-map-feature", "data"),
    Input("selected-map-feature-json", "value"),
)
def render_selected_feature(selected_feature_json):
    selected_feature = None

    if selected_feature_json:
        try:
            selected_feature = json.loads(selected_feature_json)
        except (TypeError, json.JSONDecodeError) as exc:
            print(
                "Could not decode selected map feature:",
                exc,
                selected_feature_json,
            )

    print("Dash received selected feature:", selected_feature)

    if not selected_feature:
        return (
            [
                html.H3("Select a project on the map"),
                html.P(
                    "Click a site marker or planting area to display "
                    "its information here."
                ),
            ],
            "project-detail-panel project-detail-empty",
            selected_feature,
        )

    feature_type = selected_feature.get("featureType")
    properties = selected_feature.get("properties") or {}

    if feature_type == "planting":
        return (
            render_planting_details(properties),
            "project-detail-panel",
            selected_feature,
        )

    if feature_type == "site":
        return (
            render_site_details(properties),
            "project-detail-panel",
            selected_feature,
        )

    return (
        html.P("Unknown feature type."),
        "project-detail-panel project-detail-empty",
        selected_feature,
    )


# ---------------------------------------------------------------------
# Site panel
# ---------------------------------------------------------------------
def render_site_details(properties):
    name = display_value(properties.get("Name"), "Unnamed site")

    management_key = str(
        properties.get("Management Type") or ""
    ).strip().lower()

    management = MANAGEMENT_LABELS.get(
        management_key,
        "Management schedule undetermined",
    )

    rows = [
        detail_row(
            "Activity",
            display_value(properties.get("Activity Type")),
        ),
        detail_row("Management", management),
        detail_row("Local group", properties.get("Local Group")),
        detail_row(
            "First activity",
            format_date(properties.get("Date of First Activity")),
        ),
        detail_row(
            "Last visited",
            format_date(properties.get("last_visited")),
        ),
    ]
    rows = [row for row in rows if row is not None]

    return [
        html.Div(
            [
                html.Div("Site", className="project-type-badge"),
                html.H3(name),
            ],
            className="project-detail-heading",
        ),
        html.P(
            properties.get("Description")
            or "No site description is currently available.",
            className="project-description",
        ),
        html.Div(rows, className="project-detail-grid"),
    ]


# ---------------------------------------------------------------------
# Planting panel
# ---------------------------------------------------------------------
def render_planting_details(properties):
    name = properties.get("Name") or "Unnamed planting"
    protection = properties.get("Protection")
    first_planted = properties.get("First Planted")
    last_visited = properties.get("last_visited")
    maintained = properties.get("Maintained by RW")
    planted_by_rw = properties.get("Planted by RW")
    description = properties.get("Description")
    photo_filename = properties.get("Photo")
    species_planted = properties.get("Species Planted")

    content = [
        html.Div(
            [
                html.Span("Planting", className="project-type-badge"),
                html.H3(name),
            ],
            className="project-detail-heading",
        )
    ]

    photo_story = render_photo_progress_story(name)

    if photo_story is not None:
        content.append(photo_story)

    # The timeline is placed immediately below the rendered photo.
    content.append(make_work_timeline(properties))

    summary_items = [
        {
            "label": "Planted by ReWild Wicklow",
            "value": format_text(planted_by_rw),
        },
        {
            "label": "Maintained by ReWild Wicklow",
            "value": format_boolean(maintained),
        },
        {
            "label": "Protection",
            "value": format_text(protection),
        },
    ]

    summary_items = [
        item for item in summary_items
        if item["value"] is not None and str(item["value"]).strip()
    ]

    content.append(
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            "Planted by ReWild Wicklow",
                            className="project-summary-label",
                        ),
                        html.Div(
                            format_text(planted_by_rw),
                            className="project-summary-value",
                        ),
                    ],
                    className="project-summary-item",
                ),
                html.Div(
                    [
                        html.Div(
                            "Maintained by ReWild Wicklow",
                            className="project-summary-label",
                        ),
                        html.Div(
                            format_boolean(maintained),
                            className="project-summary-value",
                        ),
                    ],
                    className="project-summary-item",
                ),
                html.Div(
                    [
                        html.Div(
                            "Protection",
                            className="project-summary-label",
                        ),
                        html.Div(
                            format_text(protection),
                            className="project-summary-value",
                        ),
                    ],
                    className="project-summary-item",
                ),
            ],
            className="project-summary-row",
        )
    )

    species_icons = render_species_icons(species_planted)

    if species_icons is not None:
        content.append(species_icons)

    return content