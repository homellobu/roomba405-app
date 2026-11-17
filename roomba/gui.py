import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk

from .robot import DOCK_PHASES
from .state import PHASE, render_state

BUTTON_LABELS = {
    "start": "▶  Limpiar toda la casa",
    "pause": "⏸  Pausar",
    "stop": "⏹  Detener",
    "resume": "⏵  Reanudar",
    "dock": "🏠  Volver a la base",
    "find": "🔔  Localizar",
    "evac": "🗑  Vaciar depósito",
}

DOCK_COMMANDS = {
    "Vaciar depósito (evac)": "evac",
    "Lavar pad (AutoWash)": "washpad",
    "Secar pad (AutoWash)": "drypad",
    "Rellenar agua": "flrefill",
}

SUCTION_OPTIONS = {"": "Por defecto", "low": "Baja", "medium": "Media",
                   "high": "Alta", "turbo": "Turbo"}

PAD_OPTIONS = {"": "Por defecto", "1": "Húmedo bajo", "2": "Húmedo medio",
               "3": "Húmedo alto"}

REFRESH_SECS = 10


def pick_robot_dialog(robots: dict) -> str:
    result = {"blid": None}
    root = tk.Tk()
    root.title("Selecciona robot")
    root.geometry("360x240")

    ttk.Label(root, text="¿Qué robot quieres controlar?",
              font=("", 12, "bold")).pack(pady=(14, 6))

    listbox = tk.Listbox(root, font=("", 12), activestyle="dotbox")
    for blid, info in robots.items():
        listbox.insert("end", f"  {info.get('name', blid)}")
    listbox.pack(fill="both", expand=True, padx=16, pady=6)
    listbox.selection_set(0)

    def confirm(*_):
        selection = listbox.curselection()
        if selection:
            result["blid"] = list(robots)[selection[0]]
        root.destroy()

    ttk.Button(root, text="Seleccionar", command=confirm).pack(pady=(4, 12))
    listbox.bind("<Double-Button-1>", confirm)
    root.bind("<Return>", confirm)
    root.mainloop()

    if not result["blid"]:
        raise SystemExit(0)
    return result["blid"]


class RoombaGUI:
    def __init__(self, backend, robot_name: str = "Roomba"):
        self.backend = backend
        self.root = tk.Tk()
        self.root.title(f"Roomba — {robot_name}")
        self.root.geometry("640x720")
        self._build()
        self._schedule_refresh()

    def _build(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text=self.root.title(), font=("", 14, "bold")).pack(side="left")
        self.phase_label = ttk.Label(header, text="—", foreground="#555")
        self.phase_label.pack(side="right")

        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True)

        control = ttk.Frame(notebook, padding=10)
        notebook.add(control, text="Control")
        self._build_control(control)

        rooms = ttk.Frame(notebook, padding=10)
        notebook.add(rooms, text="Habitaciones")
        self._build_rooms(rooms)

        routines = ttk.Frame(notebook, padding=10)
        notebook.add(routines, text="Rutinas")
        self._build_routines(routines)

        schedules = ttk.Frame(notebook, padding=10)
        notebook.add(schedules, text="Programaciones")
        self._build_schedules(schedules)

        ttk.Label(main, text="Registro:").pack(anchor="w", pady=(8, 2))
        self.log_text = scrolledtext.ScrolledText(main, height=8, state="disabled")
        self.log_text.pack(fill="both", expand=True)

    def _build_control(self, parent):
        self.status_text = tk.Text(parent, height=12, width=64, state="disabled",
                                   relief="flat", background="#f6f6f6")
        self.status_text.pack(fill="x", pady=(0, 10))

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x")
        for i, (cmd, label) in enumerate(BUTTON_LABELS.items()):
            ttk.Button(buttons, text=label,
                       command=lambda c=cmd: self._dispatch_simple(c)).grid(
                row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)

        ttk.Button(parent, text="🏠 Volver a la base (con reintentos)",
                   command=self._dispatch_dock_retry).pack(fill="x", pady=(8, 4))

        dock_frame = ttk.LabelFrame(parent, text="Base AutoWash", padding=8)
        dock_frame.pack(fill="x", pady=(8, 0))
        for i, (label, cmd) in enumerate(DOCK_COMMANDS.items()):
            ttk.Button(dock_frame, text=label,
                       command=lambda c=cmd: self._dispatch_dock_command(c)).grid(
                row=0, column=i, sticky="ew", padx=3)
            dock_frame.columnconfigure(i, weight=1)

    def _build_rooms(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 6))
        ttk.Button(top, text="↻ Actualizar habitaciones",
                   command=self._dispatch_load_rooms).pack(side="left")

        options = ttk.LabelFrame(parent, text="Opciones de limpieza", padding=8)
        options.pack(fill="x", pady=(0, 6))
        ttk.Label(options, text="Succión:").grid(row=0, column=0, padx=(0, 4))
        self.suction_var = tk.StringVar(value="")
        ttk.Combobox(options, textvariable=self.suction_var, state="readonly",
                     width=14, values=list(SUCTION_OPTIONS.values())).grid(row=0, column=1, padx=(0, 16))
        ttk.Label(options, text="Fregado (wetness):").grid(row=0, column=2, padx=(0, 4))
        self.pad_var = tk.StringVar(value="")
        ttk.Combobox(options, textvariable=self.pad_var, state="readonly",
                     width=14, values=list(PAD_OPTIONS.values())).grid(row=0, column=3)
        options.columnconfigure(4, weight=1)

        ttk.Label(parent, text="Mantén Ctrl o Shift para seleccionar varias:").pack(anchor="w")
        self.rooms_list = tk.Listbox(parent, selectmode=tk.EXTENDED, font=("", 11))
        self.rooms_list.pack(fill="both", expand=True, pady=4)

        ttk.Button(parent, text="▶ Limpiar habitaciones seleccionadas",
                   command=self._dispatch_clean_rooms).pack(fill="x", pady=(4, 0))

    def _build_routines(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 6))
        ttk.Button(top, text="↻ Actualizar rutinas",
                   command=self._dispatch_load_favorites).pack(side="left")

        ttk.Label(parent, text="Rutinas guardadas en tu cuenta de iRobot:").pack(anchor="w")
        self.favorites_list = tk.Listbox(parent, font=("", 11))
        self.favorites_list.pack(fill="both", expand=True, pady=4)
        self.favorites_list.bind("<Double-Button-1>", lambda _: self._dispatch_start_favorite())

        ttk.Button(parent, text="▶ Iniciar rutina seleccionada",
                   command=self._dispatch_start_favorite).pack(fill="x", pady=(4, 0))

    def _build_schedules(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 6))
        ttk.Button(top, text="↻ Actualizar programaciones",
                   command=self._dispatch_load_schedules).pack(side="left")

        columns = ("name", "time", "days", "enabled")
        self.schedules_tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        self.schedules_tree.heading("name", text="Nombre")
        self.schedules_tree.heading("time", text="Hora")
        self.schedules_tree.heading("days", text="Días")
        self.schedules_tree.heading("enabled", text="Activa")
        self.schedules_tree.column("name", width=220)
        self.schedules_tree.column("time", width=80, anchor="center")
        self.schedules_tree.column("days", width=180)
        self.schedules_tree.column("enabled", width=70, anchor="center")
        self.schedules_tree.pack(fill="both", expand=True)

    def _log(self, message: str):
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, append)

    def _async(self, work, done=None):
        def runner():
            try:
                result = work()
                error = None
            except Exception as e:
                result, error = None, e
            if done:
                self.root.after(0, lambda: done(result, error))

        threading.Thread(target=runner, daemon=True).start()

    def _dispatch_simple(self, cmd: str):
        label = BUTTON_LABELS.get(cmd, cmd)
        self._log(f"→ {label}")

        def done(_, error):
            if error:
                self._log(f"✗ Fallo: {error}")
            else:
                self._log(f"✓ Enviado: {label}")

        self._async(lambda: self.backend.simple(cmd), done)

    def _dispatch_dock_command(self, cmd: str):
        self._log(f"→ {cmd}")

        def done(_, error):
            if error:
                self._log(f"✗ Fallo: {error}")
            else:
                self._log(f"✓ Enviado: {cmd}")

        self._async(lambda: self.backend.dock_command(cmd), done)

    def _dispatch_dock_retry(self):
        self._log("→ Volver a la base (con reintentos)")

        def work():
            for attempt in range(3):
                self.backend.simple("dock")
                if self._wait_for_dock_phase(25):
                    return True
            return False

        def done(result, error):
            if error:
                self._log(f"✗ Fallo: {error}")
            elif result:
                self._log("✓ El robot está de regreso a la base o cargando")
            else:
                self._log("✗ No ha entrado en fase de regreso; acércalo a la base y reintenta")

        self._async(work, done)

    def _wait_for_dock_phase(self, timeout: float) -> bool:
        deadline = time.time() + timeout
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

    def _dispatch_load_rooms(self):
        self._log("→ Cargando habitaciones...")

        def done(rooms, error):
            self.rooms_list.delete(0, "end")
            if error:
                self._log(f"✗ No se pudieron cargar habitaciones: {error}")
                return
            if not rooms:
                self._log("⚠ Sin mapa activo: deja que el robot mapee la casa primero")
                return
            for room in rooms:
                kind = "habitación" if room["type"] == "RID" else "zona"
                self.rooms_list.insert("end", f"{room['name']}  ({kind})")
                self.rooms_list.itemconfig("end", fg="#333")
            self._rooms = rooms
            self._log(f"✓ {len(rooms)} habitación(es)/zona(s) cargadas")

        self._async(self.backend.get_rooms, done)

    def _dispatch_clean_rooms(self):
        selection = self.rooms_list.curselection()
        rooms = getattr(self, "_rooms", [])
        if not selection or not rooms:
            self._log("⚠ Selecciona al menos una habitación (actualiza la lista si está vacía)")
            return
        chosen = [rooms[i] for i in selection]
        suction_key = next((k for k, v in SUCTION_OPTIONS.items()
                            if v == self.suction_var.get()), "")
        pad_key = next((k for k, v in PAD_OPTIONS.items()
                        if v == self.pad_var.get()), "")
        suction = suction_key or None
        pad_wetness = int(pad_key) if pad_key else None
        names = ", ".join(r["name"] for r in chosen)
        self._log(f"→ Limpiar: {names} (succión={suction or 'defecto'}, fregado={pad_wetness or 'defecto'})")

        def done(_, error):
            if error:
                self._log(f"✗ Fallo al enviar: {error}")
            else:
                self._log(f"✓ Comando enviado: {names}")

        self._async(lambda: self.backend.clean_rooms(chosen, suction, pad_wetness), done)

    def _dispatch_load_favorites(self):
        self._log("→ Cargando rutinas...")

        def done(favorites, error):
            self.favorites_list.delete(0, "end")
            self._favorites = []
            if error:
                self._log(f"✗ No se pudieron cargar rutinas: {error}")
                return
            if not favorites:
                self._log("⚠ No hay rutinas guardadas (créalas en la app de iRobot)")
                return
            for fav in favorites:
                steps = f"{fav['steps']} paso(s)" if fav["steps"] else "vacía"
                self.favorites_list.insert("end", f"{fav['name']}  ({steps})")
            self._favorites = favorites
            self._log(f"✓ {len(favorites)} rutina(s) cargadas")

        self._async(self.backend.get_favorites, done)

    def _dispatch_start_favorite(self):
        selection = self.favorites_list.curselection()
        favorites = getattr(self, "_favorites", [])
        if not selection or not favorites:
            self._log("⚠ Selecciona una rutina (actualiza la lista si está vacía)")
            return
        fav = favorites[selection[0]]
        self._log(f"→ Iniciando rutina: {fav['name']}")

        def done(_, error):
            if error:
                self._log(f"✗ Fallo: {error}")
            else:
                self._log(f"✓ Rutina iniciada: {fav['name']}")

        self._async(lambda: self.backend.start_favorite(fav["id"]), done)

    def _dispatch_load_schedules(self):
        self._log("→ Cargando programaciones...")

        def done(schedules, error):
            for item in self.schedules_tree.get_children():
                self.schedules_tree.delete(item)
            if error:
                self._log(f"✗ No se pudieron cargar programaciones: {error}")
                return
            if not schedules:
                self._log("⚠ No hay programaciones en tu cuenta")
                return
            for schedule in schedules:
                self.schedules_tree.insert("", "end", values=(
                    schedule["name"], schedule["time"], schedule["days"],
                    "Sí" if schedule["enabled"] else "No",
                ))
            self._log(f"✓ {len(schedules)} programación(es) cargadas")

        self._async(self.backend.get_schedules, done)

    def _schedule_refresh(self):
        threading.Thread(target=self._refresh_work, daemon=True).start()
        self.root.after(REFRESH_SECS * 1000, self._schedule_refresh)

    def _refresh_work(self):
        try:
            status = self.backend.get_status()
        except Exception:
            return
        self.root.after(0, lambda: self._update_status(status))

    def _update_status(self, status: dict):
        mission = status.get("cleanMissionStatus") or {}
        phase = mission.get("phase")
        if phase:
            self.phase_label.configure(text=PHASE.get(phase, phase))
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.insert("1.0", render_state(status))
        self.status_text.configure(state="disabled")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.root.destroy()
        self.backend.close()
