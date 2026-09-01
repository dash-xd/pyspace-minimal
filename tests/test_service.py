import sys
import types

from pyspace.service import (
    APP_HEADER,
    CONTROL_TOKEN_HEADER,
    HEALTH_PATH,
    MODULE_HINT_HEADER,
    Service,
)


class Request:
    def __init__(self, path: str, app: str | None = None, headers: dict | None = None):
        self.path = path
        self.headers = dict(headers or {})
        if app is not None:
            self.headers[APP_HEADER] = app


def test_shell_health_does_not_require_an_application():
    service = Service(control_token="test")
    assert service.registry.names() == ()
    assert service.dispatch(Request(HEALTH_PATH)) == ("ok", 200)


def test_module_can_be_registered_after_an_active_app_exists():
    first = types.ModuleType("test_router_first")
    first.ROUTES = {"/value": lambda: "first"}
    second = types.ModuleType("test_router_second")
    second.ROUTES = {"/value": lambda: "second"}
    sys.modules[first.__name__] = first
    sys.modules[second.__name__] = second

    service = Service(control_token="test")
    service.register_module("first-v1", first.__name__)
    service.activate("first-v1")
    service.register_module("second-v1", second.__name__)

    assert service.dispatch(Request("/value")) == "first"
    assert service.dispatch(Request("/value", "second-v1")) == "second"
    assert service.registry.active() == "first-v1"


def test_missing_module_is_hotloaded_and_dispatched_by_same_request():
    module = types.ModuleType("test_router_hinted")
    module.ROUTES = {"/value": lambda: "hinted"}
    sys.modules[module.__name__] = module

    service = Service(control_token="test")
    request = Request(
        "/value",
        "hinted-v1",
        {
            MODULE_HINT_HEADER: module.__name__,
            CONTROL_TOKEN_HEADER: "test",
        },
    )

    assert service.dispatch(request) == "hinted"
    assert service.registry.names() == ("hinted-v1",)

    # Once warm, the loader hint and token are no longer necessary.
    assert service.dispatch(Request("/value", "hinted-v1")) == "hinted"


def test_loader_hint_requires_control_token_only_when_cold():
    module = types.ModuleType("test_router_unauthorized")
    module.ROUTES = {"/value": lambda: "nope"}
    sys.modules[module.__name__] = module

    service = Service(control_token="test")
    request = Request(
        "/value",
        "unauthorized-v1",
        {MODULE_HINT_HEADER: module.__name__},
    )

    assert service.dispatch(request) == ("Not Found", 404)
    assert service.registry.names() == ()
