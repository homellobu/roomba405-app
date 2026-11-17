import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ICON_PATH = ASSETS_DIR / "icon.png"

DOCK_PHASES = {"hmUsrDock", "hmMidMsn", "hmPostMsn", "charge", "evac"}


class WebApp:
    def __init__(self, backend, robot_name: str = "Roomba", host="127.0.0.1", port=0):
        self.backend = backend
        self.robot_name = robot_name
        handler = type("Handler", (_Handler,), {"app": self})
        self._server = ThreadingHTTPServer((host, port), handler)
        host_bound, port_bound = self._server.server_address[:2]
        self.url = f"http://{host_bound}:{port_bound}/"

    def serve_forever(self):
        self._server.serve_forever()

    def shutdown(self):
        self._server.shutdown()
        self._server.server_close()

    def dock_with_retries(self, attempts=3, wait_per_attempt=25):
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
            try:
                self._json(200, {"ok": True, "robot": self.app.robot_name,
                                 "status": self.app.backend.get_status()})
            except Exception as e:
                self._api_error(e)
        elif path == "/api/rooms":
            try:
                self._json(200, {"ok": True, "rooms": self.app.backend.get_rooms()})
            except Exception as e:
                self._api_error(e)
        elif path == "/api/favorites":
            try:
                self._json(200, {"ok": True, "favorites": self.app.backend.get_favorites()})
            except Exception as e:
                self._api_error(e)
        elif path == "/api/schedules":
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
            else:
                self._json(404, {"ok": False, "error": "no encontrado"})
        except Exception as e:
            self._api_error(e)
