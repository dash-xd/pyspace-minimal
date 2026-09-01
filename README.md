# pyspace-minimal

`pyspace-minimal` is a stable Python 3.12 Google Cloud Functions Gen 1 host for applications that are supplied at deployment time or registered while a warm instance is running.

The repository deliberately contains **no built-in application**. Its job is analogous to the stable worker shell in `gospace`: keep the Cloud Functions entry point fixed while application implementations are composed behind it.

Two runtime application forms are currently supported:

- importable Python/Flask router modules exposing `ROUTES`;
- a lazily supervised `gospace` executable reached through a Unix-domain HTTP socket.

The instance-local registry and subprocess table are caches. If Google replaces the instance, the next request reconstructs whatever state it needs from the deployment/runtime inputs.

## Why `current_app` matters

Functions Framework creates its own Flask application and pushes its application context before importing the deployed `main.py`. `pyspace.Service.build_app()` therefore obtains that existing application through Flask's `current_app` rather than starting another WSGI server.

The Functions Framework still invokes one HTTP function for every path. Pyspace intentionally keeps a manual request dispatcher behind that single function instead of trying to add Flask URL rules after startup. That matters for hotloading: Flask normally prevents application setup mutations after the first request, while pyspace can safely add a new immutable `{path: view}` application to its own registry at any point in a warm instance's lifetime.

The deployment entry point remains tiny:

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

The default root is therefore the directory containing the deployed `main.py`, preserving the original `Service(root=path.dirname(path.abspath(__file__)))` behavior. A composed deployment can override that default with `PYSPACE_ROOT` without modifying the entry point.

`cloud_function_app.CloudFunctionApp` remains as a compatibility import, but `pyspace.Service` is the canonical API.

## Application registry

Registration and activation are separate, matching the gospace worker model.

```python
service.register_module("users-v1", "my_users_router")
service.register_module("admin-v3", "my_admin_router")
service.activate("users-v1")
```

Router modules expose the existing lightweight contract:

```python
# my_users_router.py

def hello():
    return "hello"

ROUTES = {
    "/hello": hello,
}
```

The `ROUTES` mapping is copied when registered. Registered application names are immutable; deploy/register a versioned name rather than mutating an application that may have in-flight requests.

Normal traffic uses the active application. A caller can select one registered application for a single request without changing the default by sending:

```text
X-Pyspace-App: admin-v3
```

That gives pyspace the same distinction gospace now has between default activation and request-scoped named dispatch.

## Deployment-time composition

`pyspace-minimal` does not pre-register anything itself. Deployment inputs may compose an application through environment variables:

```text
ROUTER_MODULE=my_router
PYSPACE_ROUTER_NAME=my-router-v1
PYSPACE_ROUTER_ACTIVATE=true
```

`ROUTER_MODULE` must already be importable in the deployed Python environment. The existing `.github/actions/router` helper can add its package to `requirements.txt` before deployment.

A bundled gospace binary can also be declared without starting it:

```text
PYSPACE_GOSPACE_BINARY=/workspace/bin/gospace
PYSPACE_GOSPACE_NAME=gospace-v1
PYSPACE_GOSPACE_ACTIVATE=true
```

The binary is hashed at registration time. The supervisor verifies that SHA-256 again immediately before each spawn, so an immutable application name cannot silently start different executable bytes later in the lifetime of the instance.

## Runtime composition

Runtime registration is optional and disabled unless `PYSPACE_CONTROL_TOKEN` is configured. Control requests use `X-Pyspace-Control-Token`; unauthorized control paths deliberately look absent.

An already-importable Python router can be registered with:

```text
POST /_pyspace/module/<name>
{"module":"package.module","activate":true}
```

An already-present gospace executable can be registered with:

```text
POST /_pyspace/gospace/<name>
{"binary":"/tmp/gospace","activate":true}
```

Pyspace deliberately does not contain a package downloader, Go compiler, or artifact transport. Those are composition concerns. Runtime registration only turns an implementation that is already available to the instance into a named application.

## Gospace supervisor

The gospace backend is request-driven rather than a conventional daemon supervisor:

```text
request for gospace-v1
        |
        v
pyspace registry
        |
        v
process supervisor
   |          |
 alive      absent/dead
   |          |
 reuse      spawn
   |          |
   +----+-----+
        |
        v
Unix-domain HTTP socket
        |
        v
     gospace
```

There is no background restart loop. If the Cloud Functions instance is frozen or destroyed, the child process is merely lost instance-local cache state. The next request on a surviving/new instance reconciles what it needs.

The supervisor serializes spawn per process key, starts each child in its own session, probes Unix-socket readiness, inherits stdout/stderr so child logs reach the platform logger, and terminates the complete process group during explicit cleanup.

Pyspace proxies the original HTTP method, path/query, body and ordinary headers to gospace. Hop-by-hop headers and pyspace's own selection/control headers are not forwarded.

## Composition and qualification

This repository should not own live cloud smoke-test infrastructure. The intended qualification boundary follows `huram-abi-master`'s `worktree-automation` model: resolve pyspace and gospace inputs to exact commits, archive immutable component worktrees into a generated deployment repository, build the gospace executable there, and deploy the resulting Python Functions Framework composition.

That keeps the component repositories reusable and makes the generated deployment repository the evidence-bearing unit. A future Android `repo` manifest can describe the same pinned multi-repository composition without changing pyspace or gospace runtime semantics.
