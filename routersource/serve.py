"""Not touched by tools/genrouter.py - only source.py gets regenerated.
This file owns wiring source.py's routes into the fallback HTTP entry
point functions-framework requires, so main.py doesn't have to, and so
a route-providing package (source.py's register, whether the checked-in
default or a hotloaded remote one) never has to know that requirement
exists - it only ever needs to attach routes to the app it's handed,
same contract as e.g. a Node simple-router-builder-style router.
"""
from routersource.source import register as _register


def _default_main(request):
    return "not found", 404


def register(app):
    """Registers this deployment's routes onto app (via source.register),
    then returns the function functions-framework's target should point
    at.

    functions-framework builds its own Flask app and pushes that app's
    context before importing main.py - that's what makes `current_app`
    resolve to something real there, and lets source.register add live
    routes to it via plain `@app.route(...)`. It still requires the
    configured target (see the `entry_point` Terraform variable /
    FUNCTION_TARGET) to be an actual top-level function though, which is
    what the function returned here is for: functions-framework binds it
    to a catch-all "/" and "/<path:path>" rule, but Werkzeug always
    prefers a literal-path rule over that catch-all, so any request
    matching a route source.register added never reaches it - only
    requests to paths nothing else claims fall through to it.

    source.register may optionally return its own callable to use
    instead of the generic 404 above - e.g. a router that wants its own
    catch-all/home-page behavior for unmatched paths, the way a
    functions_framework.http-decorated `main` would traditionally serve
    that role. Returning None (or nothing) opts into the default.
    """
    fallback = _register(app)
    return fallback if callable(fallback) else _default_main
