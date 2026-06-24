# -*- coding: utf-8 -*-
"""
enyripter v3 — Einzeldatei-Edition (alles in EINER .pyw)
========================================================

Doppelklick auf diese Datei -> KEIN Terminalfenster, sondern direkt die
Auswahl  GUI  oder  Terminal.

Beim allerersten Start wird die benoetigte Komponente 'cryptography' bei Bedarf
AUTOMATISCH heruntergeladen (einmalig, Internet noetig). Danach laeuft alles
offline. Diese Datei ist vollstaendig eigenstaendig — es werden keine weiteren
Dateien benoetigt (ideal fuer GitHub: nur diese eine Datei hochladen).

Erzeugt aus eny_core.py + eny_cli.py + eny_gui.py + Launcher via
build_single_file.py — nicht direkt von Hand editieren, sondern die Quelldateien
aendern und neu bauen.
"""
from __future__ import annotations

import os
import sys
import subprocess


# ==========================================================================
#   AUTO-BOOTSTRAP DER ABHAENGIGKEITEN
#   (laeuft beim Start; installiert 'cryptography', falls es fehlt)
# ==========================================================================

def _eny_run_pip(pkg):
    cmd = [sys.executable, "-m", "pip", "install", pkg]
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW -> kein Konsolen-Aufblitzen
    try:
        subprocess.check_call(cmd, **kw)
        return True
    except Exception:
        try:
            subprocess.check_call(cmd + ["--user"], **kw)
            return True
        except Exception:
            return False


def _eny_gui_install(pkg):
    """Zeigt ein kleines Fenster waehrend der Erstinstallation (wenn keine Konsole da ist)."""
    try:
        import tkinter as tk
    except Exception:
        return _eny_run_pip(pkg)
    win = tk.Tk()
    win.title("enyripter — Einrichtung")
    win.configure(bg="#01040a")
    try:
        win.geometry("500x200")
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"500x200+{(sw - 500) // 2}+{(sh - 200) // 2}")
        win.resizable(False, False)
    except Exception:
        pass
    tk.Label(win, text="enyripter wird eingerichtet", font=("Consolas", 16, "bold"),
             bg="#01040a", fg="#27f08a").pack(pady=(30, 6))
    tk.Label(win, text="Benoetigte Komponente wird heruntergeladen", font=("Consolas", 10),
             bg="#01040a", fg="#7da894").pack()
    tk.Label(win, text="(nur beim ersten Start)", font=("Consolas", 9),
             bg="#01040a", fg="#7da894").pack()
    tk.Label(win, text=pkg + " ...", font=("Consolas", 11, "bold"),
             bg="#01040a", fg="#3df0ff").pack(pady=16)
    res = {"done": False, "ok": False}

    def worker():
        res["ok"] = _eny_run_pip(pkg)
        res["done"] = True

    import threading
    threading.Thread(target=worker, daemon=True).start()

    def poll():
        if res["done"]:
            try:
                win.destroy()
            except Exception:
                pass
            return
        win.after(150, poll)

    poll()
    try:
        win.mainloop()
    except Exception:
        pass
    return res["ok"]


def _eny_fatal(text):
    if sys.stdout is not None:
        try:
            print(text)
        except Exception:
            pass
    else:
        try:
            import tkinter as tk
            from tkinter import messagebox
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror("enyripter", text)
            r.destroy()
        except Exception:
            pass
    sys.exit(1)


def _ensure_dependencies():
    try:
        import cryptography  # noqa: F401
        return
    except Exception:
        pass
    pkg = "cryptography"
    if sys.stdout is not None:
        try:
            print("[enyripter] Lade benoetigte Komponente '%s' (einmalig) ..." % pkg)
        except Exception:
            pass
        _eny_run_pip(pkg)
    else:
        _eny_gui_install(pkg)
    try:
        import cryptography  # noqa: F401
    except Exception:
        _eny_fatal(
            "Die benoetigte Komponente 'cryptography' konnte nicht automatisch\n"
            "installiert werden (Internetverbindung noetig).\n\n"
            "Bitte einmalig im Terminal ausfuehren:\n\n    pip install cryptography\n"
        )


# Direkt beim Laden ausfuehren, damit der folgende Krypto-Import gelingt:
_ensure_dependencies()
