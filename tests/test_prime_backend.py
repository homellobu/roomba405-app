import asyncio
from types import SimpleNamespace
from dataclasses import dataclass, field

from roomba.prime_backend import PrimeBackend


@dataclass
class FakeRegionType:
    name: str


@dataclass
class FakeRoom:
    room_id: str
    name: str | None
    region_type: object


@dataclass
class FakeMetadata:
    rooms_metadata: list = field(default_factory=list)
    current_map_version: str = "V1"


@dataclass
class FakeVersion:
    p2map_id: str = "MAP1"


@dataclass
class FakeFavorite:
    favorite_id: str
    name: str | None
    command_defs: list


@dataclass
class FakeScheduleOptions:
    name: str | None
    enabled: bool
    start: object


@dataclass
class FakeSchedule:
    schedule_id: str
    options: FakeScheduleOptions


@dataclass
class FakeContainer:
    household_schedule_id: str
    schedules: list


@dataclass
class FakeSchedulesResponse:
    household_schedules: list


@dataclass
class FakeShadow:
    payload: dict


class FakeRobot:
    blid = "BLID1"

    def __init__(self):
        self.sent = []

    async def get_active_map_versions(self):
        return [{"p2map_id": "MAP1", "active_p2mapv_id": "V1", "name": "Casa",
                 "state": "active", "visible": True}]

    async def get_map_metadata(self, p2map_id):
        assert p2map_id == "MAP1"
        return FakeMetadata(rooms_metadata=[
            FakeRoom("15", "Salón", FakeRegionType("RID")),
            FakeRoom("16", "Pasillo", "ZID"),
        ])

    async def get_map_geojson_link(self, p2map_id, version_id):
        return {"map_url": "https://example.com/map.tar.gz"}

    async def download_map_bundle(self, url):
        assert url == "https://example.com/map.tar.gz"
        import io
        import json as jsonlib
        import tarfile
        trajectory = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": "t1",
             "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
             "properties": {"index": 0}}]}
        covering_features = [
            {"type": "Feature", "id": "c" + str(i),
             "geometry": {"type": "Polygon",
                          "coordinates": [[i, 0], [i + 0.5, 0], [i, 0.5]]},
             "properties": {"operatingModes": ["run"]}}
            for i in range(12)]
        covering = {"type": "FeatureCollection", "features": covering_features}

        rooms = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": "room1",
             "geometry": {"type": "Polygon", "coordinates": [
                 [[0, 0], [8, 0], [8, 6], [0, 6], [0, 0]]]},
             "properties": {"name": "Salón", "type": "kitchen"}}]}
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for name, payload in (("trajectory.geojson", trajectory),
                                  ("coverage.geojson", covering),
                                  ("rooms.geojson", rooms)):
                data = jsonlib.dumps(payload).encode()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    async def send_routine_command_via_cmd_topic(self, command):
        self.sent.append(command)

    async def send_simple_command(self, command):
        self.sent.append(command)

    async def get_favorites(self):
        return [FakeFavorite("F1", "Limpieza rápida", [object()])]

    async def get_user_households(self):
        return {"household": [{"household_id": "H1"}]}

    async def get_schedules(self, household_id):
        return FakeSchedulesResponse([FakeContainer("HC1", [
            FakeSchedule("S1", FakeScheduleOptions("Lunes", True, FakeStart(["mon"], 9, 30))),
        ])])


@dataclass
class FakeStart:
    day: list
    hour: int
    minute: int


def make_backend():
    backend = PrimeBackend("e", "p", blid="BLID1")
    backend.robot = FakeRobot()

    def run(coro, timeout=30):
        return asyncio.run(coro)

    backend._call = run
    return backend


def test_get_rooms():
    backend = make_backend()
    rooms = backend.get_rooms()
    assert rooms == [
        {"id": "15", "name": "Salón", "type": "RID"},
        {"id": "16", "name": "Pasillo", "type": "ZID"},
    ]
    assert backend._p2map_id == "MAP1"


def test_clean_rooms_builds_routine_command():
    from roombapy_prime.models import MissionCommandType

    backend = make_backend()
    backend.get_rooms()
    backend.clean_rooms(
        [{"id": "15", "name": "Salón", "type": "RID"}],
        suction="high", pad_wetness=2,
    )
    command = backend.robot.sent[0]
    assert command.command_type == MissionCommandType.START
    assert command.map_id == "MAP1"
    assert command.asset_id == "BLID1"
    assert command.regions[0].region_id == "15"
    assert command.regions[0].params.suction_level == 3
    assert command.regions[0].params.pad_wetness.pad_plate == 2


def test_start_favorite():
    from roombapy_prime.models import MissionCommandType

    backend = make_backend()
    backend.start_favorite("F1")
    command = backend.robot.sent[0]
    assert command.favorite_id == "F1"
    assert command.command_type == MissionCommandType.START


def test_get_favorites():
    backend = make_backend()
    favorites = backend.get_favorites()
    assert favorites == [{"id": "F1", "name": "Limpieza rápida", "steps": 1}]


def test_get_schedules():
    backend = make_backend()
    schedules = backend.get_schedules()
    assert schedules == [{
        "id": "S1", "name": "Lunes", "enabled": True,
        "time": "09:30", "days": "mon",
    }]


def test_get_schedules_accepts_list_of_households():
    class ListHouseholdsRobot(FakeRobot):
        async def get_user_households(self):
            return [{"household_id": "H1"}]

    backend = make_backend()
    backend.robot = ListHouseholdsRobot()
    schedules = backend.get_schedules()
    assert schedules and schedules[0]["id"] == "S1"


def test_get_status_merges_shadows():
    class ShadowRobot(FakeRobot):
        async def get_state(self):
            return FakeShadow({"sku": "G185040"})

        async def get_named_shadow(self, name):
            assert name == "ro-currentstate"
            return FakeShadow({"batPct": 88})

    backend = make_backend()
    backend.robot = ShadowRobot()
    status = backend.get_status()
    assert status == {"sku": "G185040", "batPct": 88}

def test_get_map_prefers_file_with_polygons():
    backend = make_backend()
    geojson = backend.get_map()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    assert geojson["features"][0]["properties"]["name"] == "Salón"
    assert geojson["features"][0]["geometry"]["type"] == "Polygon"
    assert len(geojson["features"]) == 1

def test_get_map_merges_bundle_and_skips_coverage():
    backend = make_backend()
    geojson = backend.get_map()
    kinds = {(f["geometry"]["type"], f["properties"].get("name"))
             for f in geojson["features"] if f["geometry"]}
    assert ("Polygon", "Salón") in kinds
    assert all("operatingModes" not in f.get("properties") or {}
               for f in geojson["features"])
    cached = backend.get_map()
    assert cached is geojson


def test_get_rooms_falls_back_to_bundle_names():
    backend = make_backend()

    async def unnamed(p2map_id):
        return FakeMetadata(rooms_metadata=[
            FakeRoom("room1", None, FakeRegionType("RID"))])

    backend.robot.get_map_metadata = unnamed
    rooms = backend.get_rooms()
    assert rooms[0]["name"] == "Salón"
    assert rooms[0]["type"] == "RID"

def test_trail_watch_collects_points():
    backend = make_backend()

    class Msg:
        updates = [SimpleNamespace(point=(1.0, 2.0)),
                   SimpleNamespace(point=(3.0, 4.0))]

    async def watch():
        yield Msg()

    backend.robot.watch_live_map = watch
    backend._trail_task = "started"
    asyncio.run(backend._trail_watch())
    assert backend._trail == [[1.0, 2.0], [3.0, 4.0]]
    assert backend._trail_task is None


def test_get_status_unwraps_shadow_envelope():
    class EnvelopeRobot(FakeRobot):
        async def get_state(self):
            return FakeShadow({"state": {"reported": {
                "batPct": 77,
                "cleanMissionStatus": {"phase": "run", "error": 0},
            }}})

        async def get_named_shadow(self, name):
            return FakeShadow({"state": {"reported": {"bin": {"present": True}}}})

    backend = make_backend()
    backend.robot = EnvelopeRobot()
    status = backend.get_status()
    assert status["batPct"] == 77
    assert status["cleanMissionStatus"]["phase"] == "run"
    assert status["bin"] == {"present": True}


def test_get_status_starts_and_stops_trail_by_phase():
    calls = []

    class RunRobot(FakeRobot):
        async def get_state(self):
            return FakeShadow({"cleanMissionStatus": {"phase": "run"}})

        async def get_named_shadow(self, name):
            return FakeShadow({})

    class ChargeRobot(FakeRobot):
        async def get_state(self):
            return FakeShadow({"cleanMissionStatus": {"phase": "charge"}})

        async def get_named_shadow(self, name):
            return FakeShadow({})

    backend = make_backend()
    backend._ensure_trail = lambda: calls.append("ensure")
    backend._stop_trail = lambda: calls.append("stop")
    backend.robot = RunRobot()
    backend.get_status()
    assert calls == ["ensure"]
    backend.robot = ChargeRobot()
    backend.get_status()
    assert calls == ["ensure", "stop"]


def test_simple_start_starts_trail():
    calls = []
    backend = make_backend()
    backend._ensure_trail = lambda: calls.append(True)
    backend.simple("start")
    assert calls == [True]
    backend.simple("dock")
    assert calls == [True]


def test_trail_info_reports_state():
    backend = make_backend()
    backend._last_phase = "run"
    backend._trail.append([1.0, 2.0])
    backend._trail_error = "avierto"
    assert backend.trail_info() == {
        "active": False, "points": 1, "error": "avierto", "phase": "run",
    }
