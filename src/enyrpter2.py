# -*- coding: utf-8 -*-

"""
ENCRYPT-OS · Bit-Morse-Binary Encryption Suite · ULTRA+ CLEAN
- Vollbild "Mini-OS"
- Boot-Sequenz mit Logs
- Login (ENTER)
- Direkt Desktop (Manual Mode, keine Modus-Auswahl, kein Live-Chat)
- Desktop mit:
  - App-Dock (Encryption, System Monitor, Settings, About)
  - Encryption-App (Bit-Morse-Binary) + History
  - System Monitor (CPU/RAM + Fake Taskliste)
  - Settings (Theme, UI-Dichte, Fontgröße, Dev-Overlay)
  - System Console rechts mit Live-Logs + Command-Line
- Shutdown/Logout-Animation (ESC) mit sauberem Stop der Updates
"""

import sys
import time
import random
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import pyperclip
from datetime import datetime

BACKGROUND_IMAGE = "background.png"


# ==========================
#   LOGGING / TERMINAL
# ==========================

class UILogger:
    """
    Logger, der sowohl ins Terminal schreibt
    als auch optional in ein Text-Widget im GUI.
    """
    def __init__(self):
        self.gui_text_widget = None

    def attach_widget(self, text_widget: tk.Text):
        self.gui_text_widget = text_widget

    def detach_widget(self):
        self.gui_text_widget = None

    def log(self, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        sys.stdout.flush()
        if self.gui_text_widget is not None:
            try:
                self.gui_text_widget.insert("end", line + "\n")
                # Log-Limit: max 2000 Zeilen
                max_lines = 2000
                current = int(self.gui_text_widget.index("end-1c").split(".")[0])
                if current > max_lines:
                    self.gui_text_widget.delete("1.0", f"{current - max_lines}.0")
                self.gui_text_widget.see("end")
            except tk.TclError:
                self.gui_text_widget = None


logger = UILogger()
log = logger.log


# ==========================
#   CRYPTO CORE
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
        raise ValueError(
            f"Binärtext ist unvollständig. Länge: {len(binary)} Bits (kein Vielfaches von 8)."
        )
    bytes_list = []
    for i in range(0, len(binary), 8):
        byte_bits = binary[i:i + 8]
        bytes_list.append(int(byte_bits, 2))
    data = bytes(bytes_list)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Die Binärdaten ergeben keinen gültigen UTF-8 Text (vermutlich beschädigt).")


def binary_to_bitmorse(binary: str) -> str:
    binary = "".join(binary.split())
    if not binary:
        raise ValueError("Leere Binärdaten.")
    if any(c not in "01" for c in binary):
        raise ValueError("Binärdaten dürfen nur 0 und 1 enthalten.")
    return " ".join("." if bit == "0" else "-" for bit in binary)


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
            raise ValueError(f"Ungültiges Bit-Morse-Symbol: {repr(s)}")
    return "".join(bits)


def reverse_string(s: str) -> str:
    return s[::-1]


def encrypt_message(plaintext: str) -> str:
    log("ENCRYPTION: Pipeline gestartet.")
    b1 = text_to_binary(plaintext)
    log(f"ENCRYPTION: Klartext → Binary (Bits={len(b1)}).")
    m1 = binary_to_bitmorse(b1)
    log("ENCRYPTION: Binary → Bit-Morse.")
    m2 = reverse_string(m1)
    log("ENCRYPTION: Bit-Morse string reversed.")
    b2 = text_to_binary(m2)
    log("ENCRYPTION: Reversed Bit-Morse → Binary.")
    b3 = reverse_string(b2)
    log("ENCRYPTION: Binary reversed → Cipher.")
    return b3


def decrypt_message(cipher_binary: str) -> str:
    log("DECRYPTION: Pipeline gestartet.")
    b3 = "".join(cipher_binary.split())
    if not b3:
        raise ValueError("Leere Eingabe beim Entschlüsseln.")
    if any(c not in "01" for c in b3):
        raise ValueError("Binärtext darf nur 0 und 1 enthalten.")
    log(f"DECRYPTION: Cipher Binary length={len(b3)}.")

    b2 = reverse_string(b3)
    log("DECRYPTION: Cipher reversed.")
    m2 = binary_to_text(b2)
    log("DECRYPTION: Binary → Bit-Morse string.")
    m1 = reverse_string(m2)
    log("DECRYPTION: Bit-Morse string reversed.")
    b1 = bitmorse_to_binary(m1)
    log("DECRYPTION: Bit-Morse → Binary Klartext.")
    plaintext = binary_to_text(b1)
    log("DECRYPTION: Binary → Klartext abgeschlossen.")
    return plaintext


# ==========================
#   ENCRYPT-OS GUI
# ==========================

class EncryptOS(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("ENCRYPT-OS")
        self.attributes("-fullscreen", True)
        self.configure(bg="#000000")

        self.username = None
        self.logout_running = False
        self.alive = True  # steuert Updates / after-Schleifen

        # Settings
        self.theme = "green"           # "green", "purple", "blue"
        self.ui_density = "normal"     # "compact", "normal", "large" (nur Info)
        self.font_scale = 1.0          # 0.9, 1.0, 1.1
        self.dev_overlay = tk.BooleanVar(value=False)

        # ESC → Shutdown
        self.bind("<Escape>", self.on_escape)


        # Overlay
        self.overlay = tk.Frame(self, bg="#000000", bd=0, highlightthickness=0)
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.current_screen = None

        # Clock / Status
        self.status_clock_var = None
        self.status_text_var = None

        # System Monitor
        self.cpu_label = None
        self.ram_label = None
        self.cpu_val = 27
        self.ram_val = 41
        self.fake_tasks = []

        # Encryption history
        self.enc_history = []   # list of dicts

        # Terminal command line
        self.cmd_entry = None
        self.cmd_history = []
        self.cmd_history_index = None

        # App-Views (persistente Frames)
        self.view_encryption = None
        self.view_monitor = None
        self.view_settings = None
        self.view_about = None

        # Start
        self.show_boot_screen()

        # Resize-Handling
        self.bind("<Configure>", self._on_resize)

    # ========== Theme-Farben & Fonts ==========

    def get_accent_color(self):
        if self.theme == "green":
            return "#22C55E"
        if self.theme == "purple":
            return "#A855F7"
        if self.theme == "blue":
            return "#38BDF8"
        return "#22C55E"

    def get_panel_bg(self):
        return "#020617"

    def get_panel_border(self):
        return "#111827"

    def scaled_font(self, base_size, weight="normal", family="Consolas"):
        size = int(base_size * self.font_scale)
        if size < 6:
            size = 6
        return (family, size, weight)

    # ---------- Background ----------

    def _load_background_image(self):
        try:
            img = Image.open(BACKGROUND_IMAGE)
            self.original_bg = img
            log(f"BACKGROUND: '{BACKGROUND_IMAGE}' geladen.")
        except Exception as e:
            log(f"BACKGROUND: Fehler beim Laden des Hintergrundbildes: {e}")
            self.original_bg = None
        if self.original_bg is not None:
            self._update_background()

    def _update_background(self):
        if self.original_bg is None:
            return
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        try:
            resample_filter = Image.LANCZOS
        except AttributeError:
            resample_filter = Image.BICUBIC
        img = self.original_bg.resize((w, h), resample=resample_filter)
        self.bg_image = ImageTk.PhotoImage(img)
        if self.bg_label is None:
            self.bg_label = tk.Label(self, image=self.bg_image, bd=0)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        else:
            self.bg_label.configure(image=self.bg_image)
            self.bg_label.image = self.bg_image
        self.bg_label.lower()

    def _on_resize(self, event):
        self._update_background()

    # ---------- Helper ----------

    def clear_overlay(self):
        for child in self.overlay.winfo_children():
            child.destroy()

    # ==========================
    #   Boot / Login
    # ==========================

    def show_boot_screen(self):
        self.clear_overlay()
        self.current_screen = "boot"

        frame = tk.Frame(self.overlay, bg="#000000", bd=0, highlightthickness=0)
        frame.place(relx=0.2, rely=0.15, relwidth=0.6, relheight=0.7)

        accent = self.get_accent_color()

        title = tk.Label(
            frame,
            text="ENCRYPT-OS v1.0 · System Startup",
            font=self.scaled_font(20, "bold"),
            bg="#000000",
            fg=accent,
        )
        title.pack(pady=(20, 5))

        subtitle = tk.Label(
            frame,
            text="Initializing secure encryption environment...",
            font=self.scaled_font(10),
            bg="#000000",
            fg="#9CA3AF",
        )
        subtitle.pack(pady=(0, 20))

        self.boot_log = tk.Text(
            frame,
            height=15,
            width=80,
            bg="#020617",
            fg="#D1D5DB",
            insertbackground=accent,
            relief="solid",
            borderwidth=1,
            font=self.scaled_font(9),
        )
        self.boot_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.boot_log.configure(state="disabled")

        self.boot_status = tk.Label(
            frame,
            text="[##########----------] 50%",
            font=self.scaled_font(10),
            bg="#000000",
            fg=accent,
        )
        self.boot_status.pack(pady=(5, 10))

        steps = [
            "Mounting core partitions...",
            "Scanning encryption modules...",
            "Loading Bit-Morse engine...",
            "Calibrating entropy sources...",
            "Initializing UI subsystem...",
            "Preparing user-domain services...",
            "Finalizing boot sequence...",
        ]

        def log_boot_line(text):
            self.boot_log.configure(state="normal")
            self.boot_log.insert("end", text + "\n")
            self.boot_log.see("end")
            self.boot_log.configure(state="disabled")

        def run_steps(i=0):
            if not self.alive:
                return
            if i >= len(steps):
                self.boot_status.config(text="[####################] 100%")
                self.after(500, self.show_login_screen)
                return
            bar_len = int((i + 1) / len(steps) * 20)
            bar = "[" + "#" * bar_len + "-" * (20 - bar_len) + "]"
            self.boot_status.config(text=f"{bar} {int((i+1)/len(steps)*100)}%")
            log_boot_line(f"> {steps[i]}")
            self.after(250, lambda: run_steps(i + 1))

        self.after(400, run_steps)

    def show_login_screen(self):
        self.clear_overlay()
        self.current_screen = "login"

        accent = self.get_accent_color()

        frame = tk.Frame(self.overlay, bg="#050608", bd=0, highlightthickness=0)
        frame.place(relx=0.3, rely=0.25, relwidth=0.4, relheight=0.5)

        title = tk.Label(
            frame,
            text="ENCRYPT-OS LOGIN",
            font=self.scaled_font(18, "bold"),
            bg="#050608",
            fg=accent,
        )
        title.pack(pady=(40, 10))

        subtitle = tk.Label(
            frame,
            text="Operator-Name eingeben",
            font=self.scaled_font(10),
            bg="#050608",
            fg="#9CA3AF",
        )
        subtitle.pack(pady=(0, 30))

        self.login_name_var = tk.StringVar()

        entry = tk.Entry(
            frame,
            textvariable=self.login_name_var,
            font=self.scaled_font(12),
            bg="#020617",
            fg="#E5E7EB",
            insertbackground=accent,
            relief="solid",
            borderwidth=1,
        )
        entry.pack(pady=5, ipadx=5, ipady=5)
        entry.focus_set()
        entry.bind("<Return>", lambda e: self._handle_login())  # ENTER login

        btn = tk.Button(
            frame,
            text="Login",
            command=self._handle_login,
            font=self.scaled_font(11, "bold"),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        )
        btn.pack(pady=20)

        hint = tk.Label(
            frame,
            text="(ENTER = Login · ESC: Sofortiger System-Shutdown)",
            font=self.scaled_font(9),
            bg="#050608",
            fg="#6B7280",
        )
        hint.pack(pady=(10, 0))

    def _handle_login(self):
        name = self.login_name_var.get().strip()
        if not name:
            messagebox.showwarning("Login", "Bitte einen Operator-Namen eingeben.")
            return
        self.username = name
        log(f"LOGIN: Operator = {self.username}")
        self.show_desktop_loading()

    # ==========================
    #   Desktop Loading + Desktop
    # ==========================

    def show_desktop_loading(self):
        self.clear_overlay()
        self.current_screen = "desktop_loading"

        accent = self.get_accent_color()

        frame = tk.Frame(self.overlay, bg="#050608", bd=0, highlightthickness=0)
        frame.place(relx=0.3, rely=0.3, relwidth=0.4, relheight=0.4)

        title = tk.Label(
            frame,
            text="INITIALIZING ENCRYPT-OS DESKTOP",
            font=self.scaled_font(16, "bold"),
            bg="#050608",
            fg=accent,
        )
        title.pack(pady=(25, 10))

        subtitle = tk.Label(
            frame,
            text=f"Modus: MANUAL  ·  Operator: {self.username}",
            font=self.scaled_font(11),
            bg="#050608",
            fg="#9CA3AF",
        )
        subtitle.pack(pady=(0, 15))

        self.desktop_loading_label = tk.Label(
            frame,
            text="Lade Module...",
            font=self.scaled_font(10),
            bg="#050608",
            fg="#E5E7EB",
        )
        self.desktop_loading_label.pack(pady=10)

        self.desktop_loading_bar = tk.Label(
            frame,
            text="[##########----------] 50%",
            font=self.scaled_font(10),
            bg="#050608",
            fg=accent,
        )
        self.desktop_loading_bar.pack(pady=10)

        steps = [
            ("Lade Terminal-Komponente...", 20),
            ("Verbinde mit Kryptomodulen...", 40),
            ("Initialisiere UI-Layouts...", 60),
            ("Registriere Operator-Sitzung...", 80),
            ("Starte ENCRYPT-OS Desktop...", 100),
        ]

        def run_steps(i=0):
            if not self.alive:
                return
            if i >= len(steps):
                self.after(300, self.show_main_desktop)
                return
            msg, percent = steps[i]
            bar_len = int(percent / 5)
            bar = "[" + "#" * (bar_len // 2) + "-" * (20 - bar_len // 2) + "]"
            self.desktop_loading_label.config(text=msg)
            self.desktop_loading_bar.config(text=f"{bar} {percent}%")
            self.after(300, lambda: run_steps(i + 1))

        self.after(200, run_steps)

    def show_main_desktop(self):
        self.clear_overlay()
        self.current_screen = "desktop"

        accent = self.get_accent_color()
        panel_bg = self.get_panel_bg()
        panel_border = self.get_panel_border()

        container = tk.Frame(self.overlay, bg="#050608", bd=0, highlightthickness=0)
        container.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Top-Bar
        top_bar = tk.Frame(container, bg="#020617", height=40)
        top_bar.pack(fill="x", side="top")

        title = tk.Label(
            top_bar,
            text="ENCRYPT-OS · Bit-Morse-Binary Environment",
            font=self.scaled_font(12, "bold"),
            bg="#020617",
            fg=accent,
        )
        title.pack(side="left", padx=10)

        user_label = tk.Label(
            top_bar,
            text=f"Operator: {self.username}",
            font=self.scaled_font(10),
            bg="#020617",
            fg="#9CA3AF",
        )
        user_label.pack(side="right", padx=10)

        # Desktop-Bereich
        desktop = tk.Frame(container, bg="#050608")
        desktop.pack(fill="both", expand=True)

        # Links: App-Dock
        dock = tk.Frame(desktop, bg="#020617", width=180)
        dock.pack(side="left", fill="y")
        dock.pack_propagate(False)

        dock_title = tk.Label(
            dock,
            text="APPS",
            font=self.scaled_font(11, "bold"),
            bg="#020617",
            fg=accent,
        )
        dock_title.pack(pady=(10, 5))

        self.active_app = tk.StringVar(value="encryption")

        def app_button(text, app_name):
            def switch():
                self.active_app.set(app_name)
                self.update_app_view()
            b = tk.Button(
                dock,
                text=text,
                command=switch,
                font=self.scaled_font(10),
                bg="#020617",
                fg="#E5E7EB",
                activebackground="#1F2937",
                activeforeground=accent,
                bd=0,
                padx=12,
                pady=6,
                anchor="w",
            )
            b.pack(fill="x", padx=10, pady=3)
            return b

        self.btn_app_enc = app_button("Encryption Suite", "encryption")
        self.btn_app_mon = app_button("System Monitor", "monitor")
        self.btn_app_set = app_button("Settings", "settings")
        self.btn_app_about = app_button("About / Info", "about")

        # Mitte: App-Content
        app_area = tk.Frame(desktop, bg="#050608")
        app_area.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)

        app_area.columnconfigure(0, weight=3)
        app_area.columnconfigure(1, weight=2)
        app_area.rowconfigure(0, weight=1)

        # App-Panel links (Container für Views)
        self.app_panel = tk.Frame(
            app_area,
            bg=panel_bg,
            bd=2,
            relief="solid",
            highlightthickness=1,
            highlightbackground=panel_border,
        )
        self.app_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Terminal-Panel rechts
        term_panel = tk.Frame(
            app_area,
            bg=panel_bg,
            bd=2,
            relief="solid",
            highlightthickness=1,
            highlightbackground=panel_border,
        )
        term_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        term_title = tk.Label(
            term_panel,
            text="SYSTEM CONSOLE & TASK LOG",
            font=self.scaled_font(12, "bold"),
            bg=panel_bg,
            fg=accent,
        )
        term_title.pack(anchor="w", padx=10, pady=(8, 2))

        term_sub = tk.Label(
            term_panel,
            text="Befehle: help, about, sysinfo, whoami, theme, tasks, time, clear",
            font=self.scaled_font(9),
            bg=panel_bg,
            fg="#9CA3AF",
        )
        term_sub.pack(anchor="w", padx=10, pady=(0, 4))

        self.terminal_text = tk.Text(
            term_panel,
            height=20,
            wrap="word",
            bg="#020617",
            fg="#D1D5DB",
            insertbackground=accent,
            relief="solid",
            borderwidth=1,
            font=self.scaled_font(9),
        )
        self.terminal_text.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        self.terminal_text.insert(
            "end",
            "[SYSTEM] ENCRYPT-OS Konsole initialisiert.\n"
            "[SYSTEM] Tippe 'help' und drücke Enter für verfügbare Befehle.\n\n"
        )
        self.terminal_text.see("end")

        # Command line input
        cmd_frame = tk.Frame(term_panel, bg=panel_bg)
        cmd_frame.pack(fill="x", padx=10, pady=(0, 8))

        cmd_label = tk.Label(
            cmd_frame,
            text=">",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg=accent,
        )
        cmd_label.pack(side="left")

        self.cmd_entry = tk.Entry(
            cmd_frame,
            font=self.scaled_font(10),
            bg="#020617",
            fg="#D1D5DB",
            insertbackground=accent,
            relief="solid",
            borderwidth=1,
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.cmd_entry.bind("<Return>", self.handle_console_command)
        self.cmd_entry.bind("<Up>", self.cmd_history_up)
        self.cmd_entry.bind("<Down>", self.cmd_history_down)

        logger.attach_widget(self.terminal_text)
        log("DESKTOP: ENCRYPT-OS bereit für Operator-Eingaben.")

        # Statusbar
        statusbar = tk.Frame(container, bg="#020617", height=24)
        statusbar.pack(fill="x", side="bottom")

        self.status_text_var = tk.StringVar(value="Session aktiv. ESC für sicheren Shutdown.")
        self.status_clock_var = tk.StringVar(value=datetime.now().strftime("%H:%M:%S"))

        status_label = tk.Label(
            statusbar,
            textvariable=self.status_text_var,
            font=self.scaled_font(9),
            bg="#020617",
            fg="#9CA3AF",
        )
        status_label.pack(side="left", padx=10)

        clock_label = tk.Label(
            statusbar,
            textvariable=self.status_clock_var,
            font=self.scaled_font(9),
            bg="#020617",
            fg="#9CA3AF",
        )
        clock_label.pack(side="right", padx=10)

        self.update_clock()

        # Persistente Views erzeugen
        self.view_encryption = tk.Frame(self.app_panel, bg=self.get_panel_bg())
        self.view_monitor = tk.Frame(self.app_panel, bg=self.get_panel_bg())
        self.view_settings = tk.Frame(self.app_panel, bg=self.get_panel_bg())
        self.view_about = tk.Frame(self.app_panel, bg=self.get_panel_bg())

        self.build_encryption_view_content(self.view_encryption, self.get_panel_bg(), accent)
        self.build_monitor_view_content(self.view_monitor, self.get_panel_bg(), accent)
        self.build_settings_view_content(self.view_settings, self.get_panel_bg(), accent)
        self.build_about_view_content(self.view_about, self.get_panel_bg(), accent)

        self.update_app_view()
        self.update_system_monitor()

    # ---------- Status & Clock ----------

    def set_status(self, msg: str):
        if self.status_text_var is not None:
            if self.dev_overlay.get():
                full = f"{msg}  |  Theme={self.theme}, UI={self.ui_density}, Scale={self.font_scale}"
            else:
                full = msg
            self.status_text_var.set(full)
            self.update_idletasks()
        log(f"STATUS: {msg}")

    def update_clock(self):
        if not self.alive:
            return
        if self.status_clock_var is not None:
            self.status_clock_var.set(datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self.update_clock)

    # ---------- App-View Handling ----------

    def update_app_view(self):
        for v in (self.view_encryption, self.view_monitor, self.view_settings, self.view_about):
            v.pack_forget()
        app = self.active_app.get()
        if app == "encryption":
            self.view_encryption.pack(fill="both", expand=True)
            self.set_status("Encryption Suite aktiv.")
        elif app == "monitor":
            self.view_monitor.pack(fill="both", expand=True)
            self.set_status("System Monitor aktiv.")
        elif app == "settings":
            self.view_settings.pack(fill="both", expand=True)
            self.set_status("Settings geöffnet.")
        elif app == "about":
            self.view_about.pack(fill="both", expand=True)
            self.set_status("About / Info geöffnet.")

    # ---------- Encryption View mit History ----------

    def build_encryption_view_content(self, parent, panel_bg, accent):
        wrapper = tk.Frame(parent, bg=panel_bg)
        wrapper.pack(fill="both", expand=True)

        top_row = tk.Frame(wrapper, bg=panel_bg)
        top_row.pack(fill="x", padx=10, pady=(8, 4))

        lbl_title = tk.Label(
            top_row,
            text="ENCRYPTION SUITE",
            font=self.scaled_font(12, "bold"),
            bg=panel_bg,
            fg=accent,
        )
        lbl_title.pack(side="left")

        lbl_sub = tk.Label(
            wrapper,
            text="Text ↔ Bit-Morse-Binary Cipher · Multistage Pipeline",
            font=self.scaled_font(9),
            bg=panel_bg,
            fg="#9CA3AF",
        )
        lbl_sub.pack(anchor="w", padx=10, pady=(0, 8))

        body = tk.Frame(wrapper, bg=panel_bg)
        body.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=panel_bg)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        right = tk.Frame(body, bg=panel_bg)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # LEFT
        lbl_plain = tk.Label(
            left,
            text="Klartext-Eingabe:",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        lbl_plain.pack(anchor="w")

        self.txt_plain = tk.Text(
            left,
            height=5,
            wrap="word",
            bg="#020617",
            fg="#E5E7EB",
            insertbackground=accent,
            relief="solid",
            borderwidth=1,
            font=self.scaled_font(10),
        )
        self.txt_plain.pack(fill="x", expand=False, pady=(0, 5))

        btn_enc = tk.Button(
            left,
            text="Encrypt",
            command=self.on_encrypt_click,
            font=self.scaled_font(10, "bold"),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        )
        btn_enc.pack(anchor="e", pady=(0, 5))

        lbl_cipher = tk.Label(
            left,
            text="Cipher (Binär) Ausgabe:",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        lbl_cipher.pack(anchor="w", pady=(8, 0))

        self.txt_cipher_out = tk.Text(
            left,
            height=5,
            wrap="word",
            bg="#020617",
            fg=accent,
            insertbackground=accent,
            relief="solid",
            borderwidth=1,
            font=self.scaled_font(9),
        )
        self.txt_cipher_out.pack(fill="x", expand=False, pady=(0, 5))

        btn_copy = tk.Button(
            left,
            text="Cipher kopieren",
            command=self.on_copy_cipher,
            font=self.scaled_font(10, "bold"),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        )
        btn_copy.pack(anchor="e", pady=(0, 10))

        sep = tk.Frame(left, bg="#111827", height=1)
        sep.pack(fill="x", pady=5)

        lbl_cipher_in = tk.Label(
            left,
            text="Cipher (Binär) zum Entschlüsseln:",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        lbl_cipher_in.pack(anchor="w", pady=(8, 0))

        self.txt_cipher_in = tk.Text(
            left,
            height=4,
            wrap="word",
            bg="#020617",
            fg=accent,
            insertbackground=accent,
            relief="solid",
            borderwidth=1,
            font=self.scaled_font(9),
        )
        self.txt_cipher_in.pack(fill="x", expand=False, pady=(0, 5))

        btn_dec = tk.Button(
            left,
            text="Decrypt",
            command=self.on_decrypt_click,
            font=self.scaled_font(10, "bold"),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        )
        btn_dec.pack(anchor="e", pady=(0, 5))

        lbl_plain_out = tk.Label(
            left,
            text="Entschlüsselter Klartext:",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        lbl_plain_out.pack(anchor="w", pady=(8, 0))

        self.txt_plain_out = tk.Text(
            left,
            height=4,
            wrap="word",
            bg="#020617",
            fg="#E5E7EB",
            insertbackground=accent,
            relief="solid",
            borderwidth=1,
            font=self.scaled_font(10),
        )
        self.txt_plain_out.pack(fill="x", expand=False, pady=(0, 2))

        # RIGHT: History
        hist_title = tk.Label(
            right,
            text="Encryption History (letzte 10)",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        hist_title.pack(anchor="w")

        self.history_frame = tk.Frame(right, bg=panel_bg)
        self.history_frame.pack(fill="both", expand=True, pady=(4, 4))

        hint = tk.Label(
            right,
            text="Klicke 'Load', um Text/Cipher zurück in die Felder zu laden.",
            font=self.scaled_font(8),
            bg=panel_bg,
            fg="#9CA3AF",
            wraplength=260,
            justify="left",
        )
        hint.pack(anchor="w", pady=(2, 0))

        self.render_history()

    def render_history(self):
        if not hasattr(self, "history_frame") or self.history_frame is None:
            return
        for child in self.history_frame.winfo_children():
            child.destroy()
        if not self.enc_history:
            lbl = tk.Label(
                self.history_frame,
                text="(Noch keine Einträge)",
                font=self.scaled_font(9),
                bg=self.get_panel_bg(),
                fg="#6B7280",
            )
            lbl.pack(anchor="w", pady=4)
            return
        for entry in reversed(self.enc_history):
            row = tk.Frame(self.history_frame, bg=self.get_panel_bg())
            row.pack(fill="x", pady=2)

            text = f"[{entry['time']}] {entry['plain']}"
            lbl = tk.Label(
                row,
                text=text,
                font=self.scaled_font(9),
                bg=self.get_panel_bg(),
                fg="#E5E7EB",
                anchor="w",
                justify="left",
                wraplength=220,
            )
            lbl.pack(side="left", fill="x", expand=True)

            btn = tk.Button(
                row,
                text="Load",
                command=lambda e=entry: self.load_history_entry(e),
                font=self.scaled_font(8, "bold"),
                bg="#111827",
                fg="#E5E7EB",
                activebackground="#1F2937",
                activeforeground="#E5E7EB",
                bd=0,
                padx=6,
                pady=2,
            )
            btn.pack(side="right", padx=(4, 0))

    def load_history_entry(self, entry):
        self.txt_cipher_in.delete("1.0", "end")
        self.txt_cipher_in.insert("1.0", entry["cipher_full"])
        self.txt_plain.delete("1.0", "end")
        self.txt_plain.insert("1.0", entry["plain_full"])
        self.set_status("History-Eintrag geladen.")

    # ---------- Monitor View + Tasks ----------

    def build_monitor_view_content(self, parent, panel_bg, accent):
        title = tk.Label(
            parent,
            text="SYSTEM MONITOR",
            font=self.scaled_font(12, "bold"),
            bg=panel_bg,
            fg=accent,
        )
        title.pack(anchor="w", padx=10, pady=(8, 4))

        sub = tk.Label(
            parent,
            text="Runtime Overview · CPU / Memory · Tasklist",
            font=self.scaled_font(9),
            bg=panel_bg,
            fg="#9CA3AF",
        )
        sub.pack(anchor="w", padx=10, pady=(0, 10))

        top_row = tk.Frame(parent, bg=panel_bg)
        top_row.pack(fill="x", padx=10, pady=(2, 8))

        cpu_frame = tk.Frame(top_row, bg=panel_bg)
        cpu_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))

        cpu_title = tk.Label(
            cpu_frame,
            text="CPU Load",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        cpu_title.pack(anchor="w")

        self.cpu_label = tk.Label(
            cpu_frame,
            text="[----------] 0%",
            font=self.scaled_font(10),
            bg=panel_bg,
            fg=accent,
        )
        self.cpu_label.pack(anchor="w", pady=(2, 2))

        ram_frame = tk.Frame(top_row, bg=panel_bg)
        ram_frame.pack(side="left", fill="x", expand=True, padx=(5, 0))

        ram_title = tk.Label(
            ram_frame,
            text="Memory Usage",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        ram_title.pack(anchor="w")

        self.ram_label = tk.Label(
            ram_frame,
            text="[----------] 0%",
            font=self.scaled_font(10),
            bg=panel_bg,
            fg=accent,
        )
        self.ram_label.pack(anchor="w", pady=(2, 2))

        tasks_title = tk.Label(
            parent,
            text="Task-Liste",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        tasks_title.pack(anchor="w", padx=10, pady=(8, 2))

        header = tk.Frame(parent, bg=panel_bg)
        header.pack(fill="x", padx=10)

        tk.Label(
            header,
            text="Name",
            font=self.scaled_font(9, "bold"),
            bg=panel_bg,
            fg="#9CA3AF",
            width=20,
            anchor="w",
        ).pack(side="left")

        tk.Label(
            header,
            text="CPU%",
            font=self.scaled_font(9, "bold"),
            bg=panel_bg,
            fg="#9CA3AF",
            width=6,
            anchor="e",
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            header,
            text="RAM%",
            font=self.scaled_font(9, "bold"),
            bg=panel_bg,
            fg="#9CA3AF",
            width=6,
            anchor="e",
        ).pack(side="left", padx=(10, 0))

        self.task_list_frame = tk.Frame(parent, bg=panel_bg)
        self.task_list_frame.pack(fill="both", expand=True, padx=10, pady=(2, 6))

        self.fake_tasks = [
            {"name": "encryptd", "cpu": 7, "ram": 3},
            {"name": "ui-shell", "cpu": 4, "ram": 5},
            {"name": "logger", "cpu": 2, "ram": 1},
            {"name": "entropy-daemon", "cpu": 9, "ram": 4},
            {"name": "session-manager", "cpu": 3, "ram": 2},
        ]
        self.render_task_list()

        btn_refresh = tk.Button(
            parent,
            text="Task-Stats aktualisieren",
            command=self.refresh_tasks,
            font=self.scaled_font(9, "bold"),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        )
        btn_refresh.pack(anchor="e", padx=10, pady=(0, 6))

    def render_task_list(self):
        for child in self.task_list_frame.winfo_children():
            child.destroy()
        for t in self.fake_tasks:
            row = tk.Frame(self.task_list_frame, bg=self.get_panel_bg())
            row.pack(fill="x", pady=1)
            tk.Label(
                row,
                text=t["name"],
                font=self.scaled_font(9),
                bg=self.get_panel_bg(),
                fg="#E5E7EB",
                width=20,
                anchor="w",
            ).pack(side="left")
            tk.Label(
                row,
                text=f"{t['cpu']}%",
                font=self.scaled_font(9),
                bg=self.get_panel_bg(),
                fg="#22C55E",
                width=6,
                anchor="e",
            ).pack(side="left", padx=(10, 0))
            tk.Label(
                row,
                text=f"{t['ram']}%",
                font=self.scaled_font(9),
                bg=self.get_panel_bg(),
                fg="#38BDF8",
                width=6,
                anchor="e",
            ).pack(side="left", padx=(10, 0))

    def refresh_tasks(self):
        for t in self.fake_tasks:
            t["cpu"] = max(0, min(99, t["cpu"] + random.randint(-3, 4)))
            t["ram"] = max(0, min(99, t["ram"] + random.randint(-2, 3)))
        self.render_task_list()
        self.set_status("Task-Liste aktualisiert.")

    # ---------- Settings View ----------

    def build_settings_view_content(self, parent, panel_bg, accent):
        lbl_title = tk.Label(
            parent,
            text="SETTINGS",
            font=self.scaled_font(12, "bold"),
            bg=panel_bg,
            fg=accent,
        )
        lbl_title.pack(anchor="w", padx=10, pady=(8, 4))

        lbl_sub = tk.Label(
            parent,
            text="Darstellung, Theme und UI-Optionen",
            font=self.scaled_font(9),
            bg=panel_bg,
            fg="#9CA3AF",
        )
        lbl_sub.pack(anchor="w", padx=10, pady=(0, 12))

        # Theme
        theme_lbl = tk.Label(
            parent,
            text="Theme:",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        theme_lbl.pack(anchor="w", padx=10, pady=(4, 4))

        theme_row = tk.Frame(parent, bg=panel_bg)
        theme_row.pack(anchor="w", padx=10, pady=(0, 8))

        tk.Button(
            theme_row,
            text="Neon Green",
            command=lambda: self.change_theme("green"),
            font=self.scaled_font(10),
            bg="#111827",
            fg="#22C55E",
            activebackground="#1F2937",
            activeforeground="#22C55E",
            bd=0,
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            theme_row,
            text="Neon Purple",
            command=lambda: self.change_theme("purple"),
            font=self.scaled_font(10),
            bg="#111827",
            fg="#A855F7",
            activebackground="#1F2937",
            activeforeground="#A855F7",
            bd=0,
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            theme_row,
            text="Dark Blue",
            command=lambda: self.change_theme("blue"),
            font=self.scaled_font(10),
            bg="#111827",
            fg="#38BDF8",
            activebackground="#1F2937",
            activeforeground="#38BDF8",
            bd=0,
            padx=10,
            pady=4,
        ).pack(side="left")

        # UI-Dichte
        density_lbl = tk.Label(
            parent,
            text="UI-Dichte (Info):",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        density_lbl.pack(anchor="w", padx=10, pady=(10, 4))

        density_row = tk.Frame(parent, bg=panel_bg)
        density_row.pack(anchor="w", padx=10, pady=(0, 8))

        tk.Button(
            density_row,
            text="Compact",
            command=lambda: self.set_density("compact"),
            font=self.scaled_font(10),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            density_row,
            text="Normal",
            command=lambda: self.set_density("normal"),
            font=self.scaled_font(10),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            density_row,
            text="Large",
            command=lambda: self.set_density("large"),
            font=self.scaled_font(10),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        ).pack(side="left")

        # Schriftgröße
        font_lbl = tk.Label(
            parent,
            text="Schriftgröße:",
            font=self.scaled_font(10, "bold"),
            bg=panel_bg,
            fg="#E5E7EB",
        )
        font_lbl.pack(anchor="w", padx=10, pady=(10, 4))

        font_row = tk.Frame(parent, bg=panel_bg)
        font_row.pack(anchor="w", padx=10, pady=(0, 8))

        tk.Button(
            font_row,
            text="Small",
            command=lambda: self.set_font_scale(0.9),
            font=self.scaled_font(10),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            font_row,
            text="Normal",
            command=lambda: self.set_font_scale(1.0),
            font=self.scaled_font(10),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            font_row,
            text="Large",
            command=lambda: self.set_font_scale(1.1),
            font=self.scaled_font(10),
            bg="#111827",
            fg="#E5E7EB",
            activebackground="#1F2937",
            activeforeground="#E5E7EB",
            bd=0,
            padx=10,
            pady=4,
        ).pack(side="left")

        # Dev-Overlay
        dev_row = tk.Frame(parent, bg=panel_bg)
        dev_row.pack(anchor="w", padx=10, pady=(12, 4))

        dev_check = tk.Checkbutton(
            dev_row,
            text="Developer Overlay (Statusleiste mit internen Infos)",
            variable=self.dev_overlay,
            onvalue=True,
            offvalue=False,
            font=self.scaled_font(9),
            bg=panel_bg,
            fg="#E5E7EB",
            selectcolor=panel_bg,
            activebackground=panel_bg,
            activeforeground="#E5E7EB",
        )
        dev_check.pack(anchor="w")

        info = tk.Label(
            parent,
            text="Theme- und Schriftänderungen werden nach kurzem Reload aktiv.",
            font=self.scaled_font(9),
            bg=panel_bg,
            fg="#6B7280",
        )
        info.pack(anchor="w", padx=10, pady=(14, 0))

    def change_theme(self, new_theme: str):
        if new_theme not in ("green", "purple", "blue"):
            return
        self.theme = new_theme
        log(f"SETTINGS: Theme gewechselt zu {new_theme}.")
        self.set_status(f"Theme geändert zu '{new_theme}'. Desktop wird neu geladen.")
        self.show_main_desktop()

    def set_density(self, density: str):
        if density not in ("compact", "normal", "large"):
            return
        self.ui_density = density
        log(f"SETTINGS: UI-Dichte → {density}.")
        self.set_status(f"UI-Dichte gesetzt auf '{density}' (Info).")

    def set_font_scale(self, scale: float):
        self.font_scale = scale
        log(f"SETTINGS: Schrift-Skalierung → {scale}.")
        self.set_status(f"Schriftgröße angepasst. Desktop wird neu aufgebaut.")
        self.show_main_desktop()

    # ---------- About View ----------

    def build_about_view_content(self, parent, panel_bg, accent):
        lbl_title = tk.Label(
            parent,
            text="ABOUT / INFORMATION",
            font=self.scaled_font(12, "bold"),
            bg=panel_bg,
            fg=accent,
        )
        lbl_title.pack(anchor="w", padx=10, pady=(8, 4))

        text = (
            "ENCRYPT-OS · Bit-Morse-Binary Encryption Suite · ULTRA+ CLEAN\n\n"
            "Mini-OS für eine mehrstufige Verschlüsselung "
            "(Binary → Bit-Morse → Reverse).\n\n"
            "Module:\n"
            "  • Encryption Suite: Text ↔ Cipher (Binary) mit History\n"
            "  • System Monitor: CPU / RAM KPIs + Task-Liste\n"
            "  • Settings: Theme, Schrift, UI-Overlay\n"
            "  • System Console: Live-Logs + Command-Line\n\n"
            "Kommandozeilen-Befehle (Konsole rechts):\n"
            "  help, about, sysinfo, whoami, theme, tasks, time, clear\n\n"
            "Hinweis: Systemwerte sind visuelle Repräsentationen für das OS-Look&Feel."
        )

        lbl_text = tk.Label(
            parent,
            text=text,
            font=self.scaled_font(9),
            bg=panel_bg,
            fg="#E5E7EB",
            justify="left",
            anchor="nw",
            wraplength=600,
        )
        lbl_text.pack(fill="both", expand=True, padx=10, pady=(6, 10))

    # ---------- System Monitor Update ----------

    def update_system_monitor(self):
        if not self.alive:
            return
        if self.cpu_label is not None and self.ram_label is not None:
            self.cpu_val = max(5, min(98, self.cpu_val + random.randint(-7, 7)))
            self.ram_val = max(10, min(99, self.ram_val + random.randint(-4, 4)))

            def build_bar(val):
                length = 10
                filled = int(val / 10)
                return "[" + "#" * filled + "-" * (length - filled) + f"] {val}%"

            self.cpu_label.config(text=build_bar(self.cpu_val))
            self.ram_label.config(text=build_bar(self.ram_val))

        self.after(1000, self.update_system_monitor)

    # ---------- Encryption Events (mit History) ----------

    def on_encrypt_click(self):
        plaintext = self.txt_plain.get("1.0", "end").strip()
        if not plaintext:
            messagebox.showwarning("Hinweis", "Bitte Klartext eingeben.")
            return

        self.set_status("Verschlüsselung gestartet.")
        try:
            cipher = encrypt_message(plaintext)
        except Exception as e:
            log(f"ENCRYPT ERROR: {e}")
            self.set_status("Fehler bei der Verschlüsselung.")
            messagebox.showerror("Fehler", str(e))
            return

        self.txt_cipher_out.delete("1.0", "end")
        self.txt_cipher_out.insert("1.0", cipher)

        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "plain_full": plaintext,
            "cipher_full": cipher,
            "plain": (plaintext[:40] + "...") if len(plaintext) > 40 else plaintext,
            "cipher": (cipher[:40] + "...") if len(cipher) > 40 else cipher,
        }
        self.enc_history.append(entry)
        self.enc_history = self.enc_history[-10:]
        self.render_history()

        try:
            pyperclip.copy(cipher)
            self.set_status("Verschlüsselung abgeschlossen. Cipher in Zwischenablage kopiert.")
        except pyperclip.PyperclipException:
            self.set_status("Verschlüsselung abgeschlossen (Zwischenablage nicht verfügbar).")

    def on_copy_cipher(self):
        cipher = self.txt_cipher_out.get("1.0", "end").strip()
        if not cipher:
            messagebox.showinfo("Hinweis", "Kein Cipher zum Kopieren vorhanden.")
            return
        try:
            pyperclip.copy(cipher)
            self.set_status("Cipher in Zwischenablage kopiert.")
        except pyperclip.PyperclipException:
            self.set_status("Konnte nicht in die Zwischenablage kopieren.")
            messagebox.showwarning("Warnung", "Konnte nicht in die Zwischenablage kopieren.")

    def on_decrypt_click(self):
        cipher = self.txt_cipher_in.get("1.0", "end").strip()
        if not cipher:
            messagebox.showwarning("Hinweis", "Bitte Binär-Cipher eingeben.")
            return

        self.set_status("Entschlüsselung gestartet.")
        try:
            plaintext = decrypt_message(cipher)
        except Exception as e:
            log(f"DECRYPT ERROR: {e}")
            self.set_status("Fehler bei der Entschlüsselung.")
            messagebox.showerror("Fehler", str(e))
            return

        self.txt_plain_out.delete("1.0", "end")
        self.txt_plain_out.insert("1.0", plaintext)
        self.set_status("Entschlüsselung abgeschlossen.")

    # ---------- Console: Commands + History ----------

    def handle_console_command(self, event=None):
        cmd = self.cmd_entry.get().strip()
        if cmd:
            self.cmd_history.append(cmd)
        self.cmd_history_index = None
        self.cmd_entry.delete(0, "end")
        if not cmd:
            return
        self.terminal_text.insert("end", f"> {cmd}\n")
        self.terminal_text.see("end")
        self.execute_command(cmd)

    def cmd_history_up(self, event=None):
        if not self.cmd_history:
            return "break"
        if self.cmd_history_index is None:
            self.cmd_history_index = len(self.cmd_history) - 1
        else:
            self.cmd_history_index = max(0, self.cmd_history_index - 1)
        self.cmd_entry.delete(0, "end")
        self.cmd_entry.insert(0, self.cmd_history[self.cmd_history_index])
        return "break"

    def cmd_history_down(self, event=None):
        if not self.cmd_history or self.cmd_history_index is None:
            return "break"
        self.cmd_history_index = min(len(self.cmd_history) - 1, self.cmd_history_index + 1)
        self.cmd_entry.delete(0, "end")
        self.cmd_entry.insert(0, self.cmd_history[self.cmd_history_index])
        return "break"

    def execute_command(self, cmd: str):
        parts = cmd.split()
        if not parts:
            return
        base = parts[0].lower()

        if base == "help":
            text = (
                "Verfügbare Befehle:\n"
                "  help     - Diese Übersicht\n"
                "  about    - Info über ENCRYPT-OS\n"
                "  sysinfo  - Systeminformationen\n"
                "  whoami   - Aktueller Operator\n"
                "  theme    - Zeigt aktuelles Theme\n"
                "  tasks    - Übersicht der Tasks\n"
                "  time     - Aktuelle Uhrzeit/Datum\n"
                "  clear    - Konsole leeren\n"
            )
            self.console_write(text)
        elif base == "about":
            self.console_write("ENCRYPT-OS · Bit-Morse-Binary Encryption Suite · ULTRA+ CLEAN Edition.")
        elif base == "sysinfo":
            info = (
                f"SYSINFO:\n"
                f"  Operator : {self.username}\n"
                f"  Theme    : {self.theme}\n"
                f"  UI-Dichte: {self.ui_density}\n"
                f"  FontScale: {self.font_scale}\n"
                f"  CPU Load : ~{self.cpu_val}% (visual)\n"
                f"  RAM Usage: ~{self.ram_val}% (visual)\n"
            )
            self.console_write(info)
        elif base == "whoami":
            self.console_write(f"Operator: {self.username}")
        elif base == "theme":
            self.console_write(f"Aktuelles Theme: {self.theme}")
        elif base == "tasks":
            lines = ["TASKS:"]
            for t in self.fake_tasks:
                lines.append(f"  {t['name']}: CPU {t['cpu']}% / RAM {t['ram']}%")
            self.console_write("\n".join(lines))
        elif base == "time":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.console_write(f"Aktuelle Zeit: {now}")
        elif base == "clear":
            self.terminal_text.delete("1.0", "end")
        else:
            self.console_write(f"Unbekannter Befehl: {base} (tippe 'help')")

    def console_write(self, text: str):
        self.terminal_text.insert("end", text + "\n")
        max_lines = 2000
        current = int(self.terminal_text.index("end-1c").split(".")[0])
        if current > max_lines:
            self.terminal_text.delete("1.0", f"{current - max_lines}.0")
        self.terminal_text.see("end")

    # ---------- ESC / Shutdown-Animation ----------

    def on_escape(self, event=None):
        if self.logout_running:
            return
        self.logout_running = True
        self.start_shutdown_sequence()

    def start_shutdown_sequence(self):
        log("SHUTDOWN: Sequenz gestartet.")
        self.alive = False  # keine weiteren Updates
        self.clear_overlay()

        accent = self.get_accent_color()
        frame = tk.Frame(self.overlay, bg="#050608", bd=0, highlightthickness=0)
        frame.place(relx=0.25, rely=0.3, relwidth=0.5, relheight=0.4)

        user = self.username or "Unknown Operator"

        title = tk.Label(
            frame,
            text="SHUTTING DOWN ENCRYPT-OS",
            font=self.scaled_font(18, "bold"),
            bg="#050608",
            fg="#F97316",
        )
        title.pack(pady=(25, 10))

        subtitle = tk.Label(
            frame,
            text=f"Operator: {user}",
            font=self.scaled_font(11),
            bg="#050608",
            fg="#9CA3AF",
        )
        subtitle.pack(pady=(0, 15))

        self.shutdown_label = tk.Label(
            frame,
            text="Encrypting account metadata...",
            font=self.scaled_font(10),
            bg="#050608",
            fg="#FBBF24",
        )
        self.shutdown_label.pack(pady=10)

        self.shutdown_progress = tk.Label(
            frame,
            text="[##------------------] 10%",
            font=self.scaled_font(10),
            bg="#050608",
            fg=accent,
        )
        self.shutdown_progress.pack(pady=10)

        info = tk.Label(
            frame,
            text="ESC erkannt · aktive Sessions werden sicher geschlossen...",
            font=self.scaled_font(9),
            bg="#050608",
            fg="#6B7280",
        )
        info.pack(pady=(10, 0))

        steps = [
            ("Encrypting account metadata...", 20),
            ("Sealing active ciphers...", 40),
            ("Wiping transient traces...", 60),
            ("Flushing logs...", 80),
            ("Powering down core modules...", 100),
        ]

        def run_steps(i=0):
            if i >= len(steps):
                log("SHUTDOWN: Animation abgeschlossen. Fenster wird geschlossen.")
                logger.detach_widget()
                self.after(300, self.destroy)
                return
            msg, percent = steps[i]
            bar_len = int(percent / 5)
            bar = "[" + "#" * (bar_len // 2) + "-" * (20 - bar_len // 2) + "]"
            self.shutdown_label.config(text=msg)
            self.shutdown_progress.config(text=f"{bar} {percent}%")
            self.after(250, lambda: run_steps(i + 1))

        self.after(200, run_steps)


# ==========================
#   MAIN
# ==========================

def main():
    log("ENCRYPT-OS: Start.")
    app = EncryptOS()
    app.mainloop()
    logger.detach_widget()
    log("ENCRYPT-OS: beendet.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbbruch durch Benutzer.")
        sys.exit(0)
