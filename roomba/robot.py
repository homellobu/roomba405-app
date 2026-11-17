import json
import threading
import time

from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

from .cloud import IRobotCloud
from .store import Store

TOKEN_HEADER = "x-irobot-auth"
REFRESH_EVERY = 240

SHADOW_GET = "$aws/things/{blid}/shadow/get"
SHADOW_UPDATE = "$aws/things/{blid}/shadow/update"

DOCK_PHASES = {"hmUsrDock", "hmMidMsn", "hmPostMsn", "charge", "evac"}

COMMANDS = {
    "start": "Iniciar limpieza",
    "pause": "Pausar",
    "stop": "Detener",
    "resume": "Reanudar",
    "dock": "Volver a la base",
    "find": "Localizar (pitido)",
    "evac": "Vaciar depósito",
    "reset": "Reiniciar robot",
}


class Roomba:
    def __init__(self, store: Store, cloud: IRobotCloud, session: dict, blid: str | None = None):
        self.store = store
        self.cloud = cloud
        self.session = session
        self._load_session(session, blid)

        self.conn = None
        self.state = {}
        self._lock = threading.Lock()
        self._fresh = threading.Event()
        self._refresh_stop = threading.Event()
        self._refresh_thread = None
        self._reconnect_lock = threading.Lock()

    def _load_session(self, session: dict, blid: str | None = None):
        robots = session.get("robots") or {}
        if not robots:
            raise RuntimeError("No hay robots vinculados a esta cuenta")
        if blid and blid in robots:
            chosen = blid
        elif getattr(self, "blid", None) and self.blid in robots:
            chosen = self.blid
        elif len(robots) == 1:
            chosen = next(iter(robots))
        else:
            chosen = self._pick_robot(robots)
        info = robots[chosen]
        self.blid = chosen
        self.name = info.get("name", chosen)

        for key in ("iot_token", "iot_signature", "iot_authorizer_name", "iot_clientid"):
            if not session.get(key):
                raise RuntimeError(f"Respuesta de login sin {key}")
        self.iot_token = session["iot_token"]
        self.iot_signature = session["iot_signature"]
        self.authorizer_name = session["iot_authorizer_name"]
        self.client_id = session["iot_clientid"]

        disco = session.get("_discovery", {})
        self.endpoint = disco["mqtt"]
        self.irbt_topics = disco["irbt_topics"]

    @staticmethod
    def _pick_robot(robots: dict) -> str:
        items = list(robots.items())
        print()
        for i, (blid, info) in enumerate(items, 1):
            print(f"  {i}. {info.get('name', blid)}  [{blid}]")
        while True:
            try:
                n = int(input("Selecciona robot> ").strip())
                if 1 <= n <= len(items):
                    return items[n - 1][0]
            except ValueError:
                pass

    def _cmd_topic(self) -> str:
        return f"{self.irbt_topics}/things/{self.blid}/cmd"

    def _build_connection(self):
        loop = io.EventLoopGroup(1)
        resolver = io.DefaultHostResolver(loop)
        bootstrap = io.ClientBootstrap(loop, resolver)
        tls_opts = io.TlsContextOptions()
        tls_opts.alpn_list = ["x-amzn-mqtt-ca"]
        tls_ctx = io.ClientTlsContext(tls_opts)
        return mqtt_connection_builder.direct_with_custom_authorizer(
            endpoint=self.endpoint,
            auth_authorizer_name=self.authorizer_name,
            auth_authorizer_signature=self.iot_signature,
            auth_token_key_name=TOKEN_HEADER,
            auth_token_value=self.iot_token,
            client_id=self.client_id,
            client_bootstrap=bootstrap,
            tls_ctx=tls_ctx,
            clean_session=True,
            keep_alive_secs=30,
        )

    def _subscribe(self):
        self.conn.subscribe(
            topic=SHADOW_UPDATE.format(blid=self.blid),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=self._on_message,
        )[0].result(timeout=10)
        self.conn.subscribe(
            topic=f"$aws/things/{self.blid}/shadow/get/accepted",
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=self._on_message,
        )[0].result(timeout=10)

    def connect(self):
        self.conn = self._build_connection()
        self.conn.connect().result(timeout=15)
        self._subscribe()
        self.refresh_state()
        self._start_refresh_loop()

    def _start_refresh_loop(self):
        if self._refresh_thread and self._refresh_thread.is_alive():
            return
        self._refresh_stop.clear()
        self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._refresh_thread.start()

    def _refresh_loop(self):
        while not self._refresh_stop.wait(REFRESH_EVERY):
            try:
                self._reauth_and_reconnect()
            except Exception:
                pass

    def _reauth_and_reconnect(self):
        with self._reconnect_lock:
            new_session = self.cloud.login(
                self.store.email,
                self.store.password,
                discovery=self.session.get("_discovery"),
            )
            self.store.save_session(new_session)
            self.session = new_session
            self._load_session(new_session)
            try:
                self.conn.disconnect().result(timeout=5)
            except Exception:
                pass
            self.conn = self._build_connection()
            self.conn.connect().result(timeout=15)
            self._subscribe()

    def _on_message(self, topic, payload, **_):
        try:
            data = json.loads(payload.decode())
        except Exception:
            return
        with self._lock:
            reported = data.get("state", {}).get("reported") or data.get("state") or {}
            self.state.update(reported)
            self._fresh.set()

    def refresh_state(self):
        self._fresh.clear()
        with self._reconnect_lock:
            self.conn.publish(
                topic=SHADOW_GET.format(blid=self.blid),
                payload=b"",
                qos=mqtt.QoS.AT_LEAST_ONCE,
            )
        self._fresh.wait(timeout=4)

    def _wait_for_phase(self, phases: set, timeout: float):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.refresh_state()
            mission = self.snapshot().get("cleanMissionStatus") or {}
            phase = mission.get("phase")
            if phase in phases:
                return phase
            time.sleep(3)
        return None

    def dock_with_retry(self, attempts: int = 3, wait_per_attempt: float = 25) -> bool:
        last_phase = None
        for _ in range(attempts):
            self.send("dock")
            last_phase = self._wait_for_phase(DOCK_PHASES, wait_per_attempt)
            if last_phase:
                return True
        return False

    def send(self, command: str):
        if command not in COMMANDS:
            raise ValueError(f"Comando desconocido: {command}")
        payload = json.dumps({
            "command": command,
            "time": int(time.time()),
            "initiator": "localApp",
        }).encode()
        with self._reconnect_lock:
            self.conn.publish(
                topic=self._cmd_topic(),
                payload=payload,
                qos=mqtt.QoS.AT_LEAST_ONCE,
            )[0].result(timeout=5)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.state)

    def disconnect(self):
        self._refresh_stop.set()
        if self.conn:
            try:
                self.conn.disconnect().result(timeout=5)
            except Exception:
                pass
