# 🎙️ Bisik Desktop

> **Ultra-Fast Whisper Speech-to-Text for Windows**  
> Dynamic Island floating mic widget powered by Groq LPU Whisper with zero-disk I/O, dual-model auto-fallback, and instant auto-paste.

---

## 🚀 Download & Quick Start

### [⬇️ **Download Bisik for Windows (v1.0.0)**](https://github.com/lordbarry21/bisik-desktop/releases/download/v1.0.0/Bisik-v1.0.0-Windows.zip)

1. **Unduh** file zip terbaru di atas (Bisik-v1.0.0-Windows.zip).
2. **Ekstrak** file .zip ke folder mana saja di laptop/PC Anda.
3. Jalankan **Bisik.exe**.
4. Selesai! Icon mikrofon bulat akan muncul di layar desktop dan di system tray (pojok kanan bawah).

---

## ✨ Fitur Utama

- **🎙️ Floating Mic Bubble:** Icon mic bulat minimalis (44px) yang selalu siap di layar. Klik icon untuk mulai merekam, klik lagi untuk selesai dan langsung menempelkan teks.
- **🏝️ Dynamic Island Recording Pill:** Tampilan minimalis modern tanpa teks yang mengganggu. Menampilkan visualizer gelombang suara real-time dan timer durasi.
- **🌐 Modern Language Popup:** Pemilih bahasa glassmorphic berujung bulat (*rounded 14px*). Mendukung **Auto Detect**, **Bahasa Indonesia (ID)**, dan **English (EN)**.
- **⚡ Zero-Disk I/O & Ultra Cepat:** Audio diproses langsung di memori RAM tanpa penulisan file temporer ke SSD/HDD.
- **🛡️ Dual-Model Auto-Fallback:** Menggunakan whisper-large-v3 untuk akurasi terbaik, dan otomatis beralih ke whisper-large-v3-turbo jika model utama sibuk atau mencapai limit.
- **📋 Universal Auto-Paste:** Otomatis menempelkan teks hasil transkripsi (Ctrl+V) langsung ke aplikasi yang sedang aktif (VS Code, Google Chrome, Microsoft Word, Slack, Notion, dll.) tanpa mengambil alih fokus jendela.
- **🎯 Drag & Drop:** Posisi icon mic dapat digeser bebas ke mana pun di layar sesuai kenyamanan Anda.

---

## ⌨️ Pintasan Keyboard & Kontrol

| Kontrol | Aksi |
| :--- | :--- |
| **Win + O** | Mulai merekam / Stop dan langsung transkrip |
| **Klik Icon Mic** | Mulai merekam / Stop |
| **Tahan & Geser (Drag)** | Pindahkan posisi icon mic di layar |
| **Klik Kanan Icon Mic** | Buka menu opsi (Retry rekaman terakhir, Buka histori transkrip, Startup, Exit) |

---

## 💻 Kebutuhan Sistem

- **Sistem Operasi:** Windows 10 / Windows 11 (64-bit)
- **Koneksi:** Internet aktif untuk transkripsi audio AI
- **Mikrofon:** Mikrofon internal laptop atau mikrofon eksternal

---

## 🔒 Privasi & Keamanan

- Audio Anda hanya dikirim saat Anda menekan tombol rekam atau mengklik icon mikrofon.
- Transkripsi diproses secara aman melalui serverless proxy berkecepatan tinggi.
- Histori transkrip tersimpan lokal di perangkat Anda (%LOCALAPPDATA%\Bisik\transcripts.txt).