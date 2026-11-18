import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ICON_PATH = ASSETS_DIR / "icon.png"

DOCK_PHASES = {"hmUsrDock", "hmMidMsn", "hmPostMsn", "charge", "evac"}

LAN_PORT = 8787
LAN_PORT_ATTEMPTS = 20


def lan_ip() -> str:
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.168.255.255", 9))
            return probe.getsockname()[0]
        finally:
            probe.close()
    except OSError:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return ""


class WebApp:
    def __init__(self, backend=None, robot_name: str = "Roomba", host="127.0.0.1", port=0,
                 store=None):
        self.backend = backend
        self.connect_error: str | None = None
        self.robot_name = robot_name
        self.blid: str | None = None
        self.robots = None
        self.robot_switcher = None
        self.store = store
        self.lan_bind_host = "0.0.0.0"
        self.lan_server = None
        self.lan_url: str | None = None
        handler = type("Handler", (_Handler,), {"app": self})
        self._handler = handler
        self._server = ThreadingHTTPServer((host, port), handler)
        host_bound, port_bound = self._server.server_address[:2]
        self.url = f"http://{host_bound}:{port_bound}/"

    def set_backend(self, backend):
        self.backend = backend
        self.connect_error = None

    def serve_forever(self):
        self._server.serve_forever()

    def shutdown(self):
        self.lan_disable(persist=False)
        self._server.shutdown()
        self._server.server_close()

    def lan_enabled(self) -> bool:
        return bool(self.store and self.store.data.get("lan_access"))

    def lan_enable(self) -> str | None:
        if self.lan_server:
            return self.lan_url
        server = None
        for offset in range(LAN_PORT_ATTEMPTS):
            try:
                server = ThreadingHTTPServer(
                    (self.lan_bind_host, LAN_PORT + offset), self._handler)
                break
            except OSError:
                continue
        if server is None:
            return None
        self.lan_server = server
        port = server.server_address[1]
        host = lan_ip() if self.lan_bind_host == "0.0.0.0" else self.lan_bind_host
        self.lan_url = f"http://{host}:{port}/"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        if self.store:
            self.store.data["lan_access"] = True
            self.store.save()
        return self.lan_url

    def lan_disable(self, persist: bool = True):
        server = self.lan_server
        self.lan_server = None
        self.lan_url = None
        if server:
            threading.Thread(target=self._stop_lan, args=(server,), daemon=True).start()
        if persist and self.store:
            self.store.data["lan_access"] = False
            self.store.save()

    @staticmethod
    def _stop_lan(server):
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass

    def lan_info(self) -> dict:
        return {"enabled": bool(self.lan_server), "url": self.lan_url}

    def dock_with_retries(self, attempts=3, wait_per_attempt=25):
        if self.backend is None:
            return False
        for _ in range(attempts):
            self.backend.simple("dock")
            deadline = time.time() + wait_per_attempt
            while time.time() < deadline:
                try:
                    status = self.backend.get_status()
                except Exception:
                    return False
                mission = status.get("cleanMissionStatus") or {}
                if mission.get("phase") in DOCK_PHASES:
                    return True
                time.sleep(3)
        return False


class _Handler(BaseHTTPRequestHandler):
    app: WebApp = None

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, content, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _json(self, code, payload):
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _api_error(self, error: Exception):
        self._json(503, {"ok": False, "error": str(error)})

    def _no_backend(self, connecting: bool):
        if connecting:
            self._json(200, {"ok": True, "connecting": True, "blid": self.app.blid,
                             "robot": self.app.robot_name, "status": {}})
        else:
            self._json(503, {"ok": False, "error": "conectando con el robot"})

    def _backend_ready(self):
        if self.app.backend is not None:
            return True
        self._json(503, {"ok": False, "error": "conectando con el robot"})
        return False

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            content = (WEB_DIR / "index.html").read_bytes()
            self._send(200, content, "text/html; charset=utf-8")
        elif path == "/classic.html":
            content = (WEB_DIR / "classic.html").read_bytes()
            self._send(200, content, "text/html; charset=utf-8")
        elif path == "/plate.jpg":
            content = (WEB_DIR / "plate.jpg").read_bytes()
            self._send(200, content, "image/jpeg")
        elif path == "/icon.png":
            if ICON_PATH.exists():
                self._send(200, ICON_PATH.read_bytes(), "image/png")
            else:
                self._json(404, {"ok": False, "error": "sin icono"})
        elif path == "/api/status":
            if self.app.backend is None:
                self._no_backend(self.app.connect_error is None)
                return
            try:
                trail = getattr(self.app.backend, "trail_info", None)
                self._json(200, {"ok": True, "robot": self.app.robot_name,
                                 "blid": self.app.blid,
                                 "status": self.app.backend.get_status(),
                                 "trail": trail() if callable(trail) else None,
                                 "lan": self.app.lan_info()})
            except Exception as e:
                self._api_error(e)
        elif path == "/api/rooms":
            if not self._backend_ready():
                return
            try:
                self._json(200, {"ok": True, "rooms": self.app.backend.get_rooms()})
            except Exception as e:
                self._api_error(e)
        elif path == "/api/map":
            if not self._backend_ready():
                return
            try:
                self._json(200, {"ok": True, "map": self.app.backend.get_map()})
            except Exception as e:
                self._api_error(e)
        elif path == "/api/lan":
            self._json(200, {"ok": True, "lan": self.app.lan_info()})
        elif path == "/api/robots":
            if self.app.robots is None:
                self._json(404, {"ok": False, "error": "selector no disponible"})
                return
            try:
                self._json(200, {"ok": True, "robots": self.app.robots()})
            except Exception as e:
                self._api_error(e)
        elif path == "/api/trail":
            if not self._backend_ready():
                return
            try:
                trail = self.app.backend.get_trail()
                task = getattr(self.app.backend, "_trail_task", None)
                self._json(200, {"ok": True, "trail": trail,
                                 "active": bool(task and not task.done()),
                                 "error": getattr(self.app.backend, "_trail_error", None)})
            except Exception as e:
                self._api_error(e)
        elif path == "/api/favorites":
            if not self._backend_ready():
                return
            try:
                self._json(200, {"ok": True, "favorites": self.app.backend.get_favorites()})
            except Exception as e:
                self._api_error(e)
        elif path == "/api/schedules":
            if not self._backend_ready():
                return
            try:
                self._json(200, {"ok": True, "schedules": self.app.backend.get_schedules()})
            except Exception as e:
                self._api_error(e)
        else:
            self._json(404, {"ok": False, "error": "no encontrado"})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "JSON inválido"})
            return
        try:
            if path not in ("/api/robot", "/api/lan") and not self._backend_ready():
                return
            if path == "/api/command":
                self.app.backend.simple(body["cmd"])
                self._json(200, {"ok": True})
            elif path == "/api/dock-command":
                self.app.backend.dock_command(body["cmd"])
                self._json(200, {"ok": True})
            elif path == "/api/clean":
                names = body.get("rooms") or []
                rooms = [r for r in self.app.backend.get_rooms() if r["name"] in names]
                if not rooms:
                    self._json(400, {"ok": False, "error": "habitaciones no encontradas; actualiza la lista"})
                    return
                self.app.backend.clean_rooms(rooms, body.get("suction"), body.get("pad"))
                self._json(200, {"ok": True})
            elif path == "/api/favorite":
                self.app.backend.start_favorite(body["id"])
                self._json(200, {"ok": True})
            elif path == "/api/dock-retry":
                threading.Thread(target=self.app.dock_with_retries,
                                 daemon=True).start()
                self._json(200, {"ok": True, "started": True})
            elif path == "/api/lan":
                if body.get("enabled"):
                    url = self.app.lan_enable()
                    if url is None:
                        self._json(503, {"ok": False, "error": "no se pudo abrir el puerto para la red local"})
                        return
                    self._json(200, {"ok": True, "enabled": True, "url": url})
                else:
                    self.app.lan_disable()
                    self._json(200, {"ok": True, "enabled": False, "url": None})
            elif path == "/api/robot":
                if not body.get("blid") or self.app.robot_switcher is None:
                    self._json(400, {"ok": False, "error": "cambio de robot no disponible"})
                    return
                threading.Thread(target=self.app.robot_switcher,
                                 args=(body["blid"],), daemon=True).start()
                self._json(200, {"ok": True, "started": True})
            else:
                self._json(404, {"ok": False, "error": "no encontrado"})
        except Exception as e:
            self._api_error(e)
