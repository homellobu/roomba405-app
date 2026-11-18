import asyncio
import logging
import threading

log = logging.getLogger(__name__)

SUCTION_LEVELS = {"low": 1, "medium": 2, "high": 3, "turbo": 4}

WIRE_DAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")


def _payload(response) -> dict:
    payload = getattr(response, "payload", None)
    return payload if isinstance(payload, dict) else {}


class PrimeBackend:
    def __init__(self, email: str, password: str, country: str = "ES", blid: str | None = None):
        self._email = email
        self._password = password
        self._country = country
        self._blid = blid
        self.robot = None
        self._p2map_id = None
        self._loop = None
        self._thread = None
        self._aiohttp_session = None
        self._started = threading.Event()

    def connect(self, timeout: float = 40):
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._started.wait(10):
            raise RuntimeError("No se pudo arrancar el bucle de eventos")
        self._call(self._connect_async(), timeout)
        log.info("Conectado al robot %s vía roombapy-prime", self._blid or "(primer robot)")

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()

    def _call(self, coro, timeout: float = 30):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    @staticmethod
    def _ssl_context():
        try:
            import certifi

            import ssl
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return None

    async def _connect_async(self):
        import aiohttp
        from roombapy_prime import PrimeFactory

        connector = aiohttp.TCPConnector(ssl=self._ssl_context())
        self._aiohttp_session = aiohttp.ClientSession(connector=connector)
        self.robot = await PrimeFactory.create_prime_robot(
            self._aiohttp_session,
            self._email,
            self._password,
            self._country,
            blid=self._blid,
            auto_refresh=True,
        )
        await self.robot.connect()

    def simple(self, command: str):
        self._call(self.robot.send_simple_command(command))

    def get_rooms(self) -> list[dict]:
        return self._call(self._rooms_async())

    def get_map(self):
        return self._call(self._map_async())

    async def _map_async(self):
        from roombapy_prime.models import parse_map_bundle
        from roombapy_prime.models.robot_info import parse_active_map_versions

        versions = parse_active_map_versions(await self.robot.get_active_map_versions())
        if not versions:
            return None
        version = versions[0]
        p2map_id = version.p2map_id
        version_id = None
        for attr in ("user_p2mapv_id", "active_p2mapv_id", "p2mapv_id"):
            value = getattr(version, attr, None)
            if value:
                version_id = value
                break
        if not version_id:
            metadata = await self.robot.get_map_metadata(p2map_id)
            version_id = metadata.current_map_version
        if not version_id:
            return None
        link = await self.robot.get_map_geojson_link(p2map_id, version_id)
        url = link.get("map_url") or next(
            (v for v in link.values() if isinstance(v, str) and v.startswith("http")), None
        )
        if not url:
            return None
        bundle = await self.robot.download_map_bundle(url)
        parsed = parse_map_bundle(bundle)
        for content in parsed.values():
            if isinstance(content, dict) and (
                content.get("type") == "FeatureCollection" or "features" in content
            ):
                return content
        return None

    async def _rooms_async(self) -> list[dict]:
        from roombapy_prime.models.robot_info import parse_active_map_versions

        versions = parse_active_map_versions(await self.robot.get_active_map_versions())
        if not versions:
            return []
        version = versions[0]
        self._p2map_id = version.p2map_id
        metadata = await self.robot.get_map_metadata(version.p2map_id)
        rooms = metadata.rooms_metadata or []
        result = []
        for room in rooms:
            rtype = room.region_type
            rtype_name = rtype.name if hasattr(rtype, "name") else str(rtype or "RID")
            result.append({
                "id": str(room.room_id),
                "name": room.name or str(room.room_id),
                "type": rtype_name,
            })
        return result

    def clean_rooms(self, rooms: list[dict], suction: str | None = None,
                    pad_wetness: int | None = None):
        return self._call(self._clean_async(rooms, suction, pad_wetness))

    async def _clean_async(self, rooms: list[dict], suction: str | None,
                           pad_wetness: int | None):
        from roombapy_prime.models import (
            CommandParams,
            MissionCommandType,
            PadWetnessParam,
            Region,
            RegionType,
            RoutineCommand,
        )

        params = None
        if suction or pad_wetness is not None:
            params = CommandParams(
                suction_level=SUCTION_LEVELS.get(suction.lower()) if suction else None,
                pad_wetness=PadWetnessParam(pad_plate=pad_wetness) if pad_wetness is not None else None,
            )

        command = RoutineCommand(
            command_type=MissionCommandType.START,
            asset_id=self.robot.blid,
            map_id=self._p2map_id,
            regions=[
                Region(
                    region_id=str(room["id"]),
                    region_type=RegionType[room["type"]],
                    params=params,
                )
                for room in rooms
            ],
        )
        await self.robot.send_routine_command_via_cmd_topic(command)

    def get_favorites(self) -> list[dict]:
        return self._call(self._favorites_async())

    async def _favorites_async(self) -> list[dict]:
        favorites = await self.robot.get_favorites()
        return [
            {"id": fav.favorite_id, "name": fav.name or fav.favorite_id, "steps": len(fav.command_defs or [])}
            for fav in favorites
        ]

    def start_favorite(self, favorite_id: str):
        return self._call(self._start_favorite_async(favorite_id))

    async def _start_favorite_async(self, favorite_id: str):
        from roombapy_prime.models import MissionCommandType, RoutineCommand

        command = RoutineCommand(
            command_type=MissionCommandType.START,
            asset_id=self.robot.blid,
            favorite_id=favorite_id,
        )
        await self.robot.send_routine_command_via_cmd_topic(command)

    def dock_command(self, command: str):
        return self._call(self._dock_command_async(command))

    async def _dock_command_async(self, command: str):
        from roombapy_prime.models import MissionCommandType, RoutineCommand

        await self.robot.send_routine_command_via_cmd_topic(
            RoutineCommand(
                command_type=MissionCommandType(command),
                asset_id=self.robot.blid,
            )
        )

    def get_schedules(self) -> list[dict]:
        return self._call(self._schedules_async())

    async def _schedules_async(self) -> list[dict]:
        households = await self.robot.get_user_households()
        if isinstance(households, list):
            entries = households
        else:
            entries = households.get("household") or households.get("households") or []
        schedules = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            household_id = entry.get("household_id")
            if not household_id:
                continue
            response = await self.robot.get_schedules(household_id)
            for container in response.household_schedules or []:
                for schedule in container.schedules or []:
                    options = schedule.options
                    start = options.start
                    days = ", ".join(
                        WIRE_DAYS[d] if isinstance(d, int) and 0 <= d < 7 else str(d)
                        for d in (getattr(start, "day", None) or [])
                    )
                    hour = getattr(start, "hour", None)
                    minute = getattr(start, "minute", None)
                    time_str = f"{hour:02d}:{minute:02d}" if hour is not None else "-"
                    schedules.append({
                        "id": schedule.schedule_id,
                        "name": options.name or "(sin nombre)",
                        "enabled": bool(options.enabled),
                        "time": time_str,
                        "days": days or "-",
                    })
        return schedules

    def get_status(self) -> dict:
        return self._call(self._status_async())

    async def _status_async(self) -> dict:
        state = {}
        try:
            state.update(_payload(await self.robot.get_state()))
        except Exception:
            pass
        try:
            state.update(_payload(await self.robot.get_named_shadow("ro-currentstate")))
        except Exception:
            pass
        return state

    def close(self):
        try:
            if self.robot:
                self._call(self.robot.disconnect(), 15)
            if self._aiohttp_session:
                self._call(self._aiohttp_session.close(), 10)
        except Exception:
            pass
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
