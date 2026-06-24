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

from __future__ import annotations

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


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
