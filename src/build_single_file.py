# -*- coding: utf-8 -*-
"""
build_single_file.py
=====================
Fuehrt eny_core.py + eny_cli.py + eny_gui.py + die Fragmente
(_frag_header.py, _frag_launch.py) zu EINER eigenstaendigen Datei zusammen:

    enyripter.pyw

Diese Einzeldatei laedt 'cryptography' bei Bedarf automatisch nach und zeigt das
GUI/Terminal-Menue. Ideal fuer GitHub (nur diese eine Datei hochladen).

Aufruf:  python build_single_file.py
"""

import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "enyripter.pyw")


def read(name):
    with io.open(os.path.join(HERE, name), "r", encoding="utf-8") as fh:
        return fh.read()


def transform_module(src, *, rename_run=None):
    """
    Bereitet ein Modul fuer das Zusammenfuehren auf:
      - entfernt 'from __future__ import annotations' (steht nur 1x ganz oben)
      - entfernt 'import eny_core as core'
      - schneidet den 'if __name__ == "__main__":'-Block am Ende ab
      - benennt optional die Top-Level-Funktion 'def run():' um
    """
    out_lines = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped == "from __future__ import annotations":
            continue
        if stripped == "import eny_core as core":
            continue
        if line.startswith('if __name__ == "__main__":'):
            break  # alles ab hier weglassen
        if rename_run and line == "def run():":
            line = "def %s():" % rename_run
        out_lines.append(line)
    return "\n".join(out_lines).rstrip() + "\n"


def banner(text):
    bar = "# " + "=" * 72
    return "\n\n%s\n#   %s\n%s\n\n" % (bar, text, bar)


def main():
    header = read("_frag_header.py")                       # docstring + future + bootstrap
    core = transform_module(read("eny_core.py"))           # kein run(), kein eny_core-Import
    cli = transform_module(read("eny_cli.py"), rename_run="run_cli")
    gui = transform_module(read("eny_gui.py"), rename_run="run_gui")
    launch = read("_frag_launch.py")

    # Sanity-Checks
    assert "def run_cli():" in cli, "CLI run() wurde nicht umbenannt"
    assert "def run_gui():" in gui, "GUI run() wurde nicht umbenannt"
    assert "import eny_core" not in cli and "import eny_core" not in gui, "eny_core-Import nicht entfernt"
    assert "from __future__" not in core and "from __future__" not in cli and "from __future__" not in gui

    # Kern-Konstanten duerfen NICHT von spaeteren Sektionen ueberschrieben werden
    # (sonst z.B. VERSION=1 (Format) vs. "3.0" (App) -> Krypto-Crash).
    for const in ("VERSION = ", "MAGIC = ", "NONCE_LEN = ", "SALT_LEN = ", "DEFAULT_LEVEL = "):
        for frag_name, frag in (("cli", cli), ("gui", gui), ("launch", launch)):
            for ln in frag.splitlines():
                assert not ln.startswith(const), (
                    "Kollision: '%s' wird in Sektion '%s' neu gesetzt und ueberschreibt den Kern."
                    % (const.strip(), frag_name)
                )

    bind = (
        "# Modul-Namespace als 'core'/'eny_core' verfuegbar machen, damit die aus den\n"
        "# Originalmodulen uebernommenen 'core.<name>'-Aufrufe weiterhin funktionieren.\n"
        "core = sys.modules[__name__]\n"
        "eny_core = core\n"
    )

    parts = [
        header.rstrip() + "\n",
        banner("KRYPTO-KERN  (urspruenglich eny_core.py)"),
        core,
        banner("NAMESPACE-BINDUNG"),
        bind,
        banner("TERMINAL-MODUS  (urspruenglich eny_cli.py)"),
        cli,
        banner("GUI-MODUS  (urspruenglich eny_gui.py)"),
        gui,
        banner("LAUNCHER  (Modus-Auswahl)"),
        launch.rstrip() + "\n",
    ]
    merged = "".join(parts)

    with io.open(OUT, "w", encoding="utf-8") as fh:
        fh.write(merged)

    lines = merged.count("\n") + 1
    size = len(merged.encode("utf-8"))
    print("OK -> %s" % OUT)
    print("   %d Zeilen, %d Bytes" % (lines, size))


if __name__ == "__main__":
    main()
