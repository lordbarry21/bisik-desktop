from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_NAME = "Bisik"
APP_VERSION = "1.1.0"
APP_AUTHOR = "Bari Hartanto Achmad"
GITHUB_REPO = "lordbarry21/bisik-desktop"
UPDATE_CHECK_INTERVAL_SECONDS = 3 * 60 * 60

DEFAULT_VOCABULARY_PROMPT = (
    "Percakapan coding, AI, dan software engineering dalam bahasa Indonesia dan English: "
    "Antigravity, Gemini, Claude, DeepSeek, Qwen, Whisper, Next.js, React, Tailwind, "
    "Python, TypeScript, JavaScript, JSON, API, UI, frontend, backend, bug, refactor, commit, PRD, npm, prompt."
)


@dataclass(frozen=True)
class Settings:
    transcription_url: str
    api_key: str
    model: str
    language: str
    sample_rate: int
    live_preview: bool
    auto_paste: bool
    save_transcripts: bool
    transcript_dir: Path
    hotkey: str = "win+o"
    vocabulary_prompt: str = DEFAULT_VOCABULARY_PROMPT
    fallback_model: str = "whisper-large-v3-turbo"
    input_device: str = ""
    sound_feedback: bool = True
    show_floating_icon: bool = True
    check_updates: bool = True


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and (Path(meipass) / "kaze-icon.png").exists():
            return Path(meipass)
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "_internal" / "kaze-icon.png").exists():
            return exe_dir / "_internal"
        return exe_dir
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Local"
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    user_file = data_dir() / "settings.json"
    if user_file.exists():
        return user_file
    if getattr(sys, "frozen", False):
        exe_file = Path(sys.executable).resolve().parent / "settings.json"
        if exe_file.exists():
            return exe_file
    return app_root() / "settings.json"


def load_settings() -> Settings:
    values = _read_json(settings_path())
    transcript_dir = Path(values.get("transcript_dir") or data_dir())
    transcript_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        transcription_url=str(values.get("transcription_url", "https://bisik-proxy.vercel.app/api/transcribe")).strip(),
        api_key=os.environ.get("BISIK_API_KEY", str(values.get("api_key", "")).strip()),
        model=str(values.get("model", "whisper-large-v3")).strip(),
        language=str(values.get("language", "auto")).strip().lower(),
        sample_rate=int(values.get("sample_rate", 16000)),
        live_preview=bool(values.get("live_preview", False)),
        auto_paste=bool(values.get("auto_paste", True)),
        save_transcripts=bool(values.get("save_transcripts", True)),
        transcript_dir=transcript_dir,
        hotkey=str(values.get("hotkey", "win+o")).strip().lower(),
        vocabulary_prompt=str(values.get("vocabulary_prompt", DEFAULT_VOCABULARY_PROMPT)).strip(),
        fallback_model=str(values.get("fallback_model", "whisper-large-v3-turbo")).strip(),
        input_device=str(values.get("input_device", "")).strip(),
        sound_feedback=bool(values.get("sound_feedback", True)),
        show_floating_icon=bool(values.get("show_floating_icon", True)),
        check_updates=bool(values.get("check_updates", True)),
    )


def save_settings(settings: Settings) -> None:
    data = {
        "transcription_url": settings.transcription_url,
        "api_key": settings.api_key,
        "model": settings.model,
        "fallback_model": settings.fallback_model,
        "language": settings.language,
        "sample_rate": settings.sample_rate,
        "live_preview": settings.live_preview,
        "auto_paste": settings.auto_paste,
        "save_transcripts": settings.save_transcripts,
        "hotkey": settings.hotkey,
        "vocabulary_prompt": settings.vocabulary_prompt,
        "input_device": settings.input_device,
        "sound_feedback": settings.sound_feedback,
        "show_floating_icon": settings.show_floating_icon,
        "check_updates": settings.check_updates,
    }
    target = settings_path()
    try:
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logging.info("settings_saved language=%s hotkey=%s device=%s", settings.language, settings.hotkey, settings.input_device)
    except OSError as exc:
        logging.error("settings_save_failed code=%s", type(exc).__name__)


def setup_logging() -> None:
    log_file = data_dir() / "bisik.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        logging.error("settings_missing path=%s", path)
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logging.error("settings_invalid_json line=%s column=%s", exc.lineno, exc.colno)
        return {}
