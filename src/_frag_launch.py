# ==========================================================================
#   LAUNCHER  (Modus-Auswahl GUI / Terminal, Self-Spawn, exe-Build)
#   Hinweis: Dieses Fragment wird ans Ende der Einzeldatei gehaengt; es nutzt
#   run_gui()/run_cli()/capabilities()/self_test() aus den vorherigen Sektionen.
# ==========================================================================

APP_VERSION = "3.0"


def _safe_print(*a):
    try:
        print(*a)
    except Exception:
        pass


def _has_console():
    if sys.stdout is None:
        return False
    try:
        sys.stdout.fileno()
        return True
    except Exception:
        return False


def _python_console_exe():
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
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    env = dict(os.environ)
    env["ENY_SPAWNED_CONSOLE"] = "1"
    if getattr(sys, "frozen", False):
        # Als gebaute .exe: die exe selbst mit --cli neu starten
        args = [sys.executable, "--cli"]
        cwd = os.path.dirname(os.path.abspath(sys.executable))
    else:
        args = [_python_console_exe(), os.path.abspath(__file__), "--cli"]
        cwd = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.Popen(args, cwd=cwd, creationflags=flags, env=env)
        return True
    except Exception as exc:
        _show_error(
            "Konnte kein Terminalfenster oeffnen:\n%s\n\n"
            "Bitte stattdessen den GUI-Modus nutzen." % exc
        )
        return False


def choose_mode_gui():
    """Animiertes Auswahlfenster. Rueckgabe: 'gui', 'cli' oder None."""
    try:
        import tkinter as tk
    except Exception:
        return None

    import random

    BG = "#01040a"
    PANEL = "#070d16"
    ACCENT = "#27f08a"
    ACCENT2 = "#3df0ff"
    TEXT = "#d7ffe9"
    MUTED = "#7da894"
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

    overlay = tk.Frame(root, bg=BG)
    overlay.place(relx=0.5, rely=0.5, anchor="center")

    tk.Label(overlay, text="e n y r i p t e r   v3", font=(FONT, 30, "bold"),
             bg=BG, fg=ACCENT).pack(pady=(0, 2))
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

    make_card(btn_row, "🖥", "GUI",
              "Fenster-App mit Themes, Live-Konsole & coolem Look. [G]",
              "gui").pack(side="left", padx=12)
    make_card(btn_row, "⌨", "TERMINAL",
              "Schlankes Hacker-Terminal in einem Konsolenfenster. [T]",
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
    print("=" * 50)
    print(" enyripter v3 — Modus waehlen")
    print("=" * 50)
    print("  [1] GUI")
    print("  [2] Terminal")
    print("  [0] Abbrechen")
    while True:
        try:
            ch = input("Auswahl: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if ch == "1":
            return "gui"
        if ch == "2":
            return "cli"
        if ch == "0":
            return None
        print("Bitte 1, 2 oder 0 eingeben.")


def _frozen_cli():
    """In einer fensterlosen .exe eine eigene Konsole anlegen und darin den CLI laufen lassen."""
    try:
        import ctypes
        ctypes.windll.kernel32.AllocConsole()
        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        run_cli()
    finally:
        try:
            input("\n[Enter] zum Schliessen des Fensters ...")
        except Exception:
            pass


def launch(mode):
    if mode == "gui":
        run_gui()
    elif mode == "cli":
        if _has_console():
            run_cli()
        elif getattr(sys, "frozen", False) and os.name == "nt":
            # Gebaute .exe (fensterlos) -> eigene Konsole anlegen
            _frozen_cli()
        else:
            _spawn_cli_console()


def _build_exe():
    """Baut eine eigenstaendige enyripter.exe via PyInstaller (Bonus)."""
    import subprocess
    here = os.path.abspath(__file__)
    _safe_print("Installiere PyInstaller (falls noetig) ...")
    subprocess.call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    _safe_print("Baue enyripter.exe (kann 1-2 Minuten dauern) ...")
    rc = subprocess.call([
        sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole",
        "--name", "enyripter", "--collect-all", "cryptography", here,
    ])
    if rc == 0:
        _safe_print("Fertig! Die Datei liegt unter:  dist/enyripter.exe")
    else:
        _safe_print("Build fehlgeschlagen (Code %s)." % rc)
    return rc


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(
        prog="enyripter",
        description="enyripter v3 — echte authentifizierte Verschluesselung (GUI oder Terminal).",
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--gui", action="store_true", help="direkt im GUI-Modus starten")
    g.add_argument("--cli", action="store_true", help="direkt im Terminal-Modus starten")
    p.add_argument("--selftest", action="store_true", help="nur den Krypto-Self-Test ausfuehren")
    p.add_argument("--version", action="store_true", help="Versionsinfo anzeigen")
    p.add_argument("--build-exe", action="store_true", help="eigenstaendige .exe bauen (PyInstaller)")
    a = p.parse_args(argv)

    if a.version:
        c = capabilities()
        _safe_print("enyripter v%s" % APP_VERSION)
        _safe_print("  cryptography=%s · argon2=%s · KDF=%s"
                    % (c["cryptography"], c["argon2"], c["default_kdf"]))
        return 0
    if a.build_exe:
        return _build_exe()
    if a.selftest:
        return 0 if self_test(verbose=True) else 1
    if a.gui:
        launch("gui")
        return 0
    if a.cli:
        launch("cli")
        return 0

    mode = choose_mode_gui()
    if mode is None:
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
    _spawned = os.environ.get("ENY_SPAWNED_CONSOLE") == "1"
    _rc = 0
    try:
        _rc = main()
    except (EOFError, KeyboardInterrupt):
        _safe_print("\nAbbruch durch Benutzer.")
    except Exception:
        import traceback
        traceback.print_exc()
        _rc = 1
    finally:
        if _spawned and sys.stdout is not None:
            try:
                input("\n[Enter] zum Schliessen des Fensters ...")
            except Exception:
                pass
    sys.exit(_rc or 0)
