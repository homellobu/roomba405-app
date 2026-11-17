import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

from . import theme
from .robot import DOCK_PHASES
from .state import PHASE, render_state

BUTTON_LABELS = {
    "start": "▶  Limpiar toda la casa",
    "pause": "⏸  Pausar",
    "stop": "⏹  Detener",
    "resume": "▶  Reanudar",
    "dock": "🏠  Volver a la base",
    "find": "📍  Localizar",
    "evac": "🗑  Vaciar depósito",
}

CONTROL_ROW = ["pause", "resume", "stop", "dock", "find"]

DOCK_COMMANDS = {
    "🗑  Vaciar depósito": "evac",
    "💧  Lavar pad (AutoWash)": "washpad",
    "🌡  Secar pad (AutoWash)": "drypad",
    "💦  Rellenar agua": "flrefill",
}

SUCTION_OPTIONS = {"": "Por defecto", "low": "Baja", "medium": "Media",
                   "high": "Alta", "turbo": "Turbo"}

PAD_OPTIONS = {"": "Por defecto", "1": "Húmedo bajo", "2": "Húmedo medio",
               "3": "Húmedo alto"}

REFRESH_SECS = 10

ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"

NAV_ITEMS = ["Control", "Habitaciones", "Rutinas", "Programaciones"]

NAV_ICONS = {
    "Control": "⌂",
    "Habitaciones": "▦",
    "Rutinas": "◷",
    "Programaciones": "▤",
}


def pick_robot_dialog(robots: dict) -> str:
    result = {"blid": None}
    root = tk.Tk()
    root.title("Selecciona robot")
    root.geometry("380x280")
    theme.apply(root)

    ttk.Label(root, text="¿Qué robot quieres controlar?",
              style="Title.TLabel").pack(pady=(20, 10))

    listbox = theme.listbox(root)
    for blid, info in robots.items():
        listbox.insert("end", f"  {info.get('name', blid)}")
    listbox.pack(fill="both", expand=True, padx=20, pady=8)
    listbox.selection_set(0)

    def confirm(*_):
        selection = listbox.curselection()
        if selection:
            result["blid"] = list(robots)[selection[0]]
        root.destroy()

    theme.flat_button(root, "Seleccionar", confirm, accent=True).pack(
        pady=(6, 16), fill="x", padx=20)
    listbox.bind("<Double-Button-1>", confirm)
    root.bind("<Return>", confirm)
    root.mainloop()

    if not result["blid"]:
        raise SystemExit(0)
    return result["blid"]


class RoombaGUI:
    def __init__(self, backend, robot_name: str = "Roomba"):
        self.backend = backend
        self.robot_name = robot_name
        self.root = tk.Tk()
        self.root.title(f"Roomba — {robot_name}")
        self.root.geometry("920x700")
        theme.apply(self.root)
        self._set_icon()
        self._online = None
        self._pages = {}
        self._nav_buttons = {}
        self._build()
        self._show("Control")
        self._schedule_refresh()

    def _set_icon(self):
        try:
            self._icon = tk.PhotoImage(file=str(ICON_PATH))
            self.root.iconphoto(True, self._icon)
        except Exception:
            pass

    def _build(self):
        self._build_sidebar()

        main = ttk.Frame(self.root, padding=(18, 14))
        main.pack(side="left", fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text=f"Roomba — {self.robot_name}",
                  style="Title.TLabel").pack(side="left")

        self.phase_label = tk.Label(header, text=" — ", bg=theme.SURFACE_2,
                                    fg=theme.TEXT_DIM, font=theme.FONT_PHASE,
                                    padx=14, pady=5, bd=0)
        self.phase_label.pack(side="right", padx=(10, 0))

        battery_box = ttk.Frame(header)
        battery_box.pack(side="right", padx=(10, 0))
        self.battery_label = ttk.Label(battery_box, text="Batería —",
                                       style="Dim.TLabel")
        self.battery_label.pack(side="left", padx=(0, 8))
        self.battery_canvas = tk.Canvas(battery_box, width=130, height=10,
                                        bg=theme.BG, highlightthickness=0, bd=0)
        self.battery_canvas.pack(side="left")

        status_box = ttk.Frame(header)
        status_box.pack(side="right", padx=(10, 14))
        self.status_dot = tk.Canvas(status_box, width=11, height=11,
                                    bg=theme.BG, highlightthickness=0, bd=0)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_dot.create_oval(1, 1, 10, 10, fill=theme.TEXT_DIM, width=0)
        self.online_label = ttk.Label(status_box, text="Conectando…",
                                      style="Dim.TLabel")
        self.online_label.pack(side="left")

        container = ttk.Frame(main)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        pages = {
            "Control": self._build_control,
            "Habitaciones": self._build_rooms,
            "Rutinas": self._build_routines,
            "Programaciones": self._build_schedules,
        }
        for name in NAV_ITEMS:
            page = ttk.Frame(container)
            page.grid(row=0, column=0, sticky="nsew")
            pages[name](page)
            self._pages[name] = page

    def _build_sidebar(self):
        sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=180)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="  Roomba", bg=theme.SIDEBAR, fg=theme.TEXT,
                 font=theme.FONT_TITLE, anchor="w", pady=14).pack(fill="x")

        for name in NAV_ITEMS:
            label = f"{NAV_ICONS[name]}  {name}"
            btn = theme.nav_button(sidebar, label,
                                   lambda n=name: self._show(n))
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_buttons[name] = btn

        ttk.Label(sidebar, text=self.robot_name,
                  style="Sidebar.Dim.TLabel").pack(side="bottom", pady=12)

    def _show(self, name):
        for nav_name, btn in self._nav_buttons.items():
            btn.configure(style="NavActive.TButton" if nav_name == name
                          else "Nav.TButton")
        self._pages[name].tkraise()

    def _section(self, parent, title=None):
        card = theme.card(parent)
        card.pack(fill="x", pady=(0, 12))
        inner = ttk.Frame(card, style="Card.TFrame", padding=14)
        inner.pack(fill="both", expand=True)
        if title:
            ttk.Label(inner, text=title, style="Card.Dim.TLabel").pack(
                anchor="w", pady=(0, 8))
        return inner

    def _build_control(self, parent):
        status_inner = self._section(parent)
        self.status_text = theme.text_widget(status_inner, height=9)
        self.status_text.pack(fill="x")

        theme.flat_button(parent, BUTTON_LABELS["start"],
                          lambda: self._dispatch_simple("start"),
                          accent=True).pack(fill="x", ipady=6, pady=(2, 10))

        row = ttk.Frame(parent)
        row.pack(fill="x")
        for i, cmd in enumerate(CONTROL_ROW):
            row.columnconfigure(i, weight=1)
            theme.flat_button(row, BUTTON_LABELS[cmd],
                              lambda c=cmd: self._dispatch_simple(c)).grid(
                row=0, column=i, sticky="ew", padx=3)

        theme.flat_button(parent, "🏠  Volver a la base (con reintentos)",
                          self._dispatch_dock_retry).pack(fill="x", pady=(10, 0))

        maint = self._section(parent, "Mantenimiento")
        for i, (label, cmd) in enumerate(DOCK_COMMANDS.items()):
            maint.columnconfigure(i, weight=1)
            theme.flat_button(maint, label,
                              lambda c=cmd: self._dispatch_dock_command(c)).grid(
                row=0, column=i, sticky="ew", padx=3)

        log_inner = self._section(parent, "Registro de actividad")
        self.log_text = scrolledtext.ScrolledText(
            log_inner, height=6, state="disabled", bg=theme.SURFACE, fg=theme.TEXT,
            highlightthickness=0, bd=0, font=theme.FONT_MONO, padx=4, pady=0)
        self.log_text.pack(fill="both", expand=True)

    def _build_rooms(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 10))
        theme.flat_button(top, "↻  Actualizar habitaciones",
                          self._dispatch_load_rooms).pack(side="left")

        options = self._section(parent, "Opciones de limpieza")
        ttk.Label(options, text="Succión", style="Card.Dim.TLabel").grid(
            row=0, column=0, padx=(0, 6))
        self.suction_var = tk.StringVar(value=SUCTION_OPTIONS[""])
        ttk.Combobox(options, textvariable=self.suction_var, state="readonly",
                     width=14, values=list(SUCTION_OPTIONS.values())).grid(
            row=0, column=1, padx=(0, 20))
        ttk.Label(options, text="Fregado", style="Card.Dim.TLabel").grid(
            row=0, column=2, padx=(0, 6))
        self.pad_var = tk.StringVar(value=PAD_OPTIONS[""])
        ttk.Combobox(options, textvariable=self.pad_var, state="readonly",
                     width=14, values=list(PAD_OPTIONS.values())).grid(row=0, column=3)
        options.columnconfigure(4, weight=1)

        rooms_card = self._section(parent, "Habitaciones y zonas")
        ttk.Label(rooms_card, text="Ctrl+clic o Shift+clic para seleccionar varias",
                  style="Card.Dim.TLabel").pack(anchor="w", pady=(0, 4))
        self.rooms_list = theme.listbox(rooms_card)
        self.rooms_list.pack(fill="both", expand=True, pady=(0, 8))

        theme.flat_button(parent, "▶  Limpiar habitaciones seleccionadas",
                          self._dispatch_clean_rooms, accent=True).pack(
            fill="x", ipady=4)

    def _build_routines(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 10))
        theme.flat_button(top, "↻  Actualizar rutinas",
                          self._dispatch_load_favorites).pack(side="left")

        card = self._section(parent, "Rutinas guardadas en tu cuenta de iRobot")
        self.favorites_list = theme.listbox(card)
        self.favorites_list.pack(fill="both", expand=True, pady=(0, 8))
        self.favorites_list.bind("<Double-Button-1>",
                                 lambda _: self._dispatch_start_favorite())

        theme.flat_button(parent, "▶  Iniciar rutina seleccionada",
                          self._dispatch_start_favorite, accent=True).pack(
            fill="x", ipady=4)

    def _build_schedules(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 10))
        theme.flat_button(top, "↻  Actualizar programaciones",
                          self._dispatch_load_schedules).pack(side="left")

        card = self._section(parent, "Programaciones")
        columns = ("name", "time", "days", "enabled")
        self.schedules_tree = ttk.Treeview(card, columns=columns,
                                           show="headings", height=10)
        self.schedules_tree.heading("name", text="Nombre")
        self.schedules_tree.heading("time", text="Hora")
        self.schedules_tree.heading("days", text="Días")
        self.schedules_tree.heading("enabled", text="Activa")
        self.schedules_tree.column("name", width=240)
        self.schedules_tree.column("time", width=80, anchor="center")
        self.schedules_tree.column("days", width=200)
        self.schedules_tree.column("enabled", width=70, anchor="center")
        self.schedules_tree.pack(fill="both", expand=True)

    def _log(self, message: str):
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"{time.strftime('%H:%M')}  {message}\n")
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
                self.rooms_list.insert("end", f"  {room['name']}  ·  {kind}")
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
                self.favorites_list.insert("end", f"  {fav['name']}  ·  {steps}")
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
            self.root.after(0, lambda: self._set_online(False))
            return
        self.root.after(0, lambda: self._update_status(status))

    def _set_online(self, online: bool):
        color = theme.SUCCESS if online else theme.DANGER
        text = "En línea" if online else "Sin conexión"
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 10, 10, fill=color, width=0)
        self.online_label.configure(text=text)

    def _draw_battery(self, pct):
        canvas = self.battery_canvas
        canvas.delete("all")
        width = 130
        height = 10
        canvas.create_rectangle(0, 0, width, height, outline=theme.BORDER, width=1)
        if pct:
            fill = (theme.SUCCESS if pct >= 30
                    else theme.WARNING if pct >= 15 else theme.DANGER)
            canvas.create_rectangle(1, 1, 1 + (width - 2) * pct / 100,
                                    height - 1, fill=fill, width=0)

    def _update_status(self, status: dict):
        self._set_online(True)
        battery = status.get("batPct")
        if battery is not None:
            self.battery_label.configure(text=f"Batería {battery}%")
            self._draw_battery(int(battery))
        mission = status.get("cleanMissionStatus") or {}
        phase = mission.get("phase")
        if phase:
            self.phase_label.configure(text=PHASE.get(phase, phase),
                                       bg=theme.phase_color(phase, mission.get("error")),
                                       fg="#ffffff")
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
