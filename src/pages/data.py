import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/data")

def data_card(title, content, class_name="", icon=None):
    return html.Div(
        className=f"data-grid-card {class_name}",
        children=[
            html.Div(
                className="data-card-heading",
                children=[
                    html.Span(icon, className="data-card-icon") if icon else None,
                    html.H3(title),
                ],
            ),
            content,
        ],
    )


layout = html.Main(
    className="data-page",
    children=[
        html.Section(
            className="data-grid",
            children=[
                # Large introduction card
                data_card(
                    "Volunteer Data Portal",
                    html.Div([
                        html.P(
                            "This dashboard shows project information that "
                            "can be shared safely. More detailed field records are "
                            "managed through Mergin Maps."
                        ),
                        html.P(
                            "Some sites are located on private property, so exact "
                            "locations, monitoring records and landowner information "
                            "are only available to authorised users."
                        ),
                    ]),
                    class_name="intro-card",
                    icon="✦",
                ),

                # Mergin Maps action card
                html.A(
                    href="https://app.merginmaps.com/projects",
                    target="_blank",
                    className="data-grid-card mergin-card",
                    children=[
                        html.Div("↗", className="mergin-arrow"),
                        html.Div([
                            html.P("Volunteer access"),
                            html.H3("Open Mergin Maps"),
                            html.Span(
                                "Log in to view the map or record field data."
                            ),
                        ]),
                    ],
                ),

                # Account cards
                data_card(
                    "Read-only accounts can:",
                    html.Ul([
                        html.Li("View project maps"),
                        html.Li("Browse sites and planting areas"),
                        html.Li("Review previous visits"),
                    ]),
                    class_name="readonly-card",
                    icon="◌",
                ),

                data_card(
                    "Contributor accounts can:",
                    html.Ul([
                        html.Li("Add new sites"),
                        html.Li("Map planting areas"),
                        html.Li("Record monitoring visits"),
                        html.Li("Upload observations and photos"),
                    ]),
                    class_name="contributor-card",
                    icon="＋",
                ),

                data_card(
                    "Working offline",
                    html.Div([
                        html.P(
                            "The Mergin Maps app can be used at sites with poor or "
                            "no mobile reception."
                        ),
                        html.P(
                            "Sync the map before leaving. Your records and photos "
                            "will remain on your phone until you reconnect and sync."
                        ),
                    ]),
                    class_name="offline-card",
                    icon="⌁",
                ),



                # Data quality card
                data_card(
                    "Improving the map",
                    html.Div([
                        html.P(
                            "Not every historic planting area has been mapped yet. "
                            "Volunteers are continuing to add planting boundaries "
                            "during monitoring visits."
                        ),
                        html.P(
                            "Recording visits against individual planting areas "
                            "helps us understand what work has taken place and how "
                            "different groups of trees are progressing."
                        ),
                    ]),
                    class_name="quality-card",
                    icon="✺",
                ),
                
                # Accordion card
                html.Div(
                    className="data-grid-card workflow-card",
                    children=[
                        html.Div(
                            className="data-card-heading",
                            children=[
                                html.Span("⌇", className="data-card-icon"),
                                html.H3("What happens during a monitoring visit"),
                            ],
                        ),

                        dbc.Accordion(
                            always_open=True,
                            start_collapsed=True,
                            className="colour-accordion",
                            children=[
                                dbc.AccordionItem(
                                    [
                                        html.P(
                                            "Volunteers use the map to identify a location (e.g., a "
                                            "community planting, hedgerow or restoration site) and connect everything "
                                            "recorded there to the correct project."
                                        ),
                                        html.P(
                                            "A site record provides the context for the type "
                                            "of work taking place, who is involved and how the land is "
                                            "being managed."
                                        ),
                                    ],
                                    title="Adding a site to the map!",
                                    item_id="before-leaving",
                                    className="accordion-pink",
                                ),

                                dbc.AccordionItem(
                                    [
                                        html.P(
                                            "Volunteers map the precise shape of each planting area, either by placing "
                                            "points around its boundary or by walking around the edge while "
                                            "the phone records their route using GPS."
                                        ),
                                    ],
                                    title="Mapping the site boundaries",
                                    item_id="offline",
                                    className="accordion-green",
                                ),

                                dbc.AccordionItem(
                                    [
                                        html.P(
                                            "Volunteers record what was planted, when the planting took "
                                            "place and, where possible, the species and approximate number "
                                            "of trees involved."
                                        ),
                                        html.P(
                                            "They may also record details such as guards, tubes, fencing "
                                            "or other forms of protection. Together, these observations "
                                            "create a picture of the planting effort."
                                        ),
                                    ],
                                    title="What was planted?",
                                    item_id="add-site",
                                    className="accordion-blush",
                                ),

                                dbc.AccordionItem(
                                    [
                                        html.P(
                                            "On return visits, volunteers look for signs of tree health."
                                            " This includes survival, growth, browsing, "
                                            "damage, competition from surrounding vegetation and the "
                                            "condition of guards or fencing (e.g., deer infiltration)."
                                        ),
                                        html.P(
                                            "This helps better understand what "
                                            "may be helping or limiting the development of the planting."
                                        ),
                                    ],
                                    title="Signs of progress, potential for maintenance",
                                    item_id="add-planting",
                                    className="accordion-sage",
                                ),

                                dbc.AccordionItem(
                                    [
                                        html.P(
                                            "Photographs and repeat visits show how plantings develop" 
                                            "over time. This makes future volunteer "
                                            "visits more effective and highlights areas that may need attention."
                                        ),
                                    ],
                                    title="Progress over time",
                                    item_id="record-visit",
                                    className="accordion-rose",
                                ),

                            ],
                        ),
                    ],
                ),

                # Data structure card
                data_card(
                    "What volunteers record",
                    html.Div(
                        className="record-types",
                        children=[
                            html.Div([
                                html.Span("01"),
                                html.H4("Sites"),
                                html.P(
                                    "The overall location where restoration work "
                                    "takes place."
                                ),
                            ]),
                            html.Div([
                                html.Span("02"),
                                html.H4("Planting areas"),
                                html.P(
                                    "Mapped sections showing where trees or "
                                    "hedgerows were planted."
                                ),
                            ]),
                            html.Div([
                                html.Span("03"),
                                html.H4("Visits"),
                                html.P(
                                    "Monitoring, maintenance, deer impact, notes "
                                    "and photographs."
                                ),
                            ]),
                        ],
                    ),
                    class_name="records-card",
                    icon="▦",
                ),
            ],
        )
    ],
)