# pyspace-minimal

`pyspace-minimal` is a Python 3.12 Google Cloud Functions Gen 1 host with no built-in application. Routes are supplied at deployment time or registered while an instance is warm.

The Cloud Function entry point is `main`.

## 1. Python router file

A Python router is one file exposing `ROUTES`:

```python
# hello_router.py

def hello():
    return "hello from python"


def health():
    return "ok"


ROUTES = {
    "/hello": hello,
    "/health": health,
}
```

Load it at deployment:

```text
ROUTER_MODULE=hello_router
PYSPACE_ROUTER_NAME=hello-v1
PYSPACE_ROUTER_ACTIVATE=true
```

Or register the same already-importable file at runtime:

```http
POST /_pyspace/module/hello-v1
X-Pyspace-Control-Token: <PYSPACE_CONTROL_TOKEN>
Content-Type: application/json

{"module":"hello_router","activate":true}
```

Then:

```text
GET /hello
```

returns `hello from python`.

## 2. Gospace router

Gospace is registered as one pyspace application. Pyspace starts the binary lazily on its first request and proxies requests to it over a Unix socket.

A deployment containing the gospace binary can use:

```text
PYSPACE_GOSPACE_BINARY=/workspace/bin/gospace
PYSPACE_GOSPACE_NAME=gospace-v1
PYSPACE_GOSPACE_ACTIVATE=true
```

Or register the same already-present executable at runtime:

```http
POST /_pyspace/gospace/gospace-v1
X-Pyspace-Control-Token: <PYSPACE_CONTROL_TOKEN>
Content-Type: application/json

{"binary":"/workspace/bin/gospace","activate":true}
```

The first ordinary request then causes:

```text
request
  -> pyspace
  -> start gospace if absent
  -> /tmp/pyspace/*.sock
  -> gospace router
```

Later requests on the same warm instance reuse the child process.

Gospace itself can contain native Go routers, preregistered WASM routers, or runtime-loaded WASM routers; pyspace does not need to distinguish between them.

## 3. More than one router

Registered applications have immutable names. One can be active while another is selected for a single request.

For example, with `hello-v1` active and `gospace-v1` also registered:

```text
GET /hello
```

uses `hello-v1`.

To send one request to gospace instead:

```http
GET /some/path
X-Pyspace-App: gospace-v1
```

This does not change the active application.

To change the default:

```http
POST /_pyspace/activate/gospace-v1
X-Pyspace-Control-Token: <PYSPACE_CONTROL_TOKEN>
```

## Cloud Function entry point

The repository's `main.py` is intentionally small:

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
main = app.build()
```

`PYSPACE_ROOT` is optional. Without it, the root is the directory containing `main.py`.

Functions Framework creates the Flask application. `Service` reuses that application through Flask `current_app` and keeps its own application registry, so Python routers can be registered after the instance has already handled requests without modifying Flask's URL map.

## Runtime control

Runtime registration is disabled unless `PYSPACE_CONTROL_TOKEN` is set. Send that value in `X-Pyspace-Control-Token` for control requests.

```text
GET  /_pyspace/healthz
GET  /_pyspace/apps
POST /_pyspace/module/<name>
POST /_pyspace/gospace/<name>
POST /_pyspace/activate/<name>
```

`/_pyspace/healthz` does not require the control token. The other control paths do.

Pyspace only registers code already available to the instance. It does not download Python packages, download binaries, build Go, or deploy itself. Those are composition/deployment concerns and can be handled later by the generated qualification repository and `huram-abi-master` worktree automation.
