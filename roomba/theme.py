import tkinter as tk
from tkinter import ttk

BG = "#f2f3f5"
SURFACE = "#ffffff"
SURFACE_2 = "#e9ebee"
BORDER = "#e2e4e8"
TEXT = "#1a1c20"
TEXT_DIM = "#6b7280"
ACCENT = "#22a55e"
ACCENT_DARK = "#1b8a4e"
SUCCESS = "#22a55e"
WARNING = "#e8a13f"
DANGER = "#e05d5d"

FONT = ("Helvetica Neue", 13)
FONT_SMALL = ("Helvetica Neue", 11)
FONT_TITLE = ("Helvetica Neue", 17, "bold")
FONT_PHASE = ("Helvetica Neue", 12, "bold")
FONT_MONO = ("Menlo", 12)


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
    style.configure("Card.TLabel", background=SURFACE, foreground=TEXT, font=FONT)
    style.configure("Dim.TLabel", background=BG, foreground=TEXT_DIM, font=FONT_SMALL)
    style.configure("Card.Dim.TLabel", background=SURFACE, foreground=TEXT_DIM, font=FONT_SMALL)
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=FONT_TITLE)

    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 4, 0, 0))
    style.configure("TNotebook.Tab", background=BG, foreground=TEXT_DIM,
                    padding=(18, 8), borderwidth=0, font=FONT)
    style.map("TNotebook.Tab",
              background=[("selected", SURFACE)],
              foreground=[("selected", TEXT)])

    style.configure("TButton", background=SURFACE_2, foreground=TEXT,
                    borderwidth=0, focusthickness=0, padding=(16, 9), font=FONT)
    style.map("TButton",
              background=[("active", BORDER), ("pressed", BORDER)],
              foreground=[("active", TEXT), ("pressed", TEXT)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    borderwidth=0, focusthickness=0, padding=(16, 9), font=FONT)
    style.map("Accent.TButton",
              background=[("active", ACCENT_DARK), ("pressed", ACCENT_DARK)],
              foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])

    style.configure("TLabelframe", background=SURFACE, foreground=TEXT_DIM, borderwidth=0)
    style.configure("TLabelframe.Label", background=SURFACE, foreground=TEXT_DIM, font=FONT_SMALL)

    style.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE,
                    foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER, borderwidth=1)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE)],
              foreground=[("readonly", TEXT)])

    style.configure("Treeview", background=SURFACE, foreground=TEXT,
                    fieldbackground=SURFACE, borderwidth=0, rowheight=30, font=FONT)
    style.configure("Treeview.Heading", background=BG, foreground=TEXT_DIM,
                    borderwidth=0, font=FONT_SMALL)
    style.map("Treeview", background=[("selected", ACCENT)],
              foreground=[("selected", "#ffffff")])

    style.configure("Vertical.TScrollbar", background=SURFACE_2, bordercolor=SURFACE,
                    arrowcolor=TEXT_DIM, troughcolor=SURFACE, borderwidth=0)


def card(parent, **kwargs):
    return tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER,
                    highlightthickness=1, **kwargs)


def flat_button(parent, text, command, accent=False, width=None):
    return ttk.Button(
        parent, text=text, command=command, width=width,
        style="Accent.TButton" if accent else "TButton",
    )


def listbox(parent, **kwargs):
    return tk.Listbox(
        parent, bg=SURFACE, fg=TEXT, selectbackground=ACCENT,
        selectforeground="#ffffff", highlightthickness=1,
        highlightbackground=BORDER, bd=0,
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
        highlightthickness=1, highlightbackground=BORDER, bd=0,
        font=FONT_MONO, padx=12, pady=10,
    )
