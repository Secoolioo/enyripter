# enyripter v3 🔐

Ein persönliches Verschlüsselungs-Tool mit **echter, moderner Kryptografie** — wahlweise
als **animiertes GUI** ("ENCRYPT-OS") oder als **Hacker-Terminal**.

> **Ein Klick, zwei Welten:** beim Start wählst du *mit GUI* oder *ohne GUI (Terminal)*.

---

## ⚠️ Wichtig: Was hier anders ist als bei v1/v2

v1 und v2 haben Text nur **kodiert** (Text → Binär → Bit-Morse → umdrehen). Das ist **keine
Verschlüsselung**: Wer den Code kennt, dreht es in Sekunden zurück — es gibt keinen geheimen
Schlüssel.

Und *"SHA-2048"* gibt es nicht: **SHA ist eine Einweg-Hashfunktion** und lässt sich
grundsätzlich **gar nicht entschlüsseln** (die größten echten Varianten sind SHA-512 / SHA3-512).

**v3 macht es richtig.** Die Sicherheit kommt aus deinem **Passwort** plus geprüften
Verfahren — *nicht* aus Geheimhaltung des Algorithmus (Kerckhoffs-Prinzip). Mit einem
starken Passwort ist eine Nachricht ohne dieses Passwort **praktisch nicht** zu entschlüsseln,
selbst wenn jemand den kompletten Quellcode hat.

---

## ✨ Features

- **Echte authentifizierte Verschlüsselung (AEAD):**
  - `ChaCha20-Poly1305` (Standard, schnell & sehr sicher)
  - `AES-256-GCM`
  - `Cascade` — ChaCha20 **und** AES-256 übereinander, zwei unabhängige Schlüssel (Maximum)
- **Schlüsselableitung (KDF):** `Argon2id` (falls installiert) → sonst `scrypt` → sonst `PBKDF2`
  - drei Stufen: `fast` / `strong` / `paranoid`
- **Manipulationsschutz:** zufälliges Salt + Nonce pro Nachricht, Auth-Tag, Header als AAD
  authentifiziert → jede Veränderung wird beim Entschlüsseln erkannt.
- **Drei Ausgabe-Kodierungen:** `base64` (kompakt), `hex`, `bitmorse` (die Signatur-Optik `. -`)
- **Datei-Verschlüsselung** (beliebige Dateien → `.eny`)
- **Keyfile-Unterstützung** (Passwort *und* Datei nötig)
- **zlib-Kompression** vor der Verschlüsselung (optional)
- **Passwort-Generator** (kryptografisch sicher) + **Stärke-Anzeige**
- **Self-Test** (Round-Trips, Manipulationserkennung, Keyfile, Encodings)
- **GUI:** Matrix-Rain, Glitch-Boot, Themes, Neon-Buttons, Live-Konsole, animierte Krypto-Sequenz
- **Terminal:** OP-Style Banner, Lade-Animationen, Menü, versteckte Passworteingabe

---

## 🚀 Start

Das Repo enthält genau zwei Dinge, die zählen:

| Was | Wofür |
|-----|-------|
| **`enyripter.exe`** | Einfach **doppelklicken** — läuft **ohne installiertes Python**. Es erscheint kein Terminal, sondern direkt die Auswahl **GUI** oder **Terminal**. |
| **`src/`** | Der **komplette Quellcode** (für Entwickler, zum Selber-Bauen). |

### Variante A — fertige `.exe` (am einfachsten)

`enyripter.exe` herunterladen und **doppelklicken**. Kein Python, keine Installation, kein
Download nötig — alles ist eingebaut. Es kommt sofort das Menü GUI / Terminal.

### Variante B — mit Python (Quellcode in `src/`)

Die eine, eigenständige Datei ist [`src/enyripter.pyw`](src/enyripter.pyw). Doppelklick →
kein Terminal → (falls `cryptography` fehlt, wird es **einmalig automatisch nachgeladen**) →
Menü GUI / Terminal. Oder per Kommandozeile:

```bash
python src/enyripter.pyw            # Auswahl-Fenster (GUI oder Terminal)
python src/enyripter.pyw --gui      # direkt: GUI
python src/enyripter.pyw --cli      # direkt: Terminal
python src/enyripter.pyw --selftest # Krypto-Self-Test
python src/enyripter.pyw --version
python src/enyripter.pyw --build-exe  # die enyripter.exe neu bauen (PyInstaller)
```

> Doppelklick auf `.pyw` öffnet doch eine Konsole? Dann ist `.pyw` nicht mit `pythonw.exe`
> verknüpft. Einmalig Rechtsklick → *Öffnen mit* → `pythonw.exe`. Benötigt Python ≥ 3.10.

### `.exe` selbst neu bauen

```bash
python src/enyripter.pyw --build-exe
```

Installiert bei Bedarf PyInstaller und erzeugt `dist/enyripter.exe` (~16 MB, alle
Abhängigkeiten gebündelt). Diese Datei wird dann oben als `enyripter.exe` abgelegt.

### Entwicklung

`src/enyripter.pyw` wird aus den Modulen in `src/` (`eny_core.py` / `eny_cli.py` /
`eny_gui.py` + `_frag_header.py` / `_frag_launch.py`) zusammengebaut. Nach Änderungen:

```bash
python src/build_single_file.py     # erzeugt src/enyripter.pyw neu
python src/eny_core.py              # Krypto-Self-Test
python src/test_gui_smoke.py        # GUI-Test (headless)
```

**Installation der Abhängigkeiten** (das Tool läuft auch mit nur `cryptography`):

```bash
pip install -r src/requirements.txt
```

| Paket          | Pflicht? | Wofür                                              |
|----------------|----------|----------------------------------------------------|
| `cryptography` | **ja**   | AES-GCM / ChaCha20-Poly1305                        |
| `argon2-cffi`  | nein     | stärkere KDF (sonst scrypt aus der Standardbibliothek) |
| `pyperclip`    | nein     | Zwischenablage im Terminal (GUI nutzt Tk direkt)   |
| `tkinter`      | nur GUI  | meist bei Python dabei                             |

---

## 🔒 Sicherheits-Hinweise (ehrlich)

- Die Stärke steht und fällt mit dem **Passwort**. Nutze den eingebauten Generator (≥ 20 Zeichen).
- Es gibt **keine Hintertür** und **keine Wiederherstellung**: Passwort weg = Daten weg.
  Das ist Absicht.
- `paranoid` macht die Schlüsselableitung absichtlich langsam (mehr Speicher/Zeit), um
  Brute-Force massiv zu verteuern.
- Es wurde **keine eigene Krypto erfunden** — es werden die geprüften Primitive aus der
  `cryptography`-Bibliothek (OpenSSL) und stdlib-KDFs verwendet.

---

## 📦 Das ENY3-Container-Format (für ein „Gegenprogramm")

Ein unabhängiges Programm kann Nachrichten ent-/verschlüsseln, wenn es dieses Layout kennt
und das Passwort hat. Alle Multi-Byte-Zahlen sind **Big-Endian**.

```
Offset  Größe   Feld
------  -----   ----------------------------------------------------------
0       4       MAGIC          = ASCII "ENY3"
4       1       version        = 1
5       1       flags          Bit0 (0x01) = Nutzdaten sind zlib-komprimiert
6       1       kdf_id         1=scrypt  2=argon2id  3=pbkdf2
7       1       cipher_id      1=chacha20-poly1305  2=aes-256-gcm  3=cascade
8       1       kparlen        Länge des KDF-Parameterblocks
9       *       kparams        siehe unten
...     1       saltlen        Länge des Salts (typisch 16)
...     *       salt
...     1       n_nonce        Anzahl Nonces (1; bei cascade = 2)
...     12*n    nonces         je 12 Byte
------  -----   --- ab hier: AEAD-Ausgabe (enthält den 16-Byte Auth-Tag) ---
...     *       ciphertext
```

**KDF-Parameterblock (`kparams`):**

| kdf_id | Inhalt (Big-Endian)                          |
|--------|----------------------------------------------|
| 1 scrypt   | `>BHH` = log2_n (1B), r (2B), p (2B); n = 2^log2_n |
| 2 argon2id | `>IIB` = time_cost (4B), memory_kib (4B), parallelism (1B) |
| 3 pbkdf2   | `>I`  = iterations (4B), HMAC-SHA256        |

**Ablauf Verschlüsseln:**

1. `material` = Passwort (UTF-8, NFC-normalisiert).
   Mit Keyfile: `material = HMAC-SHA256(key = SHA256(keyfile), msg = passwort_utf8)`.
2. Optional `zlib.compress` (Flag setzen, wenn es kleiner wird).
3. Schlüssel ableiten: `key = KDF(material, salt, params, dklen)`
   — `dklen = 32` (single) bzw. `64` (cascade → k1 = key[:32], k2 = key[32:]).
4. **AAD = die gesamten Header-Bytes** (Offset 0 bis Beginn ciphertext).
5. AEAD-Verschlüsselung:
   - chacha: `ChaCha20Poly1305(key).encrypt(nonce0, data, AAD)`
   - aes:    `AESGCM(key).encrypt(nonce0, data, AAD)`
   - cascade: `inner = ChaCha20Poly1305(k1).encrypt(nonce0, data, AAD)`,
     dann `out = AESGCM(k2).encrypt(nonce1, inner, AAD)`
6. Container = Header + AEAD-Ausgabe.

**Entschlüsseln** = exakt rückwärts (bei cascade zuerst AES außen, dann ChaCha innen),
anschließend ggf. `zlib.decompress`. Schlägt die Tag-Prüfung fehl → falsches Passwort
oder manipulierte Daten.

**Text-Kodierungen** des Containers:
- `base64`  : URL-sicheres Base64 (Padding kann fehlen, wird ergänzt)
- `hex`     : Hex-String
- `bitmorse`: jedes Bit → `.`(0) / `-`(1), in 8er-Gruppen mit Leerzeichen

Die Auto-Erkennung beim Entschlüsseln probiert die Kodierungen durch und akzeptiert die,
deren dekodierte Bytes mit `ENY3` beginnen.

---

## 📁 Struktur des Repos

```
enyripter.exe          ← fertige App zum Doppelklicken (kein Python nötig)
README.md
src/                   ← der komplette Quellcode
├─ enyripter.pyw       ← die eine, eigenständige Datei (Auto-Installer + Menü)
├─ build_single_file.py← baut src/enyripter.pyw aus den Modulen
├─ _frag_header.py     ← Fragment: Auto-Installer-Kopf
├─ _frag_launch.py     ← Fragment: Launcher/Chooser
├─ eny_core.py         ← Krypto-Kern + eigener Self-Test
├─ eny_gui.py          ← GUI-Modus
├─ eny_cli.py          ← Terminal-Modus
├─ enyrpter3.py        ← modularer Launcher (Entwicklung)
├─ eny_portable.py     ← „Gegenprogramm" (eigenständiger Ver-/Entschlüsseler)
├─ test_gui_smoke.py   ← GUI-Test (headless)
├─ requirements.txt    ← Abhängigkeiten (Entwicklung)
├─ bild.png / icon.ico ← App-Logo + daraus erzeugtes Icon (wird in die .exe eingebettet)
└─ enyrpter1.py / enyrpter2.py  ← alte Versionen (nur Kodierung, KEINE Verschlüsselung)
```

> Das Icon der `.exe` wird aus `src/bild.png` erzeugt (`src/icon.ico`) und beim
> `--build-exe` automatisch eingebettet — in Explorer und Taskleiste sichtbar.

### Das Gegenprogramm (`src/eny_portable.py`)

Eine **eigenständige** Datei, die das ENY3-Format unabhängig vom Haupttool
implementiert (nur stdlib + `cryptography`). Beweist: mit Format **und Passwort**
kann auch ein anderes Programm entschlüsseln — ohne Passwort niemand.

```bash
echo "<cipher>" | python src/eny_portable.py dec            # entschlüsseln (fragt Passwort)
python src/eny_portable.py enc -m "Hallo" --cipher cascade  # verschlüsseln
python src/eny_portable.py info -m "<cipher>"               # Metadaten anzeigen
```

Container von `enyripter` und `eny_portable.py` sind **vollständig
austauschbar** (in beide Richtungen getestet, inkl. Keyfile).

---

## 🧪 Tests

```bash
python src/eny_core.py          # Krypto-Self-Test (Round-Trips, Manipulation, Keyfile, ...)
python src/test_gui_smoke.py    # GUI baut sich auf + echte Encrypt→Decrypt-Runde
```
