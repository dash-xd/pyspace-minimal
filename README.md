# cloud-function-app

Reusable machinery for running a Flask app inside a **Google Cloud
Function (gen 1, Python 3.12)** via the `functions-framework` trick,
with an optional hotloaded "router" module for application-specific
routes.

The package itself contains no application code - it just:

- obtains `functions-framework`'s Flask app (via `current_app`)
- builds a Jinja environment rooted at your function's source directory
- registers a default health-check route
- dynamically imports whatever module the `ROUTER_MODULE` environment
  variable points at and layers its `ROUTES` on top, letting a router
  override the default health check

## Layout

```
cloud-function-app/
├── pyproject.toml
├── README.md
├── LICENSE
├── main.py                 # example gen 1 entry point
├── requirements.txt        # example deployment requirements
└── src/
    └── cloud_function_app/
        ├── __init__.py
        └── app.py
```

`src/cloud_function_app` is the installable package (`cloud_function_app`
import name, `cloud-function-app` distribution name). `main.py` and
`requirements.txt` at the repo root double as a working example of a
Cloud Function that consumes it.

## Install

```
pip install .
```

or, for local development against the source tree:

```
pip install -e .
```

## Usage

In your Cloud Function's `main.py`:

```python
from os import path

from cloud_function_app import CloudFunctionApp

app = CloudFunctionApp(root=path.dirname(path.abspath(__file__)))
main = app.build()
```

Pass `root` explicitly - once `cloud_function_app` is installed via
pip, its own `__file__` lives in `site-packages`, not your function's
directory, so the package can't infer your project root on its own.

## Composing a router

Set `ROUTER_MODULE` in the function's environment to an importable
module exposing `ROUTES`, a `{url_rule: view_func}` dict:

```
ROUTER_MODULE=router
```

```python
# router.py
def hello():
    return "hello"

ROUTES = {
    "/hello": hello,
}
```

`CloudFunctionApp.build()` merges `ROUTES` on top of the package's own
`DEFAULT_ROUTES` (just `/container/run`) and registers the result on
the Flask app it built. A router can add new routes, like `/hello`
above, or override an existing rule outright - a router that defines
its own `/container/run` entry replaces the default health check
instead of colliding with it, since both are merged into one dict
before anything is registered.

## Deploying to Google Cloud Functions (gen 1, Python 3.12)

The deployed source directory needs `main.py`, `requirements.txt`, and
(if you're not installing from a published index) this package's
source alongside them - `requirements.txt` here installs it from the
local directory:

```
functions-framework==3.*
.
```

Deploy with:

```
gcloud functions deploy <name> \
    --no-gen2 \
    --runtime python312 \
    --entry-point main \
    --trigger-http
```

Add your router package (e.g. `git+https://github.com/you/your-router.git@main`)
as an additional line in `requirements.txt` and set `ROUTER_MODULE` in
the function's environment variables to wire it in - see
`.github/actions/router` for a reusable CI step that does this.
