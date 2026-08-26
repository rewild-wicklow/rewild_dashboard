import dash
from dash import Dash, html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import dash_leaflet.express as dlx
import pandas as pd
import plotly.express as px

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True
)

server = app.server


def nav_link(label, href, dropdown=False):
    return dcc.Link(
        html.Span([
            label,
            html.Span("⌄", className="chevron") if dropdown else None
        ]),
        href=href,
        className="nav-link"
    )


navbar = html.Header(
    className="topbar",
    children=[
        dcc.Link(
            html.Img(src="assets/rewild_logo.png", className="logo"),
            href="/"
        ),

        html.Button(
            "☰",
            id="mobile-nav-toggle",
            className="mobile-nav-toggle",
            n_clicks=0,
            **{
                "aria-label": "Open navigation menu",
                "aria-expanded": "false",
            }
        ),

        html.Nav(
            id="nav-menu",
            className="nav-menu",
            children=[
                nav_link("About", "/", dropdown=False),
                html.Span("·", className="dot"),
                nav_link("Project Map", "/projects", dropdown=False),
                html.Span("·", className="dot"),
                nav_link("Volunteer Data Portal", "/data", dropdown=False),
                html.Span("·", className="dot"),
                nav_link("Tree Guide", "/tree-guide"),
                html.Span("·", className="dot"),
                html.A(
                    "ReWild Home",
                    href="https://rewildwicklow.ie/",
                    className="home-btn",
                    target="_blank"
                )
            ]
        )
    ]
)


app.layout = html.Div([
    navbar,
    html.Main(
        dash.page_container,
        className="page-content"
    )
])


@callback(
    Output("nav-menu", "className"),
    Output("mobile-nav-toggle", "children"),
    Output("mobile-nav-toggle", "aria-expanded"),
    Input("mobile-nav-toggle", "n_clicks"),
    State("nav-menu", "className"),
    prevent_initial_call=True,
)
def toggle_mobile_nav(n_clicks, current_class):
    is_open = "is-open" in (current_class or "")

    if is_open:
        return "nav-menu", "☰", "false"

    return "nav-menu is-open", "×", "true"


if __name__ == "__main__":
    app.run(debug=True)