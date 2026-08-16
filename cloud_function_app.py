"""Wraps building this Cloud Function's Flask app - via current_app,
functions-framework's gen 1 trick (see main.py) - its Jinja
environment (retargeted at this file's directory, since Cloud
Functions doesn't lay files out like a normal Flask project), and an
optional hotloaded router, as explicit, independently callable methods
instead of a sequence of module-level statements.
"""
import importlib
import os
from os import path

import requests
from flask import current_app, request, jsonify, redirect
from jinja2 import Environment, FileSystemLoader, select_autoescape


class CloudFunctionApp:
    def __init__(self, root=None, router_env_var='ROUTER_MODULE'):
        self.root = root or path.dirname(path.abspath(__file__))
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
        self.env = Environment(
            loader=FileSystemLoader(self.root),
            autoescape=select_autoescape(['html', 'xml', 'htm', '.xhtml', '.svg']),
        )
        return self.env

    def register_routes(self):
        @self.app.route('/container/run')
        def main():
            return "container is running", 200

        return main

    def load_router(self):
        """Point ROUTER_MODULE (or router_env_var) at any importable
        module exposing register(app) and it bolts that router's routes
        onto self.app."""
        module_name = os.environ.get(self.router_env_var)
        if not module_name:
            return None

        module = importlib.import_module(module_name)
        return module.register(self.app)

    def build(self):
        self.build_app()
        self.build_jinja_env()
        main = self.register_routes()
        self.load_router()
        return main
