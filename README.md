# pyspace-minimal

`pyspace-minimal` is a Python 3.12 Google Cloud Functions Gen 1 host whose entry point stays fixed while applications are supplied at deployment time or registered later on a warm instance.

The repository intentionally contains **no pre-registered application**. The stable part is the Python Functions Framework host; applications are composed behind it.

Pyspace currently supports two kinds of application:

1. **Python router modules** exposing a `ROUTES` mapping. These run in-process inside the Python Cloud Function.
2. **A gospace executable**. Pyspace supervises the Go process lazily and forwards requests to it over a Unix-domain HTTP socket. Gospace can then dispatch to its own native or WASM routers.

The application registry and the gospace process table are instance-local caches. If Google replaces the function instance, they disappear and are reconstructed from deployment/runtime inputs when needed again.

## 1. Minimal Cloud Function entry point

The normal `main.py` is:

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

With no override, `root` is the directory containing `main.py`:

```python
Service(root=path.dirname(path.abspath(__file__)))
```

A composed deployment can override that location without rewriting `main.py`:

```text
PYSPACE_ROOT=/workspace/application
```

`Service.build()` obtains the Flask application already created by Functions Framework through `flask.current_app`. Pyspace does **not** start a second WSGI server.

The shell itself is available even when no application has been registered:

```text
GET /_pyspace/healthz
```

returns:

```text
ok
```

All other application traffic requires either an active application or an explicit request-scoped application selection.

## 2. Python router modules

A Python application is any importable module exposing `ROUTES`:

```python
# users_router.py

def hello():
    return "hello"


def user_42():
    return {"id": 42, "name": "example"}


ROUTES = {
    "/hello": hello,
    "/users/42": user_42,
}
```

The values are ordinary callables suitable for Flask-style responses. Pyspace copies the mapping when the application is registered, so later mutation of `ROUTES` does not silently modify the registered application.

### Load a Python router at deployment time

Make the package/module importable in the deployed Python environment, then set:

```text
ROUTER_MODULE=users_router
PYSPACE_ROUTER_NAME=users-v1
PYSPACE_ROUTER_ACTIVATE=true
```

At instance initialization, pyspace effectively performs:

```python
service.register_module("users-v1", "users_router")
service.activate("users-v1")
```

Requests then go to that application by default:

```text
GET /hello
```

The existing `.github/actions/router` action can append a Python package requirement to the deployment's `requirements.txt`. `ROUTER_MODULE` identifies the importable module inside that installed package.

### Register a Python router programmatically

Code that already has a `Service` instance can register applications directly:

```python
service.register_module("users-v1", "users_router")
service.register_module("admin-v2", "admin_router")
service.activate("users-v1")
```

Registration and activation are deliberately separate.

Registered names are immutable. To deploy a changed implementation, use a new name such as:

```text
users-v2
```

rather than replacing `users-v1` while requests may still be using it.

### Hotload an already-importable Python router at runtime

Set a control token in the Cloud Function environment:

```text
PYSPACE_CONTROL_TOKEN=<secret>
```

Then register a module already present in the Python environment:

```http
POST /_pyspace/module/users-v2
X-Pyspace-Control-Token: <secret>
Content-Type: application/json

{
  "module": "users_router_v2",
  "activate": true
}
```

`activate` is optional. With `false` or omitted, the module is registered but does not become the default application.

This works after the instance has already handled requests. Pyspace does not add Flask URL rules after startup; Functions Framework continues invoking the same single Python function, and pyspace's own application registry performs the routing. This avoids Flask's normal restriction against mutating application setup after the first request.

Runtime registration does **not** install Python packages. The module must already be importable, whether because it was bundled into the deployment, installed by `requirements.txt`, or made available by a higher-level composition mechanism.

## 3. Default activation versus request-scoped selection

One registered application can be the default:

```python
service.activate("users-v1")
```

Normal requests then use `users-v1`.

A request can instead select another registered application without changing the default:

```http
GET /reports
X-Pyspace-App: admin-v2
```

This is request-scoped dispatch. After that request completes, the active/default application is still whatever it was before.

The model is:

```text
registered applications
    users-v1
    users-v2
    admin-v2
       |
       +---- active = users-v1
       |
request without X-Pyspace-App
       -> users-v1

request with X-Pyspace-App: admin-v2
       -> admin-v2 for this request only
```

The current registry can be inspected through the protected control surface:

```http
GET /_pyspace/apps
X-Pyspace-Control-Token: <secret>
```

and the default can be changed explicitly:

```http
POST /_pyspace/activate/users-v2
X-Pyspace-Control-Token: <secret>
```

If `PYSPACE_CONTROL_TOKEN` is not configured, the control surface is disabled. Requests to control paths without the correct token return `404` so the management surface is not exposed merely because the function is reachable.

## 4. Running gospace under pyspace

Pyspace can treat a gospace executable as another registered application.

The important separation is:

```text
Google Cloud Functions Gen 1
        |
        v
Python 3.12 / pyspace
        |
        +-- Python ROUTES application
        |
        `-- gospace application
                |
                | Unix-domain HTTP socket
                v
             gospace
                |
                +-- native Go router
                +-- pre-registered WASM router
                `-- runtime/lazy WASM router
```

Pyspace is responsible only for making sure the Go process exists and forwarding HTTP to it. Pyspace does not know how gospace's router registry or WASM ABI works.

### Gospace binary requirement

The gospace worker branch used with this feature supports:

```text
--unix-socket /tmp/pyspace/gospace.sock
```

A composed Linux deployment should build or provide an executable gospace binary, for example at:

```text
/workspace/bin/gospace
```

Pyspace checks that the file exists and is executable, records its SHA-256 when the application is registered, and verifies the same digest immediately before each later spawn. A versioned pyspace application name therefore cannot silently respawn different executable bytes from the same filesystem path.

### Load gospace at deployment time

Set:

```text
PYSPACE_GOSPACE_BINARY=/workspace/bin/gospace
PYSPACE_GOSPACE_NAME=gospace-v1
PYSPACE_GOSPACE_ACTIVATE=true
```

Optional tuning:

```text
PYSPACE_SOCKET_DIR=/tmp/pyspace
PYSPACE_GOSPACE_READY_TIMEOUT=5
PYSPACE_GOSPACE_REQUEST_TIMEOUT=10
```

Registration happens when the Python instance initializes, but the Go process does **not** start yet.

The first request requiring `gospace-v1` causes the process to start:

```text
first request
    |
    v
is gospace-v1 already alive and ready?
    |
    no
    |
    v
spawn gospace --unix-socket ...
    |
wait for socket readiness
    |
forward original HTTP request
```

Later requests reuse the same healthy child while that Cloud Function instance remains warm.

### Register gospace programmatically

```python
service.register_gospace(
    "gospace-v1",
    "/workspace/bin/gospace",
)
service.activate("gospace-v1")
```

Registration still does not spawn the process. `ProcessSupervisor.acquire()` is called only when a request actually dispatches to that backend.

### Hotload an already-present gospace binary at runtime

With `PYSPACE_CONTROL_TOKEN` configured:

```http
POST /_pyspace/gospace/gospace-v2
X-Pyspace-Control-Token: <secret>
Content-Type: application/json

{
  "binary": "/workspace/bin/gospace-v2",
  "activate": true
}
```

Optional fields are also accepted:

```json
{
  "binary": "/workspace/bin/gospace-v2",
  "socket_dir": "/tmp/pyspace",
  "ready_timeout": 5,
  "request_timeout": 10,
  "activate": false
}
```

The response includes the SHA-256 pyspace bound to that registration.

As with Python modules, runtime gospace registration does not download or compile anything. The executable must already exist on the function filesystem and be executable.

## 5. Sending a request through gospace

If gospace is active, ordinary requests automatically flow through it:

```http
POST /users/42
Content-Type: application/json

{"name":"alice"}
```

Pyspace forwards the original HTTP method, path/query, body, and ordinary headers to the Unix socket.

If gospace is registered but is not the active default, select it for one request:

```http
POST /users/42
X-Pyspace-App: gospace-v1
Content-Type: application/json

{"name":"alice"}
```

`X-Pyspace-App` and `X-Pyspace-Control-Token` are pyspace-internal headers and are stripped before proxying into gospace. Hop-by-hop HTTP headers are also removed.

What happens after the request reaches gospace is entirely gospace's responsibility. For example, gospace may use its currently active router, a named/request-scoped router, or a dynamically loaded WASM router according to its own API and configuration.

## 6. Supervisor behavior

`ProcessSupervisor` is a small lazy process cache, not a full daemon supervisor.

For each process key it provides:

```text
request A --+
request B --+--> same absent gospace process --> one spawn
request C --+
```

The implementation uses a per-key lock to serialize spawning.

A healthy child is reused. A dead or unready child is discarded and reconciled by the next request that needs it. There is no background restart loop.

The subprocess is created with its own process session, inherits stdout/stderr so Go logs reach the Cloud Function logger, and is stopped as a process group with bounded `SIGTERM` then `SIGKILL` escalation during explicit cleanup.

This is intentionally Cloud-Functions-style lifecycle management:

```text
child process = warm-instance cache
```

not:

```text
child process = durable daemon that must stay alive independently of requests
```

If Google destroys the Cloud Function instance, losing the Python process, gospace process, socket, and registry state is expected.

## 7. Complete example: Python router + gospace side by side

Suppose a deployment contains:

```text
main.py
users_router.py
bin/gospace
```

and configures:

```text
ROUTER_MODULE=users_router
PYSPACE_ROUTER_NAME=users-python-v1
PYSPACE_ROUTER_ACTIVATE=true

PYSPACE_GOSPACE_BINARY=/workspace/bin/gospace
PYSPACE_GOSPACE_NAME=users-go-v1
PYSPACE_GOSPACE_ACTIVATE=false
```

Then:

```text
GET /hello
```

uses the active Python router.

This request:

```http
GET /hello
X-Pyspace-App: users-go-v1
```

lazily starts gospace if necessary and sends that one request to it instead, without changing the default Python application.

Later you can explicitly switch the default:

```http
POST /_pyspace/activate/users-go-v1
X-Pyspace-Control-Token: <secret>
```

After that, normal requests go through gospace while `users-python-v1` remains registered and can still be selected per request.

## 8. What pyspace-minimal does not do

Pyspace deliberately does not own artifact acquisition or deployment orchestration. In particular, the runtime does not:

- `pip install` arbitrary packages from control requests;
- download arbitrary gospace binaries;
- compile Go code;
- fetch WASM routers for gospace;
- persist the application/process registry across Cloud Function instances;
- create deployment repositories or cloud resources.

Those concerns belong to the composition/qualification layer.

The intended future qualification flow follows `huram-abi-master`'s `worktree-automation` idioms: resolve pyspace and gospace to exact immutable commits, compose a disposable deployment repository, build the gospace executable into that payload, deploy it as a Python 3.12 Gen 1 function, prove the real supervisor/socket/router behavior, and tear the sandbox down by default.

That same boundary can later be represented by an Android `repo` manifest without changing pyspace's runtime API.

## 9. Install and local tests

Install the package:

```bash
pip install .
```

For development:

```bash
pip install -e '.[test]'
pytest
```

A minimal Cloud Functions deployment still needs:

```text
functions-framework==3.*
.
```

and deploys `main` as the Python HTTP entry point.

## Quick reference

| Goal | Mechanism |
| --- | --- |
| Shell health check | `GET /_pyspace/healthz` |
| Load Python router at deployment | `ROUTER_MODULE` + `PYSPACE_ROUTER_NAME` |
| Register Python router in code | `service.register_module(name, module)` |
| Hotload already-importable Python router | `POST /_pyspace/module/<name>` |
| Set default application | `service.activate(name)` or `POST /_pyspace/activate/<name>` |
| Select app for one request | `X-Pyspace-App: <name>` |
| Load gospace at deployment | `PYSPACE_GOSPACE_BINARY` + `PYSPACE_GOSPACE_NAME` |
| Register gospace in code | `service.register_gospace(name, binary)` |
| Hotload already-present gospace | `POST /_pyspace/gospace/<name>` |
| Inspect registry | `GET /_pyspace/apps` |
| Enable control API | `PYSPACE_CONTROL_TOKEN` |
