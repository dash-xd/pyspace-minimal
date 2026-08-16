"""Smoke-checks that every router routers.yaml declares imports and
registers cleanly, without needing a real functions-framework server -
a fast check to run in CI (see .github/actions/sync-routers) before,
or instead of, actually serving traffic with run-local.

main.py's module-level `app = current_app` needs a Flask application
context to resolve at all - functions-framework normally provides one,
but this script pushes its own throwaway app's context instead so the
same loading/registration/collision-detection logic in main.py runs
for real without needing a live server.
"""
import sys
from pathlib import Path

import flask

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

app = flask.Flask(__name__)
with app.app_context():
    import main as _main  # noqa: F401 (import executes main.py's module body)

    assert callable(_main.main), "main.py did not resolve to a callable main"

print("routers loaded OK:")
for rule in sorted(r.rule for r in app.url_map.iter_rules()):
    print(f"  {rule}")
