# -*- coding: utf-8 -*-
"""
eny_gui  ·  enyripter v3  ·  GUI-Modus  ("ENCRYPT-OS v3")
=========================================================

Animiertes Mini-OS mit ECHTER, passwortbasierter Verschluesselung (eny_core):
  * Matrix-Rain Hintergrund (Canvas)
  * Glitch-Boot, Login, animierter Desktop
  * Neon-Buttons mit Hover-Glow, Theme-Wechsel
  * Verschluesselungs-Animation (fliessende Bits), Passwort-Staerke-Meter
  * Text- & Datei-Verschluesselung, Passwortgenerator, Live-Konsole

Schwere Krypto (KDF) laeuft in Hintergrund-Threads -> UI bleibt fluessig.

Starten:  python enyrpter3.py --gui   (oder Modus-Auswahl im Launcher)
Direkt :  python eny_gui.py
"""

from __future__ import annotations

import os
import queue
import random
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

import eny_core as core


# ==========================================================================
#   Themes
# ==========================================================================

THEMES = {
    "matrix": {
        "bg": "#01040a", "panel": "#070d16", "panel2": "#0b1320",
        "accent": "#27f08a", "accent2": "#3df0ff", "text": "#d7ffe9",
        "muted": "#7da894", "warn": "#ffcc33", "err": "#ff5c6c", "rain": "#1de37a",
    },
    "cyber": {
        "bg": "#05010f", "panel": "#0d0820", "panel2": "#160d2e",
        "accent": "#ff5cf3", "accent2": "#4cd6ff", "text": "#f0e6ff",
        "muted": "#a193cc", "warn": "#ffcc33", "err": "#ff5c6c", "rain": "#c026d3",
    },
    "purple": {
        "bg": "#070317", "panel": "#120a28", "panel2": "#1c1138",
        "accent": "#b06bff", "accent2": "#4cd6ff", "text": "#ece6ff",
        "muted": "#9787c4", "warn": "#ffcc33", "err": "#ff5c6c", "rain": "#8b5cf6",
    },
    "blood": {
        "bg": "#0a0202", "panel": "#160707", "panel2": "#220a0a",
        "accent": "#ff5564", "accent2": "#ff9a52", "text": "#ffe3e3",
        "muted": "#c08585", "warn": "#ffcc33", "err": "#ff5c6c", "rain": "#e3324a",
    },
    "ice": {
        "bg": "#020812", "panel": "#06121f", "panel2": "#0a1c30",
        "accent": "#4cc5ff", "accent2": "#a5f3fc", "text": "#e0f7ff",
        "muted": "#7da7c4", "warn": "#ffcc33", "err": "#ff5c6c", "rain": "#22a7e0",
    },
}

FONT_MONO = "Consolas"


# ==========================================================================
#   Matrix-Rain Hintergrund
# ==========================================================================

class MatrixRain:
    """Effizienter Matrix-Regen auf einem Canvas (recycelt Items pro Spalte)."""

    GLYPHS = "01ｱｲｳｴｵｶｷｸｹｺｻｼｽｾﾀﾁﾂ#%&*<>=+-/\\$ABCDEF0123456789"

    def __init__(self, canvas: tk.Canvas, app):
        self.canvas = canvas
        self.app = app
        self.col_w = 16
        self.row_h = 18
        self.columns = []
        self.running = True
        self.frame = 0
        self.gen = 0  # Loop-Generation: verhindert doppelte _tick-Schleifen beim Toggeln
        self._reconfig_after = None
        self._configure()
        self.canvas.bind("<Configure>", self._on_configure)
        self._start_loop()

    def _start_loop(self):
        self.gen += 1
        self._tick(self.gen)

    def _on_configure(self, _event=None):
        # Debounce: <Configure> feuert in Bursts (Resize/F11). Nur einmal nachziehen.
        if self._reconfig_after is not None:
            try:
                self.canvas.after_cancel(self._reconfig_after)
            except Exception:
                pass
        self._reconfig_after = self.canvas.after(120, self._configure)

    def _configure(self):
        self._reconfig_after = None
        if not self.running:
            return
        w = max(self.canvas.winfo_width(), self.canvas.winfo_reqwidth(), 800)
        h = max(self.canvas.winfo_height(), self.canvas.winfo_reqheight(), 600)
        self.w, self.h = w, h
        n = max(8, w // self.col_w)
        rows = max(8, h // self.row_h)
        self.rows = rows
        # Alte Rain-Items entfernen, sonst lecken sie bei jedem Resize/F11.
        # bg_canvas haelt ausschliesslich Rain-Items -> delete("all") ist sicher.
        try:
            self.canvas.delete("all")
        except tk.TclError:
            return
        # Spalten neu aufbauen
        self.columns = []
        for i in range(n):
            self.columns.append({
                "x": i * self.col_w + 4,
                "head": random.randint(-rows, 0),
                "speed": random.choice([1, 1, 1, 2]),
                "len": random.randint(6, max(8, rows // 2)),
                "items": [],
            })

    def stop(self):
        self.running = False
        self.gen += 1

    def set_enabled(self, on):
        """Animation an/aus schalten (ruhiger Modus)."""
        if on and not self.running:
            self.running = True
            self._configure()
            self._start_loop()
        elif not on and self.running:
            self.running = False
            self.gen += 1
            try:
                self.canvas.delete("all")
            except tk.TclError:
                pass

    def _color(self):
        return self.app.theme.get("rain", "#1de37a")

    def _tick(self, gen):
        if not self.running or gen != self.gen or not self.app.alive:
            return
        self.frame += 1
        rain = self._color()
        accent = self.app.theme["accent"]
        for col in self.columns:
            if self.frame % (3 - 0) != 0 and col["speed"] == 1 and (self.frame % 2):
                # leichte Geschwindigkeitsvariation
                pass
            col["head"] += col["speed"]
            y = col["head"] * self.row_h
            ch = random.choice(self.GLYPHS)
            item = self.canvas.create_text(
                col["x"], y, text=ch, fill=accent,
                font=(FONT_MONO, 12, "bold"), anchor="n",
            )
            col["items"].append(item)
            # Trail abdunkeln
            trail = col["items"]
            if len(trail) > col["len"]:
                old = trail.pop(0)
                self.canvas.delete(old)
            # zweitvorderstes Zeichen leicht abdunkeln
            if len(trail) >= 2:
                self.canvas.itemconfigure(trail[-2], fill=rain)
            # Reset wenn unten raus
            if y > self.h + self.row_h:
                if random.random() < 0.5:
                    for it in col["items"]:
                        self.canvas.delete(it)
                    col["items"] = []
                    col["head"] = random.randint(-self.rows // 2, 0)
                    col["len"] = random.randint(6, max(8, self.rows // 2))
                    col["speed"] = random.choice([1, 1, 1, 2])
        self.canvas.after(60, lambda: self._tick(gen))


# ==========================================================================
#   Neon-Button (Label-basiert mit Hover-Glow)
# ==========================================================================

class NeonButton(tk.Label):
    def __init__(self, parent, app, text, command, *, kind="normal", **kw):
        self.app = app
        self.command = command
        self.kind = kind
        super().__init__(
            parent, text=text, cursor="hand2",
            font=app.font(11, "bold"), bd=0, padx=16, pady=8,
            **kw,
        )
        self._apply_idle()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _colors(self):
        t = self.app.theme
        if self.kind == "primary":
            return t["panel2"], t["accent"], t["accent"], t["bg"]
        if self.kind == "danger":
            return t["panel2"], t["err"], t["err"], "#ffffff"
        return t["panel"], t["text"], t["accent2"], t["bg"]

    def _apply_idle(self):
        bg, fg, hover_bg, hover_fg = self._colors()
        self.configure(bg=bg, fg=fg, highlightthickness=1,
                       highlightbackground=self.app.theme["panel2"],
                       highlightcolor=self.app.theme["accent"])
        self._idle = (bg, fg)
        self._hover = (hover_bg, hover_fg)

    def _on_enter(self, _):
        self.configure(bg=self._hover[0], fg=self._hover[1])

    def _on_leave(self, _):
        self.configure(bg=self._idle[0], fg=self._idle[1])

    def _on_click(self, _):
        # kurzer "Press"-Effekt
        self.configure(bg=self.app.theme["accent"], fg=self.app.theme["bg"])
        self.after(90, self._on_leave, None)
        if self.command:
            self.after(40, self.command)

    def refresh_theme(self):
        self._apply_idle()


# ==========================================================================
#   Haupt-App
# ==========================================================================

class EncryptOS(tk.Tk):
    def __init__(self, fullscreen=False, maximize=True, show_welcome=True):
        super().__init__()
        self.title("enyripter v3  ·  ENCRYPT-OS")
        self.configure(bg="#01040a")
        self.minsize(1000, 660)
        self.is_fullscreen = bool(fullscreen)
        if fullscreen:
            try:
                self.attributes("-fullscreen", True)
            except Exception:
                self.geometry("1280x820")
        else:
            # Normales Fenster mit Titelleiste + Schliessen-Button (nicht "sketchy")
            self.geometry("1280x820")
            self._center_window(1280, 820)
            if maximize:
                try:
                    self.state("zoomed")  # maximiert, aber mit Fensterrahmen/✕ (Windows)
                except Exception:
                    pass

        self.alive = True
        self._gen = 0  # Screen-Generation: invalidiert alte after()-Schleifen
        self._on_desktop = False
        self.animations = True          # Matrix-Hintergrund / "ruhiger Modus"
        self._show_welcome = show_welcome
        self._welcome_done = False
        self.theme_name = "matrix"
        self.theme = THEMES[self.theme_name]
        self.font_scale = 1.0
        self.username = "operator"

        # Krypto-Settings
        self.cipher_id = core.CIPHER_CHACHA
        self.level = core.DEFAULT_LEVEL
        self.encoding = "base64"
        self.compress = True
        self.username = os.environ.get("USERNAME") or os.environ.get("USER") or "operator"

        self.enc_history = []
        self.work_queue = queue.Queue()
        self.active_app = "encrypt"
        self._busy = set()  # verhindert ueberlappende Krypto-Laeufe (enc/dec/file)

        # Hintergrund-Canvas (Matrix Rain)
        self.bg_canvas = tk.Canvas(self, bg=self.theme["bg"], highlightthickness=0, bd=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.rain = None

        # Overlay fuer Screens
        self.overlay = tk.Frame(self, bg=self.theme["bg"], bd=0, highlightthickness=0)
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.bind("<Escape>", lambda e: self.on_escape())
        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.protocol("WM_DELETE_WINDOW", self.on_escape)

        self.after(60, self._start_rain)
        self.show_boot()

    # ---------- Fonts / helpers ----------

    def font(self, size, weight="normal", family=FONT_MONO):
        s = max(6, int(size * self.font_scale))
        return (family, s, weight)

    def _start_rain(self):
        if self.rain is None:
            self.rain = MatrixRain(self.bg_canvas, self)
        if not self.animations:
            self.rain.set_enabled(False)

    def _center_window(self, w, h):
        try:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2)}")
        except Exception:
            pass

    def _toggle_fullscreen(self, _event=None):
        try:
            self.is_fullscreen = not bool(self.attributes("-fullscreen"))
            self.attributes("-fullscreen", self.is_fullscreen)
        except Exception:
            pass
        return "break"

    def clear_overlay(self):
        for child in self.overlay.winfo_children():
            child.destroy()

    def _glass(self, parent, **kw):
        """Halbtransparent wirkendes Panel (dunkles Frame mit Neon-Rand)."""
        f = tk.Frame(parent, bg=self.theme["panel"], bd=0,
                     highlightthickness=1, highlightbackground=self.theme["panel2"],
                     highlightcolor=self.theme["accent"], **kw)
        return f

    # ======================================================================
    #   BOOT
    # ======================================================================

    def show_boot(self):
        self._gen += 1
        self._on_desktop = False
        self.clear_overlay()
        t = self.theme
        wrap = tk.Frame(self.overlay, bg=t["bg"])
        wrap.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.7, relheight=0.7)

        self._glitch_title = tk.Label(
            wrap, text="enyripter", font=self.font(36, "bold"),
            bg=t["bg"], fg=t["accent"],
        )
        self._glitch_title.pack(pady=(10, 4))
        self._pulse(self._glitch_title, ["accent", "accent2", "text"])

        tk.Label(wrap, text="Sichere Verschlüsselung für Texte und Dateien · wird gestartet",
                 font=self.font(11), bg=t["bg"], fg=t["muted"]).pack(pady=(0, 18))

        box = self._glass(wrap)
        box.pack(fill="both", expand=True, padx=40)
        self.boot_log = tk.Text(box, bg=t["panel"], fg=t["text"], bd=0,
                                font=self.font(10), height=14,
                                insertbackground=t["accent"], wrap="word",
                                highlightthickness=0)
        self.boot_log.pack(fill="both", expand=True, padx=14, pady=14)
        self.boot_log.configure(state="disabled")

        self.boot_bar = tk.Canvas(wrap, height=14, bg=t["bg"], highlightthickness=0)
        self.boot_bar.pack(fill="x", padx=40, pady=(14, 6))

        skip = tk.Label(wrap, text="Überspringen  ▸   (Klick / beliebige Taste)",
                        font=self.font(10), bg=t["bg"], fg=t["muted"], cursor="hand2")
        skip.pack(pady=(4, 0))
        skip.bind("<Button-1>", lambda e: self._skip_boot())
        self.bind("<Key>", lambda e: self._skip_boot())
        self.overlay.bind("<Button-1>", lambda e: self._skip_boot())

        caps = core.capabilities()
        # Ehrliche, ruhige Statuszeilen (kein Fake-Hacker-OS-Jargon -> wirkt seriös, nicht "sketchy")
        steps = [
            "Verschlüsselungs-Module werden geladen ...",
            "Verfahren bereit: ChaCha20-Poly1305 / AES-256-GCM",
            f"Schlüsselableitung bereit: {caps['default_kdf']}",
            "Sichere Zufallsquelle initialisiert",
            "Oberfläche wird vorbereitet ...",
            "Bereit.",
        ]
        self._boot_run(steps, 0, self._gen)

    def _skip_boot(self):
        """Boot-Animation ueberspringen und direkt zum Desktop."""
        if not self.alive or self.current_screen_is_desktop():
            return
        self._unbind_boot_skip()
        self.show_desktop()

    def current_screen_is_desktop(self):
        return getattr(self, "_on_desktop", False)

    def _unbind_boot_skip(self):
        try:
            self.unbind("<Key>")
            self.overlay.unbind("<Button-1>")
        except tk.TclError:
            pass

    def _boot_run(self, steps, i, gen):
        if not self.alive or gen != self._gen:
            return  # Screen wurde gewechselt / uebersprungen -> abbrechen
        try:
            if i >= len(steps):
                self._draw_progress(self.boot_bar, 1.0)
                self.after(450, self._goto_desktop_from_boot)
                return
            self._boot_line(steps[i])
            self._draw_progress(self.boot_bar, (i + 1) / len(steps))
        except tk.TclError:
            return
        self.after(random.randint(120, 220), lambda: self._boot_run(steps, i + 1, gen))

    def _goto_desktop_from_boot(self):
        if not self.alive or self.current_screen_is_desktop():
            return
        self._unbind_boot_skip()
        self.show_desktop()

    def _boot_line(self, text):
        self.boot_log.configure(state="normal")
        self.boot_log.insert("end", "> " + text + "\n")
        self.boot_log.see("end")
        self.boot_log.configure(state="disabled")

    def _draw_progress(self, canvas, frac):
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        w = canvas.winfo_width() or 600
        h = int(canvas["height"])
        t = self.theme
        canvas.create_rectangle(0, 0, w, h, fill=t["panel"], outline=t["panel2"])
        fillw = int(w * max(0.0, min(1.0, frac)))
        # Gradient-aehnliche Bloecke
        seg = 8
        for x in range(0, fillw, seg):
            shade = t["accent"] if (x // seg) % 2 == 0 else t["accent2"]
            canvas.create_rectangle(x, 1, min(x + seg - 1, fillw), h - 1, fill=shade, outline="")
        canvas.create_text(w - 6, h // 2, text=f"{int(frac*100)}%", anchor="e",
                           fill=t["bg"], font=self.font(9, "bold"))

    def _pulse(self, widget, keys, idx=0):
        if not self.alive:
            return
        try:
            widget.configure(fg=self.theme[keys[idx % len(keys)]])
        except tk.TclError:
            return
        self.after(420, lambda: self._pulse(widget, keys, idx + 1))

    # ======================================================================
    #   DESKTOP
    # ======================================================================

    def show_desktop(self):
        self._gen += 1
        self._on_desktop = True
        self._unbind_boot_skip()
        self.clear_overlay()
        t = self.theme
        root = tk.Frame(self.overlay, bg=t["bg"])
        root.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Top bar
        top = tk.Frame(root, bg=t["panel"], height=44)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)
        tk.Label(top, text="  ⬢ enyripter v3", font=self.font(13, "bold"),
                 bg=t["panel"], fg=t["accent"]).pack(side="left", padx=8)
        tk.Label(top, text="Fenster schliessen (✕) oder ESC = Beenden  ·  F11 = Vollbild",
                 font=self.font(9), bg=t["panel"], fg=t["muted"]).pack(side="left", padx=18)
        self.clock_var = tk.StringVar(value="")
        tk.Label(top, textvariable=self.clock_var, font=self.font(11),
                 bg=t["panel"], fg=t["accent2"]).pack(side="right", padx=16)
        tk.Label(top, text=f"@{self.username}", font=self.font(10),
                 bg=t["panel"], fg=t["muted"]).pack(side="right", padx=10)
        self._update_clock(self._gen)

        # Body
        body = tk.Frame(root, bg=t["bg"])
        body.pack(fill="both", expand=True)

        # Dock
        dock = tk.Frame(body, bg=t["panel"], width=210)
        dock.pack(side="left", fill="y")
        dock.pack_propagate(False)
        tk.Label(dock, text="APPS", font=self.font(11, "bold"),
                 bg=t["panel"], fg=t["muted"]).pack(pady=(16, 8))
        self.dock_buttons = {}
        for key, label in [("encrypt", "🔒  Encrypt"), ("decrypt", "🔓  Decrypt"),
                           ("files", "📁  Files"), ("generator", "🎲  Passwort"),
                           ("settings", "⚙  Settings"), ("about", "ⓘ  About")]:
            b = NeonButton(dock, self, label, lambda k=key: self._switch_app(k))
            b.pack(fill="x", padx=12, pady=4)
            b.configure(anchor="w")
            self.dock_buttons[key] = b
        NeonButton(dock, self, "⏻  Beenden", self.on_escape, kind="danger").pack(
            side="bottom", fill="x", padx=12, pady=14)

        # Center + Console
        center_wrap = tk.Frame(body, bg=t["bg"])
        center_wrap.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        center_wrap.columnconfigure(0, weight=3)
        center_wrap.columnconfigure(1, weight=2)
        center_wrap.rowconfigure(0, weight=1)

        self.app_panel = self._glass(center_wrap)
        self.app_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        console_panel = self._glass(center_wrap)
        console_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._build_console(console_panel)

        # Statusbar
        statusbar = tk.Frame(root, bg=t["panel"], height=26)
        statusbar.pack(fill="x", side="bottom")
        statusbar.pack_propagate(False)
        self.status_var = tk.StringVar(value="Bereit. ESC = Shutdown.")
        tk.Label(statusbar, textvariable=self.status_var, font=self.font(9),
                 bg=t["panel"], fg=t["muted"]).pack(side="left", padx=12)
        caps = core.capabilities()
        tk.Label(statusbar, text=f"core: {caps['default_kdf']} · cryptography={caps['cryptography']}",
                 font=self.font(9), bg=t["panel"], fg=t["muted"]).pack(side="right", padx=12)

        # App-Views
        self.views = {}
        for key, builder in [("encrypt", self._build_encrypt_view),
                             ("decrypt", self._build_decrypt_view),
                             ("files", self._build_files_view),
                             ("generator", self._build_generator_view),
                             ("settings", self._build_settings_view),
                             ("about", self._build_about_view)]:
            v = tk.Frame(self.app_panel, bg=t["panel"])
            builder(v)
            self.views[key] = v

        self._switch_app(self.active_app)

        # Einmalige Willkommens-Karte beim ersten Desktop (Onboarding, wirkt seriös)
        if self._show_welcome and not self._welcome_done:
            self.after(250, self._show_welcome_card)

    def _show_welcome_card(self):
        if self._welcome_done or not self.alive:
            return
        self._welcome_done = True
        t = self.theme
        backdrop = tk.Frame(self.overlay, bg=t["bg"])
        backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)
        card = tk.Frame(backdrop, bg=t["panel"], highlightthickness=2,
                        highlightbackground=t["accent"])
        card.place(relx=0.5, rely=0.5, anchor="center", width=560, height=420)
        tk.Label(card, text="👋  Willkommen bei enyripter", font=self.font(18, "bold"),
                 bg=t["panel"], fg=t["accent"]).pack(pady=(26, 8))
        text = (
            "Ein Werkzeug, um Texte und Dateien sicher zu verschlüsseln.\n\n"
            "So funktioniert es in 3 Schritten:\n\n"
            "  1.  VERSCHLÜSSELN:  Text eingeben, Passwort vergeben → ENCRYPT.\n"
            "       Die Ausgabe kannst du speichern oder verschicken.\n\n"
            "  2.  ENTSCHLÜSSELN:  Diese Ausgabe + dasselbe Passwort → DECRYPT.\n\n"
            "  3.  DATEIEN:  Ganze Dateien zu .eny verschlüsseln und zurück.\n\n"
            "Wichtig:  Dein Passwort ist der einzige Schlüssel — ohne genau dieses\n"
            "Passwort gibt es KEINE Wiederherstellung. Bewahre es gut auf."
        )
        tk.Label(card, text=text, font=self.font(10), bg=t["panel"], fg=t["text"],
                 justify="left").pack(padx=24, anchor="w")
        NeonButton(card, self, "Los geht's  →", backdrop.destroy, kind="primary").pack(pady=18)

    def _update_clock(self, gen):
        if not self.alive or gen != self._gen:
            return
        try:
            self.clock_var.set(datetime.now().strftime("%H:%M:%S"))
        except tk.TclError:
            return
        self.after(1000, lambda: self._update_clock(gen))

    def set_status(self, msg):
        try:
            self.status_var.set(msg)
        except (tk.TclError, AttributeError):
            pass
        self.console_log(msg)

    def _switch_app(self, key):
        self.active_app = key
        for v in self.views.values():
            v.pack_forget()
        self.views[key].pack(fill="both", expand=True)
        for k, b in self.dock_buttons.items():
            b.configure(fg=self.theme["accent"] if k == key else self.theme["text"])
        self._refresh_active_labels()

    def _active_summary(self):
        cnames = {core.CIPHER_CHACHA: "ChaCha20", core.CIPHER_AESGCM: "AES-256-GCM",
                  core.CIPHER_CASCADE: "Cascade"}
        enc = {"base64": "Base64", "hex": "Hex", "bitmorse": "Bit-Morse"}
        comp = "Kompression an" if self.compress else "Kompression aus"
        return (f"Aktiv: {cnames.get(self.cipher_id, '?')} · Stufe {self.level.capitalize()} · "
                f"{enc.get(self.encoding, self.encoding)} · {comp}")

    def _refresh_active_labels(self):
        txt = self._active_summary()
        for attr in ("enc_active", "files_active"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.configure(text=txt)
                except tk.TclError:
                    pass

    # ---------- Section header helper ----------

    def _section(self, parent, title, sub=""):
        t = self.theme
        head = tk.Frame(parent, bg=t["panel"])
        head.pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(head, text=title, font=self.font(15, "bold"),
                 bg=t["panel"], fg=t["accent"]).pack(side="left")
        if sub:
            self._sub_label = tk.Label(parent, text=sub, font=self.font(9), bg=t["panel"],
                                       fg=t["muted"], justify="left", wraplength=520)
            self._sub_label.pack(anchor="w", padx=16, pady=(0, 8))

    def _labeled_text(self, parent, label, height=5, fg=None):
        t = self.theme
        lbl = tk.Label(parent, text=label, font=self.font(10, "bold"),
                       bg=t["panel"], fg=t["text"])
        lbl.pack(anchor="w", padx=16, pady=(8, 2))
        txt = tk.Text(parent, height=height, wrap="word", bg=t["panel2"],
                      fg=fg or t["text"], insertbackground=t["accent"], bd=0,
                      font=self.font(10), highlightthickness=1,
                      highlightbackground=t["muted"], highlightcolor=t["accent"])
        txt.pack(fill="x", padx=16, pady=(0, 4))
        txt._label_widget = lbl  # damit Aufrufer die Beschriftung spaeter aendern koennen
        return txt

    def _password_row(self, parent, label="Passwort:", show_meter=True):
        """Passwortfeld mit Show/Hide (+ optionalem Staerke-Meter). Gibt die StringVar zurueck."""
        t = self.theme
        row = tk.Frame(parent, bg=t["panel"])
        row.pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(row, text=label, font=self.font(10, "bold"),
                 bg=t["panel"], fg=t["text"]).pack(side="left")
        var = tk.StringVar()
        show = {"on": False}
        entry = tk.Entry(row, textvariable=var, show="•", font=self.font(11),
                         bg=t["panel2"], fg=t["text"], insertbackground=t["accent"],
                         relief="flat", highlightthickness=1,
                         highlightbackground=t["muted"], highlightcolor=t["accent"])
        entry.pack(side="left", fill="x", expand=True, padx=8, ipady=5)

        def toggle():
            show["on"] = not show["on"]
            entry.configure(show="" if show["on"] else "•")
            eye.configure(text="🙈" if show["on"] else "👁")
        eye = tk.Label(row, text="👁", cursor="hand2", bg=t["panel"], fg=t["accent"],
                       font=self.font(12))
        eye.pack(side="left", padx=(0, 4))
        eye.bind("<Button-1>", lambda e: toggle())

        if not show_meter:
            return var

        meter = tk.Canvas(parent, height=10, bg=t["panel"], highlightthickness=0)
        meter.pack(fill="x", padx=16, pady=(4, 2))
        meter_lbl = tk.Label(parent, text="", font=self.font(9), bg=t["panel"], fg=t["muted"])
        meter_lbl.pack(anchor="w", padx=16)

        def update_meter(*_):
            if not meter.winfo_exists():
                return
            try:
                st = core.estimate_strength(var.get())
                meter.delete("all")
            except tk.TclError:
                return
            w = meter.winfo_width() or 400
            segs = 5
            gap = 4
            sw = (w - gap * (segs - 1)) / segs
            colors = [t["err"], t["err"], t["warn"], t["accent"], t["accent"]]
            for i in range(segs):
                on = i < st["score"]
                col = colors[min(st["score"], 4)] if on else t["panel2"]
                x0 = i * (sw + gap)
                meter.create_rectangle(x0, 0, x0 + sw, 10, fill=col, outline="")
            meter_lbl.configure(text=f"Passwort-Staerke: {st['label']}  (~{st['bits']} Bit)")
        var.trace_add("write", update_meter)
        parent.after(50, update_meter)
        return var

    def _keyfile_row(self, parent):
        """Optionale Keyfile-Auswahl. Gibt eine Funktion get_bytes() -> bytes|None zurueck."""
        t = self.theme
        state = {"path": None}
        row = tk.Frame(parent, bg=t["panel"])
        row.pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(row, text="Keyfile (optional):", font=self.font(10, "bold"),
                 bg=t["panel"], fg=t["text"]).pack(side="left")
        name = tk.Label(row, text="— keins —", font=self.font(9), bg=t["panel"], fg=t["muted"])

        def pick():
            p = filedialog.askopenfilename(title="Keyfile waehlen")
            if p:
                state["path"] = p
                name.configure(text=os.path.basename(p))

        def clear():
            state["path"] = None
            name.configure(text="— keins —")

        NeonButton(row, self, "📎 Datei", pick).pack(side="left", padx=8)
        NeonButton(row, self, "✕", clear).pack(side="left")
        name.pack(side="left", padx=8)
        tk.Label(parent, text="Zusatzschutz: dann wird zum Entschluesseln Passwort UND genau diese Datei gebraucht.",
                 font=self.font(8), bg=t["panel"], fg=t["muted"], wraplength=520,
                 justify="left").pack(anchor="w", padx=16)

        def get_bytes():
            if not state["path"]:
                return None
            try:
                with open(state["path"], "rb") as fh:
                    return fh.read()
            except OSError as exc:
                messagebox.showerror("Keyfile", f"Keyfile nicht lesbar:\n{exc}")
                return None
        return get_bytes

    # ---------- Encrypt view ----------

    def _build_encrypt_view(self, parent):
        t = self.theme
        self._section(parent, "VERSCHLÜSSELN",
                      "So gehts: Text eingeben, Passwort vergeben, ENCRYPT klicken. "
                      "Die Ausgabe kannst du speichern oder verschicken.")
        self.enc_active = tk.Label(parent, text="", font=self.font(9), bg=t["panel"], fg=t["accent2"])
        self.enc_active.pack(anchor="w", padx=16)
        self.enc_plain = self._labeled_text(parent, "Dein Text:", height=5)
        self.enc_pw = self._password_row(parent, "Passwort:")
        self.enc_keyfile = self._keyfile_row(parent)

        # Klare, freundliche Warnung VOR dem Verschluesseln (Passwort = einziger Schluessel)
        tk.Label(parent,
                 text="⚠ Merke dir das Passwort gut! Ohne genau dieses Passwort "
                      "lassen sich die Daten NICHT wiederherstellen — es gibt kein Zurücksetzen.",
                 font=self.font(9, "bold"), bg=t["panel"], fg=t["warn"],
                 wraplength=540, justify="left").pack(anchor="w", padx=16, pady=(6, 2))

        btnrow = tk.Frame(parent, bg=t["panel"])
        btnrow.pack(fill="x", padx=16, pady=8)
        NeonButton(btnrow, self, "⚡ ENCRYPT", self._on_encrypt, kind="primary").pack(side="left")
        NeonButton(btnrow, self, "📋 Kopieren", self._copy_cipher).pack(side="left", padx=8)
        NeonButton(btnrow, self, "🧹 Leeren", self._clear_encrypt).pack(side="left")

        self.enc_anim = tk.Canvas(parent, height=26, bg=t["panel2"], highlightthickness=0)
        self.enc_anim.pack(fill="x", padx=16, pady=(2, 4))

        self.enc_out = self._labeled_text(parent, "Verschlüsselte Ausgabe:", height=6, fg=t["accent"])

    def _clear_encrypt(self):
        self.enc_plain.delete("1.0", "end")
        self.enc_out.delete("1.0", "end")
        self.enc_anim.delete("all")
        self.set_status("Encrypt-Felder geleert.")

    def _on_encrypt(self):
        plaintext = self.enc_plain.get("1.0", "end").rstrip("\n")
        pw = self.enc_pw.get()
        if not plaintext:
            messagebox.showwarning("Hinweis", "Bitte Klartext eingeben.")
            return
        if not pw:
            messagebox.showwarning("Hinweis", "Bitte Passwort eingeben.")
            return
        if "enc" in self._busy:
            return
        kf = self.enc_keyfile()
        self._busy.add("enc")
        self.set_status(f"Verschluessle ({core.CIPHER_NAMES[self.cipher_id]}, level={self.level})...")
        self._run_async(
            lambda: core.encrypt_text(plaintext, pw, cipher_id=self.cipher_id,
                                      level=self.level, compress=self.compress,
                                      encoding=self.encoding, keyfile_bytes=kf),
            on_done=self._encrypt_done,
            anim_canvas=self.enc_anim,
        )

    def _encrypt_done(self, ok, result):
        self._busy.discard("enc")
        if not ok:
            self.set_status("Fehler bei der Verschluesselung.")
            messagebox.showerror("Fehler", str(result))
            return
        enc_names = {"base64": "Base64", "hex": "Hex", "bitmorse": "Bit-Morse"}
        try:
            self.enc_out._label_widget.configure(
                text=f"Verschlüsselte Ausgabe ({enc_names.get(self.encoding, self.encoding)}):")
        except (tk.TclError, AttributeError):
            pass
        self.enc_out.delete("1.0", "end")
        self.enc_out.insert("1.0", result)
        self._copy_text(result)
        plain_preview = self.enc_plain.get("1.0", "end").strip()
        self.enc_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "plain": (plain_preview[:30] + "…") if len(plain_preview) > 30 else plain_preview,
        })
        self.enc_history = self.enc_history[-12:]
        self._render_console_history()
        self.set_status("Fertig · Ausgabe kopiert. Passwort gut merken — sonst keine Wiederherstellung!")

    def _copy_cipher(self):
        txt = self.enc_out.get("1.0", "end").strip()
        if txt:
            self._copy_text(txt)
            self.set_status("Cipher kopiert.")

    # ---------- Decrypt view ----------

    def _build_decrypt_view(self, parent):
        t = self.theme
        self._section(parent, "ENTSCHLÜSSELN",
                      "Verschlüsselte Ausgabe einfügen, dasselbe Passwort eingeben, DECRYPT klicken. "
                      "Das Format (Base64/Hex/Bit-Morse) wird automatisch erkannt.")
        self.dec_in = self._labeled_text(parent, "Verschlüsselten Text hier einfügen:", height=6, fg=t["accent"])
        self.dec_meta = tk.Label(parent, text="", font=self.font(9), bg=t["panel"], fg=t["muted"])
        self.dec_meta.pack(anchor="w", padx=16)
        NeonButton(parent, self, "🔎 Info anzeigen", self._inspect_cipher).pack(anchor="w", padx=16, pady=2)
        self.dec_pw = self._password_row(parent, "Passwort:", show_meter=False)
        self.dec_keyfile = self._keyfile_row(parent)

        btnrow = tk.Frame(parent, bg=t["panel"])
        btnrow.pack(fill="x", padx=16, pady=8)
        NeonButton(btnrow, self, "⚡ DECRYPT", self._on_decrypt, kind="primary").pack(side="left")
        NeonButton(btnrow, self, "🧹 Leeren", self._clear_decrypt).pack(side="left", padx=8)

        self.dec_anim = tk.Canvas(parent, height=26, bg=t["panel2"], highlightthickness=0)
        self.dec_anim.pack(fill="x", padx=16, pady=(2, 4))
        self.dec_out = self._labeled_text(parent, "Dein Text (entschlüsselt):", height=6)

    def _clear_decrypt(self):
        self.dec_in.delete("1.0", "end")
        self.dec_out.delete("1.0", "end")
        self.dec_meta.configure(text="")
        self.dec_anim.delete("all")

    def _inspect_cipher(self):
        txt = self.dec_in.get("1.0", "end").strip()
        if not txt:
            return
        try:
            m = core.inspect(txt)
            self.dec_meta.configure(
                text=f"Verfahren={m['cipher']} · Schlüsselableitung={m['kdf']} · "
                     f"komprimiert={'ja' if m['compressed'] else 'nein'} · {m['ciphertext_len']} Byte")
        except core.EnyError as e:
            self.dec_meta.configure(text=f"Ungültige/unleserliche Eingabe: {e}")

    def _on_decrypt(self):
        txt = self.dec_in.get("1.0", "end").strip()
        pw = self.dec_pw.get()
        if not txt:
            messagebox.showwarning("Hinweis", "Bitte verschlüsselten Text einfügen.")
            return
        if not pw:
            messagebox.showwarning("Hinweis", "Bitte Passwort eingeben.")
            return
        if "dec" in self._busy:
            return
        kf = self.dec_keyfile()
        self._busy.add("dec")
        self.set_status("Entschlüsseln & Echtheit prüfen ...")
        self._run_async(
            lambda: core.decrypt_text(txt, pw, keyfile_bytes=kf),
            on_done=self._decrypt_done,
            anim_canvas=self.dec_anim,
        )

    def _decrypt_done(self, ok, result):
        self._busy.discard("dec")
        if not ok:
            self.set_status("Entschlüsselung fehlgeschlagen.")
            self.dec_out.delete("1.0", "end")
            messagebox.showerror(
                "Entschlüsselung fehlgeschlagen",
                f"{result}\n\nMögliche Ursachen:\n"
                "• Passwort stimmt nicht exakt\n"
                "• Es wurde beim Verschlüsseln ein Keyfile verwendet (dann hier dasselbe wählen)\n"
                "• Der Text wurde verändert/beschädigt")
            return
        self.dec_out.delete("1.0", "end")
        self.dec_out.insert("1.0", result)
        self.set_status("Entschlüsselung erfolgreich · Echtheit bestätigt.")

    # ---------- Files view ----------

    def _build_files_view(self, parent):
        t = self.theme
        self._section(parent, "DATEIEN",
                      "Beliebige Dateien ver- und entschlüsseln. Verschlüsselte Dateien enden auf .eny.")
        self.files_active = tk.Label(parent, text="", font=self.font(9), bg=t["panel"], fg=t["accent2"])
        self.files_active.pack(anchor="w", padx=16)
        self.file_pw = self._password_row(parent, "Passwort:")
        self.file_keyfile = self._keyfile_row(parent)
        info = ("• Verschlüsseln: Datei wählen → es entsteht <name>.eny\n"
                "• Entschlüsseln: .eny-Datei wählen → Original wird wiederhergestellt\n"
                "• Eine vorhandene Zieldatei wird nie ohne Rückfrage überschrieben")
        tk.Label(parent, text=info, font=self.font(10), bg=t["panel"], fg=t["muted"],
                 justify="left").pack(anchor="w", padx=16, pady=10)
        tk.Label(parent,
                 text="⚠ Ohne dasselbe Passwort (und ggf. Keyfile) ist eine .eny-Datei nicht wiederherstellbar.",
                 font=self.font(9, "bold"), bg=t["panel"], fg=t["warn"],
                 wraplength=540, justify="left").pack(anchor="w", padx=16, pady=(0, 6))
        row = tk.Frame(parent, bg=t["panel"])
        row.pack(anchor="w", padx=16, pady=8)
        NeonButton(row, self, "🔒 Datei verschlüsseln", self._encrypt_file, kind="primary").pack(side="left")
        NeonButton(row, self, "🔓 Datei entschlüsseln", self._decrypt_file).pack(side="left", padx=8)
        self.file_status = tk.Label(parent, text="", font=self.font(10), bg=t["panel"],
                                    fg=t["accent"], justify="left", wraplength=600)
        self.file_status.pack(anchor="w", padx=16, pady=10)

    def _encrypt_file(self):
        pw = self.file_pw.get()
        if not pw:
            messagebox.showwarning("Hinweis", "Bitte Passwort eingeben.")
            return
        path = filedialog.askopenfilename(title="Datei zum Verschluesseln")
        if not path:
            return
        out = path + core.ENY_FILE_SUFFIX
        overwrite = False
        if os.path.exists(out):
            if not messagebox.askyesno("Ueberschreiben?", f"{out}\nexistiert bereits. Ueberschreiben?"):
                return
            overwrite = True
        kf = self.file_keyfile()
        self.set_status("Verschlüssle Datei ...")

        def task():
            return core.encrypt_file(path, out, pw, cipher_id=self.cipher_id,
                                     level=self.level, compress=self.compress,
                                     overwrite=overwrite, keyfile_bytes=kf)

        def done(ok, res):
            if ok:
                self.file_status.configure(text=f"✓ Verschlüsselt → {res}\n"
                                                 "Passwort gut merken — sonst keine Wiederherstellung!")
                self.set_status("Datei verschlüsselt.")
            else:
                self.file_status.configure(text=f"✗ Fehler: {res}")
                messagebox.showerror("Fehler", str(res))
        self._run_async(task, on_done=done)

    def _decrypt_file(self):
        pw = self.file_pw.get()
        if not pw:
            messagebox.showwarning("Hinweis", "Bitte Passwort eingeben.")
            return
        path = filedialog.askopenfilename(title="Datei zum Entschluesseln",
                                          filetypes=[("ENY", "*.eny"), ("Alle", "*.*")])
        if not path:
            return
        out = None
        overwrite = False
        if path.endswith(".eny"):
            suggested = path[:-4]
            out = filedialog.asksaveasfilename(title="Ziel waehlen",
                                               initialfile=os.path.basename(suggested))
            if not out:
                return
            # Nutzer hat das Ziel im Dialog bestaetigt -> Ueberschreiben erlaubt
            overwrite = True
        kf = self.file_keyfile()
        self.set_status("Entschlüssle Datei ...")

        def task():
            return core.decrypt_file(path, out, pw, overwrite=overwrite, keyfile_bytes=kf)

        def done(ok, res):
            if ok:
                self.file_status.configure(text=f"✓ Entschlüsselt → {res}")
                self.set_status("Datei entschlüsselt.")
            else:
                self.file_status.configure(
                    text=f"✗ Fehler: {res}\n(Passwort exakt? Wurde ein Keyfile verwendet?)")
                messagebox.showerror("Fehler", str(res))
        self._run_async(task, on_done=done)

    # ---------- Generator view ----------

    def _build_generator_view(self, parent):
        t = self.theme
        self._section(parent, "PASSWORT-GENERATOR", "Kryptographisch sichere Zufallspasswoerter")
        row = tk.Frame(parent, bg=t["panel"])
        row.pack(anchor="w", padx=16, pady=8)
        tk.Label(row, text="Laenge:", font=self.font(10, "bold"), bg=t["panel"],
                 fg=t["text"]).pack(side="left")
        self.gen_len = tk.IntVar(value=24)
        tk.Scale(row, from_=8, to=64, orient="horizontal", variable=self.gen_len,
                 bg=t["panel"], fg=t["accent"], troughcolor=t["panel2"], highlightthickness=0,
                 length=240, font=self.font(8)).pack(side="left", padx=8)
        self.gen_sym = tk.BooleanVar(value=True)
        tk.Checkbutton(parent, text="Sonderzeichen verwenden", variable=self.gen_sym,
                       font=self.font(10), bg=t["panel"], fg=t["text"], selectcolor=t["panel2"],
                       activebackground=t["panel"], activeforeground=t["accent"]).pack(anchor="w", padx=16)
        NeonButton(parent, self, "🎲 Generieren", self._generate, kind="primary").pack(anchor="w", padx=16, pady=10)
        self.gen_out = tk.Entry(parent, font=self.font(15, "bold"), bg=t["panel2"], fg=t["accent"],
                                insertbackground=t["accent"], relief="flat", justify="center")
        self.gen_out.pack(fill="x", padx=16, ipady=8)
        self.gen_meter = tk.Label(parent, text="", font=self.font(10), bg=t["panel"], fg=t["muted"])
        self.gen_meter.pack(anchor="w", padx=16, pady=6)
        NeonButton(parent, self, "📋 Copy", self._copy_generated).pack(anchor="w", padx=16)

    def _generate(self):
        pw = core.generate_password(self.gen_len.get(), use_symbols=self.gen_sym.get())
        self.gen_out.delete(0, "end")
        self.gen_out.insert(0, pw)
        st = core.estimate_strength(pw)
        self.gen_meter.configure(text=f"Staerke: {st['label']} (~{st['bits']} Bit)")
        self.set_status("Passwort generiert.")

    def _copy_generated(self):
        pw = self.gen_out.get().strip()
        if pw:
            self._copy_text(pw)
            self.set_status("Passwort kopiert.")

    # ---------- Settings view ----------

    def _build_settings_view(self, parent):
        t = self.theme
        self._section(parent, "EINSTELLUNGEN", "Standardwerte sind für die meisten gut — Ändern ist optional.")

        outer = tk.Frame(parent, bg=t["panel"])
        outer.pack(fill="both", expand=True)

        def chooser(label, options, getter, setter, help_text=""):
            tk.Label(outer, text=label, font=self.font(10, "bold"), bg=t["panel"],
                     fg=t["text"]).pack(anchor="w", padx=16, pady=(10, 2))
            rowf = tk.Frame(outer, bg=t["panel"])
            rowf.pack(anchor="w", padx=16)
            btns = {}
            def mk(opt_key, opt_label):
                def click():
                    setter(opt_key)
                    for k, b in btns.items():
                        b.configure(fg=t["accent"] if k == getter() else t["text"])
                    self.set_status(f"{label} → {opt_label}")
                b = NeonButton(rowf, self, opt_label, click)
                b.pack(side="left", padx=4, pady=2)
                if opt_key == getter():
                    b.configure(fg=t["accent"])
                return b
            for k, lbl in options:
                btns[k] = mk(k, lbl)
            if help_text:
                tk.Label(outer, text=help_text, font=self.font(8), bg=t["panel"], fg=t["muted"],
                         wraplength=560, justify="left").pack(anchor="w", padx=16, pady=(2, 0))

        chooser("Verfahren (Cipher)",
                [(core.CIPHER_CHACHA, "ChaCha20"), (core.CIPHER_AESGCM, "AES-256-GCM"),
                 (core.CIPHER_CASCADE, "Cascade (max)")],
                lambda: self.cipher_id, self._set_cipher,
                "ChaCha20 = schnell & sehr sicher (Standard). AES-256-GCM = bewährte Alternative. "
                "Cascade = beide übereinander (maximal, aber langsamer).")
        chooser("Sicherheitsstufe",
                [("fast", "Fast"), ("strong", "Strong"), ("paranoid", "Paranoid")],
                lambda: self.level, self._set_level,
                "Höher = stärker gegen Passwort-Rateangriffe, aber langsamer "
                "(Paranoid ~1 Sekunde+ pro Vorgang, mehr bei großen Dateien).")
        chooser("Darstellung der Ausgabe (Encoding)",
                [("base64", "Base64 (empfohlen)"), ("hex", "Hex"), ("bitmorse", "Bit-Morse")],
                lambda: self.encoding, self._set_encoding,
                "Betrifft nur das AUSSEHEN der verschlüsselten Ausgabe. Beim Entschlüsseln wird "
                "das Format automatisch erkannt — die Einstellung ist dann egal.")
        chooser("Schriftgröße",
                [(0.9, "Klein"), (1.0, "Normal"), (1.2, "Groß"), (1.4, "Sehr groß")],
                lambda: self.font_scale, self._set_font_scale,
                "Vergrößert die gesamte Oberfläche (lädt den Desktop kurz neu).")
        chooser("Theme",
                [(k, k.capitalize()) for k in THEMES],
                lambda: self.theme_name, self._set_theme,
                "Nur Optik. Theme-Wechsel lädt den Desktop kurz neu.")

        self.compress_var = tk.BooleanVar(value=self.compress)
        tk.Checkbutton(outer, text="Vor dem Verschlüsseln komprimieren (zlib) — meist sinnvoll",
                       variable=self.compress_var, command=self._toggle_compress,
                       font=self.font(10), bg=t["panel"], fg=t["text"], selectcolor=t["panel2"],
                       activebackground=t["panel"], activeforeground=t["accent"]).pack(
            anchor="w", padx=16, pady=(14, 4))

        self.anim_var = tk.BooleanVar(value=self.animations)
        tk.Checkbutton(outer, text="Animierter Matrix-Hintergrund (aus = ruhiger Modus)",
                       variable=self.anim_var, command=self._toggle_animations,
                       font=self.font(10), bg=t["panel"], fg=t["text"], selectcolor=t["panel2"],
                       activebackground=t["panel"], activeforeground=t["accent"]).pack(
            anchor="w", padx=16, pady=(2, 8))

    def _toggle_animations(self):
        self.animations = self.anim_var.get()
        if self.rain:
            self.rain.set_enabled(self.animations)

    def _set_cipher(self, c):
        self.cipher_id = c
        self._refresh_active_labels()

    def _set_level(self, l):
        self.level = l
        self._refresh_active_labels()

    def _set_encoding(self, e):
        self.encoding = e
        self._refresh_active_labels()

    def _toggle_compress(self):
        self.compress = self.compress_var.get()
        self._refresh_active_labels()

    def _set_font_scale(self, scale):
        try:
            new = float(scale)
        except (TypeError, ValueError):
            return
        if abs(new - self.font_scale) < 1e-6:
            return
        self.font_scale = new
        self.show_desktop()  # mit neuer Schriftgröße neu aufbauen
        self._switch_app("settings")

    def _set_theme(self, name):
        if name in THEMES and name != self.theme_name:
            self.theme_name = name
            self.theme = THEMES[name]
            self.bg_canvas.configure(bg=self.theme["bg"])
            self.overlay.configure(bg=self.theme["bg"])
            self.show_desktop()

    # ---------- About view ----------

    def _build_about_view(self, parent):
        t = self.theme
        self._section(parent, "INFO & SCHNELLSTART", "enyripter v3")
        caps = core.capabilities()
        quick = (
            "In 3 Schritten:\n"
            "  1) VERSCHLÜSSELN: Text + Passwort eingeben → ENCRYPT. Ausgabe speichern/verschicken.\n"
            "  2) ENTSCHLÜSSELN: dieselbe Ausgabe + dasselbe Passwort → DECRYPT.\n"
            "  3) DATEIEN: ganze Dateien zu .eny verschlüsseln und zurück.\n\n"
            "Wichtig: Dein PASSWORT ist der einzige Schlüssel. Ohne genau dieses Passwort\n"
            "gibt es KEINE Wiederherstellung — es gibt absichtlich keine Hintertür.\n\n"
            "Technik (für Neugierige):\n"
            "  • Verfahren: ChaCha20-Poly1305 / AES-256-GCM / Cascade\n"
            "  • Schlüsselableitung: Argon2id (falls installiert) / scrypt / PBKDF2\n"
            "  • Schutz: Salt + Nonce + Echtheits-Prüfung (Manipulation wird erkannt)\n"
            "  • Format: ENY3 (siehe README) — auch von einem 'Gegenprogramm' lesbar,\n"
            "    das das Format kennt UND das Passwort hat.\n"
            "  • 'SHA-2048' gibt es nicht — SHA ist ein nicht umkehrbarer Hash; hier wird\n"
            "    echte Verschlüsselung genutzt. Die Stärke kommt aus dem Passwort.\n\n"
            f"System: cryptography={caps['cryptography']} · argon2={caps['argon2']} · KDF={caps['default_kdf']}\n"
            "Beenden: ✕, ESC oder der Beenden-Knopf  ·  Vollbild: F11"
        )
        lbl = tk.Label(parent, text=quick, font=self.font(11), bg=t["panel"], fg=t["text"],
                       justify="left", anchor="nw", wraplength=560)
        lbl.pack(fill="both", expand=True, padx=16, pady=10)
        # Umbruch dynamisch an Panelbreite koppeln -> kein Abschneiden bei kleinem Fenster
        lbl.bind("<Configure>", lambda e: lbl.configure(wraplength=max(280, e.width - 16)))

    # ======================================================================
    #   Konsole
    # ======================================================================

    def _build_console(self, parent):
        t = self.theme
        tk.Label(parent, text="SYSTEM CONSOLE", font=self.font(12, "bold"),
                 bg=t["panel"], fg=t["accent"]).pack(anchor="w", padx=12, pady=(10, 0))
        tk.Label(parent, text="help · sysinfo · whoami · history · selftest · caps · clear",
                 font=self.font(9), bg=t["panel"], fg=t["muted"]).pack(anchor="w", padx=12, pady=(0, 4))
        self.console = tk.Text(parent, bg=t["panel2"], fg=t["text"], bd=0, font=self.font(9),
                               wrap="word", insertbackground=t["accent"], highlightthickness=0)
        self.console.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.console.insert("end", "[SYSTEM] ENCRYPT-OS Konsole bereit. 'help' fuer Befehle.\n\n")
        self.console.configure(state="disabled")

        cmd = tk.Frame(parent, bg=t["panel"])
        cmd.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(cmd, text=">", font=self.font(11, "bold"), bg=t["panel"], fg=t["accent"]).pack(side="left")
        self.cmd_entry = tk.Entry(cmd, font=self.font(10), bg=t["panel2"], fg=t["text"],
                                  insertbackground=t["accent"], relief="flat")
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=3)
        self.cmd_entry.bind("<Return>", self._console_cmd)

    def console_log(self, msg):
        try:
            self.console.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.console.insert("end", f"[{ts}] {msg}\n")
            lines = int(self.console.index("end-1c").split(".")[0])
            if lines > 800:
                self.console.delete("1.0", f"{lines-800}.0")
            self.console.see("end")
            self.console.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass

    def _console_print(self, text):
        self.console.configure(state="normal")
        self.console.insert("end", text + "\n")
        self.console.see("end")
        self.console.configure(state="disabled")

    def _render_console_history(self):
        pass  # History wird ueber Konsole/Status sichtbar gemacht

    def _console_cmd(self, _=None):
        cmd = self.cmd_entry.get().strip()
        self.cmd_entry.delete(0, "end")
        if not cmd:
            return
        self._console_print(f"> {cmd}")
        base = cmd.split()[0].lower()
        caps = core.capabilities()
        if base == "help":
            self._console_print("Befehle: help, sysinfo, whoami, caps, history, selftest, clear, theme <name>")
        elif base == "sysinfo":
            self._console_print(f"cipher={core.CIPHER_NAMES[self.cipher_id]} level={self.level} "
                                f"encoding={self.encoding} compress={self.compress}")
        elif base == "whoami":
            self._console_print(f"operator: {self.username}")
        elif base == "caps":
            self._console_print(str(caps))
        elif base == "history":
            if not self.enc_history:
                self._console_print("(keine Eintraege)")
            for h in self.enc_history:
                self._console_print(f"  [{h['time']}] {h['plain']}")
        elif base == "selftest":
            self._console_print("Self-Test laeuft im Hintergrund...")
            self._run_async(lambda: core.self_test(verbose=False),
                            on_done=lambda ok, res: self._console_print(
                                "Self-Test: " + ("ALLE TESTS OK" if (ok and res) else "FEHLER")))
        elif base == "theme":
            parts = cmd.split()
            if len(parts) > 1 and parts[1] in THEMES:
                self._set_theme(parts[1])
            else:
                self._console_print(f"Themes: {', '.join(THEMES)}")
        elif base == "clear":
            self.console.configure(state="normal")
            self.console.delete("1.0", "end")
            self.console.configure(state="disabled")
        else:
            self._console_print(f"Unbekannter Befehl: {base}")

    # ======================================================================
    #   Async-Runner + Verschluesselungs-Animation
    # ======================================================================

    def _run_async(self, task, on_done, anim_canvas=None):
        """Fuehrt task() im Thread aus, animiert optional, ruft on_done(ok, result) im UI-Thread.

        Zwei Schutzmechanismen:
          * gen (Screen-Generation): nach Theme-Reload/Shutdown wird das Ergebnis verworfen,
            statt es in einen neu aufgebauten View zu schreiben.
          * stream_gen (pro Canvas): ein neuer Lauf invalidiert die alte Animations-Kette,
            sodass sich ueberlappende Laeufe nicht gegenseitig stoeren.
        """
        gen = self._gen
        result_box = {}

        def worker():
            try:
                result_box["res"] = task()
                result_box["ok"] = True
            except Exception as exc:  # noqa: BLE001
                result_box["ok"] = False
                result_box["res"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        stream_gen = None
        if anim_canvas is not None:
            stream_gen = getattr(anim_canvas, "_stream_gen", 0) + 1
            anim_canvas._stream_gen = stream_gen
            self._bit_stream(anim_canvas, 0, stream_gen)
        self._poll_thread(thread, result_box, on_done, anim_canvas, gen, stream_gen)

    def _poll_thread(self, thread, result_box, on_done, anim_canvas, gen, stream_gen):
        if not self.alive or gen != self._gen:
            return  # Screen gewechselt -> Ergebnis dieser Generation verwerfen
        if thread.is_alive():
            self.after(40, lambda: self._poll_thread(thread, result_box, on_done,
                                                     anim_canvas, gen, stream_gen))
            return
        if anim_canvas is not None:
            self._finish_bit_stream(anim_canvas, result_box.get("ok", False), stream_gen)
        on_done(result_box.get("ok", False), result_box.get("res"))

    def _bit_stream(self, canvas, offset, stream_gen):
        """Animierter Bit-/Glyph-Strom, solange Verschluesselung laeuft."""
        if not self.alive or not canvas.winfo_exists():
            return
        if getattr(canvas, "_stream_gen", None) != stream_gen:
            return  # ein neuer Lauf hat uebernommen
        try:
            canvas.delete("all")
        except tk.TclError:
            return
        t = self.theme
        w = canvas.winfo_width() or 400
        h = int(canvas["height"])
        step = 12
        for i, x in enumerate(range(-step, w + step, step)):
            xx = x + (offset % step)
            ch = random.choice("01")
            col = t["accent"] if (i + offset // step) % 2 == 0 else t["accent2"]
            canvas.create_text(xx, h // 2, text=ch, fill=col, font=(FONT_MONO, 11, "bold"))
        canvas.create_text(w // 2, h // 2, text=" ⟳ ENCRYPTING ", fill=t["bg"],
                           font=(FONT_MONO, 11, "bold"))
        canvas.after(55, lambda: self._bit_stream(canvas, offset + 3, stream_gen))

    def _finish_bit_stream(self, canvas, ok, stream_gen):
        if getattr(canvas, "_stream_gen", None) != stream_gen:
            return
        if not canvas.winfo_exists():
            return
        try:
            canvas.delete("all")
        except tk.TclError:
            return
        t = self.theme
        w = canvas.winfo_width() or 400
        h = int(canvas["height"])
        msg = "✓ DONE" if ok else "✗ FAILED"
        col = t["accent"] if ok else t["err"]
        canvas.create_rectangle(0, 0, w, h, fill=t["panel2"], outline="")
        canvas.create_text(w // 2, h // 2, text=msg, fill=col, font=(FONT_MONO, 12, "bold"))

    # ======================================================================
    #   Clipboard
    # ======================================================================

    def _copy_text(self, text):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()  # damit der Inhalt nach Programmende verfuegbar bleibt
            return True
        except tk.TclError:
            return False

    # ======================================================================
    #   Shutdown
    # ======================================================================

    def on_escape(self):
        # ESC im Vollbild = nur Vollbild verlassen (nicht beenden!) - sonst wirkt es
        # wie ein Lockscreen-Schreck und man kommt scheinbar nicht mehr raus.
        if self.is_fullscreen:
            try:
                self.attributes("-fullscreen", False)
                self.is_fullscreen = False
            except Exception:
                pass
            return
        if not self.alive:
            return
        self.alive = False
        self._gen += 1
        if self.rain:
            self.rain.stop()
        self.clear_overlay()
        t = self.theme
        frame = tk.Frame(self.overlay, bg=t["bg"])
        frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.6, relheight=0.4)
        # Ruhige, deutsche Formulierung + Akzentfarbe (nicht Alarm-Rot) -> wirkt nicht wie ein Wiper.
        tk.Label(frame, text="enyripter wird beendet", font=self.font(20, "bold"),
                 bg=t["bg"], fg=t["accent"]).pack(pady=(20, 10))
        self._sd_label = tk.Label(frame, text="", font=self.font(11), bg=t["bg"], fg=t["muted"])
        self._sd_label.pack(pady=10)
        self._sd_bar = tk.Canvas(frame, height=14, bg=t["bg"], highlightthickness=0)
        self._sd_bar.pack(fill="x", padx=40, pady=10)
        steps = ["Sitzung wird geschlossen ...", "Schluessel im Speicher verwerfen ...",
                 "Aufraeumen ...", "Tschuess!"]
        self._shutdown_run(steps, 0)

    def _shutdown_run(self, steps, i):
        if i >= len(steps):
            self.after(250, self.destroy)
            return
        try:
            self._sd_label.configure(text=steps[i])
            c = self._sd_bar
            c.delete("all")
            w = c.winfo_width() or 500
            frac = (i + 1) / len(steps)
            c.create_rectangle(0, 0, w, 14, fill=self.theme["panel"], outline=self.theme["panel2"])
            c.create_rectangle(0, 1, int(w * frac), 13, fill=self.theme["accent"], outline="")
        except tk.TclError:
            return
        self.after(220, lambda: self._shutdown_run(steps, i + 1))


def run():
    if not core.HAVE_CRYPTOGRAPHY:
        try:
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("Fehlende Bibliothek",
                                 "Die Bibliothek 'cryptography' fehlt.\n\npip install cryptography")
            root.destroy()
        except Exception:
            print("FEHLER: 'cryptography' fehlt. -> pip install cryptography")
        return
    app = EncryptOS()
    app.mainloop()


if __name__ == "__main__":
    run()
