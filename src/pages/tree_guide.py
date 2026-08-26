from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

import dash
import pandas as pd
from dash import ALL, Input, Output, State, callback, dcc, html


dash.register_page(
    __name__,
    path="/tree-guide",
    name="Tree Guide",
    title="Tree Guide | ReWild Wicklow",
)


ASSETS_DIR = Path("src/assets")
CSV_PATH = ASSETS_DIR / "tree_id.csv"
TREE_PHOTO_DIR = ASSETS_DIR / "tree_ids"
MARKER_DIR = ASSETS_DIR / "markers"

GUIDE_COLUMNS = [
    "Overview",
    "What to look for",
    "Where it grows",
    "Flowers, Fruit & Seeds",
    "Seasonal clues",
]

GROVE_SECTIONS = [
    ("At a glance", "Overview", "grove-tree-one"),
    ("What to look for", "What to look for", "grove-tree-two"),
    ("Where it grows", "Where it grows", "grove-tree-three"),
    ("Flowers, fruit & seeds", "Flowers, Fruit & Seeds", "grove-tree-four"),
    ("Seasonal clues", "Seasonal clues", "grove-tree-five"),
]


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", str(value).strip().lower())
    return re.sub(r"[-\s]+", "-", value).strip("-")


def clean_cell(value) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def split_list(value) -> list[str]:
    text = clean_cell(value)
    if not text:
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"\s*\|\s*|\n+|(?=•)", text)

    items = []
    seen = set()

    for part in parts:
        item = re.sub(r"^[\s•\-–—]+", "", part).strip()
        item = re.sub(r"\s+", " ", item).rstrip(" .;")
        if not item:
            continue

        key = item.casefold()
        if key not in seen:
            items.append(item)
            seen.add(key)

    return items


def find_asset_url(directory: Path, stem_or_filename: str) -> str | None:
    value = clean_cell(stem_or_filename)
    if not value:
        return None

    requested = Path(value)
    candidates = []

    if requested.suffix:
        candidates.append(directory / requested.name)
    else:
        for extension in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
            candidates.append(directory / f"{requested.name}{extension}")

    for candidate in candidates:
        if candidate.exists():
            relative = candidate.relative_to(ASSETS_DIR).as_posix()
            return f"/assets/{quote(relative)}"

    fallback = candidates[0] if candidates else directory / requested.name
    relative = fallback.relative_to(ASSETS_DIR).as_posix()
    return f"/assets/{quote(relative)}"


def marker_url(category: str) -> str:
    aliases = {
        "guelder rose": "guelder-rose",
        "scots pine": "scots-pine",
        "wild cherry": "wild-cherry",
        "crab apple": "crab-apple",
    }
    marker_stem = aliases.get(category.casefold(), slugify(category))
    return find_asset_url(MARKER_DIR, marker_stem) or "/assets/markers/tree.png"


def load_tree_guide() -> tuple[dict[str, list[dict]], list[str]]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Tree guide data was not found at {CSV_PATH}. "
            "Place the CSV in assets/tree_id.csv."
        )

    dataframe = pd.read_csv(CSV_PATH)
    dataframe = dataframe.loc[
        :,
        ~dataframe.columns.astype(str).str.startswith("Unnamed"),
    ]

    required = {"Tree Category", "Tree Species", *GUIDE_COLUMNS}
    missing = sorted(required.difference(dataframe.columns))
    if missing:
        raise ValueError(
            "tree_id.csv is missing required columns: "
            + ", ".join(missing)
        )

    guide: dict[str, list[dict]] = {}
    category_order: list[str] = []

    for _, row in dataframe.iterrows():
        category = clean_cell(row.get("Tree Category"))
        species = clean_cell(row.get("Tree Species"))

        if not category or not species:
            continue

        if category not in guide:
            guide[category] = []
            category_order.append(category)

        guide[category].append(
            {
                "category": category,
                "species": species,
                "photo": find_asset_url(
                    TREE_PHOTO_DIR,
                    clean_cell(row.get("Photo")),
                ),
                "source": clean_cell(row.get("Source Link")),
                "sections": {
                    column: split_list(row.get(column))
                    for column in GUIDE_COLUMNS
                },
            }
        )

    return guide, category_order


TREE_GUIDE, CATEGORY_ORDER = load_tree_guide()
DEFAULT_CATEGORY = CATEGORY_ORDER[0]
DEFAULT_SELECTION = {"category": DEFAULT_CATEGORY, "variant": 0}


def build_tree_selector(category: str):
    variants = TREE_GUIDE[category]
    species_label = (
        variants[0]["species"]
        if len(variants) == 1
        else f"{len(variants)} species"
    )

    return html.Button(
        [
            html.Div(
                html.Img(
                    src=marker_url(category),
                    alt="",
                    className="tree-selector-image",
                ),
                className="tree-selector-image-wrap",
            ),
            html.Div(
                [
                    html.Span("Tree category", className="tree-selector-category"),
                    html.H3(category, className="tree-selector-name"),
                    html.Span(
                        species_label,
                        className="tree-selector-scientific",
                    ),
                ],
                className="tree-selector-copy",
            ),
            html.Span(
                "Explore",
                className="tree-selector-action",
                **{"aria-hidden": "true"},
            ),
        ],
        id={"type": "tree-guide-selector", "tree": category},
        className="tree-selector-card",
        type="button",
        **{
            "aria-label": f"View the {category} tree guide",
            "aria-pressed": "false",
        },
    )


def build_compact_list(items: list[str]):
    if not items:
        return html.P(
            "Information to be added.",
            className="grove-empty-note",
        )

    return html.Ul(
        [html.Li(item) for item in items],
        className="grove-fact-list",
    )


def build_info_tree(
    title: str,
    items: list[str],
    tree_class: str,
    position: int,
):
    return html.Div(
        [
            html.Button(
                html.Div(
                    [
                        html.H3(title),
                        build_compact_list(items),
                    ],
                    className="grove-tree-canopy-content",
                ),
                id={"type": "grove-info-tree", "index": position},
                className="grove-tree-canopy",
                type="button",
                **{
                    "aria-label": f"Bring {title} information forward",
                    "aria-pressed": "false",
                },
            ),
            html.Div(className="grove-tree-trunk"),
            html.Div(className="grove-tree-shadow"),
        ],
        className=f"grove-info-tree {tree_class}",
    )


def build_variant_controls(category: str, variant_index: int):
    variants = TREE_GUIDE[category]
    is_single = len(variants) <= 1

    return html.Div(
        [
            html.Button(
                "‹",
                id="tree-variant-previous",
                className="tree-variant-arrow",
                type="button",
                disabled=is_single,
                **{"aria-label": "Previous species"},
            ),
            html.Div(
                [
                    html.Span(
                        (
                            "1 species"
                            if is_single
                            else f"{variant_index + 1} of {len(variants)}"
                        ),
                        className="tree-variant-count",
                    ),
                    html.Div(
                        [
                            html.Span(
                                variant["species"],
                                className=(
                                    "tree-variant-pill is-active"
                                    if index == variant_index
                                    else "tree-variant-pill"
                                ),
                            )
                            for index, variant in enumerate(variants)
                        ],
                        className="tree-variant-pills",
                    ),
                ],
                className="tree-variant-status",
            ),
            html.Button(
                "›",
                id="tree-variant-next",
                className="tree-variant-arrow",
                type="button",
                disabled=is_single,
                **{"aria-label": "Next species"},
            ),
        ],
        className=(
            "tree-variant-controls is-single"
            if is_single
            else "tree-variant-controls"
        ),
    )


def build_source_link(tree: dict):
    if not tree["source"]:
        return None

    return html.P(
        [
            "Images and identification information were adapted from ",
            html.A(
                "this source",
                href=tree["source"],
                target="_blank",
                rel="noopener noreferrer",
                className="tree-heading-source-link",
            ),
            ", where you can find additional photographs and species details.",
        ],
        className="tree-heading-source-note",
    )


def build_selected_tree_header(category: str, tree: dict, variant_index: int):
    image_src = tree["photo"] or marker_url(category)
    image_alt = (
        f"Real-life view of {tree['species']}"
        if tree["photo"]
        else f"{category} marker"
    )

    image = html.Button(
        [
            html.Img(
                src=image_src,
                alt=image_alt,
                className=(
                    "selected-tree-photo"
                    if tree["photo"]
                    else "selected-tree-photo selected-tree-photo-marker"
                ),
            ),
            html.Span(
                "Click to enlarge",
                className="selected-tree-photo-hint",
            ),
        ],
        id="selected-tree-photo-button",
        className="selected-tree-photo-button",
        type="button",
        **{"aria-label": f"Enlarge image of {tree['species']}"},
    )

    return html.Header(
        [
            html.Div(
                image,
                className="selected-tree-photo-wrap",
            ),
            html.Div(
                [
                    html.Span(
                        category,
                        className="expanded-tree-category",
                    ),
                    html.H2(
                        tree["species"],
                        className="expanded-tree-name",
                    ),
                    build_variant_controls(category, variant_index),
                    build_source_link(tree),
                ],
                className="selected-tree-heading-copy",
            ),
        ],
        className="grove-heading selected-tree-heading",
    )


def build_expanded_tree(
    category: str,
    variant_index: int = 0,
    active_info_tree: int = 1,
):
    variants = TREE_GUIDE[category]
    variant_index %= len(variants)
    tree = variants[variant_index]

    grove_trees = [
        build_info_tree(
            title,
            tree["sections"][column],
            tree_class,
            position,
        )
        for position, (title, column, tree_class) in enumerate(
            GROVE_SECTIONS,
            start=1,
        )
    ]

    return html.Article(
        [
            build_selected_tree_header(category, tree, variant_index),
            html.Div(
                grove_trees,
                className=f"rewilding-grove active-tree-{active_info_tree}",
            ),
            html.Div(className="grove-ground"),
        ],
        className="expanded-tree grove-guide",
        **{"aria-live": "polite"},
    )


layout = html.Main(
    [
        dcc.Store(id="tree-guide-selection", data=DEFAULT_SELECTION),
        dcc.Store(id="active-grove-tree", data=1),
        html.Div(
            [
                html.Div(
                    [
                        html.Button(
                            "×",
                            id="tree-photo-modal-close",
                            className="tree-photo-modal-close",
                            type="button",
                            **{"aria-label": "Close enlarged tree image"},
                        ),
                        html.Img(
                            id="tree-photo-modal-image",
                            src="",
                            alt="",
                            className="tree-photo-modal-image",
                        ),
                    ],
                    className="tree-photo-modal-dialog",
                ),
            ],
            id="tree-photo-modal",
            className="tree-photo-modal",
            style={"display": "none"},
            role="dialog",
            **{
                "aria-modal": "true",
                "aria-label": "Expanded tree photograph",
            },
        ),
        html.Section(
            [
                html.Div(
                    [
                        html.Span(
                            "ReWild Wicklow field guide",
                            className="tree-guide-kicker",
                        ),
                        html.H1("Identify the trees we plant"),
                        html.P(
                            "Explore the tree guide. Some categories include "
                            "several related species (e.g., willow and birch) that you can move through "
                            "inside the guide.",
                            className="tree-guide-intro",
                        ),
                    ],
                    className="tree-guide-heading-copy",
                ),
                html.Div(
                    [
                        html.Span(
                            str(len(CATEGORY_ORDER)),
                            className="tree-guide-stat-number",
                        ),
                        html.Span(
                            "tree categories in the guide",
                            className="tree-guide-stat-label",
                        ),
                    ],
                    className="tree-guide-stat",
                ),
            ],
            className="tree-guide-hero",
        ),
        html.Section(
            [
                html.Div(
                    [
                        html.Span(
                            "Choose a tree",
                            className="tree-guide-section-kicker",
                        ),
                        html.H2("Explore the planting palette"),
                        html.P(
                            "Select a category to grow its identification guide.",
                        ),
                    ],
                    className="tree-guide-section-heading",
                ),
                html.Div(
                    [
                        build_tree_selector(category)
                        for category in CATEGORY_ORDER
                    ],
                    id="tree-selector-grid",
                    className="tree-selector-grid",
                ),
            ],
            className="tree-guide-picker-section",
        ),
        html.Section(
            [
                html.Div(
                    [
                        html.Span(
                            "Selected tree",
                            className="tree-guide-section-kicker",
                        ),
                        html.P(
                            "Select an information tree to bring it forward. "
                            "Use the species controls when a category contains "
                            "more than one species.",
                            className="tree-guide-selected-intro",
                        ),
                    ],
                    className="tree-guide-selected-heading",
                ),
                html.Div(
                    build_expanded_tree(DEFAULT_CATEGORY),
                    id="expanded-tree-container",
                ),
            ],
            id="tree-guide-growth-section",
            className="tree-guide-expanded-section",
        ),
    ],
    className="tree-guide-page",
)


@callback(
    Output("tree-guide-selection", "data"),
    Output("active-grove-tree", "data", allow_duplicate=True),
    Input({"type": "tree-guide-selector", "tree": ALL}, "n_clicks"),
    State("tree-guide-selection", "data"),
    prevent_initial_call=True,
)
def select_tree(_n_clicks, current_selection):
    triggered = dash.ctx.triggered_id

    if not triggered:
        return dash.no_update, dash.no_update

    category = triggered.get("tree")

    if category not in TREE_GUIDE:
        return dash.no_update, dash.no_update

    return {"category": category, "variant": 0}, 1


@callback(
    Output("tree-guide-selection", "data", allow_duplicate=True),
    Input("tree-variant-previous", "n_clicks"),
    Input("tree-variant-next", "n_clicks"),
    State("tree-guide-selection", "data"),
    prevent_initial_call=True,
)
def change_variant(_previous, _next, selection):
    if not selection:
        return dash.no_update

    category = selection.get("category", DEFAULT_CATEGORY)
    current_index = int(selection.get("variant", 0))
    variants = TREE_GUIDE.get(category, [])

    if len(variants) <= 1:
        return dash.no_update

    triggered = dash.ctx.triggered_id

    if triggered == "tree-variant-previous":
        next_index = (current_index - 1) % len(variants)
    elif triggered == "tree-variant-next":
        next_index = (current_index + 1) % len(variants)
    else:
        return dash.no_update

    return {"category": category, "variant": next_index}


@callback(
    Output("tree-photo-modal", "style"),
    Output("tree-photo-modal-image", "src"),
    Output("tree-photo-modal-image", "alt"),
    Input("selected-tree-photo-button", "n_clicks"),
    Input("tree-photo-modal-close", "n_clicks"),
    State("tree-guide-selection", "data"),
    prevent_initial_call=True,
)
def toggle_tree_photo_modal(
    open_clicks,
    close_clicks,
    selection,
):
    triggered = dash.ctx.triggered_id

    # ---------------------------------------------------------
    # CLOSE
    # ---------------------------------------------------------
    if (
        triggered == "tree-photo-modal-close"
        and close_clicks
        and close_clicks > 0
    ):
        return (
            {"display": "none"},
            "",
            "",
        )

    # ---------------------------------------------------------
    # DO NOT OPEN unless the image was ACTUALLY clicked.
    #
    # Dash may trigger this callback when the dynamically
    # rendered selected-tree-photo-button first appears.
    # In that case n_clicks is None/0.
    # ---------------------------------------------------------
    if (
        triggered != "selected-tree-photo-button"
        or not open_clicks
        or open_clicks < 1
    ):
        return (
            {"display": "none"},
            "",
            "",
        )

    # ---------------------------------------------------------
    # REAL USER CLICK — OPEN IMAGE
    # ---------------------------------------------------------
    selection = selection or DEFAULT_SELECTION
    category = selection.get(
        "category",
        DEFAULT_CATEGORY,
    )

    if category not in TREE_GUIDE:
        category = DEFAULT_CATEGORY

    variants = TREE_GUIDE[category]

    variant_index = (
        int(selection.get("variant", 0))
        % len(variants)
    )

    tree = variants[variant_index]

    image_src = (
        tree["photo"]
        or marker_url(category)
    )

    image_alt = (
        f"Real-life view of {tree['species']}"
        if tree["photo"]
        else f"{category} marker"
    )

    return (
        {"display": "flex"},
        image_src,
        image_alt,
    )

@callback(
    Output("active-grove-tree", "data"),
    Input({"type": "grove-info-tree", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def activate_grove_tree(_n_clicks):
    triggered = dash.ctx.triggered_id

    if not triggered:
        return dash.no_update

    return int(triggered["index"])


@callback(
    Output("expanded-tree-container", "children"),
    Output(
        {"type": "tree-guide-selector", "tree": ALL},
        "className",
    ),
    Output(
        {"type": "tree-guide-selector", "tree": ALL},
        "aria-pressed",
    ),
    Input("tree-guide-selection", "data"),
    Input("active-grove-tree", "data"),
    State({"type": "tree-guide-selector", "tree": ALL}, "id"),
)
def update_tree_guide(selection, active_info_tree, selector_ids):
    selection = selection or DEFAULT_SELECTION
    category = selection.get("category", DEFAULT_CATEGORY)

    if category not in TREE_GUIDE:
        category = DEFAULT_CATEGORY

    variant_index = int(selection.get("variant", 0))
    active_info_tree = int(active_info_tree or 1)

    classes = []
    pressed_states = []

    for selector_id in selector_ids:
        is_selected = selector_id["tree"] == category
        classes.append(
            "tree-selector-card is-selected"
            if is_selected
            else "tree-selector-card"
        )
        pressed_states.append("true" if is_selected else "false")

    return (
        build_expanded_tree(
            category,
            variant_index,
            active_info_tree,
        ),
        classes,
        pressed_states,
    )
