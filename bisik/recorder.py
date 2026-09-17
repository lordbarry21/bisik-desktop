from __future__ import annotations

import io
import logging
import os
import tempfile
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np
import sounddevice as sd


def trim_and_normalize_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    if audio.size == 0:
        return audio

    samples = audio.flatten()
    window_size = int(sample_rate * 0.03)
    if window_size <= 0 or samples.size < window_size:
        return samples

    num_windows = samples.size // window_size
    trimmed_samples = samples[: num_windows * window_size]
    windows = trimmed_samples.reshape((num_windows, window_size))

    rms = np.sqrt(np.mean(windows.astype(np.float32) ** 2, axis=1))
    speech_mask = rms > 140

    if not np.any(speech_mask):
        return np.zeros((0,), dtype=np.int16)

    start_idx = int(np.argmax(speech_mask))
    end_idx = int(num_windows - np.argmax(speech_mask[::-1]))

    pad_before = int(0.15 * sample_rate)
    pad_after = int(0.20 * sample_rate)

    sample_start = max(0, start_idx * window_size - pad_before)
    sample_end = min(samples.size, end_idx * window_size + pad_after)

    trimmed = samples[sample_start:sample_end]

    peak = float(np.max(np.abs(trimmed)))
    if peak > 200.0:
        target_peak = 26000.0
        gain = min(4.0, target_peak / peak)
        normalized = np.clip(trimmed.astype(np.float32) * gain, -32767.0, 32767.0)
        return normalized.astype(np.int16)

    return trimmed


def get_input_devices() -> list[tuple[int, str]]:
    devices: list[tuple[int, str]] = []
    try:
        seen = set()
        for idx, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                name = str(dev.get("name", f"Device {idx}")).strip()
                if name and name not in seen:
                    seen.add(name)
                    devices.append((idx, name))
    except Exception as exc:
        logging.warning("query_input_devices_failed error=%s", exc)
    return devices


def play_sound_cue(cue_type: str) -> None:
    def _play() -> None:
        try:
            import winsound
            if cue_type == "start":
                winsound.Beep(780, 25)
                winsound.Beep(1040, 35)
            elif cue_type == "stop":
                winsound.Beep(880, 30)
            elif cue_type == "done":
                winsound.Beep(980, 25)
                winsound.Beep(1320, 35)
            elif cue_type == "error":
                winsound.Beep(440, 60)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()


@dataclass(frozen=True)
class AudioBuffer:
    frames: list[np.ndarray]
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        samples = sum(frame.shape[0] for frame in self.frames)
        return samples / self.sample_rate if self.sample_rate else 0.0

    def to_wav_bytes(self, trim_silence: bool = True) -> bytes:
        if not self.frames:
            raise ValueError("audio_buffer_empty")
        audio = np.concatenate(self.frames, axis=0)
        if trim_silence:
            audio = trim_and_normalize_audio(audio, self.sample_rate)
        if audio.size == 0:
            return b""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio.astype(np.int16).tobytes())
        return buf.getvalue()

    def to_wav(self, prefix: str) -> Path:
        data = self.to_wav_bytes(trim_silence=False)
        if not data:
            raise ValueError("audio_buffer_empty")
        fd, raw_path = tempfile.mkstemp(prefix=prefix, suffix=".wav")
        path = Path(raw_path)
        os.close(fd)
        path.write_bytes(data)
        return path


class AudioRecorder:
    def __init__(self, requested_sample_rate: int, input_device: str = "") -> None:
        self.requested_sample_rate = requested_sample_rate
        self.sample_rate = requested_sample_rate
        self.input_device = input_device.strip()
        self.level = 0.0
        self._frames: list[np.ndarray] = []
        self._lock = Lock()
        self._stream: sd.InputStream | None = None

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def set_device(self, device: str) -> None:
        self.input_device = device.strip()

    def start(self) -> None:
        if self._stream:
            return
        self._frames = []
        self.level = 0.0
        self.sample_rate = self.requested_sample_rate
        dev = self._resolve_device(self.input_device)
        try:
            self._stream = self._open_stream(self.sample_rate, dev)
        except Exception as exc:
            fallback_rate = self._default_input_rate()
            logging.error("audio_open_failed_%s fallback_rate=%s dev=%s", type(exc).__name__, fallback_rate, dev)
            self.sample_rate = fallback_rate
            self._stream = self._open_stream(self.sample_rate, None)
        self._stream.start()

    def stop(self) -> AudioBuffer:
        stream = self._stream
        self._stream = None
        if stream:
            stream.stop()
            stream.close()
        with self._lock:
            frames = list(self._frames)
            self._frames = []
        return AudioBuffer(frames=frames, sample_rate=self.sample_rate)

    def _resolve_device(self, device_str: str) -> int | str | None:
        if not device_str:
            return None
        try:
            return int(device_str)
        except ValueError:
            return device_str

    def _open_stream(self, sample_rate: int, device: int | str | None) -> sd.InputStream:
        return sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            device=device,
            callback=self._on_audio,
        )

    def _on_audio(self, indata: np.ndarray, _frames: int, _time: object, status: sd.CallbackFlags) -> None:
        if status:
            logging.warning("audio_callback_status=%s", status)
        frame = indata.copy()
        with self._lock:
            self._frames.append(frame)
        mean = float(np.abs(frame.astype(np.float32)).mean() / 32768.0)
        self.level = min(1.0, mean * 16.0)

    def _default_input_rate(self) -> int:
        try:
            device = sd.query_devices(kind="input")
            return int(device.get("default_samplerate") or 44100)
        except Exception:
            return 16000
