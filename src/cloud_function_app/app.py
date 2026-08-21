"""Wraps building this Cloud Function's Flask app - via current_app,
functions-framework's gen 1 trick (see main.py) - its Jinja
environment, and an optional hotloaded router, as explicit,
independently callable methods instead of a sequence of module-level
statements.
"""
import importlib
import os

from flask import current_app
from jinja2 import Environment, FileSystemLoader, select_autoescape


class CloudFunctionApp:
    DEFAULT_ROUTES = {
        '/container/run': lambda: ("container is running", 200),
    }

    def __init__(self, root=None, router_env_var='ROUTER_MODULE'):
        self.root = root
        self.router_env_var = router_env_var
        self.app = None
        self.env = None

    def build_app(self):
        """functions-framework builds its own Flask app and pushes that
        app's context before importing main.py - current_app resolves
        to it from here."""
        self.app = current_app
        return self.app

    def build_jinja_env(self):
        """Falls back to the current working directory - which, at
        runtime, is the Cloud Function's source directory - rather than
        this package's own install location, since once installed via
        pip, __file__ would point into site-packages instead of the
        consuming function's project."""
        root = self.root or os.getcwd()
        self.env = Environment(
            loader=FileSystemLoader(root),
            autoescape=select_autoescape(['html', 'xml', 'htm', '.xhtml', '.svg']),
        )
        return self.env

    def load_router_routes(self):
        """Point ROUTER_MODULE (or router_env_var) at any importable
        module exposing ROUTES, a {url_rule: view_func} dict, and
        return it. Missing module or ROUTES yields no extra routes."""
        module_name = os.environ.get(self.router_env_var)
        if not module_name:
            return {}

        module = importlib.import_module(module_name)
        return getattr(module, 'ROUTES', {})

    def register_routes(self):
        """Registers DEFAULT_ROUTES, then layers the hotloaded
        router's routes on top - a router rule for '/container/run'
        overrides the default health check rather than colliding with
        it, since both are merged into the same {rule: view} dict
        before any of them touch self.app."""
        routes = dict(self.DEFAULT_ROUTES)
        routes.update(self.load_router_routes())

        for rule, view_func in routes.items():
            self.app.add_url_rule(rule, endpoint=rule, view_func=view_func)

        return routes['/container/run']

    def build(self):
        self.build_app()
        self.build_jinja_env()
        return self.register_routes()
