from __future__ import annotations

import logging
from typing import Any

import requests

from .config import Settings
from .recorder import AudioBuffer

KNOWN_HALLUCINATIONS = {
    "thank you.",
    "thank you",
    "thank you very much.",
    "thanks for watching.",
    "thanks for watching!",
    "terima kasih.",
    "terima kasih",
    "terima kasih sudah menonton.",
    "you",
    "you.",
    "bye.",
    "bye",
}


class TranscriptionError(RuntimeError):
    pass


import time

MAX_RETRIES = 3
RETRY_BACKOFF = (1.0, 2.5, 5.0)
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_PROMPT_CHARS = 800


def sanitize_prompt(prompt: str, max_chars: int = MAX_PROMPT_CHARS) -> str:
    cleaned = prompt.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars]
    last_delim = max(truncated.rfind(","), truncated.rfind(" "), truncated.rfind("."))
    if last_delim > max_chars // 2:
        return truncated[:last_delim].strip()
    return truncated.strip()


def is_model_exhausted(status_code: int, response_text: str) -> bool:
    if status_code == 429:
        return True
    if status_code in {400, 403, 404, 500, 502, 503, 504}:
        lower = response_text.lower()
        exhaustion_indicators = (
            "quota",
            "rate_limit",
            "rate limit",
            "exceeded",
            "exhausted",
            "insufficient",
            "balance",
            "credit",
            "overloaded",
            "capacity",
            "unavailable",
            "not found",
            "model_not_found",
            "model not found",
            "unsupported model",
            "tokens per minute",
            "requests per minute",
        )
        return any(term in lower for term in exhaustion_indicators)
    return False


class Transcriber:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings

    def transcribe(self, audio: AudioBuffer, label: str = "final") -> str:
        # For long audio (> 8 minutes / 480s), transcribe in chunks to respect API limits
        if audio.duration_seconds > 480.0:
            return self._transcribe_chunked(audio)

        wav_bytes = audio.to_wav_bytes(trim_silence=True)
        if not wav_bytes:
            raise TranscriptionError("No voice detected")
        return self._post_audio_with_retry(wav_bytes)

    def _transcribe_chunked(self, audio: AudioBuffer) -> str:
        chunk_seconds = 300.0  # 5-minute chunks
        total_samples = sum(frame.shape[0] for frame in audio.frames)
        samples_per_chunk = int(chunk_seconds * audio.sample_rate)
        import numpy as np

        full_audio = np.concatenate(audio.frames, axis=0)
        chunks: list[str] = []

        for start in range(0, full_audio.shape[0], samples_per_chunk):
            segment = full_audio[start : start + samples_per_chunk]
            segment_buf = AudioBuffer(frames=[segment], sample_rate=audio.sample_rate)
            wav_bytes = segment_buf.to_wav_bytes(trim_silence=True)
            if not wav_bytes:
                continue
            chunk_text = self._post_audio_with_retry(wav_bytes)
            if chunk_text:
                chunks.append(chunk_text)

        joined = " ".join(chunks).strip()
        if not joined:
            raise TranscriptionError("No speech recognized")
        return joined

    def _post_audio_with_retry(self, wav_bytes: bytes) -> str:
        if not self.settings.transcription_url:
            logging.error("transcription_api_missing_url")
            raise TranscriptionError("Missing transcription URL")

        models_to_try: list[str] = [self.settings.model]
        if self.settings.fallback_model and self.settings.fallback_model != self.settings.model:
            models_to_try.append(self.settings.fallback_model)

        headers = {"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}
        last_error: Exception | None = None

        for model_idx, current_model in enumerate(models_to_try):
            has_fallback = model_idx + 1 < len(models_to_try)
            next_model = models_to_try[model_idx + 1] if has_fallback else None

            data: dict[str, str] = {
                "model": current_model,
                "response_format": "json",
                "temperature": "0.0",
            }
            if self.settings.vocabulary_prompt:
                data["prompt"] = sanitize_prompt(self.settings.vocabulary_prompt)
            if should_send_language(self.settings.language):
                data["language"] = self.settings.language

            for attempt in range(MAX_RETRIES + 1):
                try:
                    response = self.session.post(
                        self.settings.transcription_url,
                        headers=headers,
                        data=data,
                        files={"file": ("speech.wav", wav_bytes, "audio/wav")},
                        timeout=(10, 180),
                    )

                    # Check if this model is exhausted / overloaded / rate-limited
                    if is_model_exhausted(response.status_code, response.text) and has_fallback:
                        logging.warning(
                            "model_exhausted model=%s status=%s falling_back_to=%s body=%s",
                            current_model,
                            response.status_code,
                            next_model,
                            response.text[:200],
                        )
                        break

                    if response.status_code in TRANSIENT_STATUS_CODES and attempt < MAX_RETRIES:
                        delay = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                        logging.warning(
                            "transcription_api_transient_error model=%s status=%s attempt=%s/%s retrying_in=%ss",
                            current_model,
                            response.status_code,
                            attempt + 1,
                            MAX_RETRIES,
                            delay,
                        )
                        time.sleep(delay)
                        continue

                    if response.status_code >= 400:
                        logging.error(
                            "transcription_api_http_%s model=%s body=%s",
                            response.status_code,
                            current_model,
                            response.text[:400],
                        )
                        if has_fallback:
                            logging.warning("transcription_error_falling_back model=%s next_model=%s", current_model, next_model)
                            break
                        raise TranscriptionError(f"API error {response.status_code}")

                    logging.info(
                        "transcription_api_http_%s model=%s attempt=%s",
                        response.status_code,
                        current_model,
                        attempt + 1,
                    )
                    text = extract_text(response)
                    text = sanitize_transcript(text)
                    if not text:
                        logging.info("transcription_result_empty_or_hallucination_filtered")
                        raise TranscriptionError("No speech recognized")
                    return text

                except (requests.Timeout, requests.ConnectionError) as exc:
                    last_error = exc
                    if attempt < MAX_RETRIES:
                        delay = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                        logging.warning(
                            "transcription_network_glitch model=%s type=%s attempt=%s/%s retrying_in=%ss",
                            current_model,
                            type(exc).__name__,
                            attempt + 1,
                            MAX_RETRIES,
                            delay,
                        )
                        time.sleep(delay)
                        continue
                    if has_fallback:
                        logging.warning(
                            "transcription_network_exhausted_falling_back model=%s next_model=%s",
                            current_model,
                            next_model,
                        )
                        break
                    logging.error("transcription_api_retries_exhausted model=%s error=%s", current_model, type(exc).__name__)
                    raise TranscriptionError("Connection failed after multiple retries") from exc
                except requests.RequestException as exc:
                    last_error = exc
                    logging.error("transcription_api_request_failed model=%s code=%s", current_model, type(exc).__name__)
                    if has_fallback:
                        break
                    raise TranscriptionError("Transcription request failed") from exc

        if last_error:
            raise TranscriptionError("Transcription failed after retries and fallback") from last_error
        raise TranscriptionError("Transcription failed (all models exhausted)")


def extract_text(response: requests.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return response.text.strip()
    try:
        payload: Any = response.json()
    except ValueError:
        logging.error("transcription_api_invalid_json")
        return ""
    if isinstance(payload, dict):
        value = payload.get("text") or payload.get("transcript")
        return str(value).strip() if value else ""
    return ""


def sanitize_transcript(text: str) -> str:
    cleaned = text.strip()
    if cleaned.lower() in KNOWN_HALLUCINATIONS:
        return ""
    return cleaned


def should_send_language(language: str) -> bool:
    return language.strip().lower() not in {"", "auto", "detect"}

