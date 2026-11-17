import tkinter as tk
from tkinter import ttk

BG = "#1b1d23"
SURFACE = "#242730"
SURFACE_2 = "#2e323d"
TEXT = "#e8eaf0"
TEXT_DIM = "#9aa0ae"
ACCENT = "#4f8cff"
ACCENT_DARK = "#3a6fd8"
SUCCESS = "#3fbf7f"
WARNING = "#e8b23f"
DANGER = "#e05d5d"

FONT = ("SF Pro Text", 12)
FONT_SMALL = ("SF Pro Text", 11)
FONT_TITLE = ("SF Pro Display", 16, "bold")
FONT_PHASE = ("SF Pro Display", 13, "bold")


def apply(root: tk.Tk):
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT, font=FONT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE)
    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT)
    style.configure("Dim.TLabel", background=BG, foreground=TEXT_DIM, font=FONT_SMALL)
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=FONT_TITLE)

    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 4, 0, 0))
    style.configure("TNotebook.Tab", background=SURFACE, foreground=TEXT_DIM,
                    padding=(18, 8), borderwidth=0, font=FONT)
    style.map("TNotebook.Tab",
              background=[("selected", SURFACE_2)],
              foreground=[("selected", TEXT)])

    style.configure("TButton", background=SURFACE_2, foreground=TEXT,
                    borderwidth=0, padding=(12, 8), font=FONT)
    style.map("TButton", background=[("active", ACCENT_DARK), ("pressed", ACCENT_DARK)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
    style.map("Accent.TButton", background=[("active", ACCENT_DARK), ("pressed", ACCENT_DARK)])

    style.configure("TLabelframe", background=BG, foreground=TEXT_DIM, borderwidth=0)
    style.configure("TLabelframe.Label", background=BG, foreground=TEXT_DIM, font=FONT_SMALL)

    style.configure("TCombobox", fieldbackground=SURFACE_2, background=SURFACE_2,
                    foreground=TEXT, arrowcolor=TEXT, borderwidth=0)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE_2)],
              foreground=[("readonly", TEXT)])

    style.configure("Treeview", background=SURFACE, foreground=TEXT,
                    fieldbackground=SURFACE, borderwidth=0, rowheight=28, font=FONT)
    style.configure("Treeview.Heading", background=SURFACE_2, foreground=TEXT_DIM,
                    borderwidth=0, font=FONT_SMALL)
    style.map("Treeview", background=[("selected", ACCENT)],
              foreground=[("selected", "#ffffff")])


def flat_button(parent, text, command, accent=False, width=None):
    btn = tk.Button(
        parent, text=text, command=command, bd=0, relief="flat", highlightthickness=0,
        bg=ACCENT if accent else SURFACE_2,
        fg="#ffffff" if accent else TEXT,
        activebackground=ACCENT_DARK if accent else SURFACE_2,
        activeforeground="#ffffff",
        font=FONT, padx=16, pady=9, cursor="hand2", width=width,
    )
    hover_bg = ACCENT_DARK if accent else SURFACE_2
    normal_bg = ACCENT if accent else SURFACE_2
    btn.bind("<Enter>", lambda _: btn.configure(bg=hover_bg))
    btn.bind("<Leave>", lambda _: btn.configure(bg=normal_bg))
    return btn


def listbox(parent, **kwargs):
    return tk.Listbox(
        parent, bg=SURFACE, fg=TEXT, selectbackground=ACCENT,
        selectforeground="#ffffff", highlightthickness=0, bd=0,
        activestyle="none", font=FONT, **kwargs
    )


def phase_color(phase: str | None, error=None) -> str:
    if error:
        return DANGER
    return {
        "charge": SUCCESS,
        "run": ACCENT,
        "pause": WARNING,
        "hmUsrDock": WARNING,
        "hmMidMsn": WARNING,
        "hmPostMsn": WARNING,
        "evac": WARNING,
        "chargingerror": DANGER,
    }.get(phase or "", TEXT_DIM)


def text_widget(parent, height=None):
    return tk.Text(
        parent, height=height, state="disabled", relief="flat",
        bg=SURFACE, fg=TEXT, insertbackground=TEXT,
        highlightthickness=0, bd=0, font=("Menlo", 12), padx=12, pady=10,
    )
