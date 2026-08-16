"""Generic router hook: point an environment variable (ROUTER_MODULE by
default) at any importable module exposing register(app), and
load_router(app) imports it and calls register(app) - the one
mechanism used to bolt an arbitrary other router's routes onto a Flask
app. Returns whatever register(app) returns (or None if the env var
isn't set), in case a caller wants to use that.
"""
import importlib
import os


def load_router(app, env_var='ROUTER_MODULE'):
    module_name = os.environ.get(env_var)
    if not module_name:
        return None

    module = importlib.import_module(module_name)
    return module.register(app)
