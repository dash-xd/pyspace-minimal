import requests
import os
from os import path

from flask import Flask, current_app, request, jsonify, redirect
app = current_app

from jinja2 import Environment, FileSystemLoader, select_autoescape
env = Environment(
    loader=FileSystemLoader(path.dirname(path.abspath(__file__))),
    autoescape=select_autoescape(['html', 'xml', 'htm', '.xhtml', '.svg'])
)

@app.route('/container/run')
def main():
    return "container is running", 200

# Hook: point ROUTER_MODULE at any importable module exposing
# register(app) - e.g. ROUTER_MODULE=gcp_python_function_inspector.router,
# with that package added to requirements.txt (a plain PyPI name, or
# git+https://... for a repo not published to PyPI) - and it bolts its
# routes onto this same app. Leave ROUTER_MODULE unset to just deploy
# the /container/run route above with nothing hooked in.
router_module = os.environ.get('ROUTER_MODULE')
if router_module:
    import importlib
    importlib.import_module(router_module).register(app)
