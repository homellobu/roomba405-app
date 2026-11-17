import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

from . import theme
from .robot import DOCK_PHASES
from .state import PHASE, render_state

BUTTON_LABELS = {
    "start": "▶  Empezar limpieza",
    "pause": "⏸  Pausar",
    "stop": "⏹  Detener",
    "resume": "⏵  Reanudar",
    "dock": "🏠  Volver a la base",
    "find": "📍  Localizar",
    "evac": "🗑  Vaciar depósito",
}

ROUND_BUTTONS = [
    ("pause", "⏸"),
    ("resume", "⏵"),
    ("stop", "⏹"),
    ("dock", "🏠"),
    ("find", "📍"),
]

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

ALL_ROOMS = "Todas las habitaciones"


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

    theme.capsule_button(root, "Seleccionar", confirm, accent=True,
                         bg=theme.BG, min_width=200).pack(pady=(6, 16))
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
        self.root.geometry("1020x700")
        theme.apply(self.root)
        self._set_icon()
        self._online = None
        self._pages = {}
        self._nav_buttons = {}
        self._rooms = []
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
        topbar = ttk.Frame(self.root, padding=(20, 12))
        topbar.pack(fill="x")

        tk.Label(topbar, text="Roomba", bg=theme.BG, fg=theme.TEXT,
                 font=("Helvetica Neue", 15, "bold")).pack(side="left")

        self.status_dot = tk.Canvas(topbar, width=11, height=11,
                                    bg=theme.BG, highlightthickness=0, bd=0)
        self.status_dot.pack(side="left", padx=(18, 5), pady=4)
        self.status_dot.create_oval(1, 1, 10, 10, fill=theme.TEXT_DIM, width=0)
        self.online_label = ttk.Label(topbar, text="Conectando…",
                                      style="Dim.TLabel")
        self.online_label.pack(side="left")

        for name in reversed(NAV_ITEMS):
            btn = theme.nav_button(topbar, name, lambda n=name: self._show(n))
            btn.pack(side="right", padx=(4, 0))
            self._nav_buttons[name] = btn

        container = ttk.Frame(self.root)
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
            page = ttk.Frame(container, padding=(20, 6, 20, 16))
            page.grid(row=0, column=0, sticky="nsew")
            pages[name](page)
            self._pages[name] = page

    def _show(self, name):
        for nav_name, btn in self._nav_buttons.items():
            btn.configure(style="NavActive.TButton" if nav_name == name
                          else "Nav.TButton")
        self._pages[name].tkraise()

    def _build_control(self, parent):
        left = ttk.Frame(parent)
        left.pack(side="left", fill="both", expand=True, padx=(0, 18))

        ttk.Label(left, text="Tu casa, en calma",
                  style="Title.TLabel").pack(anchor="w", pady=(6, 2))
        self.phase_line = tk.Label(left, text="Esperando estado del robot…",
                                   bg=theme.BG, fg=theme.TEXT_DIM, font=theme.FONT_PHASE)
        self.phase_line.pack(anchor="w", pady=(0, 10))

        if ICON_PATH.exists():
            try:
                self._scene_photo = tk.PhotoImage(file=str(ICON_PATH))
                factor = max(1, self._scene_photo.width() // 180)
                self._scene_photo = self._scene_photo.subsample(factor, factor)
                tk.Label(left, image=self._scene_photo, bg=theme.BG,
                         bd=0).pack(pady=(0, 14))
            except Exception:
                pass

        ttk.Label(left, text="ESTADO DE MANTENIMIENTO",
                  style="Dim.TLabel").pack(anchor="w", pady=(0, 6))
        circles = ttk.Frame(left)
        circles.pack(anchor="w")
        self._circles = {}
        for label in ("Batería", "Depósito", "Conexión"):
            canvas = theme.ring(circles)
            canvas.pack(side="left", padx=(0, 18))
            self._circles[label] = canvas

        ttk.Label(left, text="DETALLES DEL ROBOT",
                  style="Dim.TLabel").pack(anchor="w", pady=(14, 6))
        self.status_text = theme.text_widget(left, height=6)
        self.status_text.pack(fill="x")

        panel = theme.card(parent)
        panel.pack(side="left", fill="both", expand=False)
        panel.configure(width=380)
        panel.pack_propagate(False)
        inner = ttk.Frame(panel, style="Card.TFrame", padding=18)
        inner.pack(fill="both", expand=True)

        ttk.Label(inner, text="SELECCIONA UNA HABITACIÓN",
                  style="Card.Dim.TLabel").pack(anchor="w", pady=(0, 6))
        self.room_var = tk.StringVar(value=ALL_ROOMS)
        self.room_combo = ttk.Combobox(inner, textvariable=self.room_var,
                                       state="readonly", width=27,
                                       values=[ALL_ROOMS])
        self.room_combo.pack(fill="x", pady=(0, 10))

        options = ttk.Frame(inner, style="Card.TFrame")
        options.pack(fill="x", pady=(0, 12))
        ttk.Label(options, text="Succión", style="Card.Dim.TLabel").grid(
            row=0, column=0, padx=(0, 6))
        self.suction_var = tk.StringVar(value=SUCTION_OPTIONS[""])
        ttk.Combobox(options, textvariable=self.suction_var, state="readonly",
                     width=12, values=list(SUCTION_OPTIONS.values())).grid(
            row=0, column=1, padx=(0, 14))
        ttk.Label(options, text="Fregado", style="Card.Dim.TLabel").grid(
            row=0, column=2, padx=(0, 6))
        self.pad_var = tk.StringVar(value=PAD_OPTIONS[""])
        ttk.Combobox(options, textvariable=self.pad_var, state="readonly",
                     width=12, values=list(PAD_OPTIONS.values())).grid(row=0, column=3)
        options.columnconfigure(4, weight=1)

        theme.capsule_button(inner, BUTTON_LABELS["start"],
                             self._dispatch_start_cleaning, accent=True,
                             bg=theme.SURFACE, font=("Helvetica Neue", 14, "bold"),
                             padx=28, pady=11, min_width=330).pack(pady=(0, 14))

        rounds = ttk.Frame(inner, style="Card.TFrame")
        rounds.pack(anchor="center", pady=(0, 14))
        for cmd, icon in ROUND_BUTTONS:
            if cmd == "dock":
                action = self._dispatch_dock_retry
            else:
                action = lambda c=cmd: self._dispatch_simple(c)
            theme.circle_button(rounds, icon, action,
                                bg=theme.SURFACE).pack(side="left", padx=5)

        ttk.Label(inner, text="MANTENIMIENTO",
                  style="Card.Dim.TLabel").pack(anchor="w", pady=(0, 6))
        maint = ttk.Frame(inner, style="Card.TFrame")
        maint.pack(fill="x", pady=(0, 12))
        for i, (label, cmd) in enumerate(DOCK_COMMANDS.items()):
            theme.capsule_button(maint, label,
                                 lambda c=cmd: self._dispatch_dock_command(c),
                                 bg=theme.SURFACE, padx=14, pady=7).grid(
                row=i // 2, column=i % 2, padx=4, pady=4)

        ttk.Label(inner, text="REGISTRO DE ACTIVIDAD",
                  style="Card.Dim.TLabel").pack(anchor="w", pady=(0, 6))
        self.log_text = scrolledtext.ScrolledText(
            inner, height=6, state="disabled", bg=theme.SURFACE, fg=theme.TEXT,
            highlightthickness=1, highlightbackground=theme.BORDER, bd=0,
            font=theme.FONT_MONO, padx=10, pady=8)
        self.log_text.pack(fill="both", expand=True)

    def _build_rooms(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 10))
        theme.capsule_button(top, "↻  Actualizar habitaciones",
                             self._dispatch_load_rooms, bg=theme.BG).pack(side="left")

        options = theme.card(parent)
        options.pack(fill="x", pady=(0, 12))
        inner = ttk.Frame(options, style="Card.TFrame", padding=14)
        inner.pack(fill="x")
        ttk.Label(inner, text="Succión", style="Card.Dim.TLabel").grid(
            row=0, column=0, padx=(0, 6))
        ttk.Combobox(inner, textvariable=self.suction_var, state="readonly",
                     width=14, values=list(SUCTION_OPTIONS.values())).grid(
            row=0, column=1, padx=(0, 20))
        ttk.Label(inner, text="Fregado", style="Card.Dim.TLabel").grid(
            row=0, column=2, padx=(0, 6))
        ttk.Combobox(inner, textvariable=self.pad_var, state="readonly",
                     width=14, values=list(PAD_OPTIONS.values())).grid(row=0, column=3)
        inner.columnconfigure(4, weight=1)

        card = theme.card(parent)
        card.pack(fill="both", expand=True, pady=(0, 12))
        inner = ttk.Frame(card, style="Card.TFrame", padding=14)
        inner.pack(fill="both", expand=True)
        ttk.Label(inner, text="Ctrl+clic o Shift+clic para seleccionar varias",
                  style="Card.Dim.TLabel").pack(anchor="w", pady=(0, 4))
        self.rooms_list = theme.listbox(inner)
        self.rooms_list.pack(fill="both", expand=True, pady=(0, 8))

        theme.capsule_button(parent, "▶  Limpiar habitaciones seleccionadas",
                             self._dispatch_clean_rooms, accent=True,
                             bg=theme.BG, min_width=320).pack(pady=(2, 0))

    def _build_routines(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 10))
        theme.capsule_button(top, "↻  Actualizar rutinas",
                             self._dispatch_load_favorites, bg=theme.BG).pack(side="left")

        card = theme.card(parent)
        card.pack(fill="both", expand=True, pady=(0, 12))
        inner = ttk.Frame(card, style="Card.TFrame", padding=14)
        inner.pack(fill="both", expand=True)
        ttk.Label(inner, text="Rutinas guardadas en tu cuenta de iRobot",
                  style="Card.Dim.TLabel").pack(anchor="w", pady=(0, 4))
        self.favorites_list = theme.listbox(inner)
        self.favorites_list.pack(fill="both", expand=True, pady=(0, 8))
        self.favorites_list.bind("<Double-Button-1>",
                                 lambda _: self._dispatch_start_favorite())

        theme.capsule_button(parent, "▶  Iniciar rutina seleccionada",
                             self._dispatch_start_favorite, accent=True,
                             bg=theme.BG, min_width=320).pack(pady=(2, 0))

    def _build_schedules(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 10))
        theme.capsule_button(top, "↻  Actualizar programaciones",
                             self._dispatch_load_schedules, bg=theme.BG).pack(side="left")

        card = theme.card(parent)
        card.pack(fill="both", expand=True)
        inner = ttk.Frame(card, style="Card.TFrame", padding=14)
        inner.pack(fill="both", expand=True)
        columns = ("name", "time", "days", "enabled")
        self.schedules_tree = ttk.Treeview(inner, columns=columns,
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

    def _dispatch_start_cleaning(self):
        if self.room_var.get() == ALL_ROOMS:
            self._dispatch_simple("start")
            return
        rooms = self._rooms
        chosen = [r for r in rooms if r["name"] == self.room_var.get()]
        if not chosen:
            self._log("⚠ Actualiza las habitaciones para usar limpieza por habitación")
            return
        suction_key = next((k for k, v in SUCTION_OPTIONS.items()
                            if v == self.suction_var.get()), "")
        pad_key = next((k for k, v in PAD_OPTIONS.items()
                        if v == self.pad_var.get()), "")
        suction = suction_key or None
        pad_wetness = int(pad_key) if pad_key else None
        names = chosen[0]["name"]
        self._log(f"→ Limpiar: {names} (succión={suction or 'defecto'}, fregado={pad_wetness or 'defecto'})")

        def done(_, error):
            if error:
                self._log(f"✗ Fallo al enviar: {error}")
            else:
                self._log(f"✓ Comando enviado: {names}")

        self._async(lambda: self.backend.clean_rooms(chosen, suction, pad_wetness), done)

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
            if error:
                self._log(f"✗ No se pudieron cargar habitaciones: {error}")
                return
            if not rooms:
                self._log("⚠ Sin mapa activo: deja que el robot mapee la casa primero")
                return
            self._rooms = rooms
            names = [ALL_ROOMS] + [room["name"] for room in rooms]
            self.room_combo.configure(values=names)
            self.rooms_list.delete(0, "end")
            for room in rooms:
                kind = "habitación" if room["type"] == "RID" else "zona"
                self.rooms_list.insert("end", f"  {room['name']}  ·  {kind}")
            self._log(f"✓ {len(rooms)} habitación(es)/zona(s) cargadas")

        self._async(self.backend.get_rooms, done)

    def _dispatch_clean_rooms(self):
        selection = self.rooms_list.curselection()
        rooms = self._rooms
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

    def _update_circles(self, status: dict):
        battery = status.get("batPct")
        if battery is None:
            theme.draw_ring(self._circles["Batería"], 0, theme.TEXT_DIM,
                            "Batería", "—")
        else:
            pct = max(0, min(100, int(battery)))
            color = (theme.SUCCESS if pct >= 30
                     else theme.WARNING if pct >= 15 else theme.DANGER)
            theme.draw_ring(self._circles["Batería"], pct / 100, color,
                            "Batería", f"{pct}%")

        bin_state = status.get("bin") or {}
        if not bin_state:
            theme.draw_ring(self._circles["Depósito"], 0, theme.TEXT_DIM,
                            "Depósito", "—")
        elif bin_state.get("full"):
            theme.draw_ring(self._circles["Depósito"], 1.0, theme.WARNING,
                            "Depósito", "Lleno")
        elif bin_state.get("present") is False:
            theme.draw_ring(self._circles["Depósito"], 0, theme.DANGER,
                            "Depósito", "Ausente")
        else:
            theme.draw_ring(self._circles["Depósito"], 1.0, theme.SUCCESS,
                            "Depósito", "OK")

        if self._online:
            theme.draw_ring(self._circles["Conexión"], 1.0, theme.SUCCESS,
                            "Conexión", "OK")
        else:
            theme.draw_ring(self._circles["Conexión"], 0, theme.DANGER,
                            "Conexión", "Sin")

    def _update_status(self, status: dict):
        self._online = True
        self._set_online(True)
        self._update_circles(status)
        mission = status.get("cleanMissionStatus") or {}
        phase = mission.get("phase")
        error = mission.get("error")
        if error:
            self.phase_line.configure(text=f"⚠  {PHASE.get(phase, phase or 'Error')}: "
                                           f"{error}", fg=theme.DANGER)
        elif phase:
            self.phase_line.configure(text=f"✓  {PHASE.get(phase, phase)}",
                                      fg=theme.phase_color(phase))
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
