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


# ========================================================================
#   KRYPTO-KERN  (urspruenglich eny_core.py)
# ========================================================================

# -*- coding: utf-8 -*-
"""
eny_core  ·  enyripter v3 cryptographic core
=============================================

Echte, moderne, authentifizierte Verschluesselung (kein "Encoding").

Sicherheits-Design (Kerckhoffs-Prinzip):
    Die Staerke kommt NICHT daher, dass der Algorithmus geheim ist,
    sondern aus einem geheimen Passwort + geprueften Verfahren:

      * Schluesselableitung:  Argon2id (falls verfuegbar) sonst scrypt,
                              sonst PBKDF2-HMAC-SHA256  (alle mit Salt)
      * Verschluesselung:     ChaCha20-Poly1305  /  AES-256-GCM
                              /  "Cascade" (ChaCha20 -> AES-256, zwei Schluessel)
      * Integritaet:          AEAD-Auth-Tag + Header als Associated Data
                              -> jede Manipulation wird erkannt
      * Frische:              zufaelliges Salt + Nonce pro Nachricht
      * Optional:             zlib-Kompression, Keyfile zusaetzlich zum Passwort

Container-Format (Binaer, danach optional als Text kodiert):

    MAGIC      4   b"ENY3"
    version    1   (=1)
    flags      1   bit0 = zlib-komprimiert
    kdf_id     1   1=scrypt 2=argon2id 3=pbkdf2
    cipher_id  1   1=chacha20poly1305 2=aes256gcm 3=cascade
    kparlen    1   Laenge des KDF-Parameterblocks
    kparams    *   KDF-Parameter (siehe _pack_kdf_params)
    saltlen    1   Laenge des Salts
    salt       *
    n_nonce    1   Anzahl Nonces (1, bei cascade 2)
    nonces     12*n_nonce
    --------------- ab hier authentifizierte Nutzdaten ---------------
    ciphertext *   (AEAD: enthaelt am Ende den 16-Byte Poly1305/GCM-Tag)

Der gesamte Header (MAGIC..nonces) wird als AAD authentifiziert, d.h.
ein Angreifer kann weder Version noch KDF-/Cipher-Parameter faelschen.

Dieses Modul hat keine GUI-/CLI-Abhaengigkeiten und ist eigenstaendig
testbar (python eny_core.py  ->  Self-Test).
"""


import base64
import hashlib
import hmac
import os
import secrets
import struct
import tempfile
import unicodedata
import zlib
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
#   Abhaengigkeiten (mit freundlichen Fehlermeldungen)
# ---------------------------------------------------------------------------

try:
    from cryptography.hazmat.primitives.ciphers.aead import (
        AESGCM,
        ChaCha20Poly1305,
    )
    from cryptography.exceptions import InvalidTag
    HAVE_CRYPTOGRAPHY = True
except Exception:  # pragma: no cover
    HAVE_CRYPTOGRAPHY = False

    class InvalidTag(Exception):
        pass

try:
    from argon2.low_level import hash_secret_raw, Type as _Argon2Type
    HAVE_ARGON2 = True
except Exception:
    HAVE_ARGON2 = False


# ---------------------------------------------------------------------------
#   Konstanten
# ---------------------------------------------------------------------------

MAGIC = b"ENY3"
VERSION = 1

FLAG_COMPRESSED = 0x01

KDF_SCRYPT = 1
KDF_ARGON2ID = 2
KDF_PBKDF2 = 3

CIPHER_CHACHA = 1
CIPHER_AESGCM = 2
CIPHER_CASCADE = 3

KDF_NAMES = {KDF_SCRYPT: "scrypt", KDF_ARGON2ID: "argon2id", KDF_PBKDF2: "pbkdf2"}
CIPHER_NAMES = {
    CIPHER_CHACHA: "chacha20-poly1305",
    CIPHER_AESGCM: "aes-256-gcm",
    CIPHER_CASCADE: "cascade (chacha20 -> aes-256)",
}

NONCE_LEN = 12
SALT_LEN = 16
TAG_LEN = 16  # informativ; das AEAD haengt den Tag selbst an

# Sicherheits-Stufen -> KDF-Kostenparameter
#   scrypt:   n = 2**log2_n, r, p           (Speicher ~ 128*n*r Bytes)
#   argon2id: time_cost, memory_kib, parallelism
LEVELS = {
    "fast": {
        "scrypt": {"log2_n": 14, "r": 8, "p": 1},     # ~16 MiB
        "argon2id": {"t": 2, "m_kib": 64 * 1024, "p": 1},
        "pbkdf2": {"iterations": 200_000},
    },
    "strong": {
        "scrypt": {"log2_n": 15, "r": 8, "p": 1},     # ~32 MiB
        "argon2id": {"t": 3, "m_kib": 256 * 1024, "p": 2},
        "pbkdf2": {"iterations": 600_000},
    },
    "paranoid": {
        "scrypt": {"log2_n": 17, "r": 8, "p": 1},     # ~128 MiB
        "argon2id": {"t": 4, "m_kib": 512 * 1024, "p": 4},
        "pbkdf2": {"iterations": 1_200_000},
    },
}
DEFAULT_LEVEL = "strong"

# Obergrenzen fuer KDF-Kostenparameter AUS EINEM CONTAINER (Schutz gegen
# Speicher-/CPU-DoS, wenn jemand einen manipulierten Container zum Entschluesseln
# unterschiebt). Grosszuegig oberhalb der 'paranoid'-Presets, aber endlich.
SCRYPT_MAX_LOG2N = 21          # n bis 2^21
SCRYPT_MAX_R = 16
SCRYPT_MAX_P = 16
SCRYPT_MAX_MEM = 1 << 30        # harte Speicherdecke (1 GiB, unter C-long INT_MAX) fuer scrypt
PBKDF2_MAX_ITER = 10_000_000
ARGON2_MAX_T = 16
ARGON2_MAX_M_KIB = 1 << 20     # 1 GiB
ARGON2_MAX_P = 16


# ---------------------------------------------------------------------------
#   Fehlerklassen
# ---------------------------------------------------------------------------

class EnyError(Exception):
    """Basisklasse aller eny_core-Fehler."""


class DependencyError(EnyError):
    """Eine benoetigte Bibliothek fehlt."""


class DecryptError(EnyError):
    """Entschluesselung fehlgeschlagen (falsches Passwort / beschaedigt / manipuliert)."""


class FormatError(EnyError):
    """Daten sind kein gueltiger ENY3-Container."""


# ---------------------------------------------------------------------------
#   Hilfsfunktionen: Passwort-Material
# ---------------------------------------------------------------------------

def _normalize_password(password: str) -> bytes:
    """Unicode-Normalisierung (NFC), damit gleiche Passwoerter byte-gleich sind."""
    if not isinstance(password, str):
        raise TypeError("Passwort muss ein String sein.")
    return unicodedata.normalize("NFC", password).encode("utf-8")


def _password_material(password: str, keyfile_bytes: Optional[bytes]) -> bytes:
    """
    Kombiniert Passwort und optionales Keyfile zu Schluesselmaterial.
    Keyfile -> Passwort werden via HMAC verknuepft (beides noetig zum Entschluesseln).
    """
    pw = _normalize_password(password)
    if keyfile_bytes:
        kf_key = hashlib.sha256(keyfile_bytes).digest()
        return hmac.new(kf_key, pw, hashlib.sha256).digest()
    return pw


# ---------------------------------------------------------------------------
#   KDF
# ---------------------------------------------------------------------------

def _pack_kdf_params(kdf_id: int, params: dict) -> bytes:
    if kdf_id == KDF_SCRYPT:
        return struct.pack(">BHH", params["log2_n"], params["r"], params["p"])
    if kdf_id == KDF_ARGON2ID:
        return struct.pack(">IIB", params["t"], params["m_kib"], params["p"])
    if kdf_id == KDF_PBKDF2:
        return struct.pack(">I", params["iterations"])
    raise FormatError(f"Unbekannte KDF-ID: {kdf_id}")


def _validate_kdf_params(kdf_id: int, params: dict) -> None:
    """Lehnt absurde/gefaehrliche Kostenparameter aus untrusted Containern ab."""
    if kdf_id == KDF_SCRYPT:
        if not (1 <= params["log2_n"] <= SCRYPT_MAX_LOG2N):
            raise FormatError(f"scrypt log2_n ausserhalb des erlaubten Bereichs (1..{SCRYPT_MAX_LOG2N}).")
        if not (1 <= params["r"] <= SCRYPT_MAX_R):
            raise FormatError(f"scrypt r ausserhalb des erlaubten Bereichs (1..{SCRYPT_MAX_R}).")
        if not (1 <= params["p"] <= SCRYPT_MAX_P):
            raise FormatError(f"scrypt p ausserhalb des erlaubten Bereichs (1..{SCRYPT_MAX_P}).")
    elif kdf_id == KDF_ARGON2ID:
        if not (1 <= params["t"] <= ARGON2_MAX_T):
            raise FormatError(f"argon2 time_cost ausserhalb des erlaubten Bereichs (1..{ARGON2_MAX_T}).")
        if not (8 <= params["m_kib"] <= ARGON2_MAX_M_KIB):
            raise FormatError(f"argon2 memory ausserhalb des erlaubten Bereichs (8..{ARGON2_MAX_M_KIB} KiB).")
        if not (1 <= params["p"] <= ARGON2_MAX_P):
            raise FormatError(f"argon2 parallelism ausserhalb des erlaubten Bereichs (1..{ARGON2_MAX_P}).")
    elif kdf_id == KDF_PBKDF2:
        if not (1 <= params["iterations"] <= PBKDF2_MAX_ITER):
            raise FormatError(f"pbkdf2 iterations ausserhalb des erlaubten Bereichs (1..{PBKDF2_MAX_ITER}).")
    else:
        raise FormatError(f"Unbekannte KDF-ID: {kdf_id}")


def _unpack_kdf_params(kdf_id: int, blob: bytes) -> dict:
    try:
        if kdf_id == KDF_SCRYPT:
            log2_n, r, p = struct.unpack(">BHH", blob)
            params = {"log2_n": log2_n, "r": r, "p": p}
        elif kdf_id == KDF_ARGON2ID:
            t, m_kib, p = struct.unpack(">IIB", blob)
            params = {"t": t, "m_kib": m_kib, "p": p}
        elif kdf_id == KDF_PBKDF2:
            (iterations,) = struct.unpack(">I", blob)
            params = {"iterations": iterations}
        else:
            raise FormatError(f"Unbekannte KDF-ID: {kdf_id}")
    except struct.error as exc:
        raise FormatError(f"Beschaedigte KDF-Parameter: {exc}") from exc
    _validate_kdf_params(kdf_id, params)  # Schutz gegen DoS durch manipulierte Parameter
    return params


def _derive_key(material: bytes, salt: bytes, kdf_id: int, params: dict, dklen: int) -> bytes:
    if kdf_id == KDF_SCRYPT:
        n = 1 << params["log2_n"]
        r = params["r"]
        p = params["p"]
        # Tatsaechlicher scrypt-Speicherbedarf ~ 128*r*(N+p+2). Mit kleiner Reserve,
        # aber harte Decke: verhindert Speicher-DoS UND C-long-Overflow von maxmem.
        required = 128 * r * (n + p + 2)
        if required > SCRYPT_MAX_MEM:
            raise FormatError("scrypt-Parameter verlangen zu viel Speicher (DoS-Schutz).")
        maxmem = min(required + (1 << 20), SCRYPT_MAX_MEM)
        return hashlib.scrypt(material, salt=salt, n=n, r=r, p=p, dklen=dklen, maxmem=maxmem)
    if kdf_id == KDF_ARGON2ID:
        if not HAVE_ARGON2:
            raise DependencyError(
                "Dieser Container nutzt Argon2id, aber 'argon2-cffi' ist nicht installiert.\n"
                "  ->  pip install argon2-cffi"
            )
        return hash_secret_raw(
            secret=material,
            salt=salt,
            time_cost=params["t"],
            memory_cost=params["m_kib"],
            parallelism=params["p"],
            hash_len=dklen,
            type=_Argon2Type.ID,
        )
    if kdf_id == KDF_PBKDF2:
        return hashlib.pbkdf2_hmac("sha256", material, salt, params["iterations"], dklen=dklen)
    raise FormatError(f"Unbekannte KDF-ID: {kdf_id}")


def _choose_default_kdf() -> int:
    """Bevorzugt Argon2id (falls installiert), sonst scrypt."""
    return KDF_ARGON2ID if HAVE_ARGON2 else KDF_SCRYPT


def _kdf_params_for(kdf_id: int, level: str) -> dict:
    if level not in LEVELS:
        raise EnyError(f"Unbekannte Sicherheitsstufe: {level!r} (erlaubt: {list(LEVELS)})")
    name = KDF_NAMES[kdf_id]
    return dict(LEVELS[level][name])


# ---------------------------------------------------------------------------
#   AEAD
# ---------------------------------------------------------------------------

def _require_crypto():
    if not HAVE_CRYPTOGRAPHY:
        raise DependencyError(
            "Die Bibliothek 'cryptography' wird fuer die Verschluesselung benoetigt.\n"
            "  ->  pip install cryptography"
        )


def _aead_encrypt(cipher_id: int, key: bytes, nonces: list[bytes], data: bytes, aad: bytes) -> bytes:
    _require_crypto()
    if cipher_id == CIPHER_CHACHA:
        return ChaCha20Poly1305(key).encrypt(nonces[0], data, aad)
    if cipher_id == CIPHER_AESGCM:
        return AESGCM(key).encrypt(nonces[0], data, aad)
    if cipher_id == CIPHER_CASCADE:
        k1, k2 = key[:32], key[32:]
        inner = ChaCha20Poly1305(k1).encrypt(nonces[0], data, aad)
        outer = AESGCM(k2).encrypt(nonces[1], inner, aad)
        return outer
    raise FormatError(f"Unbekannte Cipher-ID: {cipher_id}")


def _aead_decrypt(cipher_id: int, key: bytes, nonces: list[bytes], ct: bytes, aad: bytes) -> bytes:
    _require_crypto()
    if cipher_id == CIPHER_CHACHA:
        return ChaCha20Poly1305(key).decrypt(nonces[0], ct, aad)
    if cipher_id == CIPHER_AESGCM:
        return AESGCM(key).decrypt(nonces[0], ct, aad)
    if cipher_id == CIPHER_CASCADE:
        k1, k2 = key[:32], key[32:]
        inner = AESGCM(k2).decrypt(nonces[1], ct, aad)
        return ChaCha20Poly1305(k1).decrypt(nonces[0], inner, aad)
    raise FormatError(f"Unbekannte Cipher-ID: {cipher_id}")


def _nonce_count(cipher_id: int) -> int:
    return 2 if cipher_id == CIPHER_CASCADE else 1


def _key_len(cipher_id: int) -> int:
    return 64 if cipher_id == CIPHER_CASCADE else 32


# ---------------------------------------------------------------------------
#   Header (de)serialisieren
# ---------------------------------------------------------------------------

@dataclass
class Header:
    version: int
    flags: int
    kdf_id: int
    cipher_id: int
    kdf_params: dict
    salt: bytes
    nonces: list[bytes]
    raw: bytes  # exakte Bytes (werden als AAD verwendet)


def _build_header(flags, kdf_id, cipher_id, kdf_params, salt, nonces) -> bytes:
    kpar = _pack_kdf_params(kdf_id, kdf_params)
    if len(kpar) > 255 or len(salt) > 255:
        raise FormatError("Parameter zu lang.")
    out = bytearray()
    out += MAGIC
    out += bytes([VERSION, flags & 0xFF, kdf_id, cipher_id])
    out += bytes([len(kpar)]) + kpar
    out += bytes([len(salt)]) + salt
    out += bytes([len(nonces)])
    for n in nonces:
        if len(n) != NONCE_LEN:
            raise FormatError("Ungueltige Nonce-Laenge.")
        out += n
    return bytes(out)


def _parse_header(blob: bytes) -> tuple[Header, int]:
    """Liest den Header aus blob. Gibt (Header, offset_des_ciphertexts) zurueck."""
    try:
        if blob[:4] != MAGIC:
            raise FormatError("Kein ENY3-Container (falsche Signatur).")
        pos = 4
        version, flags, kdf_id, cipher_id = blob[pos], blob[pos + 1], blob[pos + 2], blob[pos + 3]
        pos += 4
        if version != VERSION:
            raise FormatError(f"Nicht unterstuetzte Container-Version: {version}")
        if cipher_id not in CIPHER_NAMES:
            raise FormatError(f"Unbekannte Cipher-ID: {cipher_id}")
        kparlen = blob[pos]; pos += 1
        kpar = blob[pos:pos + kparlen]; pos += kparlen
        if len(kpar) != kparlen:
            raise FormatError("Header abgeschnitten (KDF-Parameter).")
        saltlen = blob[pos]; pos += 1
        salt = blob[pos:pos + saltlen]; pos += saltlen
        if len(salt) != saltlen:
            raise FormatError("Header abgeschnitten (Salt).")
        n_nonce = blob[pos]; pos += 1
        if n_nonce != _nonce_count(cipher_id):
            raise FormatError(
                f"Nonce-Anzahl {n_nonce} passt nicht zu Cipher {cipher_id} "
                f"(erwartet {_nonce_count(cipher_id)})."
            )
        nonces = []
        for _ in range(n_nonce):
            nonces.append(blob[pos:pos + NONCE_LEN]); pos += NONCE_LEN
            if len(nonces[-1]) != NONCE_LEN:
                raise FormatError("Header abgeschnitten (Nonce).")
        kdf_params = _unpack_kdf_params(kdf_id, kpar)
        raw = blob[:pos]
        return Header(version, flags, kdf_id, cipher_id, kdf_params, salt, nonces, raw), pos
    except IndexError as exc:
        raise FormatError(f"Header abgeschnitten: {exc}") from exc


# ---------------------------------------------------------------------------
#   Oeffentliche Kern-API: bytes -> bytes
# ---------------------------------------------------------------------------

def encrypt_bytes(
    plaintext: bytes,
    password: str,
    *,
    cipher_id: int = CIPHER_CHACHA,
    kdf_id: Optional[int] = None,
    level: str = DEFAULT_LEVEL,
    compress: bool = True,
    keyfile_bytes: Optional[bytes] = None,
) -> bytes:
    """Verschluesselt plaintext (bytes) -> ENY3-Container (bytes)."""
    _require_crypto()
    if kdf_id is None:
        kdf_id = _choose_default_kdf()
    if cipher_id not in CIPHER_NAMES:
        raise EnyError(f"Unbekannte Cipher-ID: {cipher_id}")

    material = _password_material(password, keyfile_bytes)

    flags = 0
    data = plaintext
    if compress:
        comp = zlib.compress(plaintext, 9)
        if len(comp) < len(plaintext):
            data = comp
            flags |= FLAG_COMPRESSED

    salt = secrets.token_bytes(SALT_LEN)
    params = _kdf_params_for(kdf_id, level)
    dklen = _key_len(cipher_id)
    key = _derive_key(material, salt, kdf_id, params, dklen)
    nonces = [secrets.token_bytes(NONCE_LEN) for _ in range(_nonce_count(cipher_id))]

    header = _build_header(flags, kdf_id, cipher_id, params, salt, nonces)
    ct = _aead_encrypt(cipher_id, key, nonces, data, header)
    return header + ct


def decrypt_bytes(
    container: bytes,
    password: str,
    *,
    keyfile_bytes: Optional[bytes] = None,
) -> bytes:
    """Entschluesselt einen ENY3-Container (bytes) -> plaintext (bytes)."""
    if not container or len(container) < 8 or container[:4] != MAGIC:
        raise FormatError("Eingabe ist kein gueltiger ENY3-Container.")
    header, offset = _parse_header(container)
    ct = container[offset:]
    if not ct:
        raise FormatError("Container enthaelt keine Nutzdaten.")

    material = _password_material(password, keyfile_bytes)
    dklen = _key_len(header.cipher_id)
    try:
        key = _derive_key(material, header.salt, header.kdf_id, header.kdf_params, dklen)
    except EnyError:
        raise
    except (OverflowError, MemoryError, ValueError) as exc:
        # manipulierte/absurde KDF-Parameter -> sauberer Format-Fehler statt rohem Crash
        raise FormatError(f"Ungueltige/beschaedigte KDF-Parameter: {exc}") from exc

    try:
        data = _aead_decrypt(header.cipher_id, key, header.nonces, ct, header.raw)
    except InvalidTag as exc:
        raise DecryptError(
            "Entschluesselung fehlgeschlagen: falsches Passwort/Keyfile "
            "oder Daten wurden beschaedigt/manipuliert."
        ) from exc
    except IndexError as exc:
        # inkonsistente Nonce-/Cipher-Kombination im Container (Defense-in-Depth)
        raise FormatError(f"Beschaedigter Container (Nonce/Cipher inkonsistent): {exc}") from exc

    if header.flags & FLAG_COMPRESSED:
        try:
            data = zlib.decompress(data)
        except zlib.error as exc:
            raise DecryptError(f"Dekompression fehlgeschlagen: {exc}") from exc
    return data


# ---------------------------------------------------------------------------
#   Text-Kodierung des Containers (base64 / hex / bit-morse Optik)
# ---------------------------------------------------------------------------

ENCODINGS = ("base64", "hex", "bitmorse")


def _to_base64(blob: bytes) -> str:
    return base64.urlsafe_b64encode(blob).decode("ascii")


def _from_base64(text: str) -> bytes:
    s = "".join(text.split())
    pad = (-len(s)) % 4
    return base64.urlsafe_b64decode(s + "=" * pad)


def _to_hex(blob: bytes) -> str:
    return blob.hex()


def _from_hex(text: str) -> bytes:
    return bytes.fromhex("".join(text.split()))


def _to_bitmorse(blob: bytes) -> str:
    """Signatur-Optik: jedes Bit -> '.' (0) / '-' (1), in 8er-Gruppen."""
    bits = "".join(f"{b:08b}" for b in blob)
    symbols = "".join("." if c == "0" else "-" for c in bits)
    # in 8er-Gruppen mit Leerzeichen (1 Byte pro Gruppe)
    return " ".join(symbols[i:i + 8] for i in range(0, len(symbols), 8))


def _from_bitmorse(text: str) -> bytes:
    cleaned = "".join(ch for ch in text if ch in ".-")
    if len(cleaned) % 8 != 0:
        raise ValueError("Bit-Morse-Laenge kein Vielfaches von 8.")
    bits = "".join("0" if ch == "." else "1" for ch in cleaned)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def encode_text(blob: bytes, encoding: str = "base64") -> str:
    if encoding == "base64":
        return _to_base64(blob)
    if encoding == "hex":
        return _to_hex(blob)
    if encoding == "bitmorse":
        return _to_bitmorse(blob)
    raise EnyError(f"Unbekannte Kodierung: {encoding}")


def decode_text(text: str) -> bytes:
    """
    Erkennt die Kodierung automatisch:
    Es wird jede Variante probiert und akzeptiert, sobald die MAGIC-Signatur passt.
    """
    text = text.strip()
    if not text:
        raise FormatError("Leere Eingabe.")
    candidates = set(text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))
    decoders = []
    if candidates <= set(".-"):
        decoders = [_from_bitmorse]
    else:
        decoders = [_from_base64, _from_hex]
    for dec in decoders:
        try:
            blob = dec(text)
        except Exception:
            continue
        if blob[:4] == MAGIC:
            return blob
    raise FormatError(
        "Konnte Eingabe nicht als ENY3-Container erkennen "
        "(weder base64, hex noch Bit-Morse, oder falsche Signatur)."
    )


# ---------------------------------------------------------------------------
#   Komfort-API: Text <-> Text
# ---------------------------------------------------------------------------

def encrypt_text(
    plaintext: str,
    password: str,
    *,
    cipher_id: int = CIPHER_CHACHA,
    kdf_id: Optional[int] = None,
    level: str = DEFAULT_LEVEL,
    compress: bool = True,
    encoding: str = "base64",
    keyfile_bytes: Optional[bytes] = None,
) -> str:
    blob = encrypt_bytes(
        plaintext.encode("utf-8"),
        password,
        cipher_id=cipher_id,
        kdf_id=kdf_id,
        level=level,
        compress=compress,
        keyfile_bytes=keyfile_bytes,
    )
    return encode_text(blob, encoding)


def decrypt_text(
    ciphertext: str,
    password: str,
    *,
    keyfile_bytes: Optional[bytes] = None,
) -> str:
    blob = decode_text(ciphertext)
    data = decrypt_bytes(blob, password, keyfile_bytes=keyfile_bytes)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DecryptError(
            "Entschluesselt, aber Ergebnis ist kein gueltiger UTF-8 Text."
        ) from exc


# ---------------------------------------------------------------------------
#   Datei-API
# ---------------------------------------------------------------------------

ENY_FILE_SUFFIX = ".eny"


def _atomic_write(out_path: str, data: bytes, overwrite: bool) -> None:
    """
    Schreibt 'data' atomar nach out_path. Ohne overwrite=True wird eine bereits
    existierende Datei NICHT angetastet (Schutz vor Datenverlust). Bei Fehlern
    bleibt die Zieldatei unveraendert (Schreiben in Temp + os.replace).
    """
    if not overwrite and os.path.exists(out_path):
        raise EnyError(f"Zieldatei existiert bereits (overwrite=False): {out_path}")
    directory = os.path.dirname(os.path.abspath(out_path))
    fd, tmp = tempfile.mkstemp(prefix=".eny_tmp_", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, out_path)  # atomar
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def encrypt_file(
    in_path: str,
    out_path: Optional[str],
    password: str,
    *,
    cipher_id: int = CIPHER_CHACHA,
    kdf_id: Optional[int] = None,
    level: str = DEFAULT_LEVEL,
    compress: bool = True,
    keyfile_bytes: Optional[bytes] = None,
    overwrite: bool = False,
) -> str:
    with open(in_path, "rb") as fh:
        data = fh.read()
    blob = encrypt_bytes(
        data, password,
        cipher_id=cipher_id, kdf_id=kdf_id, level=level,
        compress=compress, keyfile_bytes=keyfile_bytes,
    )
    if out_path is None:
        out_path = in_path + ENY_FILE_SUFFIX
    _atomic_write(out_path, blob, overwrite)
    return out_path


def decrypt_file(
    in_path: str,
    out_path: Optional[str],
    password: str,
    *,
    keyfile_bytes: Optional[bytes] = None,
    overwrite: bool = False,
) -> str:
    with open(in_path, "rb") as fh:
        blob = fh.read()
    data = decrypt_bytes(blob, password, keyfile_bytes=keyfile_bytes)
    if out_path is None:
        if in_path.endswith(ENY_FILE_SUFFIX):
            out_path = in_path[: -len(ENY_FILE_SUFFIX)]
        else:
            out_path = in_path + ".dec"
    _atomic_write(out_path, data, overwrite)
    return out_path


# ---------------------------------------------------------------------------
#   Passwort: Generator + Staerke-Schaetzung
# ---------------------------------------------------------------------------

_PW_LOWER = "abcdefghijkmnopqrstuvwxyz"
_PW_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_PW_DIGITS = "23456789"
_PW_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?/"


def generate_password(length: int = 24, *, use_symbols: bool = True) -> str:
    """Erzeugt ein kryptographisch sicheres Zufallspasswort (secrets)."""
    if length < 8:
        length = 8
    pool = _PW_LOWER + _PW_UPPER + _PW_DIGITS + (_PW_SYMBOLS if use_symbols else "")
    # mindestens je 1 aus jeder Klasse fuer gute Mischung
    required = [
        secrets.choice(_PW_LOWER),
        secrets.choice(_PW_UPPER),
        secrets.choice(_PW_DIGITS),
    ]
    if use_symbols:
        required.append(secrets.choice(_PW_SYMBOLS))
    rest = [secrets.choice(pool) for _ in range(length - len(required))]
    chars = required + rest
    # Fisher-Yates Shuffle mit secrets
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def estimate_strength(password: str) -> dict:
    """
    Grobe, konservative Entropie-Schaetzung (Bits) + Label.
    Kein Ersatz fuer zxcvbn, aber ein nuetzlicher Indikator.
    """
    if not password:
        return {"bits": 0.0, "label": "leer", "score": 0}
    pool = 0
    if any(c.islower() and c.isascii() for c in password):
        pool += 26
    if any(c.isupper() and c.isascii() for c in password):
        pool += 26
    if any(c.isdigit() and c.isascii() for c in password):
        pool += 10
    if any((not c.isalnum()) and c.isascii() for c in password):
        pool += 32
    # Nicht-ASCII: grosse Buchstaben-Alphabete (CJK etc.) + sonstige Symbole/Emoji
    if any(c.isalpha() and not c.isascii() for c in password):
        pool += 2000
    if any((not c.isalpha()) and not c.isascii() for c in password):
        pool += 1000
    pool = max(pool, 1)
    import math
    bits = len(password) * math.log2(pool)

    # Abzuege fuer offensichtliche Schwaechen
    unique = len(set(password))
    if unique <= 2:
        bits *= 0.4
    elif unique <= 4:
        bits *= 0.7
    lowered = password.lower()
    common = ("password", "passwort", "1234", "qwert", "qwertz", "admin", "hallo", "letmein")
    if any(c in lowered for c in common):
        bits = min(bits, 20.0)

    if bits < 28:
        label, score = "sehr schwach", 0
    elif bits < 40:
        label, score = "schwach", 1
    elif bits < 60:
        label, score = "okay", 2
    elif bits < 80:
        label, score = "stark", 3
    else:
        label, score = "sehr stark", 4
    return {"bits": round(bits, 1), "label": label, "score": score}


# ---------------------------------------------------------------------------
#   Info / Inspektion
# ---------------------------------------------------------------------------

def inspect(container_or_text) -> dict:
    """Liest die Metadaten eines Containers, ohne zu entschluesseln."""
    if isinstance(container_or_text, str):
        blob = decode_text(container_or_text)
    else:
        blob = container_or_text
    header, offset = _parse_header(blob)
    return {
        "version": header.version,
        "kdf": KDF_NAMES.get(header.kdf_id, f"#{header.kdf_id}"),
        "kdf_params": header.kdf_params,
        "cipher": CIPHER_NAMES.get(header.cipher_id, f"#{header.cipher_id}"),
        "compressed": bool(header.flags & FLAG_COMPRESSED),
        "salt_hex": header.salt.hex(),
        "nonces": [n.hex() for n in header.nonces],
        "header_len": offset,
        "ciphertext_len": len(blob) - offset,
        "total_len": len(blob),
    }


def capabilities() -> dict:
    return {
        "cryptography": HAVE_CRYPTOGRAPHY,
        "argon2": HAVE_ARGON2,
        "default_kdf": KDF_NAMES[_choose_default_kdf()],
        "ciphers": list(CIPHER_NAMES.values()),
    }


# ---------------------------------------------------------------------------
#   Self-Test (python eny_core.py)
# ---------------------------------------------------------------------------

def self_test(verbose: bool = True) -> bool:
    results: list[tuple[str, bool, str]] = []

    def check(name, fn):
        try:
            fn()
            results.append((name, True, ""))
        except Exception as exc:  # noqa: BLE001
            results.append((name, False, f"{type(exc).__name__}: {exc}"))

    samples = [
        "Hallo Welt!",
        "Umlaute: äöüÄÖÜß – Emoji: 🔐🚀 – CJK: 你好世界",
        "",  # leer
        "A" * 5000,  # gross
        "x",  # winzig
    ]

    kdfs = [KDF_SCRYPT, KDF_PBKDF2]
    if HAVE_ARGON2:
        kdfs.append(KDF_ARGON2ID)
    ciphers = [CIPHER_CHACHA]
    if HAVE_CRYPTOGRAPHY:
        ciphers = [CIPHER_CHACHA, CIPHER_AESGCM, CIPHER_CASCADE]

    def roundtrip_all():
        for kdf in kdfs:
            for cip in ciphers:
                for enc in ENCODINGS:
                    for msg in samples:
                        ct = encrypt_text(
                            msg, "Korrekt-Pferd-Batterie-Heftklammer!",
                            cipher_id=cip, kdf_id=kdf, level="fast", encoding=enc,
                        )
                        out = decrypt_text(ct, "Korrekt-Pferd-Batterie-Heftklammer!")
                        assert out == msg, f"Roundtrip fail kdf={kdf} cip={cip} enc={enc}"

    def wrong_password_fails():
        ct = encrypt_text("geheim", "richtig", level="fast")
        try:
            decrypt_text(ct, "falsch")
        except DecryptError:
            return
        raise AssertionError("Falsches Passwort wurde faelschlich akzeptiert!")

    def tamper_detected():
        blob = bytearray(encrypt_bytes(b"sensible daten", "pw", level="fast"))
        blob[-1] ^= 0x01  # ein Bit im Tag kippen
        try:
            decrypt_bytes(bytes(blob), "pw")
        except DecryptError:
            return
        raise AssertionError("Manipulation wurde NICHT erkannt!")

    def header_tamper_detected():
        blob = bytearray(encrypt_bytes(b"daten", "pw", cipher_id=CIPHER_CHACHA, level="fast"))
        # flags-Byte (Index 5) manipulieren -> AAD passt nicht mehr
        blob[5] ^= 0x01
        try:
            decrypt_bytes(bytes(blob), "pw")
        except (DecryptError, DecryptError):
            return
        except Exception:
            return
        raise AssertionError("Header-Manipulation wurde NICHT erkannt!")

    def keyfile_required():
        kf = os.urandom(64)
        blob = encrypt_bytes(b"top secret", "pw", level="fast", keyfile_bytes=kf)
        # ohne Keyfile -> Fehler
        try:
            decrypt_bytes(blob, "pw")
        except DecryptError:
            pass
        else:
            raise AssertionError("Keyfile war nicht noetig!")
        # mit Keyfile -> ok
        out = decrypt_bytes(blob, "pw", keyfile_bytes=kf)
        assert out == b"top secret"

    def encoding_roundtrip():
        blob = encrypt_bytes(b"abc", "pw", level="fast")
        for enc in ENCODINGS:
            txt = encode_text(blob, enc)
            assert decode_text(txt) == blob, f"Encoding {enc} roundtrip fail"

    def generator_quality():
        pw = generate_password(32)
        assert len(pw) == 32
        st = estimate_strength(pw)
        assert st["score"] >= 3, f"Generiertes Passwort zu schwach: {st}"

    def malformed_params_rejected():
        base = encrypt_bytes(b"x", "pw", cipher_id=CIPHER_CHACHA, kdf_id=KDF_SCRYPT, level="fast")
        # absurde scrypt-Kosten (log2_n=255) -> FormatError, OHNE riesige Allokation
        b = bytearray(base); b[9] = 255
        try:
            decrypt_bytes(bytes(b), "pw")
        except FormatError:
            pass
        else:
            raise AssertionError("absurde KDF-Parameter wurden nicht abgelehnt")
        # unbekannte Cipher-ID
        b = bytearray(base); b[7] = 99
        try:
            decrypt_bytes(bytes(b), "pw")
        except FormatError:
            pass
        else:
            raise AssertionError("unbekannte Cipher-ID nicht abgelehnt")
        # Cipher/Nonce-Mismatch (chacha -> cascade, aber nur 1 Nonce) -> kein roher IndexError
        b = bytearray(base); b[7] = CIPHER_CASCADE
        try:
            decrypt_bytes(bytes(b), "pw")
        except FormatError:
            pass
        else:
            raise AssertionError("Nonce/Cipher-Mismatch nicht abgelehnt")

    def truncated_rejected():
        base = encrypt_bytes(b"hallo", "pw", level="fast")
        for cut in (3, 7, 12, len(base) - 1):
            try:
                decrypt_bytes(base[:cut], "pw")
            except EnyError:
                pass
            else:
                raise AssertionError(f"abgeschnittener Container (cut={cut}) nicht abgelehnt")

    def file_roundtrip_and_overwrite():
        import os as _os
        import tempfile as _tf
        d = _tf.mkdtemp(prefix="eny_test_")
        p = _os.path.join(d, "secret.txt")
        payload = b"Dateiinhalt 123 \xff\x00\x10 binaer"
        try:
            with open(p, "wb") as f:
                f.write(payload)
            enc = encrypt_file(p, None, "pw", level="fast")
            assert enc.endswith(".eny")
            # Overwrite-Schutz: erneutes Schreiben auf existierende Datei ohne overwrite -> Fehler
            try:
                encrypt_file(p, enc, "pw", level="fast")
            except EnyError:
                pass
            else:
                raise AssertionError("Overwrite-Schutz greift nicht")
            # mit overwrite=True erlaubt
            encrypt_file(p, enc, "pw", level="fast", overwrite=True)
            out = _os.path.join(d, "restored.txt")
            decrypt_file(enc, out, "pw")
            with open(out, "rb") as f:
                assert f.read() == payload, "Datei-Roundtrip-Inhalt falsch"
        finally:
            for fp in _os.listdir(d):
                try:
                    _os.remove(_os.path.join(d, fp))
                except OSError:
                    pass
            try:
                _os.rmdir(d)
            except OSError:
                pass

    def unicode_strength():
        st = estimate_strength("日本語パスワードです")
        assert st["bits"] > 0, f"CJK-Passwort faelschlich als 0 Bit bewertet: {st}"
        assert estimate_strength("🔐🚀🌟🎲🛡")["bits"] > 0

    check("Roundtrip (alle KDFs/Cipher/Encodings/Samples)", roundtrip_all)
    check("Falsches Passwort wird abgelehnt", wrong_password_fails)
    check("Manipulation am Ciphertext erkannt", tamper_detected)
    check("Manipulation am Header erkannt", header_tamper_detected)
    check("Keyfile ist erforderlich", keyfile_required)
    check("Encoding-Roundtrip (base64/hex/bitmorse)", encoding_roundtrip)
    check("Passwort-Generator-Qualitaet", generator_quality)
    check("Manipulierte/absurde Parameter -> FormatError (DoS-Schutz)", malformed_params_rejected)
    check("Abgeschnittene Container werden sauber abgelehnt", truncated_rejected)
    check("Datei-Roundtrip + Overwrite-Schutz", file_roundtrip_and_overwrite)
    check("Unicode-Passwortstaerke > 0", unicode_strength)

    ok = all(r[1] for r in results)
    if verbose:
        print("=" * 62)
        print(" eny_core Self-Test")
        print("=" * 62)
        caps = capabilities()
        print(f" cryptography : {caps['cryptography']}")
        print(f" argon2id     : {caps['argon2']}")
        print(f" default KDF  : {caps['default_kdf']}")
        print("-" * 62)
        for name, passed, detail in results:
            mark = "OK  " if passed else "FAIL"
            line = f" [{mark}] {name}"
            if detail:
                line += f"\n        -> {detail}"
            print(line)
        print("-" * 62)
        print(" ERGEBNIS:", "ALLE TESTS BESTANDEN" if ok else "FEHLER GEFUNDEN")
        print("=" * 62)
    return ok


# ========================================================================
#   NAMESPACE-BINDUNG
# ========================================================================

# Modul-Namespace als 'core'/'eny_core' verfuegbar machen, damit die aus den
# Originalmodulen uebernommenen 'core.<name>'-Aufrufe weiterhin funktionieren.
core = sys.modules[__name__]
eny_core = core


# ========================================================================
#   TERMINAL-MODUS  (urspruenglich eny_cli.py)
# ========================================================================

# -*- coding: utf-8 -*-
"""
eny_cli  ·  enyripter v3  ·  Terminal-Modus
===========================================

OP-Style Hacker-Terminal mit ECHTER, passwortbasierter Verschluesselung
(ChaCha20-Poly1305 / AES-256-GCM / Cascade, Argon2id/scrypt) aus eny_core.

Starten:  python enyrpter3.py --cli      (oder Modus-Auswahl im Launcher)
Direkt :  python eny_cli.py
"""


import os
import sys
import time
import random
import getpass


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


def run_cli():
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


# ========================================================================
#   GUI-MODUS  (urspruenglich eny_gui.py)
# ========================================================================

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


import os
import queue
import random
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox



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


def run_gui():
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


# ========================================================================
#   LAUNCHER  (Modus-Auswahl)
# ========================================================================

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
    here_dir = os.path.dirname(here)
    _safe_print("Installiere PyInstaller (falls noetig) ...")
    subprocess.call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    _safe_print("Baue enyripter.exe (kann 1-2 Minuten dauern) ...")
    args = [
        sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole",
        "--name", "enyripter", "--collect-all", "cryptography",
    ]
    # App-Icon einbetten, falls icon.ico daneben liegt (wird aus bild.png erzeugt)
    icon = os.path.join(here_dir, "icon.ico")
    if os.path.exists(icon):
        args += ["--icon", icon]
        _safe_print("Verwende Icon: %s" % icon)
    args.append(here)
    rc = subprocess.call(args)
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
