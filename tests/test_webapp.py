import json
import urllib.request

import pytest

from roomba.webapp import WebApp


class FakeBackend:
    def __init__(self):
        self.sent = []
        self.cleaned = []
        self.status = {"batPct": 80, "cleanMissionStatus": {"phase": "charge", "error": 0}}
        self.rooms = [{"name": "Salón", "type": "RID", "id": "15", "map_id": "MAP1"}]
        self.favorites = [{"id": "F1", "name": "Noche", "steps": 2}]
        self.schedules = [{"id": "S1", "name": "Lunes", "enabled": True,
                           "time": "09:30", "days": "mon"}]
        self.geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [
                    [[0, 0], [10, 0], [10, 8], [0, 8], [0, 0]]]},
                "properties": {"name": "Salón"},
            }],
        }
        self.fail_status = False

    def get_status(self):
        if self.fail_status:
            raise RuntimeError("sin conexión")
        return self.status

    def simple(self, cmd):
        self.sent.append(cmd)

    def dock_command(self, cmd):
        self.sent.append(cmd)

    def get_rooms(self):
        return self.rooms

    def clean_rooms(self, rooms, suction=None, pad_wetness=None):
        self.cleaned.append((rooms, suction, pad_wetness))

    def get_favorites(self):
        return self.favorites

    def start_favorite(self, fid):
        self.sent.append(("favorite", fid))

    def get_schedules(self):
        return self.schedules

    def get_map(self):
        return self.geojson


@pytest.fixture()
def server():
    backend = FakeBackend()
    app = WebApp(backend, robot_name="Test")
    thread = __import__("threading").Thread(target=app.serve_forever, daemon=True)
    thread.start()
    yield backend, app.url
    app.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as res:
        return json.loads(res.read())


def post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read())


def test_index_served(server):
    _, url = server
    with urllib.request.urlopen(url, timeout=5) as res:
        html = res.read().decode()
        assert res.headers["Content-Type"].startswith("text/html")
    for texto in (
        "Limpiar toda la casa",
        "Mapa de la casa",
        "Mantenimiento",
        "Registro de actividad",
        "Habitaciones",
        "Rutinas",
        "Programaciones",
    ):
        assert texto in html
    with urllib.request.urlopen(url + "classic.html", timeout=5) as res:
        assert b"Tu casa, en calma" in res.read()


def test_map_endpoint(server):
    backend, url = server
    data = get(url + "api/map")
    assert data["ok"] is True
    assert data["map"]["type"] == "FeatureCollection"
    backend.geojson = None
    data = get(url + "api/map")
    assert data["ok"] is True and data["map"] is None


def test_map_endpoint_connecting():
    app = WebApp(robot_name="Test")
    thread = __import__("threading").Thread(target=app.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            get(app.url + "api/map")
        assert exc.value.code == 503
    finally:
        app.shutdown()


def test_status_endpoint(server):
    backend, url = server
    data = get(url + "api/status")
    assert data["ok"] is True
    assert data["status"]["batPct"] == 80
    backend.fail_status = True
    try:
        get(url + "api/status")
        raise AssertionError("debía fallar")
    except urllib.error.HTTPError as e:
        assert e.code == 503


def test_command_endpoints(server):
    backend, url = server
    assert post(url + "api/command", {"cmd": "pause"}) == {"ok": True}
    assert post(url + "api/dock-command", {"cmd": "washpad"}) == {"ok": True}
    assert backend.sent == ["pause", "washpad"]


def test_clean_endpoint(server):
    backend, url = server
    data = post(url + "api/clean", {"rooms": ["Salón"], "suction": "high", "pad": 2})
    assert data == {"ok": True}
    rooms, suction, pad = backend.cleaned[0]
    assert rooms[0]["name"] == "Salón"
    assert suction == "high"
    assert pad == 2


def test_rooms_favorites_schedules(server):
    backend, url = server
    assert get(url + "api/rooms")["rooms"][0]["name"] == "Salón"
    assert get(url + "api/favorites")["favorites"][0]["id"] == "F1"
    assert get(url + "api/schedules")["schedules"][0]["time"] == "09:30"
    assert post(url + "api/favorite", {"id": "F1"}) == {"ok": True}
    assert backend.sent == [("favorite", "F1")]


def test_connecting_state():
    app = WebApp(robot_name="Test")
    thread = __import__("threading").Thread(target=app.serve_forever, daemon=True)
    thread.start()
    try:
        data = get(app.url + "api/status")
        assert data == {"ok": True, "connecting": True, "robot": "Test", "status": {}}
        with pytest.raises(urllib.error.HTTPError):
            post(app.url + "api/command", {"cmd": "pause"})
        backend = FakeBackend()
        app.set_backend(backend)
        data = get(app.url + "api/status")
        assert data["ok"] is True and "connecting" not in data
        assert data["status"]["batPct"] == 80
    finally:
        app.shutdown()
