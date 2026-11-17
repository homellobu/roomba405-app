#!/usr/bin/env python3
import os
import sys
import traceback
import webbrowser
from pathlib import Path

ERROR_LOG = Path.home() / ".roomba_app" / "ultimo_error.txt"


def save_and_summarize(error: str) -> str:
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        ERROR_LOG.write_text(error)
    except OSError:
        pass
    lines = error.strip().splitlines()
    tail = lines[-12:]
    return "\n".join(tail) + f"\n\n(Error completo guardado en: {ERROR_LOG})"


def run():
    from roomba.cli import login_flow, resolve_blid
    from roomba.cloud import IRobotCloud
    from roomba.prime_backend import PrimeBackend
    from roomba.store import Store
    from roomba.webapp import WebApp

    country = os.environ.get("ROOMBA_COUNTRY", "ES")
    store = Store()
    cloud = IRobotCloud(country=country)
    session = login_flow(store, cloud)
    blid = resolve_blid(store, session)
    if blid is None:
        from roomba.gui import pick_robot_dialog
        blid = pick_robot_dialog(session["robots"])
        store.set_blid(blid)
    robot_name = session["robots"][blid].get("name", "Roomba")

    backend = PrimeBackend(store.email, store.password, country=country, blid=blid)
    backend.connect()
    app = WebApp(backend, robot_name=robot_name)
    print(f"Roomba ({robot_name}): interfaz disponible en {app.url}")
    print("Cierra esta ventana o pulsa Ctrl+C para salir.")
    webbrowser.open(app.url)
    try:
        app.serve_forever()
    finally:
        backend.close()


try:
    run()
except SystemExit:
    raise
except BaseException:
    error = traceback.format_exc()
    summary = save_and_summarize(error)
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Roomba", summary)
    except Exception:
        print(error, file=sys.stderr)
    sys.exit(1)
