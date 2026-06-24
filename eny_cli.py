# -*- coding: utf-8 -*-
"""
eny_cli  ·  enyripter v3  ·  Terminal-Modus
===========================================

OP-Style Hacker-Terminal mit ECHTER, passwortbasierter Verschluesselung
(ChaCha20-Poly1305 / AES-256-GCM / Cascade, Argon2id/scrypt) aus eny_core.

Starten:  python enyrpter3.py --cli      (oder Modus-Auswahl im Launcher)
Direkt :  python eny_cli.py
"""

from __future__ import annotations

import os
import sys
import time
import random
import getpass

import eny_core as core

# ==========================================================================
#   ANSI / Farben
# ==========================================================================

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

FG_GREEN = "\033[92m"
FG_CYAN = "\033[96m"
FG_MAGENTA = "\033[95m"
FG_YELLOW = "\033[93m"
FG_RED = "\033[91m"
FG_BLUE = "\033[94m"
FG_WHITE = "\033[97m"
FG_GREY = "\033[90m"


def enable_ansi():
    """Aktiviert ANSI/VT-Farben + UTF-8 unter Windows-Konsolen."""
    # stdout/stderr auf UTF-8, damit Emojis/Box-Zeichen nie crashen
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11, ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        # Fallback: leeres os.system aktiviert auf neueren Windows ebenfalls VT
        os.system("")


# Optionale Zwischenablage
try:
    import pyperclip
    _HAVE_PYPERCLIP = True
except Exception:
    pyperclip = None
    _HAVE_PYPERCLIP = False


def copy_to_clipboard(text: str) -> bool:
    if _HAVE_PYPERCLIP:
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            return False
    # Windows-Fallback ueber 'clip'
    if os.name == "nt":
        try:
            import subprocess
            subprocess.run("clip", input=text.encode("utf-16le"), check=True, shell=True)
            return True
        except Exception:
            return False
    return False


# ==========================================================================
#   Animationen / Effekte
# ==========================================================================

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def slow_print(text, delay=0.008, color=""):
    for ch in text:
        sys.stdout.write(color + ch + (RESET if color else ""))
        sys.stdout.flush()
        time.sleep(delay)
    print()


def loading_bar(prefix="Processing", length=28, duration=0.6, color=FG_GREEN):
    step_time = duration / max(length, 1)
    sys.stdout.write(color + BOLD + prefix + " [" + RESET)
    sys.stdout.flush()
    for _ in range(length):
        sys.stdout.write(color + "█" + RESET)
        sys.stdout.flush()
        time.sleep(step_time)
    sys.stdout.write(color + BOLD + "] OK" + RESET + "\n")
    sys.stdout.flush()


def loading_spinner(text="Verarbeite", duration=0.6, color=FG_CYAN):
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start = time.time()
    i = 0
    while time.time() - start < duration:
        sys.stdout.write(f"\r{color}{frames[i % len(frames)]} {text}...{RESET}")
        sys.stdout.flush()
        time.sleep(0.06)
        i += 1
    sys.stdout.write("\r" + " " * (len(text) + 14) + "\r")
    sys.stdout.flush()


def matrix_noise_line(width=64):
    return "".join(random.choice("01") for _ in range(width))


def matrix_rain(lines=6, width=64, delay=0.04, color=FG_GREEN):
    for _ in range(lines):
        print(color + DIM + matrix_noise_line(width) + RESET)
        time.sleep(delay)


# ==========================================================================
#   Banner / UI
# ==========================================================================

BANNER = r"""
   ███████╗███╗   ██╗██╗   ██╗██████╗ ██╗██████╗ ████████╗███████╗██████╗
   ██╔════╝████╗  ██║╚██╗ ██╔╝██╔══██╗██║██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
   █████╗  ██╔██╗ ██║ ╚████╔╝ ██████╔╝██║██████╔╝   ██║   █████╗  ██████╔╝
   ██╔══╝  ██║╚██╗██║  ╚██╔╝  ██╔══██╗██║██╔═══╝    ██║   ██╔══╝  ██╔══██╗
   ███████╗██║ ╚████║   ██║   ██║  ██║██║██║        ██║   ███████╗██║  ██║
   ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝        ╚═╝   ╚══════╝╚═╝  ╚═╝
"""


def print_banner():
    print(FG_GREEN + BOLD + BANNER + RESET)
    print(FG_CYAN + DIM + "        v3 · AUTHENTICATED ENCRYPTION SUITE · ChaCha20 · AES-256 · Argon2/scrypt" + RESET)
    print(FG_GREY + "        ~hofa · echte Verschluesselung statt nur Kodierung" + RESET)
    print()


def subtitle(text):
    print(f"{FG_GREEN}{'─' * 4}{RESET} {FG_CYAN}{BOLD}{text}{RESET} {FG_GREEN}{'─' * (70 - len(text))}{RESET}")


def intro_animation():
    clear_screen()
    print_banner()
    slow_print("Booting encryption core...", delay=0.012, color=FG_GREY + DIM)
    matrix_rain(lines=3, width=70)
    loading_bar("Initializing ciphers", duration=0.6, color=FG_CYAN)
    caps = core.capabilities()
    print(FG_GREY + f"   cryptography={caps['cryptography']}  argon2={caps['argon2']}  default-KDF={caps['default_kdf']}" + RESET)
    time.sleep(0.2)


# ==========================================================================
#   Session-Einstellungen
# ==========================================================================

class Settings:
    def __init__(self):
        self.cipher_id = core.CIPHER_CHACHA
        self.level = core.DEFAULT_LEVEL
        self.encoding = "base64"
        self.compress = True

    def cipher_name(self):
        return core.CIPHER_NAMES[self.cipher_id]

    def summary(self):
        return (f"Cipher={self.cipher_name()} · Level={self.level} · "
                f"Encoding={self.encoding} · Kompression={'an' if self.compress else 'aus'}")


# ==========================================================================
#   Eingabehilfen
# ==========================================================================

def safe_input(prompt=""):
    """input(), das EOF/Strg+C in None verwandelt statt zu crashen."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _clean_path(s):
    """Entfernt umschliessende Anfuehrungszeichen (\" oder ') aus Pfaden."""
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1]
    return s


def read_optional_keyfile():
    """Fragt optional ein Keyfile ab. Gibt bytes oder None zurueck."""
    path = _clean_path(safe_input(FG_CYAN + "Keyfile-Pfad (Enter = keins): " + RESET))
    if not path:
        return None
    if not os.path.isfile(path):
        print(FG_YELLOW + "  Keyfile nicht gefunden — fahre OHNE Keyfile fort." + RESET)
        return None
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as e:
        print(FG_RED + f"  Keyfile nicht lesbar: {e} — fahre OHNE Keyfile fort." + RESET)
        return None


def read_password(prompt="Passwort", confirm=False):
    print(FG_GREY + DIM + "  (Eingabe ist aus Sicherheitsgruenden unsichtbar — einfach tippen + Enter)" + RESET)
    while True:
        try:
            pw = getpass.getpass(FG_CYAN + f"{prompt}: " + RESET)
            if not pw:
                print(FG_RED + "  Passwort darf nicht leer sein." + RESET)
                continue
            if confirm:
                pw2 = getpass.getpass(FG_CYAN + f"{prompt} (wiederholen): " + RESET)
                if pw != pw2:
                    print(FG_RED + "  Passwoerter stimmen nicht ueberein. Nochmal." + RESET)
                    continue
            return pw
        except (EOFError, KeyboardInterrupt):
            print()
            return None


def read_multiline(prompt):
    print(FG_WHITE + prompt + RESET)
    print(FG_GREY + DIM + "  Fertig? Schreibe in eine NEUE, leere Zeile das Wort  ENDE  und druecke Enter." + RESET)
    print(FG_GREY + DIM + "  (alternativ Strg+Z dann Enter unter Windows / Strg+D unter Linux/Mac)" + RESET)
    lines = []
    while True:
        try:
            line = input(FG_CYAN + "│ " + RESET)
        except EOFError:
            break
        if line.strip().lower() in ("ende", "eof"):
            break
        lines.append(line)
    return "\n".join(lines)


def pause():
    safe_input(FG_GREY + "\nWeiter mit [Enter]..." + RESET)


def show_strength(pw):
    st = core.estimate_strength(pw)
    bar_len = int(st["score"] / 4 * 20)
    colors = [FG_RED, FG_RED, FG_YELLOW, FG_GREEN, FG_GREEN]
    c = colors[st["score"]]
    bar = c + "█" * bar_len + FG_GREY + "░" * (20 - bar_len) + RESET
    print(f"   Passwort-Staerke: [{bar}] {c}{st['label']}{RESET} (~{st['bits']} Bit)")


# ==========================================================================
#   Aktionen
# ==========================================================================

def action_encrypt_text(settings: Settings):
    clear_screen()
    print_banner()
    subtitle("TEXT VERSCHLUESSELN")
    print(FG_GREY + "   " + settings.summary() + RESET + "\n")

    plaintext = read_multiline("Klartext eingeben:")
    if not plaintext:
        print(FG_YELLOW + "Kein Text eingegeben." + RESET)
        pause()
        return

    pw = read_password("Passwort waehlen", confirm=True)
    if pw is None:
        return
    show_strength(pw)
    keyfile = read_optional_keyfile()

    try:
        print()
        loading_spinner("Schluessel ableiten (KDF)", duration=0.5, color=FG_CYAN)
        loading_bar("Verschluessle (AEAD)", duration=0.4, color=FG_GREEN)
        loading_bar("Kodiere Ausgabe", duration=0.3, color=FG_MAGENTA)
        cipher = core.encrypt_text(
            plaintext, pw,
            cipher_id=settings.cipher_id,
            level=settings.level,
            compress=settings.compress,
            encoding=settings.encoding,
            keyfile_bytes=keyfile,
        )
    except core.EnyError as e:
        print(FG_RED + BOLD + "\n[FEHLER] " + RESET + FG_RED + str(e) + RESET)
        pause()
        return

    print()
    subtitle("CIPHER OUTPUT")
    print(FG_GREEN + cipher + RESET)
    print(FG_GREEN + "─" * 74 + RESET)
    if copy_to_clipboard(cipher):
        print(FG_CYAN + "→ In Zwischenablage kopiert." + RESET)
    print(FG_YELLOW + BOLD + "Wichtig: Passwort"
          + (" + Keyfile" if keyfile else "") +
          " gut aufbewahren — ohne ist KEINE Wiederherstellung moeglich." + RESET)
    pause()


def action_decrypt_text(settings: Settings):
    clear_screen()
    print_banner()
    subtitle("TEXT ENTSCHLUESSELN")
    cipher = read_multiline("\nCipher einfuegen (base64 / hex / Bit-Morse):")
    if not cipher.strip():
        print(FG_YELLOW + "Nichts eingegeben." + RESET)
        pause()
        return

    try:
        meta = core.inspect(cipher)
        print(FG_GREY + f"\n   Erkannt: Verfahren={meta['cipher']} · KDF={meta['kdf']} · "
              f"komprimiert={'ja' if meta['compressed'] else 'nein'} · {meta['ciphertext_len']} Byte" + RESET)
    except core.EnyError:
        print(FG_RED + "   Konnte Container-Metadaten nicht lesen (evtl. ungueltig)." + RESET)

    pw = read_password("Passwort")
    if pw is None:
        return
    keyfile = read_optional_keyfile()

    try:
        print()
        loading_spinner("Schluessel ableiten (KDF)", duration=0.5, color=FG_CYAN)
        loading_bar("Pruefe Auth-Tag & entschluessle", duration=0.4, color=FG_GREEN)
        plaintext = core.decrypt_text(cipher, pw, keyfile_bytes=keyfile)
    except core.EnyError as e:
        print(FG_RED + BOLD + "\n[FEHLER] " + RESET + FG_RED + str(e) + RESET)
        print(FG_GREY + "  (Passwort exakt? Wurde beim Verschluesseln ein Keyfile genutzt?)" + RESET)
        pause()
        return

    print()
    subtitle("KLARTEXT")
    print(FG_WHITE + BOLD + plaintext + RESET)
    print(FG_GREEN + "─" * 74 + RESET)
    pause()


def action_encrypt_file(settings: Settings):
    clear_screen()
    print_banner()
    subtitle("DATEI VERSCHLUESSELN")
    in_path = _clean_path(safe_input(FG_CYAN + "Pfad zur Datei: " + RESET))
    if not in_path or not os.path.isfile(in_path):
        print(FG_RED + "Datei nicht gefunden." + RESET)
        pause()
        return
    pw = read_password("Passwort waehlen", confirm=True)
    if pw is None:
        return
    show_strength(pw)
    keyfile = read_optional_keyfile()
    out_path = in_path + core.ENY_FILE_SUFFIX
    overwrite = False
    if os.path.exists(out_path):
        ans = safe_input(FG_YELLOW + f"{out_path} existiert bereits. Ueberschreiben? [j/N]: " + RESET)
        if (ans or "").strip().lower() not in ("j", "ja", "y", "yes"):
            print(FG_GREY + "Abgebrochen." + RESET)
            pause()
            return
        overwrite = True
    try:
        print()
        loading_spinner("Schluessel ableiten (KDF)", duration=0.5, color=FG_CYAN)
        loading_bar("Verschluessle Datei", duration=0.5, color=FG_GREEN)
        out = core.encrypt_file(
            in_path, out_path, pw,
            cipher_id=settings.cipher_id, level=settings.level, compress=settings.compress,
            overwrite=overwrite, keyfile_bytes=keyfile,
        )
    except core.EnyError as e:
        print(FG_RED + BOLD + "\n[FEHLER] " + RESET + FG_RED + str(e) + RESET)
        pause()
        return
    size = os.path.getsize(out)
    print(FG_GREEN + f"\n→ Verschluesselt: {out}  ({size} Byte)" + RESET)
    pause()


def action_decrypt_file(settings: Settings):
    clear_screen()
    print_banner()
    subtitle("DATEI ENTSCHLUESSELN")
    in_path = _clean_path(safe_input(FG_CYAN + "Pfad zur .eny-Datei: " + RESET))
    if not in_path or not os.path.isfile(in_path):
        print(FG_RED + "Datei nicht gefunden." + RESET)
        pause()
        return
    pw = read_password("Passwort")
    if pw is None:
        return
    keyfile = read_optional_keyfile()
    out_default = in_path[:-4] if in_path.endswith(core.ENY_FILE_SUFFIX) else in_path + ".dec"
    out_path = _clean_path(safe_input(FG_CYAN + f"Ziel [{out_default}]: " + RESET)) or None
    target = out_path or out_default
    overwrite = False
    if os.path.exists(target):
        ans = safe_input(FG_YELLOW + f"{target} existiert bereits. Ueberschreiben? [j/N]: " + RESET)
        if (ans or "").strip().lower() not in ("j", "ja", "y", "yes"):
            print(FG_GREY + "Abgebrochen." + RESET)
            pause()
            return
        overwrite = True
    try:
        print()
        loading_spinner("Schluessel ableiten (KDF)", duration=0.5, color=FG_CYAN)
        loading_bar("Pruefe Auth-Tag & entschluessle", duration=0.5, color=FG_GREEN)
        out = core.decrypt_file(in_path, out_path, pw, overwrite=overwrite, keyfile_bytes=keyfile)
    except core.EnyError as e:
        print(FG_RED + BOLD + "\n[FEHLER] " + RESET + FG_RED + str(e) + RESET)
        print(FG_GREY + "  (Passwort exakt? Wurde beim Verschluesseln ein Keyfile genutzt?)" + RESET)
        pause()
        return
    print(FG_GREEN + f"\n→ Entschluesselt: {out}" + RESET)
    pause()


def action_generate_password(settings: Settings):
    clear_screen()
    print_banner()
    subtitle("PASSWORT-GENERATOR")
    raw = (safe_input(FG_CYAN + "Laenge [24]: " + RESET) or "").strip()
    try:
        length = int(raw) if raw else 24
    except ValueError:
        length = 24
    ans = (safe_input(FG_CYAN + "Sonderzeichen? [J/n]: " + RESET) or "").strip().lower()
    use_sym = ans not in ("n", "no", "nein")
    pw = core.generate_password(length, use_symbols=use_sym)
    print(FG_GREEN + BOLD + f"\n   {pw}" + RESET + "\n")
    show_strength(pw)
    if copy_to_clipboard(pw):
        print(FG_CYAN + "→ In Zwischenablage kopiert." + RESET)
    pause()


def action_settings(settings: Settings):
    while True:
        clear_screen()
        print_banner()
        subtitle("EINSTELLUNGEN")
        print(f"   {FG_YELLOW}[1]{RESET} Cipher    : {FG_WHITE}{settings.cipher_name()}{RESET}")
        print(f"   {FG_YELLOW}[2]{RESET} Sicherheit: {FG_WHITE}{settings.level}{RESET}  (fast/strong/paranoid)")
        print(f"   {FG_YELLOW}[3]{RESET} Encoding  : {FG_WHITE}{settings.encoding}{RESET}  (base64/hex/bitmorse)")
        print(f"   {FG_YELLOW}[4]{RESET} Kompression: {FG_WHITE}{'an' if settings.compress else 'aus'}{RESET}")
        print(f"   {FG_YELLOW}[0]{RESET} Zurueck")
        choice = safe_input(FG_CYAN + "\nAuswahl: " + RESET)
        if choice is None:
            return
        choice = choice.strip()
        if choice == "1":
            print("\n   1) chacha20-poly1305  2) aes-256-gcm  3) cascade (max)")
            c = (safe_input(FG_CYAN + "   Cipher: " + RESET) or "").strip()
            settings.cipher_id = {"1": core.CIPHER_CHACHA, "2": core.CIPHER_AESGCM,
                                  "3": core.CIPHER_CASCADE}.get(c, settings.cipher_id)
        elif choice == "2":
            c = (safe_input(FG_CYAN + "   Level (fast/strong/paranoid): " + RESET) or "").strip().lower()
            if c in core.LEVELS:
                settings.level = c
        elif choice == "3":
            c = (safe_input(FG_CYAN + "   Encoding (base64/hex/bitmorse): " + RESET) or "").strip().lower()
            if c in core.ENCODINGS:
                settings.encoding = c
        elif choice == "4":
            settings.compress = not settings.compress
        elif choice == "0":
            return


def action_selftest(settings: Settings):
    clear_screen()
    print_banner()
    subtitle("SELF-TEST")
    core.self_test(verbose=True)
    pause()


def action_about(settings: Settings):
    clear_screen()
    print_banner()
    subtitle("ABOUT")
    caps = core.capabilities()
    print(f"""{FG_WHITE}
   enyripter v3 · Terminal-Modus

   Echte authentifizierte Verschluesselung:
     • Cipher  : ChaCha20-Poly1305 / AES-256-GCM / Cascade
     • KDF     : Argon2id (falls installiert) / scrypt / PBKDF2
     • Schutz  : Salt + Nonce + Auth-Tag (Manipulation wird erkannt)
     • Extra   : Datei-Verschluesselung, Keyfile, Kompression,
                 Passwortgenerator & -staerke, 3 Ausgabe-Kodierungen

   Wichtig: Die Sicherheit haengt an deinem PASSWORT, nicht am Code.
            Mit starkem Passwort ist eine Nachricht ohne dieses
            praktisch nicht zu entschluesseln (256-Bit-Schluesselraum).
            Ohne dein Passwort gibt es KEINE Wiederherstellung.

   System: cryptography={caps['cryptography']} · argon2={caps['argon2']} · KDF={caps['default_kdf']}
{RESET}""")
    pause()


# ==========================================================================
#   Hauptmenue
# ==========================================================================

def print_menu(settings: Settings):
    print()
    subtitle("MAIN MENU")
    print(f"   {FG_YELLOW}[1]{RESET} {FG_WHITE}Text verschluesseln{RESET}")
    print(f"   {FG_YELLOW}[2]{RESET} {FG_WHITE}Text entschluesseln{RESET}")
    print(f"   {FG_YELLOW}[3]{RESET} {FG_WHITE}Datei verschluesseln{RESET}")
    print(f"   {FG_YELLOW}[4]{RESET} {FG_WHITE}Datei entschluesseln{RESET}")
    print(f"   {FG_YELLOW}[5]{RESET} {FG_WHITE}Passwort generieren{RESET}")
    print(f"   {FG_YELLOW}[6]{RESET} {FG_WHITE}Einstellungen{RESET}   {FG_GREY}({settings.summary()}){RESET}")
    print(f"   {FG_YELLOW}[7]{RESET} {FG_WHITE}Self-Test{RESET}")
    print(f"   {FG_YELLOW}[8]{RESET} {FG_WHITE}About{RESET}")
    print(f"   {FG_YELLOW}[9]{RESET} {FG_WHITE}Beenden{RESET}")
    print(FG_GREEN + "─" * 74 + RESET)


def run():
    enable_ansi()
    if not core.HAVE_CRYPTOGRAPHY:
        print(FG_RED + "FEHLER: 'cryptography' fehlt. Bitte: pip install cryptography" + RESET)
        return
    intro_animation()
    settings = Settings()
    actions = {
        "1": action_encrypt_text, "2": action_decrypt_text,
        "3": action_encrypt_file, "4": action_decrypt_file,
        "5": action_generate_password, "6": action_settings,
        "7": action_selftest, "8": action_about,
    }
    while True:
        print_menu(settings)
        try:
            choice = input(FG_CYAN + "Auswahl (1-9): " + RESET).strip()
        except (EOFError, KeyboardInterrupt):
            choice = "9"
        if choice == "9":
            clear_screen()
            print_banner()
            slow_print("Shutting down encryption core...", delay=0.012, color=FG_GREY + DIM)
            matrix_rain(lines=2, width=70)
            print(FG_CYAN + BOLD + "Goodbye, Operator." + RESET + "\n")
            break
        action = actions.get(choice)
        if action:
            try:
                action(settings)
            except KeyboardInterrupt:
                print(FG_YELLOW + "\nAbgebrochen." + RESET)
                time.sleep(0.5)
            except EOFError:
                # stdin geschlossen -> sauber beenden statt Endlosschleife
                break
        else:
            print(FG_RED + "Ungueltige Auswahl." + RESET)
            time.sleep(0.6)
            clear_screen()
            print_banner()


if __name__ == "__main__":
    _spawned = os.environ.get("ENY_SPAWNED_CONSOLE") == "1"
    try:
        run()
    except (EOFError, KeyboardInterrupt):
        print("\n" + FG_RED + "Abbruch durch Benutzer." + RESET)
    except Exception:
        # Im gespawnten Fenster darf ein Fehler nicht spurlos verschwinden
        import traceback
        traceback.print_exc()
    finally:
        # Wenn per Doppelklick ein eigenes Fenster geoeffnet wurde: offen halten,
        # damit man die Ausgabe lesen kann (sonst schliesst Windows es sofort).
        if _spawned:
            try:
                input("\n[Enter] zum Schliessen des Fensters ...")
            except Exception:
                pass
    sys.exit(0)
