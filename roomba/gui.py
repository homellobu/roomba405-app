import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from .robot import COMMANDS, DOCK_PHASES
from .state import PHASE, render_state


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

BUTTON_LABELS = {
    "start": "▶  Limpiar",
    "pause": "⏸  Pausar",
    "stop": "⏹  Detener",
    "resume": "⏵  Reanudar",
    "dock": "🏠  Volver a la base",
    "find": "🔔  Localizar",
    "evac": "🗑  Vaciar depósito",
    "reset": "♻  Reiniciar robot",
}

REFRESH_SECS = 10


class RoombaGUI:
    def __init__(self, robot):
        self.robot = robot
        self.root = tk.Tk()
        self.root.title(f"Roomba — {robot.name}")
        self.root.geometry("520x640")
        self._build()
        self._schedule_refresh()

    def _build(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text=self.robot.name, font=("", 16, "bold")).pack(side="left")
        self.phase_label = ttk.Label(header, text="—", foreground="#555")
        self.phase_label.pack(side="right")

        self.status_text = tk.Text(main, height=14, width=60, state="disabled",
                                   relief="flat", background="#f6f6f6")
        self.status_text.pack(fill="both", expand=False, pady=(0, 10))

        buttons = ttk.Frame(main)
        buttons.pack(fill="x")
        for i, (cmd, label) in enumerate(BUTTON_LABELS.items()):
            btn = ttk.Button(buttons, text=label,
                             command=lambda c=cmd: self._dispatch_command(c))
            btn.grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)

        retry_btn = ttk.Button(main, text="🏠 Volver a la base (con reintentos)",
                               command=self._dispatch_dock_retry)
        retry_btn.pack(fill="x", pady=(8, 4))

        ttk.Label(main, text="Registro:").pack(anchor="w", pady=(8, 2))
        self.log_text = scrolledtext.ScrolledText(main, height=8, state="disabled")
        self.log_text.pack(fill="both", expand=True)

    def _log(self, message: str):
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, append)

    def _dispatch_command(self, cmd: str):
        label = BUTTON_LABELS.get(cmd, cmd)

        def work():
            self._log(f"→ {label}")
            try:
                self.robot.send(cmd)
                self._log(f"✓ Enviado: {label}")
            except Exception as e:
                self._log(f"✗ Fallo al enviar {label}: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _dispatch_dock_retry(self):
        def work():
            self._log("→ Volver a la base (con reintentos)")
            try:
                ok = self.robot.dock_with_retry()
                if ok:
                    self._log("✓ El robot está de regreso a la base o cargando")
                else:
                    self._log("✗ El robot no ha entrado en fase de regreso; colócalo cerca de la base y reintenta")
            except Exception as e:
                self._log(f"✗ Fallo: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _schedule_refresh(self):
        threading.Thread(target=self._refresh_work, daemon=True).start()
        self.root.after(REFRESH_SECS * 1000, self._schedule_refresh)

    def _refresh_work(self):
        try:
            self.robot.refresh_state()
        except Exception:
            pass
        self.root.after(0, self._update_status)

    def _update_status(self):
        state = self.robot.snapshot()
        mission = state.get("cleanMissionStatus") or {}
        phase = mission.get("phase")
        if phase:
            self.phase_label.configure(text=PHASE.get(phase, phase))
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.insert("1.0", render_state(state))
        self.status_text.configure(state="disabled")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.root.destroy()
        self.robot.disconnect()
