# -*- coding: utf-8 -*-
"""
eny_portable  ·  Das "Gegenprogramm" zu enyripter v3
=====================================================

Ein EIGENSTAENDIGES Ein-Datei-Werkzeug, das ENY3-Container ver- und
entschluesselt, OHNE die anderen enyripter-Module zu brauchen. Es haengt nur
von der Standardbibliothek und 'cryptography' ab (Argon2 optional).

Damit ist bewiesen: Wer das (offen dokumentierte) Format kennt UND das Passwort
hat, kann Nachrichten entschluesseln — ganz ohne das Haupt-Tool. Wer das
Passwort NICHT hat, kann es nicht (das ist der Sinn echter Verschluesselung).

Benutzung:
    python eny_portable.py dec               # Cipher von stdin, Passwort-Abfrage
    python eny_portable.py dec -i geheim.txt
    echo "<cipher>" | python eny_portable.py dec
    python eny_portable.py enc -m "Hallo"    # verschluesseln (Cipher nach stdout)
    python eny_portable.py info              # Container-Metadaten anzeigen

Optionen: -p/--password, -k/--keyfile, --cipher chacha|aes|cascade,
          --level fast|strong|paranoid, --encoding base64|hex|bitmorse
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import secrets
import struct
import sys
import unicodedata
import zlib

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.exceptions import InvalidTag

try:
    from argon2.low_level import hash_secret_raw, Type as _Argon2Type
    HAVE_ARGON2 = True
except Exception:
    HAVE_ARGON2 = False

# ------------------------------------------------------------------ Format
MAGIC = b"ENY3"
VERSION = 1
FLAG_COMPRESSED = 0x01
KDF_SCRYPT, KDF_ARGON2ID, KDF_PBKDF2 = 1, 2, 3
CIPHER_CHACHA, CIPHER_AESGCM, CIPHER_CASCADE = 1, 2, 3
NONCE_LEN, SALT_LEN = 12, 16

CIPHER_IDS = {"chacha": CIPHER_CHACHA, "aes": CIPHER_AESGCM, "cascade": CIPHER_CASCADE}
CIPHER_NAMES = {CIPHER_CHACHA: "chacha20-poly1305", CIPHER_AESGCM: "aes-256-gcm",
                CIPHER_CASCADE: "cascade(chacha->aes)"}
KDF_NAMES = {KDF_SCRYPT: "scrypt", KDF_ARGON2ID: "argon2id", KDF_PBKDF2: "pbkdf2"}

LEVELS = {
    "fast":     {"scrypt": (14, 8, 1), "argon2id": (2, 64 * 1024, 1), "pbkdf2": 200_000},
    "strong":   {"scrypt": (15, 8, 1), "argon2id": (3, 256 * 1024, 2), "pbkdf2": 600_000},
    "paranoid": {"scrypt": (17, 8, 1), "argon2id": (4, 512 * 1024, 4), "pbkdf2": 1_200_000},
}

# DoS-Schutz: Obergrenzen fuer KDF-Kosten aus untrusted Containern
SCRYPT_MAX_LOG2N, SCRYPT_MAX_R, SCRYPT_MAX_P = 21, 16, 16
SCRYPT_MAX_MEM = 1 << 30
PBKDF2_MAX_ITER = 10_000_000
ARGON2_MAX_T, ARGON2_MAX_M_KIB, ARGON2_MAX_P = 16, 1 << 20, 16


class PortableError(Exception):
    pass


# ------------------------------------------------------------------ Helpers
def _norm_pw(password, keyfile_bytes):
    pw = unicodedata.normalize("NFC", password).encode("utf-8")
    if keyfile_bytes:
        return hmac.new(hashlib.sha256(keyfile_bytes).digest(), pw, hashlib.sha256).digest()
    return pw


def _pack_params(kdf_id, level):
    if kdf_id == KDF_SCRYPT:
        log2_n, r, p = LEVELS[level]["scrypt"]
        return struct.pack(">BHH", log2_n, r, p)
    if kdf_id == KDF_ARGON2ID:
        t, m, p = LEVELS[level]["argon2id"]
        return struct.pack(">IIB", t, m, p)
    return struct.pack(">I", LEVELS[level]["pbkdf2"])


def _unpack_params(kdf_id, blob):
    if kdf_id == KDF_SCRYPT:
        log2_n, r, p = struct.unpack(">BHH", blob)
        if not (1 <= log2_n <= SCRYPT_MAX_LOG2N and 1 <= r <= SCRYPT_MAX_R and 1 <= p <= SCRYPT_MAX_P):
            raise PortableError("scrypt-Parameter ausserhalb des erlaubten Bereichs.")
        return ("scrypt", log2_n, r, p)
    if kdf_id == KDF_ARGON2ID:
        t, m, p = struct.unpack(">IIB", blob)
        if not (1 <= t <= ARGON2_MAX_T and 8 <= m <= ARGON2_MAX_M_KIB and 1 <= p <= ARGON2_MAX_P):
            raise PortableError("argon2-Parameter ausserhalb des erlaubten Bereichs.")
        return ("argon2id", t, m, p)
    if kdf_id == KDF_PBKDF2:
        (it,) = struct.unpack(">I", blob)
        if not (1 <= it <= PBKDF2_MAX_ITER):
            raise PortableError("pbkdf2-iterations ausserhalb des erlaubten Bereichs.")
        return ("pbkdf2", it)
    raise PortableError(f"Unbekannte KDF-ID: {kdf_id}")


def _derive(material, salt, params, dklen):
    kind = params[0]
    if kind == "scrypt":
        _, log2_n, r, p = params
        n = 1 << log2_n
        required = 128 * r * (n + p + 2)
        if required > SCRYPT_MAX_MEM:
            raise PortableError("scrypt-Parameter verlangen zu viel Speicher.")
        return hashlib.scrypt(material, salt=salt, n=n, r=r, p=p, dklen=dklen,
                              maxmem=min(required + (1 << 20), SCRYPT_MAX_MEM))
    if kind == "argon2id":
        if not HAVE_ARGON2:
            raise PortableError("Container nutzt Argon2id, aber 'argon2-cffi' fehlt.")
        _, t, m, p = params
        return hash_secret_raw(material, salt, time_cost=t, memory_cost=m,
                               parallelism=p, hash_len=dklen, type=_Argon2Type.ID)
    _, it = params
    return hashlib.pbkdf2_hmac("sha256", material, salt, it, dklen=dklen)


def _nonce_count(cipher_id):
    return 2 if cipher_id == CIPHER_CASCADE else 1


def _key_len(cipher_id):
    return 64 if cipher_id == CIPHER_CASCADE else 32


# ------------------------------------------------------------------ Encoding
def _to_bitmorse(blob):
    bits = "".join(f"{b:08b}" for b in blob)
    sym = "".join("." if c == "0" else "-" for c in bits)
    return " ".join(sym[i:i + 8] for i in range(0, len(sym), 8))


def _from_bitmorse(text):
    cleaned = "".join(c for c in text if c in ".-")
    if len(cleaned) % 8:
        raise ValueError("Bit-Morse-Laenge kein Vielfaches von 8.")
    bits = "".join("0" if c == "." else "1" for c in cleaned)
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def encode_text(blob, encoding):
    if encoding == "base64":
        return base64.urlsafe_b64encode(blob).decode("ascii")
    if encoding == "hex":
        return blob.hex()
    if encoding == "bitmorse":
        return _to_bitmorse(blob)
    raise PortableError(f"Unbekannte Kodierung: {encoding}")


def decode_text(text):
    text = text.strip()
    if not text:
        raise PortableError("Leere Eingabe.")
    compact = "".join(text.split())
    if set(compact) <= set(".-"):
        decoders = [_from_bitmorse]
    else:
        def b64(s):
            s2 = "".join(s.split())
            return base64.urlsafe_b64decode(s2 + "=" * ((-len(s2)) % 4))
        decoders = [b64, lambda s: bytes.fromhex("".join(s.split()))]
    for dec in decoders:
        try:
            blob = dec(text)
        except Exception:
            continue
        if blob[:4] == MAGIC:
            return blob
    raise PortableError("Eingabe ist kein erkennbarer ENY3-Container.")


# ------------------------------------------------------------------ Core
def _parse(blob):
    if len(blob) < 8 or blob[:4] != MAGIC:
        raise PortableError("Kein ENY3-Container.")
    try:
        pos = 4
        version, flags, kdf_id, cipher_id = blob[pos], blob[pos + 1], blob[pos + 2], blob[pos + 3]
        pos += 4
        if version != VERSION:
            raise PortableError(f"Nicht unterstuetzte Version: {version}")
        if cipher_id not in CIPHER_NAMES:
            raise PortableError(f"Unbekannte Cipher-ID: {cipher_id}")
        kparlen = blob[pos]; pos += 1
        kpar = blob[pos:pos + kparlen]; pos += kparlen
        if len(kpar) != kparlen:
            raise PortableError("Header abgeschnitten (KDF-Parameter).")
        saltlen = blob[pos]; pos += 1
        salt = blob[pos:pos + saltlen]; pos += saltlen
        if len(salt) != saltlen:
            raise PortableError("Header abgeschnitten (Salt).")
        n_nonce = blob[pos]; pos += 1
        if n_nonce != _nonce_count(cipher_id):
            raise PortableError(f"Nonce-Anzahl {n_nonce} passt nicht zu Cipher {cipher_id}.")
        nonces = []
        for _ in range(n_nonce):
            n = blob[pos:pos + NONCE_LEN]; pos += NONCE_LEN
            if len(n) != NONCE_LEN:
                raise PortableError("Header abgeschnitten (Nonce).")
            nonces.append(n)
        params = _unpack_params(kdf_id, kpar)
    except IndexError as exc:
        raise PortableError(f"Header abgeschnitten: {exc}") from exc
    return version, flags, kdf_id, cipher_id, params, salt, nonces, blob[:pos], blob[pos:]


def encrypt(plaintext, password, *, cipher="chacha", level="strong",
            encoding="base64", compress=True, keyfile_bytes=None):
    cipher_id = CIPHER_IDS[cipher]
    kdf_id = KDF_ARGON2ID if HAVE_ARGON2 else KDF_SCRYPT
    material = _norm_pw(password, keyfile_bytes)
    data = plaintext.encode("utf-8")
    flags = 0
    if compress:
        comp = zlib.compress(data, 9)
        if len(comp) < len(data):
            data, flags = comp, flags | FLAG_COMPRESSED
    salt = secrets.token_bytes(SALT_LEN)
    kpar = _pack_params(kdf_id, level)
    nonces = [secrets.token_bytes(NONCE_LEN) for _ in range(_nonce_count(cipher_id))]
    header = bytearray(MAGIC)
    header += bytes([VERSION, flags, kdf_id, cipher_id, len(kpar)]) + kpar
    header += bytes([len(salt)]) + salt + bytes([len(nonces)])
    for n in nonces:
        header += n
    header = bytes(header)
    params = _unpack_params(kdf_id, kpar)
    key = _derive(material, salt, params, _key_len(cipher_id))
    if cipher_id == CIPHER_CHACHA:
        ct = ChaCha20Poly1305(key).encrypt(nonces[0], data, header)
    elif cipher_id == CIPHER_AESGCM:
        ct = AESGCM(key).encrypt(nonces[0], data, header)
    else:
        inner = ChaCha20Poly1305(key[:32]).encrypt(nonces[0], data, header)
        ct = AESGCM(key[32:]).encrypt(nonces[1], inner, header)
    return encode_text(header + ct, encoding)


def decrypt(ciphertext, password, *, keyfile_bytes=None):
    blob = decode_text(ciphertext)
    version, flags, kdf_id, cipher_id, params, salt, nonces, header, ct = _parse(blob)
    if not ct:
        raise PortableError("Container enthaelt keine Nutzdaten.")
    material = _norm_pw(password, keyfile_bytes)
    try:
        key = _derive(material, salt, params, _key_len(cipher_id))
    except (OverflowError, MemoryError, ValueError) as exc:
        raise PortableError(f"Ungueltige KDF-Parameter: {exc}") from exc
    try:
        if cipher_id == CIPHER_CHACHA:
            data = ChaCha20Poly1305(key).decrypt(nonces[0], ct, header)
        elif cipher_id == CIPHER_AESGCM:
            data = AESGCM(key).decrypt(nonces[0], ct, header)
        else:
            inner = AESGCM(key[32:]).decrypt(nonces[1], ct, header)
            data = ChaCha20Poly1305(key[:32]).decrypt(nonces[0], inner, header)
    except InvalidTag as exc:
        raise PortableError("Falsches Passwort/Keyfile oder Daten manipuliert.") from exc
    except IndexError as exc:
        raise PortableError(f"Beschaedigter Container: {exc}") from exc
    if flags & FLAG_COMPRESSED:
        data = zlib.decompress(data)
    return data.decode("utf-8")


def info(ciphertext):
    blob = decode_text(ciphertext)
    version, flags, kdf_id, cipher_id, params, salt, nonces, header, ct = _parse(blob)
    return {
        "version": version,
        "cipher": CIPHER_NAMES[cipher_id],
        "kdf": KDF_NAMES.get(kdf_id, f"#{kdf_id}"),
        "kdf_params": params,
        "compressed": bool(flags & FLAG_COMPRESSED),
        "salt": salt.hex(),
        "ciphertext_len": len(ct),
    }


# ------------------------------------------------------------------ CLI
def _read_keyfile(path):
    if not path:
        return None
    with open(path, "rb") as fh:
        return fh.read()


def main(argv=None):
    # stdout/stderr auf UTF-8, damit Emojis/Umlaute nie an cp1252 scheitern
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="eny_portable",
                                 description="Eigenstaendiger ENY3-Ver-/Entschluesseler (Gegenprogramm).")
    ap.add_argument("mode", choices=["enc", "dec", "info"])
    ap.add_argument("-m", "--message", help="Klartext (enc) bzw. Cipher (dec/info); sonst stdin")
    ap.add_argument("-i", "--input", help="Datei mit Klartext/Cipher")
    ap.add_argument("-p", "--password", help="Passwort (sonst sichere Abfrage)")
    ap.add_argument("-k", "--keyfile", help="optionales Keyfile")
    ap.add_argument("--cipher", choices=list(CIPHER_IDS), default="chacha")
    ap.add_argument("--level", choices=list(LEVELS), default="strong")
    ap.add_argument("--encoding", choices=["base64", "hex", "bitmorse"], default="base64")
    ap.add_argument("--no-compress", action="store_true")
    args = ap.parse_args(argv)

    if args.message is not None:
        text = args.message
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()

    try:
        kf = _read_keyfile(args.keyfile)
        if args.mode == "info":
            for k, v in info(text).items():
                print(f"{k:14}: {v}")
            return 0
        pw = args.password or getpass.getpass("Passwort: ")
        if args.mode == "enc":
            print(encrypt(text, pw, cipher=args.cipher, level=args.level,
                          encoding=args.encoding, compress=not args.no_compress,
                          keyfile_bytes=kf))
        else:
            sys.stdout.write(decrypt(text, pw, keyfile_bytes=kf))
            sys.stdout.write("\n")
        return 0
    except PortableError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
