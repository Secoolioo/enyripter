# -*- coding: utf-8 -*-
"""
enyripter v3  ·  Launcher
=========================

Ein Einstieg, zwei Welten:

    python enyrpter3.py            ->  animierte Modus-Auswahl (GUI / Terminal)
    python enyrpter3.py --gui      ->  direkt ins animierte ENCRYPT-OS (GUI)
    python enyrpter3.py --cli      ->  direkt ins Hacker-Terminal
    python enyrpter3.py --selftest ->  nur den Krypto-Self-Test laufen lassen
    python enyrpter3.py --version  ->  Versionsinfo

Die eigentliche Verschluesselung steckt in eny_core.py (echte AEAD-Krypto).
GUI: eny_gui.py   ·   Terminal: eny_cli.py
"""

from __future__ import annotations

import argparse
import os
import sys

VERSION = "3.0"


def _safe_print(*a):
    """print(), das unter pythonw (sys.stdout is None) nicht crasht."""
    try:
        print(*a)
    except Exception:
        pass


# ==========================================================================
#   Animierte Modus-Auswahl (Tkinter)
# ==========================================================================

def choose_mode_gui():
    """
    Zeigt ein animiertes Auswahlfenster.
    Rueckgabe: "gui", "cli" oder None (abgebrochen).
    """
    try:
        import tkinter as tk
    except Exception:
        return None

    import random

    BG = "#01040a"
    PANEL = "#070d16"
    ACCENT = "#27f08a"
    ACCENT2 = "#00e5ff"
    TEXT = "#d7ffe9"
    MUTED = "#5b7a6b"
    FONT = "Consolas"

    result = {"mode": None}
    root = tk.Tk()
    root.title("enyripter v3 · Modus waehlen")
    root.configure(bg=BG)
    W, H = 760, 500
    try:
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
    except Exception:
        root.geometry(f"{W}x{H}")
    root.resizable(False, False)

    canvas = tk.Canvas(root, bg=BG, highlightthickness=0, width=W, height=H)
    canvas.place(x=0, y=0, relwidth=1, relheight=1)

    # --- Mini Matrix-Rain ---
    state = {"alive": True}
    cols = []
    col_w, row_h = 16, 18
    glyphs = "01ｱｲｳｴｵｶｷｸ#%&*<>=+-/$ABCDEF0123456789"
    for i in range(W // col_w):
        cols.append({"x": i * col_w + 4, "head": random.randint(-30, 0),
                     "len": random.randint(5, 16), "items": [], "speed": random.choice([1, 1, 2])})

    def rain():
        if not state["alive"]:
            return
        for c in cols:
            c["head"] += c["speed"]
            y = c["head"] * row_h
            it = canvas.create_text(c["x"], y, text=random.choice(glyphs), fill=ACCENT,
                                    font=(FONT, 11, "bold"), anchor="n", tags="rain")
            c["items"].append(it)
            if len(c["items"]) > c["len"]:
                canvas.delete(c["items"].pop(0))
            if len(c["items"]) >= 2:
                canvas.itemconfigure(c["items"][-2], fill="#0f7a44")
            if y > H + row_h:
                for o in c["items"]:
                    canvas.delete(o)
                c["items"] = []
                c["head"] = random.randint(-15, 0)
        canvas.tag_lower("rain")
        canvas.after(70, rain)

    # --- Inhalt (oben drueber) ---
    overlay = tk.Frame(root, bg=BG)
    overlay.place(relx=0.5, rely=0.5, anchor="center")

    title = tk.Label(overlay, text="e n y r i p t e r   v3", font=(FONT, 30, "bold"),
                     bg=BG, fg=ACCENT)
    title.pack(pady=(0, 2))
    tk.Label(overlay, text="ECHTE VERSCHLUESSELUNG · ChaCha20 · AES-256 · Argon2/scrypt",
             font=(FONT, 10), bg=BG, fg=ACCENT2).pack()
    tk.Label(overlay, text="Wie moechtest du starten?", font=(FONT, 12),
             bg=BG, fg=MUTED).pack(pady=(18, 14))

    btn_row = tk.Frame(overlay, bg=BG)
    btn_row.pack()

    def make_card(parent, icon, head, desc, mode):
        card = tk.Frame(parent, bg=PANEL, highlightthickness=2, highlightbackground=PANEL,
                        highlightcolor=ACCENT, cursor="hand2", width=300, height=170)
        card.pack_propagate(False)
        tk.Label(card, text=icon, font=(FONT, 34, "bold"), bg=PANEL, fg=ACCENT).pack(pady=(18, 2))
        tk.Label(card, text=head, font=(FONT, 15, "bold"), bg=PANEL, fg=TEXT).pack()
        tk.Label(card, text=desc, font=(FONT, 9), bg=PANEL, fg=MUTED, wraplength=260,
                 justify="center").pack(pady=(6, 0))

        def enter(_=None):
            card.configure(highlightbackground=ACCENT, bg="#0b1320")
            for w in card.winfo_children():
                w.configure(bg="#0b1320")

        def leave(_=None):
            card.configure(highlightbackground=PANEL, bg=PANEL)
            for w in card.winfo_children():
                w.configure(bg=PANEL)

        def click(_=None):
            result["mode"] = mode
            state["alive"] = False
            root.destroy()

        for wdg in [card] + list(card.winfo_children()):
            wdg.bind("<Enter>", enter)
            wdg.bind("<Leave>", leave)
            wdg.bind("<Button-1>", click)
        return card

    make_card(btn_row, "🖥", "GUI MODE",
              "Animiertes ENCRYPT-OS mit Matrix-Rain, Themes & Live-Konsole. [G]",
              "gui").pack(side="left", padx=12)
    make_card(btn_row, "⌨", "TERMINAL MODE",
              "OP-Style Hacker-Terminal direkt in der Konsole. [T]",
              "cli").pack(side="left", padx=12)

    tk.Label(overlay, text="G = GUI   ·   T = Terminal   ·   ESC = Abbrechen",
             font=(FONT, 9), bg=BG, fg=MUTED).pack(pady=(20, 0))

    def pick(mode):
        result["mode"] = mode
        state["alive"] = False
        root.destroy()

    root.bind("<g>", lambda e: pick("gui"))
    root.bind("<G>", lambda e: pick("gui"))
    root.bind("<t>", lambda e: pick("cli"))
    root.bind("<T>", lambda e: pick("cli"))
    root.bind("<Return>", lambda e: pick("gui"))
    root.bind("<Escape>", lambda e: (state.update(alive=False), root.destroy()))
    root.protocol("WM_DELETE_WINDOW", lambda: (state.update(alive=False), root.destroy()))

    # Fade-in
    try:
        root.attributes("-alpha", 0.0)

        def fade(a=0.0):
            if a < 1.0 and state["alive"]:
                root.attributes("-alpha", a)
                root.after(20, lambda: fade(a + 0.08))
            else:
                try:
                    root.attributes("-alpha", 1.0)
                except Exception:
                    pass
        fade()
    except Exception:
        pass

    rain()
    root.mainloop()
    return result["mode"]


def choose_mode_console():
    """Konsolen-Fallback fuer die Modus-Auswahl (falls kein Tk verfuegbar)."""
    print("=" * 50)
    print(" enyripter v3 — Modus waehlen")
    print("=" * 50)
    print("  [1] GUI   (animiertes ENCRYPT-OS)")
    print("  [2] Terminal (Hacker-Konsole)")
    print("  [0] Abbrechen")
    while True:
        try:
            choice = input("Auswahl: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if choice == "1":
            return "gui"
        if choice == "2":
            return "cli"
        if choice == "0":
            return None
        print("Ungueltige Auswahl - bitte 1, 2 oder 0 eingeben.")


# ==========================================================================
#   Start
# ==========================================================================

def _has_console():
    """True, wenn ein nutzbares Terminal vorhanden ist (unter pythonw: nein)."""
    if sys.stdout is None:
        return False
    try:
        sys.stdout.fileno()
        return True
    except Exception:
        return False


def _python_console_exe():
    """Pfad zu python.exe (mit Konsole), auch wenn wir gerade unter pythonw.exe laufen."""
    exe = sys.executable or ""
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[: -len("pythonw.exe")] + "python.exe"
        if os.path.exists(cand):
            return cand
    if exe and not exe.lower().endswith("pythonw.exe"):
        return exe
    import shutil
    return shutil.which("python") or shutil.which("py") or "python"


def _show_error(msg):
    """Fehler anzeigen: per Konsole, sonst (pythonw) als Tk-Messagebox."""
    if _has_console():
        _safe_print(msg)
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("enyripter", msg)
        r.destroy()
    except Exception:
        pass


def _spawn_cli_console():
    """Oeffnet ein NEUES Konsolenfenster und startet darin den Terminal-Modus."""
    import subprocess
    base = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(base, "eny_cli.py")
    py = _python_console_exe()
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    # Markieren, damit das Fenster bei Ende/Fehler offen bleibt (eny_cli pausiert dann).
    env = dict(os.environ)
    env["ENY_SPAWNED_CONSOLE"] = "1"
    try:
        subprocess.Popen([py, script], cwd=base, creationflags=flags, env=env)
        return True
    except Exception as exc:
        _show_error(
            "Konnte kein Terminalfenster oeffnen:\n"
            f"{exc}\n\n"
            "Bitte stattdessen den GUI-Modus nutzen oder Python neu installieren."
        )
        return False


def launch(mode):
    if mode == "gui":
        import eny_gui
        eny_gui.run()
    elif mode == "cli":
        if _has_console():
            import eny_cli
            eny_cli.run()
        else:
            # Per Doppelklick (pythonw) gestartet -> eigenes Konsolenfenster aufmachen
            _spawn_cli_console()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="enyrpter3",
        description="enyripter v3 — echte authentifizierte Verschluesselung (GUI oder Terminal).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--gui", action="store_true", help="direkt im GUI-Modus starten")
    group.add_argument("--cli", action="store_true", help="direkt im Terminal-Modus starten")
    parser.add_argument("--selftest", action="store_true", help="nur den Krypto-Self-Test ausfuehren")
    parser.add_argument("--version", action="store_true", help="Versionsinfo anzeigen")
    args = parser.parse_args(argv)

    if args.version:
        import eny_core
        caps = eny_core.capabilities()
        _safe_print(f"enyripter v{VERSION}")
        _safe_print(f"  cryptography={caps['cryptography']} · argon2={caps['argon2']} · KDF={caps['default_kdf']}")
        return 0

    if args.selftest:
        import eny_core
        return 0 if eny_core.self_test(verbose=True) else 1

    if args.gui:
        launch("gui")
        return 0
    if args.cli:
        launch("cli")
        return 0

    # Keine Modus-Flags -> Auswahl anzeigen
    mode = choose_mode_gui()
    if mode is None:
        # Tk nicht verfuegbar ODER Fenster geschlossen -> Konsolen-Fallback nur,
        # wenn Tk gar nicht ging. Hier: einfacher Console-Fallback.
        try:
            import tkinter  # noqa: F401
            tk_ok = True
        except Exception:
            tk_ok = False
        if not tk_ok:
            mode = choose_mode_console()
    if mode is None:
        _safe_print("Abgebrochen.")
        return 0
    launch(mode)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nAbbruch durch Benutzer.")
        sys.exit(0)
