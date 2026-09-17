from __future__ import annotations

import numpy as np
import requests

from bisik.config import load_settings, save_settings
from bisik.recorder import AudioBuffer, trim_and_normalize_audio
from bisik.transcriber import extract_text, sanitize_transcript, should_send_language


def test_in_memory_wav_writer() -> None:
    audio = AudioBuffer(frames=[np.zeros((160, 1), dtype=np.int16)], sample_rate=16000)
    wav_bytes = audio.to_wav_bytes(trim_silence=False)
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


def test_silence_trimming() -> None:
    sr = 16000
    silence = np.zeros(sr, dtype=np.int16)
    tone = (np.sin(np.linspace(0, 50, sr)) * 12000).astype(np.int16)
    mixed = np.concatenate([silence, tone, silence])
    trimmed = trim_and_normalize_audio(mixed, sr)
    assert len(trimmed) < len(mixed)
    assert len(trimmed) > 0

    # All silence should return empty
    all_silence = trim_and_normalize_audio(silence, sr)
    assert len(all_silence) == 0


def test_extract_text_and_sanitizer() -> None:
    response = requests.Response()
    response.status_code = 200
    response.headers["content-type"] = "application/json"
    response._content = b'{"text":"halo dunia"}'
    assert extract_text(response) == "halo dunia"
    assert sanitize_transcript("halo dunia") == "halo dunia"

    # Known hallucinations must be sanitized to empty string
    assert sanitize_transcript("Thank you.") == ""
    assert sanitize_transcript("Terima kasih.") == ""
    assert sanitize_transcript("you") == ""


def test_language_auto_detection() -> None:
    assert not should_send_language("auto")
    assert not should_send_language("")
    assert should_send_language("id")
    assert should_send_language("en")


def test_settings_persistence() -> None:
    settings = load_settings()
    assert settings.model == "whisper-large-v3"
    assert settings.fallback_model == "whisper-large-v3-turbo"
    assert "Antigravity" in settings.vocabulary_prompt
    assert settings.language in ("auto", "id", "en")
    assert isinstance(settings.show_floating_icon, bool)
    assert isinstance(settings.check_updates, bool)


def test_prompt_sanitization() -> None:
    from bisik.transcriber import sanitize_prompt

    short_prompt = "Antigravity, Gemini, React"
    assert sanitize_prompt(short_prompt) == short_prompt

    # A very long prompt (> 1000 characters) must be safely truncated to <= 800 chars
    long_prompt = "kata kunci, " * 150
    truncated = sanitize_prompt(long_prompt, max_chars=800)
    assert len(truncated) <= 800
    assert not truncated.endswith(",")


def test_model_fallback_on_exhaustion() -> None:
    from bisik.transcriber import Transcriber, is_model_exhausted

    assert is_model_exhausted(429, "Too Many Requests")
    assert is_model_exhausted(400, "Quota exceeded for whisper-large-v3")
    assert is_model_exhausted(503, "Model capacity exhausted, please retry")
    assert not is_model_exhausted(200, "ok")
    assert not is_model_exhausted(400, "invalid parameter")

    # Simulate fallback from whisper-large-v3 to whisper-large-v3-turbo
    settings = load_settings()
    transcriber = Transcriber(settings)

    call_models: list[str] = []

    def mock_post(url: str, **kwargs: object) -> requests.Response:
        data = kwargs.get("data", {})
        model_used = data.get("model") if isinstance(data, dict) else ""
        call_models.append(str(model_used))

        res = requests.Response()
        if model_used == "whisper-large-v3":
            # Primary model is exhausted
            res.status_code = 429
            res.headers["content-type"] = "application/json"
            res._content = b'{"error":"Rate limit reached / quota exhausted"}'
        else:
            # Fallback model succeeds
            res.status_code = 200
            res.headers["content-type"] = "application/json"
            res._content = b'{"text":"Fallback model turbo succeeded"}'
        return res

    transcriber.session.post = mock_post  # type: ignore[method-assign]
    audio = AudioBuffer(frames=[(np.sin(np.linspace(0, 10, 16000)) * 10000).astype(np.int16).reshape(-1, 1)], sample_rate=16000)
    result = transcriber.transcribe(audio)

    assert result == "Fallback model turbo succeeded"
    assert call_models == ["whisper-large-v3", "whisper-large-v3-turbo"]


def test_updater_version_checks() -> None:
    from bisik.updater import parse_version, is_newer_version

    assert parse_version("1.1.0") == (1, 1, 0)
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("v2.0.0-rc1") == (2, 0, 0)
    assert parse_version("2") == (2,)

    assert is_newer_version("1.2.0", "1.1.0") is True
    assert is_newer_version("v1.10.0", "v1.9.0") is True
    assert is_newer_version("1.1.0", "1.1.0") is False
    assert is_newer_version("1.0.9", "1.1.0") is False
    assert is_newer_version("v1.0.0", "1.1.0") is False
    assert is_newer_version("2.0.0", "1.9.9") is True




def test_startup_and_tray_message_safety() -> None:
    from pathlib import Path
    from bisik.tray import TrayIcon, TRAY_MESSAGE, WM_LBUTTONDBLCLK

    toggled = []
    opened = []

    tray = TrayIcon(
        title="TestBisik",
        icon_path=Path("bisik.ico"),
        on_toggle=lambda: toggled.append(True),
        on_menu=lambda x, y: None,
        on_open=lambda: opened.append(True),
        on_exit=lambda: None,
        is_recording=lambda: False,
    )

    cmd = tray._startup_command()
    assert "--startup" in cmd, f"Expected --startup in startup command, got: {cmd}"

    # Simulating double-click on tray icon or activate message from second instance
    # MUST call on_open and MUST NOT call on_toggle (which starts recording!)
    res = tray._window_proc(0, TRAY_MESSAGE, 0, WM_LBUTTONDBLCLK)
    assert res == 0
    assert len(opened) == 1, "on_open should have been called"
    assert len(toggled) == 0, "on_toggle MUST NOT be called on double click / startup!"

if __name__ == "__main__":
    test_in_memory_wav_writer()
    test_silence_trimming()
    test_extract_text_and_sanitizer()
    test_language_auto_detection()
    test_settings_persistence()
    test_prompt_sanitization()
    test_model_fallback_on_exhaustion()
    test_updater_version_checks()
    test_startup_and_tray_message_safety()
    print("all_tests_passed")
