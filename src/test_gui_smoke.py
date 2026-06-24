# -*- coding: utf-8 -*-
"""
Headless-Smoke-Test fuer eny_gui (kein Fullscreen).
Baut den Desktop, exerziert alle Views/Themes und fuehrt eine echte
Encrypt -> Decrypt Runde ueber die UI-Async-Pipeline aus.

  python test_gui_smoke.py    ->  Exit 0 bei Erfolg
"""
import sys
import time

import eny_gui


def pump(app, seconds):
    """Event-Loop manuell fuer 'seconds' Sekunden treiben."""
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        app.update_idletasks()
        time.sleep(0.01)


def pump_until(app, predicate, timeout):
    end = time.time() + timeout
    while time.time() < end:
        app.update()
        app.update_idletasks()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def main():
    errors = []
    try:
        app = eny_gui.EncryptOS(fullscreen=False, maximize=False, show_welcome=False)
    except Exception as exc:
        print(f"FAIL: Konnte App nicht erstellen: {exc!r}")
        return 1

    try:
        # Boot/Login ueberspringen, direkt Desktop bauen
        app.show_desktop()
        pump(app, 0.3)

        # Alle Views durchschalten
        for key in ("encrypt", "decrypt", "files", "generator", "settings", "about"):
            try:
                app._switch_app(key)
                pump(app, 0.08)
            except Exception as exc:
                errors.append(f"switch {key}: {exc!r}")

        # Themes durchprobieren (baut Desktop jeweils neu)
        for theme in list(eny_gui.THEMES):
            try:
                app._set_theme(theme)
                pump(app, 0.12)
            except Exception as exc:
                errors.append(f"theme {theme}: {exc!r}")
        app._set_theme("matrix")
        pump(app, 0.1)

        # Passwort-Generator
        try:
            app._switch_app("generator")
            pump(app, 0.05)
            app._generate()
            pump(app, 0.05)
            assert app.gen_out.get().strip(), "Generator leer"
        except Exception as exc:
            errors.append(f"generator: {exc!r}")

        # ECHTE Encrypt -> Decrypt Runde ueber die UI
        secret = "Geheime Nachricht 🔐 äöü 你好"
        password = "Sehr-Sicheres-PW-2026!"
        try:
            app._switch_app("encrypt")
            pump(app, 0.05)
            app.enc_plain.delete("1.0", "end")
            app.enc_plain.insert("1.0", secret)
            app.enc_pw.set(password)
            app.level = "fast"  # Test schnell halten
            app._on_encrypt()
            ok = pump_until(app, lambda: app.enc_out.get("1.0", "end").strip() != "", timeout=15)
            cipher = app.enc_out.get("1.0", "end").strip()
            if not ok or not cipher:
                errors.append("encrypt: kein Cipher erzeugt")
            else:
                app._switch_app("decrypt")
                pump(app, 0.05)
                app.dec_in.delete("1.0", "end")
                app.dec_in.insert("1.0", cipher)
                app.dec_pw.set(password)
                app._on_decrypt()
                ok2 = pump_until(app, lambda: app.dec_out.get("1.0", "end").strip() != "", timeout=15)
                got = app.dec_out.get("1.0", "end").strip()
                if not ok2:
                    errors.append("decrypt: kein Ergebnis")
                elif got != secret:
                    errors.append(f"roundtrip mismatch: {got!r} != {secret!r}")
        except Exception as exc:
            errors.append(f"roundtrip: {exc!r}")

        # Falsches Passwort -> Fehlerpfad (sollte nicht crashen)
        try:
            app.dec_pw.set("FALSCH")
            app._inspect_cipher()
            pump(app, 0.05)
        except Exception as exc:
            errors.append(f"inspect: {exc!r}")

    finally:
        # Sauber herunterfahren: alive=False + gen-Bump lassen alle after()-Schleifen
        # auslaufen, kurz pumpen (anstehende Callbacks abarbeiten), dann zerstoeren.
        app.alive = False
        app._gen += 1
        if getattr(app, "rain", None):
            app.rain.stop()
        pump(app, 0.3)
        try:
            app.destroy()
        except Exception:
            pass

    if errors:
        print("SMOKE-TEST FEHLER:")
        for e in errors:
            print("  -", e)
        return 1
    print("GUI SMOKE-TEST: ALLE CHECKS BESTANDEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
