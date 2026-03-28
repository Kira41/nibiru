from __future__ import annotations

import sys
import types


class _FakeFlaskApp:
    def __init__(self, name: str):
        self.name = name
        self.secret_key = ''
        self.root_path = '.'

    def route(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

    get = post = delete = route


class _FakeResponse:
    def __init__(self, data=None, mimetype: str | None = None):
        self.data = data
        self.mimetype = mimetype


def install() -> None:
    if 'flask' not in sys.modules:
        flask = types.ModuleType('flask')
        flask.Flask = _FakeFlaskApp
        flask.Response = _FakeResponse
        flask.jsonify = lambda *args, **kwargs: {'args': args, 'kwargs': kwargs}
        flask.redirect = lambda location: location
        flask.render_template_string = lambda template, **context: template
        flask.request = types.SimpleNamespace(form={}, method='GET', args={})
        flask.send_file = lambda *args, **kwargs: {'args': args, 'kwargs': kwargs}
        flask.send_from_directory = lambda *args, **kwargs: {'args': args, 'kwargs': kwargs}
        flask.url_for = lambda endpoint, **values: f'/{endpoint}'
        flask.session = {}
        sys.modules['flask'] = flask

    if 'PIL' not in sys.modules:
        pil = types.ModuleType('PIL')

        class _FakeImageObject:
            def save(self, fp, format=None):
                fp.write(b'fake-image')

        class _FakeImageModule:
            @staticmethod
            def new(mode, size, color=None):
                return _FakeImageObject()

        pil.Image = _FakeImageModule
        sys.modules['PIL'] = pil

    if 'requests' not in sys.modules:
        requests = types.ModuleType('requests')

        class _FakeResponseObject:
            def __init__(self, text: str = '', status_code: int = 200):
                self.text = text
                self.status_code = status_code

            def json(self):
                return {}

            def raise_for_status(self) -> None:
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

        requests.Response = _FakeResponseObject
        requests.get = lambda *args, **kwargs: _FakeResponseObject()
        requests.post = lambda *args, **kwargs: _FakeResponseObject()
        requests.request = lambda *args, **kwargs: _FakeResponseObject()
        sys.modules['requests'] = requests
