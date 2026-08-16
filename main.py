"""Generic GCP Cloud Functions (1st gen) Flask entry point. Owns no
routes or business logic, and never imports a route-providing repo
directly. It always imports the routersource package below; that
package's source.py is what a deploy step regenerates to target a
specific repo's routes (see .github/actions/router, or run
`python tools/genrouter.py --router-module=...` directly).

Checked in, this targets the default: a health check route and
nothing else, so this repo builds, runs, and deploys standalone with
no external route-providing dependency until something overrides it.

functions-framework builds its own Flask app and pushes that app's
context before importing this module - that's what makes `current_app`
resolve to something real here, and letting routersource.register(app)
add live routes to it via plain `@app.route(...)`. It also still
requires this module's configured target (see the `entry_point`
Terraform variable / FUNCTION_TARGET) to be an actual top-level
function, which is what `main` below is for: functions-framework binds
it to a catch-all "/" and "/<path:path>" rule, but Werkzeug always
prefers a literal-path rule over that catch-all, so any request
matching a route added by routersource.register never reaches it. Only
requests to paths nothing above claims fall through to it.
"""
from os import path

from flask import current_app
from jinja2 import Environment, FileSystemLoader, select_autoescape

from routersource import register

app = current_app

env = Environment(
    loader=FileSystemLoader(path.dirname(path.abspath(__file__))),
    autoescape=select_autoescape(["html", "xml", "htm", ".xhtml", ".svg"]),
)

register(app)


def main(request):
    return "not found", 404
