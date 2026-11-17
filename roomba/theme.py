import tkinter as tk
from tkinter import ttk

BG = "#e9e6d3"
SURFACE = "#f5f3e8"
SURFACE_2 = "#e2dfcc"
BORDER = "#d9d5bf"
CIRCLE = "#e7eedb"
TEXT = "#20241a"
TEXT_DIM = "#84886f"
ACCENT = "#305237"
ACCENT_DARK = "#264229"
SUCCESS = "#5a8a5e"
WARNING = "#c9a13f"
DANGER = "#c05d50"

FONT = ("Helvetica Neue", 13)
FONT_SMALL = ("Helvetica Neue", 11)
FONT_TITLE = ("Helvetica Neue", 26, "bold")
FONT_PHASE = ("Helvetica Neue", 13, "bold")
FONT_MONO = ("Menlo", 11)
FONT_ICON = ("Helvetica Neue", 17)


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

    style.configure("TButton", background=SURFACE_2, foreground=TEXT,
                    borderwidth=0, focusthickness=0, padding=(14, 8), font=FONT)
    style.map("TButton",
              background=[("active", BORDER), ("pressed", BORDER)],
              foreground=[("active", TEXT), ("pressed", TEXT)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    borderwidth=0, focusthickness=0, padding=(14, 8), font=FONT)
    style.map("Accent.TButton",
              background=[("active", ACCENT_DARK), ("pressed", ACCENT_DARK)],
              foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])

    style.configure("Nav.TButton", background=BG, foreground=TEXT_DIM,
                    borderwidth=0, focusthickness=0, padding=(12, 6), font=FONT_SMALL)
    style.map("Nav.TButton",
              background=[("active", SURFACE), ("pressed", SURFACE)],
              foreground=[("active", TEXT), ("pressed", TEXT)])
    style.configure("NavActive.TButton", background=SURFACE, foreground=ACCENT,
                    borderwidth=0, focusthickness=0, padding=(12, 6), font=FONT_PHASE)
    style.map("NavActive.TButton",
              background=[("active", SURFACE), ("pressed", SURFACE)],
              foreground=[("active", ACCENT), ("pressed", ACCENT)])

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


def flat_button(parent, text, command, accent=False, width=None, style_name=None):
    name = style_name or ("Accent.TButton" if accent else "TButton")
    return ttk.Button(parent, text=text, command=command, width=width, style=name)


def nav_button(parent, text, command, active=False):
    return ttk.Button(parent, text=text, command=command,
                      style="NavActive.TButton" if active else "Nav.TButton")


def circle_button(parent, icon, command, size=54, bg=None):
    canvas = tk.Canvas(parent, width=size, height=size,
                       bg=bg or SURFACE, highlightthickness=0, bd=0,
                       cursor="hand2")
    pad = 3
    canvas.create_oval(pad, pad, size - pad, size - pad,
                       fill=SURFACE, outline=BORDER, width=1, tags="btn")
    canvas.create_text(size / 2, size / 2, text=icon, font=FONT_ICON,
                       fill=TEXT, tags="btn")

    def press(_):
        command()

    def enter(_):
        canvas.itemconfigure("btn", outline=ACCENT)

    def leave(_):
        canvas.itemconfigure("btn", outline=BORDER)

    canvas.tag_bind("btn", "<Button-1>", press)
    canvas.tag_bind("btn", "<Enter>", enter)
    canvas.tag_bind("btn", "<Leave>", leave)
    return canvas


def ring(parent, size=76, bg=None):
    canvas = tk.Canvas(parent, width=size, height=size + 4,
                       bg=bg or BG, highlightthickness=0, bd=0)
    return canvas


def draw_ring(canvas, fraction, color, label, value, size=76):
    canvas.delete("all")
    pad = 6
    canvas.create_arc(pad, pad, size - pad, size - pad, start=90,
                      extent=359.9, style="arc", outline=BORDER, width=5)
    if fraction > 0:
        canvas.create_arc(pad, pad, size - pad, size - pad, start=90,
                          extent=-360 * max(0.0, min(1.0, fraction)),
                          style="arc", outline=color, width=5)
    canvas.create_text(size / 2, size / 2 - 2, text=value,
                       font=("Helvetica Neue", 14, "bold"), fill=TEXT)
    canvas.create_text(size / 2, size + 6, text=label,
                       font=FONT_SMALL, fill=TEXT_DIM)


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
