from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Literal, Any

from PIL import Image

from .config import APP_NAME, APP_VERSION, APP_AUTHOR, Settings, app_root, data_dir, load_settings, save_settings, setup_logging
from .overlay import Overlay
from .recorder import AudioBuffer, AudioRecorder, play_sound_cue
from .transcriber import Transcriber, TranscriptionError
from .tray import TrayIcon
from .settings_window import SettingsWindow
from .updater import ReleaseInfo, UpdateChecker

CommandValue = Any
Command = tuple[str, CommandValue, int | None]
State = Literal["ready", "recording", "transcribing"]

MUTEX_NAME = "Global\\Bisik_SingleInstance_Mutex_Bari"


def init_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def acquire_single_instance_mutex():
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    ERROR_ALREADY_EXISTS = 183
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        is_startup = "--startup" in sys.argv or "--silent" in sys.argv
        if not is_startup:
            hwnd = user32.FindWindowW("BisikTrayWindow", None)
            if hwnd:
                user32.PostMessageW(hwnd, 0x8000 + 11, 0, 0x0203)
        return None
    return mutex


class AppController:
    def __init__(self, settings: Settings, overlay: Overlay) -> None:
        self.settings = settings
        self.overlay = overlay
        self.recorder = AudioRecorder(settings.sample_rate, settings.input_device)
        self.transcriber = Transcriber(settings)
        self.commands: Queue[Command] = Queue()
        self.state: State = "ready"
        self._recording_start_time = 0.0
        self._tray: TrayIcon | None = None
        self._paste_target_hwnd: int | None = None
        self._session_id = 0
        self._settings_window: SettingsWindow | None = None
        self._available_update: ReleaseInfo | None = None
        self._updater = UpdateChecker(on_update_found=lambda info: self.enqueue("update_available", info))

        self.overlay.set_language(self.settings.language)
        self.overlay.set_show_floating_icon(self.settings.show_floating_icon)
        self.overlay.set_close_handler(self.dismiss_overlay)
        self.overlay.set_language_handler(self.change_language)
        self.overlay.set_toggle_handler(self.toggle)
        self.overlay.set_menu_handler(lambda x, y: self.enqueue("menu", (x, y)))

    def run(self) -> None:
        icon_path = ensure_icon(data_dir())
        self._tray = TrayIcon(
            APP_NAME,
            icon_path,
            lambda: self.enqueue("toggle"),
            lambda x, y: self.enqueue("menu", (x, y)),
            lambda: self.enqueue("open_app"),
            lambda: self.enqueue("exit"),
            lambda: self.state == "recording",
            hotkey=self.settings.hotkey,
        )
        self._tray.start()
        self._tray.clean_duplicate_startup()
        if self.settings.check_updates:
            self._updater.start()
        if self.settings.show_floating_icon:
            self.overlay.show_idle()
        else:
            self.overlay.hide()
        self.overlay.dispatch_later(self._poll_commands, 16)
        self.overlay.root.mainloop()

    def enqueue(self, name: str, value: CommandValue = None, session_id: int | None = None) -> None:
        self.commands.put((name, value, session_id))

    def change_language(self, language: str) -> None:
        self.settings = replace(self.settings, language=language)
        self.transcriber.update_settings(self.settings)
        self.overlay.set_language(language)
        save_settings(self.settings)

    def apply_settings(self, new_settings: Settings) -> None:
        self.settings = new_settings
        self.transcriber.update_settings(new_settings)
        self.recorder.set_device(new_settings.input_device)
        self.overlay.set_language(new_settings.language)
        self.overlay.set_show_floating_icon(new_settings.show_floating_icon)
        if new_settings.show_floating_icon:
            if self.state == "ready":
                self.overlay.show_idle()
        else:
            if self.state == "ready":
                self.overlay.hide()
        if self._tray and new_settings.hotkey != self._tray.hotkey:
            self._tray.hotkey = new_settings.hotkey
            self._tray._register_hotkey()
        if new_settings.check_updates and not self.settings.check_updates:
            self._updater.start()
        elif not new_settings.check_updates and self.settings.check_updates:
            self._updater.stop()

    def toggle_floating_icon(self) -> None:
        new_state = not self.settings.show_floating_icon
        self.settings = replace(self.settings, show_floating_icon=new_state)
        self.overlay.set_show_floating_icon(new_state)
        save_settings(self.settings)
        if new_state:
            if self.state == "ready":
                self.overlay.show_idle()
        else:
            if self.state == "ready":
                self.overlay.hide()

    def open_settings(self) -> None:
        if self._settings_window and self._settings_window.win.winfo_exists():
            self._settings_window.win.lift()
            self._settings_window.win.focus_set()
            return
        self._settings_window = SettingsWindow(
            self.overlay.root,
            self.settings,
            self.apply_settings,
            self._tray.startup_enabled if self._tray else lambda: False,
            self._tray.toggle_startup if self._tray else lambda: None,
            latest_release=self._available_update,
            check_update_fn=self._updater.check_now,
        )

    def toggle(self) -> None:
        if self.state == "recording":
            self.stop_recording()
        elif self.state == "ready":
            self.start_recording()

    def start_recording(self) -> None:
        self._session_id += 1
        self._paste_target_hwnd = get_foreground_window()
        try:
            self.recorder.start()
            if self.settings.sound_feedback:
                play_sound_cue("start")
        except Exception as exc:
            logging.error("audio_start_failed code=%s", type(exc).__name__)
            if self.settings.sound_feedback:
                play_sound_cue("error")
            self.overlay.show("error", hide_after_ms=3000)
            return
        self.state = "recording"
        self._recording_start_time = time.monotonic()
        self.overlay.set_duration(0.0)
        self.overlay.show("recording")

    def stop_recording(self) -> None:
        audio = self.recorder.stop()
        if self.settings.sound_feedback:
            play_sound_cue("stop")
        if audio.duration_seconds < 0.25:
            self.state = "ready"
            if self.settings.sound_feedback:
                play_sound_cue("error")
            self.overlay.show("error", hide_after_ms=1000)
            return
        self.state = "transcribing"
        self.overlay.set_duration(audio.duration_seconds)
        self.overlay.show("transcribing")
        threading.Thread(target=self._final_transcribe, args=(audio, self._session_id), name="BisikFinalTranscribe", daemon=True).start()

    def close(self) -> None:
        if self.recorder.is_recording:
            self.recorder.stop()
        self._updater.stop()
        if self._tray:
            self._tray.stop()
        self.overlay.close()

    def dismiss_overlay(self) -> None:
        if self.recorder.is_recording:
            self.recorder.stop()
            self.state = "ready"
            self._session_id += 1
        if self.settings.show_floating_icon:
            self.overlay.show_idle()
        else:
            self.overlay.hide()

    def _poll_commands(self) -> None:
        while not self.commands.empty():
            name, value, session_id = self.commands.get()
            if name == "toggle":
                self.toggle()
            elif name == "toggle_icon":
                self.toggle_floating_icon()
            elif name == "update_available" and isinstance(value, ReleaseInfo):
                self._available_update = value
                if self._tray:
                    self._tray.notify("Bisik Update Available", f"Version {value.version} is available! Right-click tray to download.")
            elif name == "update_latest" and isinstance(value, ReleaseInfo):
                if self._tray:
                    self._tray.notify("Bisik is Up to Date", f"You are running the latest version (v{APP_VERSION}).")
            elif name == "update_failed":
                if self._tray:
                    self._tray.notify("Update Check", "Unable to check for updates. Please check your connection.")
            elif name == "menu" and isinstance(value, tuple):
                self._show_tray_menu(value[0], value[1])
            elif name == "done" and value and session_id == self._session_id:
                if self.settings.sound_feedback:
                    play_sound_cue("done")
                self.overlay.show("done", hide_after_ms=450)
                self._handle_transcript(str(value))
            elif name == "error" and session_id == self._session_id:
                self.state = "ready"
                if self.settings.sound_feedback:
                    play_sound_cue("error")
                self.overlay.show("error", hide_after_ms=1200)
                if self._tray and value:
                    self._tray.notify("Bisik Transcription Error", str(value))
            elif name == "settings":
                self.open_settings()
            elif name in ("open_app", "open"):
                if self.settings.show_floating_icon:
                    self.overlay.show_idle()
                self.open_settings()
            elif name == "exit":
                self.close()
                return

        if self.state == "recording":
            elapsed = time.monotonic() - self._recording_start_time
            self.overlay.set_duration(elapsed)
            self.overlay.set_level(self.recorder.level)

        self.overlay.dispatch_later(self._poll_commands, 16)

    def _show_tray_menu(self, x: int, y: int) -> None:
        menu = tk.Menu(self.overlay.root, tearoff=0)
        if self._available_update and self._available_update.is_newer:
            target_url = self._available_update.download_url or self._available_update.html_url
            menu.add_command(
                label=f"✨ Update Available (v{self._available_update.version})",
                command=lambda: webbrowser.open(target_url),
            )
            menu.add_separator()
        menu.add_command(label="Stop recording" if self.state == "recording" else "Start recording", command=self.toggle)
        menu.add_command(label="Retry last recording", command=self.retry_last_recording)
        menu.add_separator()
        menu.add_command(
            label="Hide floating icon" if self.settings.show_floating_icon else "Show floating icon",
            command=self.toggle_floating_icon,
        )
        menu.add_separator()

        lang_menu = tk.Menu(menu, tearoff=0)
        languages = [("auto", "Auto Detect"), ("id", "Bahasa Indonesia (ID)"), ("en", "English (EN)")]
        for code, label in languages:
            mark = "● " if self.settings.language == code else "○ "
            lang_menu.add_command(label=f"{mark}{label}", command=lambda c=code: self.change_language(c))
        menu.add_cascade(label=f"Language ({self.settings.language.upper()})", menu=lang_menu)

        menu.add_command(label="Settings...", command=self.open_settings)
        menu.add_command(label="Check for updates...", command=self.check_updates_manual)
        menu.add_command(label="Open transcripts folder", command=lambda: os.startfile(self.settings.transcript_dir))
        enabled = self._tray.startup_enabled() if self._tray else False
        menu.add_command(label=("[x] " if enabled else "[ ] ") + "Start with Windows", command=self._toggle_startup)
        menu.add_separator()
        menu.add_command(label=f"About {APP_NAME}", command=self.open_settings)
        menu.add_command(label="Exit", command=self.close)
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def check_updates_manual(self) -> None:
        def _bg() -> None:
            info = self._updater.check_now()
            if info and info.is_newer:
                self.enqueue("update_available", info)
            elif info:
                self.enqueue("update_latest", info)
            else:
                self.enqueue("update_failed")

        threading.Thread(target=_bg, name="BisikManualUpdate", daemon=True).start()

    def _toggle_startup(self) -> None:
        if self._tray:
            self._tray.toggle_startup()

    def _final_transcribe(self, audio: AudioBuffer, session_id: int) -> None:
        self._last_audio = audio
        try:
            text = self.transcriber.transcribe(audio, "final")
        except TranscriptionError as exc:
            logging.warning("transcription_error msg=%s", exc)
            self._save_rescue_audio(audio)
            self.enqueue("error", str(exc), session_id)
            return
        self.enqueue("done", text, session_id)

    def _save_rescue_audio(self, audio: AudioBuffer) -> None:
        try:
            rescue_path = data_dir() / "last_recording.wav"
            data = audio.to_wav_bytes(trim_silence=False)
            if data:
                rescue_path.write_bytes(data)
                logging.info("rescue_audio_saved path=%s size=%s", rescue_path, len(data))
        except Exception as exc:
            logging.error("rescue_audio_save_failed error=%s", type(exc).__name__)

    def retry_last_recording(self) -> None:
        if self.state != "ready":
            return
        audio = getattr(self, "_last_audio", None)
        if not audio:
            rescue_path = data_dir() / "last_recording.wav"
            if rescue_path.exists():
                import wave
                import numpy as np

                try:
                    with wave.open(str(rescue_path), "rb") as wf:
                        sr = wf.getframerate()
                        frames_data = wf.readframes(wf.getnframes())
                        arr = np.frombuffer(frames_data, dtype=np.int16).reshape(-1, 1)
                        audio = AudioBuffer(frames=[arr], sample_rate=sr)
                        self._last_audio = audio
                except Exception as exc:
                    logging.error("failed_reading_rescue_audio error=%s", type(exc).__name__)

        if not audio:
            self.overlay.show("error", hide_after_ms=1200)
            return

        self._session_id += 1
        self._paste_target_hwnd = get_foreground_window()
        self.state = "transcribing"
        self.overlay.set_duration(audio.duration_seconds)
        self.overlay.show("transcribing")
        threading.Thread(
            target=self._final_transcribe,
            args=(audio, self._session_id),
            name="BisikRetryTranscribe",
            daemon=True,
        ).start()

    def _handle_transcript(self, text: str) -> None:
        self.state = "ready"
        self._copy_to_clipboard(text)
        if self.settings.save_transcripts:
            self._save_transcript(text)
        if self.settings.auto_paste:
            self.overlay.dispatch_later(self._paste_clipboard, 120)

    def _copy_to_clipboard(self, text: str) -> None:
        self.overlay.root.clipboard_clear()
        self.overlay.root.clipboard_append(text)
        self.overlay.root.update()

    def _paste_clipboard(self) -> None:
        try:
            import keyboard

            if not focus_window(self._paste_target_hwnd):
                logging.error("paste_target_focus_failed hwnd=%s", self._paste_target_hwnd)
                return
            keyboard.send("ctrl+v")
        except Exception as exc:
            logging.error("auto_paste_failed code=%s", type(exc).__name__)

    def _save_transcript(self, text: str) -> None:
        path = self.settings.transcript_dir / "transcripts.txt"
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as file:
            file.write(f"[{stamp}] {text}\n")


def ensure_icon(folder: Path) -> Path:
    path = folder / "bisik-kaze.ico"
    image = Image.open(app_root() / "kaze-icon.png").convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
    image.save(path, sizes=[(256, 256), (64, 64), (32, 32), (16, 16)])
    return path


def get_foreground_window() -> int | None:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    return int(hwnd) if hwnd else None


def focus_window(hwnd: int | None) -> bool:
    user32 = ctypes.windll.user32
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    return bool(user32.SetForegroundWindow(hwnd))


def main() -> None:
    init_dpi_awareness()
    setup_logging()
    mutex = acquire_single_instance_mutex()
    if not mutex:
        logging.info("bisik_another_instance_already_running_exiting")
        sys.exit(0)

    settings = load_settings()
    overlay = Overlay()
    app = AppController(settings, overlay)
    try:
        app.run()
    finally:
        if mutex:
            ctypes.windll.kernel32.CloseHandle(mutex)
