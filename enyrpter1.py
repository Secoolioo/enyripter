# -*- coding: utf-8 -*-

"""
KRASSE BIT-MORSE-BINÄR VERSCHLÜSSELUNG
Mit OP-Style Terminal-UI im Encryption-Look.
"""

import os
import sys
import time
import pyperclip
import random

# ==========================
#   ANSI-FARBEN & STILE
# ==========================

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

BG_BLACK = "\033[40m"

# ==========================
#   HILFSFUNKTIONEN (SYSTEM)
# ==========================


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def slow_print(text, delay=0.01):
    """Zeichenweise drucken für Hacker-Feeling."""
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def loading_bar(prefix="Processing", length=30, duration=0.7, color=FG_GREEN):
    """Kurzer animierter Fortschrittsbalken."""
    steps = length
    total_time = duration
    step_time = total_time / steps

    sys.stdout.write(color + BOLD + prefix + " [" + RESET)
    sys.stdout.flush()
    for i in range(steps):
        sys.stdout.write(color + "#" + RESET)
        sys.stdout.flush()
        time.sleep(step_time)
    sys.stdout.write(color + BOLD + "] DONE" + RESET + "\n")
    sys.stdout.flush()


def loading_spinner(text="Verarbeite", duration=0.6, color=FG_CYAN):
    """Kurzer Spinner (max ~0.6s)."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start = time.time()
    i = 0
    while time.time() - start < duration:
        frame = frames[i % len(frames)]
        sys.stdout.write(f"\r{color}{frame} {text}...{RESET}")
        sys.stdout.flush()
        time.sleep(0.07)
        i += 1
    sys.stdout.write("\r" + " " * (len(text) + 10) + "\r")
    sys.stdout.flush()


def matrix_noise_line(width=60):
    """Eine Zeile pseudo-Matrix-Noise."""
    chars = "01"
    return "".join(random.choice(chars) for _ in range(width))


# ==========================
#   TEXT ↔ BINÄR (UTF-8)
# ==========================


def text_to_binary(text: str) -> str:
    data = text.encode("utf-8")
    return "".join(f"{byte:08b}" for byte in data)


def binary_to_text(binary: str) -> str:
    binary = "".join(binary.split())
    if not binary:
        raise ValueError("Leere Binär-Eingabe.")
    if any(c not in "01" for c in binary):
        raise ValueError("Binärtext darf nur 0 und 1 enthalten.")
    if len(binary) % 8 != 0:
        raise ValueError(f"Binärtext ist unvollständig. Länge: {len(binary)} Bits (kein Vielfaches von 8).")

    bytes_list = []
    for i in range(0, len(binary), 8):
        byte_bits = binary[i:i + 8]
        bytes_list.append(int(byte_bits, 2))
    data = bytes(bytes_list)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Die Binärdaten ergeben keinen gültigen UTF-8 Text (vermutlich beschädigt).")

# ==========================
#   BINÄR ↔ "BIT-MORSE"
# ==========================


def binary_to_bitmorse(binary: str) -> str:
    binary = "".join(binary.split())
    if not binary:
        raise ValueError("Leere Binärdaten.")
    if any(c not in "01" for c in binary):
        raise ValueError("Binärdaten dürfen nur 0 und 1 enthalten.")

    symbols = []
    for bit in binary:
        symbols.append("." if bit == "0" else "-")
    return " ".join(symbols)


def bitmorse_to_binary(bitmorse: str) -> str:
    parts = [p for p in bitmorse.strip().split(" ") if p != ""]
    if not parts:
        raise ValueError("Leerer Bit-Morse-String.")

    bits = []
    for s in parts:
        if s == ".":
            bits.append("0")
        elif s == "-":
            bits.append("1")
        else:
            raise ValueError(f"Ungültiges Bit-Morse-Symbol: {repr(s)} (erwartet '.' oder '-')")
    return "".join(bits)

# ==========================
#   STRING REVERSE
# ==========================


def reverse_string(s: str) -> str:
    return s[::-1]

# ==========================
#   KRASSE VER-/ENTSCHLÜSSELUNG
# ==========================


def encrypt_message(plaintext: str) -> str:
    """
    1) Text (UTF-8) → Binär (b1)
    2) b1 → Bit-Morse (m1)
    3) m1 → reverse String (m2)
    4) m2 → Binär (b2)
    5) b2 → reverse (b3) = Cipher
    """
    b1 = text_to_binary(plaintext)
    m1 = binary_to_bitmorse(b1)
    m2 = reverse_string(m1)
    b2 = text_to_binary(m2)
    b3 = reverse_string(b2)
    return b3


def decrypt_message(cipher_binary: str) -> str:
    """
    1) b3 → reverse (b2)
    2) b2 → Text (m2)
    3) m2 → reverse (m1)
    4) m1 → Binär (b1)
    5) b1 → Text (UTF-8)
    """
    b3 = "".join(cipher_binary.split())
    if not b3:
        raise ValueError("Leere Eingabe beim Entschlüsseln.")
    if any(c not in "01" for c in b3):
        raise ValueError("Binärtext darf nur 0 und 1 enthalten.")

    b2 = reverse_string(b3)
    m2 = binary_to_text(b2)
    m1 = reverse_string(m2)
    b1 = bitmorse_to_binary(m1)
    plaintext = binary_to_text(b1)
    return plaintext

# ==========================
#   OP-UI FUNKTIONEN
# ==========================


def print_banner():
    banner = f"""
{FG_GREEN}{BOLD}    ██████╗ ██╗████████╗     ███╗   ███╗ ██████╗ ██████╗ ███████╗
    ██╔══██╗██║╚══██╔══╝     ████╗ ████║██╔═══██╗██╔══██╗██╔════╝
    ██████╔╝██║   ██║        ██╔████╔██║██║   ██║██████╔╝█████╗  
    ██╔═══╝ ██║   ██║        ██║╚██╔╝██║██║   ██║██╔══██╗██╔══╝  
    ██║     ██║   ██║   ██╗  ██║ ╚═╝ ██║╚██████╔╝██║  ██║███████╗
    ╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝{RESET}
{FG_CYAN}{DIM}                     BIT·MORSE·BINARY ENCRYPTION SUITE ~hofa{RESET}
"""
    print(banner)


def print_subtitle(text):
    line = f"{FG_GREEN}{'-' * 10}{RESET} {FG_CYAN}{text}{RESET} {FG_GREEN}{'-' * 10}{RESET}"
    print(line)


def intro_animation():
    clear_screen()
    print_banner()
    slow_print(FG_GREY + DIM + "Booting encryption core..." + RESET, delay=0.03)
    for _ in range(3):
        print(FG_GREEN + DIM + matrix_noise_line(60) + RESET)
        time.sleep(0.1)
    loading_bar(prefix="Initializing ciphers", duration=0.7, color=FG_CYAN)
    time.sleep(0.2)


def print_menu():
    print()
    print_subtitle("MAIN MENU")
    print(f"{FG_YELLOW}[1]{RESET} {FG_WHITE}Nachricht verschlüsseln{RESET}")
    print(f"{FG_YELLOW}[2]{RESET} {FG_WHITE}Nachricht entschlüsseln{RESET}")
    print(f"{FG_YELLOW}[3]{RESET} {FG_WHITE}Beenden{RESET}")
    print(FG_GREEN + "-" * 40 + RESET)


def encrypt_ui():
    clear_screen()
    print_banner()
    print_subtitle("ENCRYPTION MODE")
    print(FG_WHITE + "Klartext eingeben (beliebiger deutscher Text):" + RESET)
    plaintext = input(FG_CYAN + "> " + RESET)

    try:
        print()
        loading_spinner("Analyzing plaintext", duration=0.5, color=FG_CYAN)
        loading_bar("Transforming to binary", duration=0.4, color=FG_GREEN)
        loading_bar("Routing through bit-morse core", duration=0.4, color=FG_MAGENTA)
        loading_spinner("Finalizing cipher", duration=0.4, color=FG_YELLOW)

        cipher = encrypt_message(plaintext)
    except ValueError as e:
        print()
        print(FG_RED + BOLD + "[FEHLER]" + RESET)
        print(FG_RED + "  " + str(e) + RESET)
        input(FG_GREY + "\nWeiter mit [Enter]..." + RESET)
        return

    print()
    print_subtitle("CIPHER OUTPUT (BINARY)")
    print(FG_GREEN + BOLD + cipher + RESET)
    print(FG_GREEN + "-" * 60 + RESET)

    # Kopieren in Zwischenablage
    try:
        pyperclip.copy(cipher)
        print(FG_CYAN + "Hinweis: Cipher wurde in die Zwischenablage kopiert." + RESET)
    except pyperclip.PyperclipException:
        print(FG_YELLOW + "Warnung: Konnte nicht in die Zwischenablage kopieren." + RESET)

    print()
    print(FG_GREY + DIM + "Tipp: Speichere diesen Binärstring sicher, er ist dein Schlüssel zum Klartext." + RESET)
    input(FG_GREY + "\nWeiter mit [Enter]..." + RESET)


def decrypt_ui():
    clear_screen()
    print_banner()
    print_subtitle("DECRYPTION MODE")
    print(FG_WHITE + "Binärtext eingeben (nur 0 und 1, Leerzeichen egal):" + RESET)
    cipher = input(FG_CYAN + "> " + RESET)

    try:
        print()
        loading_spinner("Validating cipher", duration=0.5, color=FG_CYAN)
        loading_bar("Decoding binary layers", duration=0.4, color=FG_GREEN)
        loading_bar("Unfolding bit-morse pattern", duration=0.4, color=FG_MAGENTA)
        loading_spinner("Reconstructing plaintext", duration=0.4, color=FG_YELLOW)

        plaintext = decrypt_message(cipher)
    except ValueError as e:
        print()
        print(FG_RED + BOLD + "[FEHLER]" + RESET)
        print(FG_RED + "  " + str(e) + RESET)
        input(FG_GREY + "\nWeiter mit [Enter]..." + RESET)
        return

    print()
    print_subtitle("DECRYPTED PLAINTEXT")
    print(FG_WHITE + BOLD + plaintext + RESET)
    print(FG_GREEN + "-" * 60 + RESET)
    input(FG_GREY + "\nWeiter mit [Enter]..." + RESET)


# ==========================
#   MAIN LOOP
# ==========================


def main():
    intro_animation()

    while True:
        print_menu()
        choice = input(FG_CYAN + "Auswahl (1-3): " + RESET).strip()

        if choice == "1":
            encrypt_ui()
        elif choice == "2":
            decrypt_ui()
        elif choice == "3":
            clear_screen()
            print_banner()
            slow_print(FG_GREY + DIM + "Shutting down encryption core..." + RESET, delay=0.03)
            for _ in range(2):
                print(FG_GREEN + DIM + matrix_noise_line(60) + RESET)
                time.sleep(0.1)
            print(FG_CYAN + BOLD + "Goodbye, Operator." + RESET)
            print()
            break
        else:
            print(FG_RED + "Ungültige Auswahl. Bitte 1, 2 oder 3 eingeben." + RESET)
            time.sleep(0.8)
            clear_screen()
            print_banner()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n" + FG_RED + "Abbruch durch Benutzer." + RESET)
        sys.exit(0)
