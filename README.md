<div align="center">

<img src="assets/logo.png" width="120" height="120" alt="Bisik Logo" style="border-radius: 26px;" />

# 🎙️ Bisik

**Ultra-fast, distraction-free AI voice typing & dictation assistant for Windows.**  
Powered by OpenAI's Whisper Large v3 with per-pixel alpha floating Dynamic Island.

[![Release](https://img.shields.io/badge/Release-v1.1.0-38bdf8?style=for-the-badge&logo=windows)](https://github.com/lordbarry21/bisik-desktop/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows_10_%7C_11_(64--bit)-0284c7?style=for-the-badge&logo=windows11)](https://github.com/lordbarry21/bisik-desktop)
[![License](https://img.shields.io/badge/License-MIT-10b981?style=for-the-badge)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Bari_Hartanto_Achmad-8b5cf6?style=for-the-badge)](https://github.com/lordbarry21)

<br/>

[**Download Windows Installer (.exe)**](https://github.com/lordbarry21/bisik-desktop/releases/latest) • [**Download Portable (.zip)**](https://github.com/lordbarry21/bisik-desktop/releases/latest) • [**Report Issue**](https://github.com/lordbarry21/bisik-desktop/issues)

</div>

---

## 🌟 Overview

**Bisik** (Indonesian for *"Whisper"*) is a native Windows voice dictation tool inspired by Wispr Flow and Superwhisper. It sits unobtrusively on your desktop as a sleek circular microphone bubble. 

Press **`Win+O`** anywhere—in VS Code, Chrome, Slack, Word, Discord, or Terminal—speak naturally, and watch your voice transcribe and auto-paste directly into your active cursor position in milliseconds.

```
       [ 🎙️ 44px Bubble ]  ──( Click / Win+O )──►  [ 🔴 00:08 ||||||| 🌐 AUTO ▾  ✕ ]
```

---

## ✨ Features

- 🏝️ **Floating Dynamic Island UI**: 
  - Sits as a minimalist 44px circular mic bubble when idle.
  - **Show or Hide On Demand**: Toggle the floating icon via the right-click menu or Settings to keep your desktop completely distraction-free when idle. The island seamlessly appears whenever you trigger dictation.
  - Expands smoothly to a 240px recording pill with live audio waveform bars, speech timer, status indicator, language selector, and close button.
  - **Zero Jagged Edges**: Rendered via Win32 hardware-accelerated per-pixel alpha (`UpdateLayeredWindow`), blending seamlessly into white, dark, or wallpaper backgrounds with zero halo or pixelation.
  - Click-through transparency outside the pill boundaries.

- 🔎 **Full Windows Integration**:
  - Automatically indexed in **Windows Search** (press Start, type `Bisik`, hit Enter).
  - Clean **Desktop Shortcut** and **Start Menu** entry.
  - Registered in Windows Settings & Control Panel (Add or Remove Programs) with dedicated 1-click uninstaller.
  - Single-instance protection via Win32 Mutex (never runs conflicting duplicates).
  - Native Per-Monitor High-DPI awareness (razor sharp on 100%, 125%, 150%, 200% displays).

- 🧠 **Whisper Large v3 with Dual-Model Auto-Fallback**:
  - Uses state-of-the-art `whisper-large-v3` for human-level accuracy.
  - Automatic, seamless fallback to `whisper-large-v3-turbo` if the primary model is rate-limited or exhausted.

- 🛡️ **Anti-Hallucination & Speech Normalization**:
  - Pre-transcription RMS energy gating cuts out leading and trailing silence.
  - Filters ghost hallucinations (*"Thank you for watching"*, *"Bye"*, etc.).
  - Automatic gain control and peak normalization for whisper-quiet and loud environments.

- ⚙️ **Modern Dark-Mode Settings Center**:
  - Configure API endpoints, API keys, and custom models.
  - Choose your preferred microphone input device from detected hardware.
  - Customize global toggle hotkey (e.g. `Win+O`, `Ctrl+Shift+Space`).
  - Toggle subtle audio feedback chimes on start/finish.
  - Customize technical vocabulary and programming keyword prompts.

- 🌐 **Instant Multi-Language Dictation**:
  - Quick-switch between **Auto Detect**, **Bahasa Indonesia (ID)**, and **English (EN)** directly from the pill widget or system tray.

- 🔄 **Automatic Update Reminders**:
  - Background daemon checks GitHub Releases periodically every 3 hours.
  - Non-intrusive Windows system tray notifications when a new version is published.
  - Direct download shortcut from the system tray menu and Settings Center.
  - Manual "Check for updates" option at any time.

---

## 📥 Installation

### Method 1: Windows Setup Installer (Recommended)

1. Download **`Bisik-v1.1.0-Windows-Setup.exe`** from [Releases](https://github.com/lordbarry21/bisik-desktop/releases/latest).
2. Run the installer (no administrator privileges needed—installs cleanly to `%LOCALAPPDATA%\Programs\Bisik`).
3. Follow the wizard to add a **Desktop shortcut** and enable **Auto-start with Windows**.
4. Bisik will launch immediately and be accessible from **Windows Search**, **Desktop**, and the **System Tray**.

### Method 2: Portable Edition

1. Download **`Bisik-v1.1.0-Windows-Portable.zip`**.
2. Extract anywhere on your PC (e.g. `D:\Apps\Bisik`).
3. Run `Bisik.exe`. All configurations and logs will stay portable.

### Method 3: Run from Source

```bash
# Clone the repository
git clone https://github.com/lordbarry21/bisik-desktop.git
cd bisik

# Install dependencies
pip install -r requirements.txt

# Run Bisik
python main.py
```

---

## ⌨️ How to Use

| Action | Shortcut / Gesture | Description |
| :--- | :--- | :--- |
| **Toggle Recording** | `Win + O` (or click mic bubble) | Starts recording audio with waveform visualization |
| **Stop & Transcribe** | `Win + O` (or click anywhere on pill) | Stops recording, transcribes, and auto-pastes at cursor |
| **Switch Language** | Click `🌐 AUTO ▾` on pill | Opens popup to switch between Auto, ID, and EN |
| **Cancel Recording** | Click `✕` button on pill | Discards current audio buffer without transcribing |
| **Move Overlay** | Left-Click & Drag | Relocate the floating widget anywhere on your screen |
| **System Tray Menu** | Right-Click Tray Icon | Access Settings, Transcripts folder, Startup toggle, and Exit |
| **Open Settings** | Tray Menu → Settings... | Configure API keys, microphone device, hotkey, and audio cues |

---

## ⚙️ Configuration (`settings.json`)

Settings can be edited visually in the **Settings Center** or manually via `settings.json`:

```json
{
  "transcription_url": "https://bisik-proxy.vercel.app/api/transcribe",
  "api_key": "",
  "model": "whisper-large-v3",
  "fallback_model": "whisper-large-v3-turbo",
  "language": "auto",
  "sample_rate": 16000,
  "live_preview": false,
  "auto_paste": true,
  "save_transcripts": true,
  "hotkey": "win+o",
  "sound_feedback": true,
  "input_device": "",
  "vocabulary_prompt": "Percakapan coding, AI, dan software engineering dalam bahasa Indonesia dan English: Antigravity, Gemini, Claude, DeepSeek, Qwen, Whisper, Next.js, React, Tailwind, Python, TypeScript, JavaScript, JSON, API, UI, frontend, backend, bug, refactor, commit, PRD, npm, prompt."
}
```

---

## 🛠️ Building & Packaging

To compile the standalone binary and Inno Setup installer locally:

```powershell
# Automated one-click build (PyInstaller + Inno Setup + Portable ZIP)
python build.py
```

The output artifacts will be placed in `dist/`:
- `dist/Bisik/Bisik.exe` (Standalone executable directory)
- `dist/Bisik-v1.1.0-Windows-Setup.exe` (Windows Installer)
- `dist/Bisik-v1.1.0-Windows-Portable.zip` (Portable release archive)

---

## 👨‍💻 Author

Crafted with vibe coding by **Bari Hartanto Achmad**  
- GitHub: [@lordbarry21](https://github.com/lordbarry21)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
