from __future__ import annotations

import os
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk
from collections.abc import Callable
from typing import Any

from .config import APP_NAME, APP_VERSION, APP_AUTHOR, Settings, app_root, save_settings, GITHUB_REPO
from .recorder import get_input_devices
from .updater import ReleaseInfo, fetch_latest_release


class SettingsWindow:
    def __init__(
        self,
        parent: tk.Tk,
        settings: Settings,
        on_save: Callable[[Settings], None],
        startup_enabled: Callable[[], bool],
        toggle_startup: Callable[[], None],
        latest_release: ReleaseInfo | None = None,
        check_update_fn: Callable[[], ReleaseInfo | None] | None = None,
    ) -> None:
        self.parent = parent
        self.settings = settings
        self.on_save_callback = on_save
        self.startup_enabled = startup_enabled
        self.toggle_startup = toggle_startup
        self.latest_release = latest_release
        self.check_update_fn = check_update_fn or (lambda: fetch_latest_release(GITHUB_REPO, APP_VERSION))

        self.win = tk.Toplevel(parent)
        self.win.title(f"{APP_NAME} Settings")
        self.win.geometry("540x620")
        self.win.resizable(False, False)
        self.win.configure(bg="#0f1117")
        self.win.attributes("-topmost", True)

        try:
            self.win.iconbitmap(str(app_root() / "bisik.ico"))
        except Exception:
            pass

        self._center_window()
        self._build_ui()

    def _center_window(self) -> None:
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = max(20, (sw - 540) // 2)
        y = max(20, (sh - 620) // 2)
        self.win.geometry(f"540x620+{x}+{y}")

    def _build_ui(self) -> None:
        bg = "#0f1117"
        card_bg = "#181b24"
        fg_white = "#f8fafc"
        fg_muted = "#94a3b8"
        accent = "#38bdf8"
        border_color = "#262b38"

        # Header Frame
        header = tk.Frame(self.win, bg=bg, pady=12, padx=20)
        header.pack(fill="x")

        title_lbl = tk.Label(header, text=f"{APP_NAME} Configuration", font=("Segoe UI", 14, "bold"), fg=fg_white, bg=bg)
        title_lbl.pack(anchor="w")
        sub_lbl = tk.Label(header, text=f"Version {APP_VERSION}  •  Developed by {APP_AUTHOR}", font=("Segoe UI", 9), fg=fg_muted, bg=bg)
        sub_lbl.pack(anchor="w")

        # Container notebook / tabs
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background="#1a1e29", foreground=fg_muted, padding=[16, 6], font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", card_bg)], foreground=[("selected", accent)])

        notebook = ttk.Notebook(self.win)
        notebook.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        tab_api = tk.Frame(notebook, bg=card_bg, padx=16, pady=16)
        tab_audio = tk.Frame(notebook, bg=card_bg, padx=16, pady=16)
        tab_about = tk.Frame(notebook, bg=card_bg, padx=16, pady=16)

        notebook.add(tab_api, text="Transcription API")
        notebook.add(tab_audio, text="Audio & Hotkey")
        notebook.add(tab_about, text="Behavior & About")

        # === TAB 1: API SETTINGS ===
        self._add_label(tab_api, "Transcription API Endpoint URL:", card_bg, fg_white)
        self.url_var = tk.StringVar(value=self.settings.transcription_url)
        self.url_entry = self._add_entry(tab_api, self.url_var, card_bg, fg_white, border_color)

        self._add_label(tab_api, "API Key (Bearer Token):", card_bg, fg_white)
        self.api_key_var = tk.StringVar(value=self.settings.api_key)
        key_frame = tk.Frame(tab_api, bg=card_bg)
        key_frame.pack(fill="x", pady=(2, 10))
        self.key_entry = tk.Entry(key_frame, textvariable=self.api_key_var, show="•", bg="#0e1017", fg=fg_white, insertbackground=fg_white, relief="flat", highlightthickness=1, highlightbackground=border_color, highlightcolor=accent, font=("Segoe UI", 9))
        self.key_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))
        self.show_key_var = tk.BooleanVar(value=False)
        show_btn = tk.Checkbutton(key_frame, text="Show", variable=self.show_key_var, bg=card_bg, fg=fg_muted, selectcolor="#0e1017", activebackground=card_bg, activeforeground=fg_white, command=self._toggle_show_key)
        show_btn.pack(side="right")

        self._add_label(tab_api, "Primary Model Name:", card_bg, fg_white)
        self.model_var = tk.StringVar(value=self.settings.model)
        self.model_combo = ttk.Combobox(tab_api, textvariable=self.model_var, values=["whisper-large-v3", "whisper-large-v3-turbo", "whisper-1", "groq-whisper"], font=("Segoe UI", 9))
        self.model_combo.pack(fill="x", pady=(2, 10), ipady=2)

        self._add_label(tab_api, "Fallback Model Name:", card_bg, fg_white)
        self.fallback_var = tk.StringVar(value=self.settings.fallback_model)
        self._add_entry(tab_api, self.fallback_var, card_bg, fg_white, border_color)

        self._add_label(tab_api, "Vocabulary & Context Prompt (Keywords, Names, Coding terms):", card_bg, fg_white)
        self.prompt_text = tk.Text(tab_api, bg="#0e1017", fg=fg_white, insertbackground=fg_white, relief="flat", highlightthickness=1, highlightbackground=border_color, highlightcolor=accent, font=("Segoe UI", 9), height=4, wrap="word")
        self.prompt_text.pack(fill="x", pady=(2, 6))
        self.prompt_text.insert("1.0", self.settings.vocabulary_prompt)

        # === TAB 2: AUDIO & HOTKEY ===
        self._add_label(tab_audio, "Global Toggle Shortcut Hotkey:", card_bg, fg_white)
        self.hotkey_var = tk.StringVar(value=self.settings.hotkey)
        self._add_entry(tab_audio, self.hotkey_var, card_bg, fg_white, border_color)
        hint_lbl = tk.Label(tab_audio, text="Default: win+o. Examples: ctrl+shift+space, alt+space, win+o", font=("Segoe UI", 8), fg=fg_muted, bg=card_bg)
        hint_lbl.pack(anchor="w", pady=(0, 12))

        self._add_label(tab_audio, "Microphone Input Device:", card_bg, fg_white)
        self.input_devices = get_input_devices()
        device_labels = ["(Default System Microphone)"] + [f"[{idx}] {name}" for idx, name in self.input_devices]
        self.device_var = tk.StringVar()
        
        # Match existing setting
        current_dev = self.settings.input_device
        selected_idx = 0
        if current_dev:
            for i, (d_idx, d_name) in enumerate(self.input_devices):
                if current_dev in (str(d_idx), d_name):
                    selected_idx = i + 1
                    break
        self.device_var.set(device_labels[selected_idx])

        self.device_combo = ttk.Combobox(tab_audio, textvariable=self.device_var, values=device_labels, state="readonly", font=("Segoe UI", 9))
        self.device_combo.pack(fill="x", pady=(2, 16), ipady=2)

        self.sound_feedback_var = tk.BooleanVar(value=self.settings.sound_feedback)
        cb_sound = tk.Checkbutton(tab_audio, text="Play audio cue sound on recording start / finish", variable=self.sound_feedback_var, bg=card_bg, fg=fg_white, selectcolor="#0e1017", activebackground=card_bg, activeforeground=fg_white, font=("Segoe UI", 9))
        cb_sound.pack(anchor="w", pady=4)

        self.live_preview_var = tk.BooleanVar(value=self.settings.live_preview)
        cb_live = tk.Checkbutton(tab_audio, text="Enable real-time audio chunk preview (if supported by server)", variable=self.live_preview_var, bg=card_bg, fg=fg_white, selectcolor="#0e1017", activebackground=card_bg, activeforeground=fg_white, font=("Segoe UI", 9))
        cb_live.pack(anchor="w", pady=4)

        # === TAB 3: BEHAVIOR & ABOUT ===
        self.floating_icon_var = tk.BooleanVar(value=self.settings.show_floating_icon)
        cb_icon = tk.Checkbutton(tab_about, text="Show floating microphone icon on desktop (when idle)", variable=self.floating_icon_var, bg=card_bg, fg=fg_white, selectcolor="#0e1017", activebackground=card_bg, activeforeground=fg_white, font=("Segoe UI", 9))
        cb_icon.pack(anchor="w", pady=4)

        self.auto_paste_var = tk.BooleanVar(value=self.settings.auto_paste)
        cb_paste = tk.Checkbutton(tab_about, text="Auto-paste transcript into focused app (Ctrl+V)", variable=self.auto_paste_var, bg=card_bg, fg=fg_white, selectcolor="#0e1017", activebackground=card_bg, activeforeground=fg_white, font=("Segoe UI", 9))
        cb_paste.pack(anchor="w", pady=4)

        self.save_transcripts_var = tk.BooleanVar(value=self.settings.save_transcripts)
        cb_save = tk.Checkbutton(tab_about, text="Log transcripts history to file (transcripts.txt)", variable=self.save_transcripts_var, bg=card_bg, fg=fg_white, selectcolor="#0e1017", activebackground=card_bg, activeforeground=fg_white, font=("Segoe UI", 9))
        cb_save.pack(anchor="w", pady=4)

        self.startup_var = tk.BooleanVar(value=self.startup_enabled())
        cb_start = tk.Checkbutton(tab_about, text="Start Bisik automatically with Windows", variable=self.startup_var, bg=card_bg, fg=fg_white, selectcolor="#0e1017", activebackground=card_bg, activeforeground=fg_white, font=("Segoe UI", 9))
        cb_start.pack(anchor="w", pady=4)

        self.check_updates_var = tk.BooleanVar(value=self.settings.check_updates)
        cb_updates = tk.Checkbutton(
            tab_about,
            text="Automatically check for updates every 3 hours",
            variable=self.check_updates_var,
            bg=card_bg,
            fg=fg_white,
            selectcolor="#0e1017",
            activebackground=card_bg,
            activeforeground=fg_white,
            font=("Segoe UI", 9),
        )
        cb_updates.pack(anchor="w", pady=4)

        sep = tk.Frame(tab_about, height=1, bg=border_color)
        sep.pack(fill="x", pady=16)

        about_card = tk.Frame(tab_about, bg="#12151c", padx=12, pady=12, highlightthickness=1, highlightbackground=border_color)
        about_card.pack(fill="x")

        tk.Label(about_card, text=f"{APP_NAME} - AI Voice Typing & Dictation", font=("Segoe UI", 10, "bold"), fg=accent, bg="#12151c").pack(anchor="w")
        tk.Label(about_card, text="Seamless distraction-free floating Island voice assistant for Windows.", font=("Segoe UI", 9), fg=fg_muted, bg="#12151c").pack(anchor="w", pady=(2, 6))
        tk.Label(about_card, text=f"Crafted with vibe coding by {APP_AUTHOR}", font=("Segoe UI", 9, "bold"), fg=fg_white, bg="#12151c").pack(anchor="w")

        # Update status line & button inside about_card
        upd_frame = tk.Frame(about_card, bg="#12151c")
        upd_frame.pack(fill="x", pady=(10, 0))
        self.upd_status_lbl = tk.Label(
            upd_frame,
            text=f"Current version: v{APP_VERSION}",
            font=("Segoe UI", 9),
            fg=fg_muted,
            bg="#12151c",
        )
        self.upd_status_lbl.pack(side="left")

        self.upd_btn = tk.Button(
            upd_frame,
            text="Check for Updates",
            bg="#262b38",
            fg=fg_white,
            activebackground="#333a4c",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_check_updates_click,
        )
        self.upd_btn.pack(side="right")

        if self.latest_release and self.latest_release.is_newer:
            self._set_update_available_ui(self.latest_release)

        # Bottom Action Bar
        bottom_bar = tk.Frame(self.win, bg=bg, pady=12, padx=20)
        bottom_bar.pack(fill="x", side="bottom")

        save_btn = tk.Button(bottom_bar, text="Save Settings", bg=accent, fg="#0b0f19", activebackground="#7dd3fc", font=("Segoe UI", 9, "bold"), relief="flat", padx=18, pady=6, cursor="hand2", command=self._save)
        save_btn.pack(side="right", padx=(8, 0))

        cancel_btn = tk.Button(bottom_bar, text="Cancel", bg="#262b38", fg=fg_white, activebackground="#333a4c", font=("Segoe UI", 9), relief="flat", padx=16, pady=6, cursor="hand2", command=self.win.destroy)
        cancel_btn.pack(side="right")

    def _add_label(self, parent: tk.Widget, text: str, bg: str, fg: str) -> None:
        lbl = tk.Label(parent, text=text, font=("Segoe UI", 9, "bold"), fg=fg, bg=bg)
        lbl.pack(anchor="w", pady=(4, 2))

    def _add_entry(self, parent: tk.Widget, var: tk.StringVar, bg: str, fg: str, border: str) -> tk.Entry:
        ent = tk.Entry(parent, textvariable=var, bg="#0e1017", fg=fg, insertbackground=fg, relief="flat", highlightthickness=1, highlightbackground=border, highlightcolor="#38bdf8", font=("Segoe UI", 9))
        ent.pack(fill="x", pady=(0, 10), ipady=4)
        return ent

    def _toggle_show_key(self) -> None:
        self.key_entry.configure(show="" if self.show_key_var.get() else "•")

    def _set_update_available_ui(self, info: ReleaseInfo) -> None:
        self.upd_status_lbl.config(
            text=f"✨ v{info.version} is available!",
            fg="#38bdf8",
        )
        url = info.download_url or info.html_url
        self.upd_btn.config(
            text="Download Update",
            bg="#0284c7",
            command=lambda: webbrowser.open(url),
        )

    def _on_check_updates_click(self) -> None:
        self.upd_status_lbl.config(text="Checking for updates...", fg="#94a3b8")
        self.upd_btn.config(state="disabled")

        def _run_check() -> None:
            try:
                info = self.check_update_fn()
                def _update_ui() -> None:
                    if not self.win.winfo_exists():
                        return
                    self.upd_btn.config(state="normal")
                    if info and info.is_newer:
                        self._set_update_available_ui(info)
                    elif info:
                        self.upd_status_lbl.config(text=f"✓ v{APP_VERSION} is the latest version", fg="#22c55e")
                        self.upd_btn.config(text="Check Again")
                    else:
                        self.upd_status_lbl.config(text="Unable to check (offline)", fg="#ef4444")
                        self.upd_btn.config(text="Retry")
                self.win.after(0, _update_ui)
            except Exception:
                def _error_ui() -> None:
                    if self.win.winfo_exists():
                        self.upd_btn.config(state="normal", text="Retry")
                        self.upd_status_lbl.config(text="Check failed", fg="#ef4444")
                self.win.after(0, _error_ui)

        threading.Thread(target=_run_check, name="BisikSettingsUpdateCheck", daemon=True).start()

    def _save(self) -> None:
        # Resolve device
        dev_label = self.device_var.get()
        dev_setting = ""
        if dev_label != "(Default System Microphone)":
            for idx, name in self.input_devices:
                if dev_label == f"[{idx}] {name}":
                    dev_setting = name
                    break

        # Toggle startup if changed
        if self.startup_var.get() != self.startup_enabled():
            self.toggle_startup()

        new_settings = Settings(
            transcription_url=self.url_var.get().strip(),
            api_key=self.api_key_var.get().strip(),
            model=self.model_var.get().strip(),
            fallback_model=self.fallback_var.get().strip(),
            language=self.settings.language,
            sample_rate=self.settings.sample_rate,
            live_preview=self.live_preview_var.get(),
            auto_paste=self.auto_paste_var.get(),
            save_transcripts=self.save_transcripts_var.get(),
            transcript_dir=self.settings.transcript_dir,
            hotkey=self.hotkey_var.get().strip().lower() or "win+o",
            vocabulary_prompt=self.prompt_text.get("1.0", "end").strip(),
            input_device=dev_setting,
            sound_feedback=self.sound_feedback_var.get(),
            show_floating_icon=self.floating_icon_var.get(),
            check_updates=self.check_updates_var.get(),
        )

        save_settings(new_settings)
        self.on_save_callback(new_settings)
        self.win.destroy()
