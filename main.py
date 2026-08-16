"""Generic GCP Cloud Functions (1st gen) Flask entry point. Owns no
routes or business logic, and never imports a router-providing repo
directly by name - which (and how many) routers back this deployment
is entirely driven by routers.yaml, loaded dynamically at import time
below. See .github/actions/sync-routers (backed by the `repo`
multi-repo tool and manifest/default.xml) for how each router's actual
code gets fetched into the local paths routers.yaml references, or run
tools/sync-routers.sh directly.

Checked in, routers.yaml declares a single router
(gcp_python_function_inspector.router) mounted at "/" - see that file
to add more, or point it at something else entirely.

functions-framework builds its own Flask app and pushes that app's
context before importing this module, which is what makes `current_app`
resolve to something real here. _load_routers(app) below hands each
configured router that same app (or a Blueprint, if it's mounted under
a prefix) to register routes on directly via plain `@app.route(...)`,
then returns the function functions-framework's target (entry_point
"main") should actually point at - the last router to return a
callable from its register(app) wins that role; if none do, requests
to anything no router claimed just get a 404.
"""
import importlib
import sys
from collections import Counter
from pathlib import Path

import yaml
from flask import Blueprint, current_app
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent

app = current_app

env = Environment(
    loader=FileSystemLoader(str(ROOT)),
    autoescape=select_autoescape(["html", "xml", "htm", ".xhtml", ".svg"]),
)


def _default_main(request):
    return "not found", 404


def _load_routers(app):
    config = yaml.safe_load((ROOT / "routers.yaml").read_text()) or {}

    claimed_by: dict[str, str] = {}
    fallback = None

    for entry in config.get("routers", []):
        name = entry.get("name", entry["module"])
        module_name = entry["module"]
        mount = entry.get("mount") or "/"

        router_dir = str(ROOT / entry["path"])
        if router_dir not in sys.path:
            sys.path.insert(0, router_dir)
        module = importlib.import_module(module_name)

        if mount == "/":
            result = module.register(app)
        else:
            blueprint = Blueprint(name, module_name)
            result = module.register(blueprint)
            app.register_blueprint(blueprint, url_prefix=mount)

        # A plain set of rule strings would collapse two Rule objects
        # that share a path into one entry, hiding exactly the
        # collision this is meant to catch - counting occurrences
        # instead means any path with more than one Rule registered to
        # it (which can only have just happened, since every prior
        # iteration left counts at 1) gets caught immediately.
        counts = Counter(rule.rule for rule in app.url_map.iter_rules())
        for rule, count in counts.items():
            if count > 1:
                raise RuntimeError(
                    f"router {name!r} registered {rule!r}, already claimed by "
                    f"{claimed_by.get(rule, 'an earlier router')!r} - give one "
                    "of them a distinct mount prefix in routers.yaml"
                )
            claimed_by.setdefault(rule, name)

        if callable(result):
            fallback = result

    return fallback or _default_main


main = _load_routers(app)
