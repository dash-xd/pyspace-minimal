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
from os import path

from pyspace import Service

app = Service(root=path.dirname(path.abspath(__file__)))
main = app.build()
```

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
PYSPACE_GOSPACE_NAME=gospace
PYSPACE_GOSPACE_ACTIVATE=true
```

Registration is cheap. The Go process is not spawned until a request actually dispatches to that application.

## Runtime hotloading

Programmatic registration is the primary primitive. For controlled development/runtime composition, setting `PYSPACE_CONTROL_TOKEN` also enables a hidden control surface. Requests without the exact `X-Pyspace-Control-Token` receive `404` so the management surface is not discoverable merely because the function is reachable.

The current endpoints are:

```text
GET  /_pyspace/apps
POST /_pyspace/activate/<name>
POST /_pyspace/module/<name>
POST /_pyspace/gospace/<name>
```

Register an already-installed Python module:

```json
{
  "module": "my_router",
  "activate": true
}
```

Register a bundled/local gospace executable:

```json
{
  "binary": "/workspace/bin/gospace",
  "activate": true
}
```

The control surface does not install packages, download executables, or create deployment artifacts. It only composes resources already made available by the deployment/runtime. Artifact acquisition belongs to a higher-level composition system.

## Gospace supervision

`ProcessSupervisor` is deliberately much smaller than systemd/s6. It implements request-driven reconciliation:

```text
request needs gospace
        |
        v
process cached and socket healthy?
        | yes
        +-----------------> reuse
        |
        no
        v
spawn exact argv once
        |
wait for Unix socket readiness
        |
        v
proxy original HTTP request
```

The supervisor uses a per-key lock, `subprocess.Popen(..., start_new_session=True)`, inherited stdout/stderr, Unix-socket readiness probing, and bounded SIGTERM -> SIGKILL cleanup. It has no background restart loop. If a child dies while the instance remains warm, the next request reconciles it. If the Cloud Function instance disappears, both Python and the child disappear together.

`gospace`'s worker CLI on `codex/modular-router-worker-wasm` supports:

```text
--unix-socket /tmp/pyspace/gospace.sock
```

Pyspace starts it that way and proxies the incoming method, path/query, headers, and body over the local socket. Gospace remains responsible for its own native/WASM router registry and execution. Pyspace does not understand the gospace WASM ABI.

The resulting boundary is:

```text
Google Cloud Functions Gen 1
        |
        v
Python 3.12 / pyspace
        |
        +-- Python router application (in-process)
        |
        `-- lazy gospace process
                |
                `-- native / pre-registered WASM / runtime WASM router
```

A future Redis HTTP-dispatch path can therefore target the gospace application through pyspace while keeping the Redis, Python supervision, gospace router loading, and WASM guest responsibilities separate.

## Composition and qualification boundary

This repository should remain a reusable host primitive, not a standing smoke-test deployment. The intended qualification model follows the same pattern used by `dash-xd/github-cdn` and `xd-dash/huram-abi-master`'s `worktree-automation`:

1. lock mutable source refs to immutable SHAs;
2. compose a disposable deployment repository from those exact inputs;
3. attach the profile-owned deployment/qualification harness;
4. deploy and prove the real runtime behavior;
5. tear down by default, with retention handled explicitly by the sandbox lifecycle policy;
6. only promote a composition after an exact successful qualification.

That future composition may use Android's Repo tool to materialize `pyspace-minimal`, `gospace`, and other components from a manifest. Neither pyspace nor gospace needs to own that orchestration now.

## Install and test

```bash
pip install .
```

For development:

```bash
pip install -e '.[test]'
pytest
```

The deployment requirements remain minimal:

```text
functions-framework==3.*
.
```

Deploy the composed source directory as a Python 3.12 Gen 1 HTTP function with `main` as the entry point.
