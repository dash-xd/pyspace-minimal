import sys
import types

from pyspace.service import APP_HEADER, HEALTH_PATH, Service


class Request:
    def __init__(self, path: str, app: str | None = None):
        self.path = path
        self.headers = {} if app is None else {APP_HEADER: app}


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

    # This models a warm instance: another module is imported and registered
    # after the default application has already been selected.
    service.register_module("second-v1", second.__name__)

    assert service.dispatch(Request("/value")) == "first"
    assert service.dispatch(Request("/value", "second-v1")) == "second"
    assert service.registry.active() == "first-v1"
