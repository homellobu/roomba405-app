#!/usr/bin/env python3
import os
import sys
import threading
import time
import traceback
from pathlib import Path

ERROR_LOG = Path.home() / ".roomba_app" / "ultimo_error.txt"
STEP_LOG = Path.home() / ".roomba_app" / "launcher.log"


def log_step(message: str):
    line = f"{time.strftime('%H:%M:%S')}  {message}"
    print(line, flush=True)
    try:
        STEP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with STEP_LOG.open("a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def save_and_summarize(error: str) -> str:
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        ERROR_LOG.write_text(error)
    except OSError:
        pass
    lines = error.strip().splitlines()
    tail = lines[-12:]
    return "\n".join(tail) + f"\n\n(Error completo guardado en: {ERROR_LOG})"


def wait_forever():
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def open_interface(app):
    try:
        import webview
    except Exception as e:
        log_step(f"pywebview no disponible ({e}); abriendo navegador")
        import webbrowser
        webbrowser.open(app.url)
        wait_forever()
        return
    try:
        log_step("creando ventana nativa")
        webview.create_window("Roomba", app.url,
                              width=1170, height=800, min_size=(900, 640))
        webview.start()
        log_step("ventana cerrada")
    except Exception as e:
        log_step(f"ventana nativa falló: {e}; abriendo navegador")
        import webbrowser
        webbrowser.open(app.url)
        wait_forever()


def run():
    from roomba.cli import login_flow, resolve_blid
    from roomba.cloud import IRobotCloud
    from roomba.prime_backend import PrimeBackend
    from roomba.store import Store
    from roomba.webapp import WebApp

    country = os.environ.get("ROOMBA_COUNTRY", "ES")
    log_step("iniciando launcher")
    store = Store()
    cloud = IRobotCloud(country=country)
    log_step("login en iRobot")
    session = login_flow(store, cloud)
    blid = resolve_blid(store, session)
    if blid is None:
        from roomba.gui import pick_robot_dialog
        blid = pick_robot_dialog(session["robots"])
        store.set_blid(blid)
    robot_name = session["robots"][blid].get("name", "Roomba")
    log_step(f"robot seleccionado: {robot_name} ({blid})")

    backend = PrimeBackend(store.email, store.password, country=country, blid=blid)

    app = WebApp(robot_name=robot_name, store=store)
    robots_map = session["robots"]
    app.blid = blid
    app.robots = lambda: [{"name": robots_map[b].get("name", "Roomba"), "blid": b}
                          for b in robots_map]

    def switch_robot(new_blid):
        viejo = None
        try:
            if new_blid not in robots_map:
                app.connect_error = "robot desconocido: " + new_blid
                return
            viejo = app.backend
            app.backend = None
            app.connect_error = None
            nuevo_nombre = robots_map[new_blid].get("name", "Roomba")
            app.robot_name = nuevo_nombre
            app.blid = new_blid
            store.set_blid(new_blid)
            log_step(f"cambiando a robot: {nuevo_nombre} ({new_blid})")
            nuevo = PrimeBackend(store.email, store.password, country=country, blid=new_blid)
            nuevo.connect()
            app.set_backend(nuevo)
            log_step("cambio de robot completado")
        except BaseException:
            app.connect_error = traceback.format_exc()
            log_step("fallo al cambiar de robot")
        finally:
            if viejo is not None:
                try:
                    viejo.close()
                except Exception:
                    pass

    app.robot_switcher = switch_robot
    log_step(f"servidor listo en {app.url}")
    if store.data.get("lan_access"):
        lan_url = app.lan_enable()
        log_step(f"acceso iPhone/iPad activo en {lan_url}" if lan_url
                 else "acceso iPhone/iPad pedido pero no se pudo abrir el puerto")

    server_thread = threading.Thread(target=app.serve_forever, daemon=True)
    server_thread.start()

    def connect():
        try:
            log_step("conectando con el robot")
            backend.connect()
            app.set_backend(backend)
            log_step("conectado")
        except BaseException:
            app.connect_error = traceback.format_exc()
            log_step("fallo al conectar con el robot")

    threading.Thread(target=connect, daemon=True).start()
    open_interface(app)
    backend.close()


try:
    run()
except SystemExit:
    raise
except BaseException:
    error = traceback.format_exc()
    summary = save_and_summarize(error)
    log_step("ERROR FATAL:\n" + error)
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Roomba", summary)
    except Exception:
        print(error, file=sys.stderr)
    sys.exit(1)
