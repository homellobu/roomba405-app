#!/usr/bin/env python3
import os
import sys
import traceback
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
    from roomba.gui import RoombaGUI, pick_robot_dialog
    from roomba.prime_backend import PrimeBackend
    from roomba.store import Store

    country = os.environ.get("ROOMBA_COUNTRY", "ES")
    store = Store()
    cloud = IRobotCloud(country=country)
    session = login_flow(store, cloud)
    blid = resolve_blid(store, session)
    if blid is None:
        blid = pick_robot_dialog(session["robots"])
        store.set_blid(blid)
    robot_name = session["robots"][blid].get("name", "Roomba")

    backend = PrimeBackend(store.email, store.password, country=country, blid=blid)
    backend.connect()
    RoombaGUI(backend, robot_name=robot_name).run()


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
