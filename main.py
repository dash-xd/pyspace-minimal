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
context before importing this module, which is what makes `current_app`
resolve to something real here. register(app) (see routersource/serve.py)
attaches whatever routes routersource.source provides directly to that
app via plain `@app.route(...)`, then hands back the function
functions-framework's target (entry_point "main") should actually point
at.
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

main = register(app)
