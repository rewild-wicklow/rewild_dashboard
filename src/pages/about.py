import json
from datetime import datetime
from pathlib import Path

import dash
from dash import (
    ALL,
    Input,
    Output,
    callback,
    ctx,
    dcc,
    html,
)
import pandas as pd
import plotly.graph_objects as go
from utils.qgis_data import load_qgis2web_features

dash.register_page(
    __name__,
    path="/",
    name="About"
)

TIMELINE_PLANTINGS_FILE = Path(
    "src/assets/qgis-map/data/Plantings_3.js"
)

PHOTO_INDEX_FILE = Path(
    "src/assets/qgis-map/data/planting_photo_index.js"
)

PHOTO_TYPE_ORDER = {
    "planting": 0,
    "growth": 1,
    "observation": 2,
    "visit": 3,
    "maintenance": 4,
    "monitoring": 5,
}

PHOTO_TYPE_LABELS = {
    "planting": "First planted",
    "growth": "Growth update",
    "observation": "Observation",
    "visit": "Visit",
    "maintenance": "Maintenance",
    "monitoring": "Monitoring",
}

PLANTING_FEATURES = load_qgis2web_features(
    TIMELINE_PLANTINGS_FILE
)

FEATURED_PLANTINGS = [
    {
        "name": "An Óige Knockree - ReWild Large Exclosure ",
        "display_name": "An Óige Knockree",
        "story": "Large woodland restoration",
    },
    {
        "name": "Glencree Forest Downhill",
        "display_name": "Glencree Forest Downhill",
        "story": "Mixed native woodland",
    },
    {
        "name": "ECNR Field exclosure",
        "display_name": "ECNR Field Exclosure",
        "story": "Small exclosure work",
    },
    {
        "name": "VT Hedgerow exclosure along bank",
        "display_name": "VT Hedgerow",
        "story": "Wildlife support, enviromental protection",
    },
    {
        "name": "Glensoulan Valley planting",
        "display_name": "Glensoulan Valley",
        "story": "Early rewilding and care",
    },
]


def clean_qgis_photo_filename(filename):
    return (
        str(filename)
        .replace("\\", "_")
        .replace("/", "_")
        .replace(":", "_")
        .strip()
    )


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


def get_planting_photo_records(planting_name):
    """Return indexed photos sorted by date, then by event type."""
    normalized_name = str(planting_name or "").strip().casefold()
    records = [
        record for record in PLANTING_PHOTO_RECORDS
        if str(record.get("planting_site_name") or "").strip().casefold() == normalized_name
    ]

    def sort_key(record):
        parsed_date = pd.to_datetime(record.get("date"), errors="coerce")
        if pd.isna(parsed_date):
            parsed_date = pd.Timestamp.max
        photo_type = str(record.get("photo_type") or "").strip().lower()
        return (
            parsed_date,
            PHOTO_TYPE_ORDER.get(photo_type, 999),
            str(record.get("source_filename") or "").casefold(),
        )

    return sorted(records, key=sort_key)


def make_featured_photo_scroller(planting_name, display_name):
    """Render one or more indexed photos as a horizontally scrollable strip."""
    records = get_planting_photo_records(planting_name)
    if not records:
        return html.Div(
            "No photograph currently recorded",
            className="featured-preview-placeholder",
        )

    dated_records = [record for record in records if record.get("date")]
    latest_date = max((record["date"] for record in dated_records), default=None)
    cards = []

    for index, record in enumerate(records):
        image_src = photo_record_src(record)
        if not image_src:
            continue
        photo_type = str(record.get("photo_type") or "visit").strip().lower()
        type_label = PHOTO_TYPE_LABELS.get(
            photo_type,
            photo_type.replace("-", " ").title(),
        )
        is_latest = (
            record.get("date") == latest_date
            if latest_date
            else index == len(records) - 1
        )
        cards.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Img(
                                src=image_src,
                                alt=f"{type_label} photograph of {display_name}",
                                className="featured-preview-image",
                            ),
                            html.Span(
                                "Latest",
                                className="featured-preview-latest",
                            ) if is_latest else None,
                        ],
                        className="featured-preview-image-wrap",
                    ),
                    html.Div(
                        [
                            html.Div(
                                format_about_date(record.get("date")) or "Date not recorded",
                                className="featured-preview-photo-date",
                            ),
                            html.Div(
                                type_label,
                                className="featured-preview-photo-type",
                            ),
                        ],
                        className="featured-preview-photo-caption",
                    ),
                ],
                className="featured-preview-photo-card",
            )
        )

    if not cards:
        return html.Div(
            "No photograph currently recorded",
            className="featured-preview-placeholder",
        )

    return html.Div(
        [
            html.Div(cards, className="featured-preview-photo-track"),
            html.Div(
                "← Scroll through the planting record →",
                className="featured-preview-scroll-hint",
            ) if len(cards) > 1 else None,
        ],
        className="featured-preview-photo-library",
    )


PLANTING_PHOTO_RECORDS = load_photo_index(PHOTO_INDEX_FILE)


def build_about_timeline_events(features):
    events = []

    for feature in features:
        properties = feature.get("properties") or {}

        planting_name = (
            properties.get("Name")
            or "Unnamed planting"
        )

        photo_filename = properties.get("Photo")
        description = properties.get("Description")
        species = properties.get("Species Planted")

        for field_name, event_label in (
            ("First Planted", "Planting established"),
            ("last_visited", "Latest recorded visit"),
        ):
            parsed_date = pd.to_datetime(
                properties.get(field_name),
                errors="coerce",
            )

            if pd.isna(parsed_date):
                continue

            photo_records = get_planting_photo_records(
                planting_name
            )
            photo_url = (
                photo_record_src(photo_records[0])
                if photo_records
                else None
            )

            events.append(
                {
                    "Date": parsed_date,
                    "Event": event_label,
                    "Planting": planting_name,
                    "Photo": photo_url,
                    "Description": description,
                    "Species": species,
                }
            )

    if not events:
        return pd.DataFrame(
            columns=[
                "Date",
                "Event",
                "Planting",
                "Photo",
                "Description",
                "Species",
            ]
        )

    return (
        pd.DataFrame(events)
        .sort_values("Date")
        .reset_index(drop=True)
    )


ABOUT_TIMELINE_EVENTS = build_about_timeline_events(
    PLANTING_FEATURES
)



def make_about_timeline():
    if ABOUT_TIMELINE_EVENTS.empty:
        return go.Figure()

    events = ABOUT_TIMELINE_EVENTS.copy()

    events["Position"] = [
        0.09 if index % 2 == 0 else -0.09
        for index in range(len(events))
    ]

    events["EventIndex"] = events.index

    timeline_start = pd.Timestamp(
        events["Date"].min().year - 1,
        1,
        1,
    )

    timeline_end = pd.Timestamp(
        events["Date"].max().year + 1,
        1,
        1,
    )

    planted = events[
        events["Event"] == "Planting established"
    ]

    revisited = events[
        events["Event"] == "Latest recorded visit"
    ]

    fig = go.Figure()

    fig.add_shape(
        type="line",
        x0=timeline_start,
        x1=timeline_end,
        y0=0,
        y1=0,
        line={
            "color": "#a8bea0",
            "width": 4,
        },
        layer="below",
    )

    fig.add_trace(
        go.Scatter(
            x=planted["Date"],
            y=planted["Position"],
            mode="markers",
            name="Planting established",
            marker={
                "size": 14,
                "color": "#789f68",
                "symbol": "circle",
                "line": {
                    "width": 0.5,
                    "color": "#ffffff",
                },
            },
            customdata=planted[
                [
                    "EventIndex",
                    "Planting",
                    "Event",
                ]
            ].to_numpy(),
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "%{customdata[2]}<br>"
                "%{x|%-d %B %Y}"
                "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=revisited["Date"],
            y=revisited["Position"],
            mode="markers",
            name="Recorded return visit",
            marker={
                "size": 14,
                "symbol": "diamond",
                "line": {
                    "width": 0.5,
                    "color": "#ffffff",
                },
            },
            customdata=revisited[
                [
                    "EventIndex",
                    "Planting",
                    "Event",
                ]
            ].to_numpy(),
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "%{customdata[2]}<br>"
                "%{x|%-d %B %Y}"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        height=370,
        dragmode="zoom",
        margin={
            "l": 20,
            "r": 20,
            "t": 70,
            "b": 30,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="closest",
        showlegend=True,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.05,
            "xanchor": "left",
            "x": 0,
            "font": {
                "size": 13,
                "color": "#43543f",
            },
        },
        xaxis={
            "range": [timeline_start, timeline_end],
            "tickformat": "%Y",
            "dtick": "M12",
            "showgrid": False,
            "zeroline": False,
            "showline": False,

            # Allow zooming and horizontal panning.
            "fixedrange": False,

            "ticks": "outside",
            "ticklen": 5,
            "tickcolor": "#8fa18a",
            "tickfont": {
                "size": 14,
                "color": "#43543f",
            },
        },
        yaxis={
            "visible": False,
            "range": [-0.28, 0.28],
            "fixedrange": True,
        },
    )

    return fig

def format_about_date(value):
    parsed = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed):
        return ""

    return parsed.strftime("%-d %B %Y")

def get_feature_properties(planting_name):
    """Return the properties for a planting with the requested name."""
    normalized_target = str(planting_name).strip()

    for feature in PLANTING_FEATURES:
        properties = feature.get("properties") or {}

        feature_name = str(
            properties.get("Name") or ""
        ).strip()

        if feature_name == normalized_target:
            return properties

    return None


def get_feature_photo_url(properties):
    """Return the first indexed photo URL for a planting."""
    if not properties:
        return None
    records = get_planting_photo_records(properties.get("Name"))
    if not records:
        return None
    return photo_record_src(records[0])

def make_featured_journey_preview(feature_config):
    properties = get_feature_properties(
        feature_config["name"]
    )

    if not properties:
        return [
            html.Div(
                "Planting information unavailable",
                className="featured-preview-placeholder",
            )
        ]

    first_planted = pd.to_datetime(
        properties.get("First Planted"),
        errors="coerce",
    )

    last_visited = pd.to_datetime(
        properties.get("last_visited"),
        errors="coerce",
    )

    image_content = make_featured_photo_scroller(
        feature_config["name"],
        feature_config["display_name"],
    )

    date_parts = []

    if not pd.isna(first_planted):
        date_parts.append(
            f"Planted {format_about_date(first_planted)}"
        )

    if not pd.isna(last_visited):
        date_parts.append(
            f"Latest visit {format_about_date(last_visited)}"
        )

    date_text = " · ".join(date_parts)

    return [
        image_content,
        html.Div(
            [
                html.Div(
                    feature_config["story"],
                    className="featured-preview-story",
                ),
                html.H3(
                    feature_config["display_name"],
                    className="featured-preview-title",
                ),
                html.Div(
                    date_text,
                    className="featured-preview-dates",
                )
                if date_text
                else None,
                html.P(
                    properties.get("Description")
                    or (
                        "This planting forms part of ReWild "
                        "Wicklow’s growing record of restoration "
                        "and continued care."
                    ),
                    className="featured-preview-description",
                ),
            ],
            className="featured-preview-copy",
        ),
    ]


def make_default_featured_preview():
    return make_featured_journey_preview(
        FEATURED_PLANTINGS[0]
    )

def make_featured_planting_rows():
    records = []

    for feature_config in FEATURED_PLANTINGS:
        properties = get_feature_properties(
            feature_config["name"]
        )

        if not properties:
            continue

        first_planted = pd.to_datetime(
            properties.get("First Planted"),
            errors="coerce",
        )

        last_visited = pd.to_datetime(
            properties.get("last_visited"),
            errors="coerce",
        )

        valid_dates = [
            date
            for date in (first_planted, last_visited)
            if not pd.isna(date)
        ]

        if not valid_dates:
            continue

        records.append(
            {
                "config": feature_config,
                "properties": properties,
                "first_planted": first_planted,
                "last_visited": last_visited,
                "valid_dates": valid_dates,
            }
        )

    if not records:
        return html.P(
            "No featured planting dates are currently available."
        )

    all_dates = [
        date
        for record in records
        for date in record["valid_dates"]
    ]

    timeline_start = min(all_dates).normalize()
    timeline_end = max(all_dates).normalize()

    total_days = max(
        (timeline_end - timeline_start).days,
        1,
    )

    year_labels = []

    for year in range(
        timeline_start.year,
        timeline_end.year + 1,
    ):
        year_date = pd.Timestamp(year, 1, 1)

        position = (
            (year_date - timeline_start).days
            / total_days
            * 100
        )

        position = max(0, min(position, 100))

        year_labels.append(
            html.Div(
                str(year),
                className="featured-journey-year",
                style={"left": f"{position}%"},
            )
        )

    rows = []

    for index, record in enumerate(records):
        feature_config = record["config"]
        first_planted = record["first_planted"]
        last_visited = record["last_visited"]

        markers = []

        if not pd.isna(first_planted):
            planting_position = (
                (first_planted - timeline_start).days
                / total_days
                * 100
            )

            markers.append(
                html.Button(
                    [
                        html.Span(
                            className=(
                                "featured-marker-shape "
                                "featured-marker-planting"
                            )
                        ),
                        html.Span(
                            (
                                "Planting established "
                                f"{format_about_date(first_planted)}"
                            ),
                            className="featured-marker-tooltip",
                        ),
                    ],
                    id={
                        "type": "featured-journey-trigger",
                        "index": index,
                    },
                    n_clicks=0,
                    className=(
                        "featured-marker-button "
                        "featured-marker-button-planting"
                    ),
                    style={
                        "left": f"{planting_position}%"
                    },
                    title=(
                        "Planting established — "
                        f"{format_about_date(first_planted)}"
                    ),
                )
            )

        if not pd.isna(last_visited):
            visit_position = (
                (last_visited - timeline_start).days
                / total_days
                * 100
            )

            markers.append(
                html.Button(
                    [
                        html.Span(
                            className=(
                                "featured-marker-shape "
                                "featured-marker-visit"
                            )
                        ),
                        html.Span(
                            (
                                "Latest recorded visit "
                                f"{format_about_date(last_visited)}"
                            ),
                            className="featured-marker-tooltip",
                        ),
                    ],
                    id={
                        "type": "featured-journey-trigger",
                        "index": index,
                    },
                    n_clicks=0,
                    className=(
                        "featured-marker-button "
                        "featured-marker-button-visit"
                    ),
                    style={
                        "left": f"{visit_position}%"
                    },
                    title=(
                        "Latest recorded visit — "
                        f"{format_about_date(last_visited)}"
                    ),
                )
            )

        rows.append(
            html.Div(
                [
                    html.Button(
                        [
                            html.H3(
                                feature_config["display_name"],
                                className="featured-journey-name",
                            ),
                            html.Div(
                                feature_config["story"],
                                className="featured-journey-story",
                            ),
                        ],
                        id={
                            "type": "featured-journey-trigger",
                            "index": index,
                        },
                        n_clicks=0,
                        className="featured-journey-label",
                    ),

                    html.Div(
                        [
                            html.Div(
                                className="featured-journey-line"
                            ),
                            *markers,
                        ],
                        className="featured-journey-track",
                    ),
                ],
                className="featured-journey-row",
            )
        )

    return [
        html.Div(
            [
                html.Div(
                    [
                        html.Span(
                            className=(
                                "featured-legend-symbol "
                                "featured-legend-planting"
                            )
                        ),
                        html.Span("Planting established"),
                    ],
                    className="featured-legend-item",
                ),
                html.Div(
                    [
                        html.Span(
                            className=(
                                "featured-legend-symbol "
                                "featured-legend-visit"
                            )
                        ),
                        html.Span("Latest recorded visit"),
                    ],
                    className="featured-legend-item",
                ),
            ],
            className="featured-journey-legend",
        ),

        html.Div(
            year_labels,
            className="featured-journey-axis",
        ),

        html.Div(
            rows,
            className="featured-journeys-list",
        ),
    ]

def make_timeline_preview(event):
    image = event.get("Photo")

    image_content = (
        html.Img(
            src=image,
            alt=f"Photograph of {event['Planting']}",
            className="about-preview-image",
        )
        if image
        else html.Div(
            "No photograph recorded",
            className="about-preview-placeholder",
        )
    )

    return [
        image_content,
        html.Div(
            [
                html.Div(
                    event["Event"],
                    className="about-preview-event",
                ),
                html.H3(
                    event["Planting"],
                    className="about-preview-title",
                ),
                html.Div(
                    format_about_date(event["Date"]),
                    className="about-preview-date",
                ),
                html.P(
                    event.get("Description")
                    or (
                        "This point marks part of the planting’s "
                        "recorded history."
                    ),
                    className="about-preview-description",
                ),
            ],
            className="about-preview-copy",
        ),
    ]


def make_default_timeline_preview():
    if ABOUT_TIMELINE_EVENTS.empty:
        return html.P(
            "No dated planting records are currently available."
        )

    newest_planting = (
        ABOUT_TIMELINE_EVENTS[
            ABOUT_TIMELINE_EVENTS["Event"]
            == "Planting established"
        ]
        .sort_values("Date")
        .iloc[-1]
        .to_dict()
    )

    return make_timeline_preview(newest_planting)

def about_reason_card(title, text):
    return html.Div(
        [
            html.Div(
                title[0],
                className="about-reason-icon",
            ),
            html.H3(title),
            html.P(text),
        ],
        className="about-reason-card",
    )

layout = html.Div(
    [
        html.Section(
            [
                html.Div(
                    [
                        html.Div("ReWild's living record", className="about-eyebrow"),
                        html.H1(
                            "Following ReWild Wicklow’s work as it grows",
                            className="about-hero-title",
                        ),
                    ],
                    className="about-hero-copy",
                ),
                html.Div(
                    [
                        html.Div(
                            str(len(PLANTING_FEATURES)),
                            className="about-stat-number",
                        ),
                        html.Div(
                            "mapped planting areas",
                            className="about-stat-label",
                        ),
                    ],
                    className="about-stat-card",
                ),
            ],
            className="about-hero",
        ),

        html.Section(
            [
                html.Div(
                    [
                        html.Div(
                            "PLANTING JOURNEYS",
                            className="about-section-eyebrow",
                        ),
                        html.H2(
                            "Follow the Progress.",
                            className="about-section-title",
                        ),
                        html.Div(
                            [
                                html.P(
                                    "Each timeline shows when one of five plantings was "
                                    "established and its latest recorded visit. This preview "
                                    "aims to show the diversity of ReWild Wicklow’s work, "
                                    "including large woodland restoration, hedgerow planting, "
                                    "and wetland care.",
                                    className="about-section-description",
                                ),
                                html.P(
                                    "There are many more plantings across Wicklow, and the "
                                    "Project Map shows every planting recorded by ReWild "
                                    "Wicklow volunteers.",
                                    className=(
                                        "about-section-description "
                                        "about-section-description-indented"
                                    ),
                                ),
                            ]
                        )
                    ],
                    className="featured-journeys-heading",
                ),

                html.Div(
                    [
                        html.Div(
                            make_featured_planting_rows(),
                            className="featured-journeys-chart",
                        ),

                        html.Div(
                            id="featured-journey-preview",
                            children=make_default_featured_preview(),
                            className="featured-journey-preview",
                        ),
                    ],
                    className="featured-journeys-content",
                ),

                html.Div(
                    [
                        dcc.Link(
                            [
                                html.Div(
                                    [
                                        html.Span(
                                            "Continue exploring",
                                            className=(
                                                "featured-map-link-eyebrow"
                                            ),
                                        ),
                                        html.Span(
                                            (
                                                "See every planting on the "
                                                "project map"
                                            ),
                                            className=(
                                                "featured-map-link-text"
                                            ),
                                        ),
                                    ],
                                    className="featured-map-link-copy",
                                ),
                                html.Span(
                                    "→",
                                    className="featured-map-link-arrow",
                                ),
                            ],
                            href="/projects",
                            className="featured-map-link",
                        )
                    ],
                    className="featured-map-link-wrapper",
                ),
            ],
            className="featured-journeys-section",
        ),

    ],
    className="about-page",
)

@callback(
    Output("featured-journey-preview", "children"),
    Input(
        {
            "type": "featured-journey-trigger",
            "index": ALL,
        },
        "n_clicks",
    ),
    prevent_initial_call=True,
)
def update_featured_journey_preview(_clicks):
    triggered_id = ctx.triggered_id

    if not isinstance(triggered_id, dict):
        return make_default_featured_preview()

    feature_index = triggered_id.get("index")

    if feature_index is None:
        return make_default_featured_preview()

    try:
        feature_config = FEATURED_PLANTINGS[
            int(feature_index)
        ]
    except (IndexError, TypeError, ValueError):
        return make_default_featured_preview()

    return make_featured_journey_preview(
        feature_config
    )