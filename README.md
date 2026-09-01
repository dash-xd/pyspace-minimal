# pyspace-minimal

`pyspace-minimal` is a Python 3.12 Google Cloud Functions Gen 1 host with no built-in app. A request can name an app that is already warm, or carry a loader hint that lets pyspace register it and handle that same request immediately.

## Python router

```python
# hello_router.py
from flask import request


def hello():
    return "payload=" + request.get_data(as_text=True)


ROUTES = {
    "/hello": hello,
}
```

If it is not registered yet, the first request carries the app name, module hint, control token, and normal request payload together:

```http
POST /hello
X-Pyspace-App: hello-v1
X-Pyspace-Module: hello_router
X-Pyspace-Control-Token: <PYSPACE_CONTROL_TOKEN>
Content-Type: text/plain

abc
```

The response is:

```text
payload=abc
```

Pyspace imports `hello_router`, registers it as `hello-v1`, then sends the same request to `/hello`. There is no separate registration request.

Once the instance is warm, only the app name is needed:

```http
POST /hello
X-Pyspace-App: hello-v1
Content-Type: text/plain

xyz
```

You can still pre-register the same router at deployment:

```text
ROUTER_MODULE=hello_router
PYSPACE_ROUTER_NAME=hello-v1
PYSPACE_ROUTER_ACTIVATE=true
```

## Gospace app

A request can use the same pattern to lazy-load the gospace executable:

```http
POST /...
X-Pyspace-App: gospace-v1
X-Pyspace-Gospace-Binary: /workspace/bin/gospace
X-Pyspace-Control-Token: <PYSPACE_CONTROL_TOKEN>
...
```

On a miss, pyspace registers the executable, starts it on a Unix socket, and forwards that same request. If `gospace-v1` is already warm, `X-Pyspace-Gospace-Binary` and the pyspace control token are not needed.

The forwarded request may also contain gospace's own router hint, so one cold request can do:

```text
request + pyspace hint + gospace hint + WASM
        |
        v
pyspace loads/spawns gospace if needed
        |
        v
gospace loads the WASM router if needed
        |
        v
original request payload runs through the router
```

See `dash-xd/gospace` for the `X-Gospace-Router` multipart request format.

## Request-scoped selection

`X-Pyspace-App` selects one app for one request without changing the default:

```http
GET /hello
X-Pyspace-App: hello-v1
```

To change the default explicitly:

```http
POST /_pyspace/activate/hello-v1
X-Pyspace-Control-Token: <PYSPACE_CONTROL_TOKEN>
```

## Cloud Function entry point

```python
import os
from os import path

from pyspace import Service

app = Service(
    root=os.environ.get(
        "PYSPACE_ROOT",
        path.dirname(path.abspath(__file__)),
    )
)
_dispatch = app.build()


def main(request):
    return _dispatch(request)
```

`PYSPACE_ROOT` is optional. Without it, pyspace uses the directory containing `main.py`. The wrapper is intentional: Functions Framework requires the exported `main` target itself to be a Python function rather than a bound method.

## Hint headers

```text
X-Pyspace-App             target app name
X-Pyspace-Module          importable Python module, used only on a cache miss
X-Pyspace-Gospace-Binary  gospace executable path, used only on a cache miss
X-Pyspace-Control-Token   required only when a request causes a runtime load
```

Exactly one loader hint may be supplied on a cache miss. Registered app names are immutable for the lifetime of the instance.

The older `/_pyspace/module/<name>` and `/_pyspace/gospace/<name>` control endpoints remain available for explicit management, but they are not required for lazy request dispatch.
