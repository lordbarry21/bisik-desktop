#!/usr/bin/env python3
"""
Bisik Production Build Script
Author: Bari Hartanto Achmad

Compiles Bisik into:
1. PyInstaller bundled distribution (dist/Bisik)
2. Standalone Windows Installer (dist/Bisik-v1.1.0-Windows-Setup.exe)
3. Standalone Portable ZIP (dist/Bisik-v1.1.0-Windows-Portable.zip)
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list[str]) -> None:
    print(f"\n[BUILD] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def find_iscc() -> Path | None:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    # Try PATH
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    return Path(iscc) if iscc else None


def main() -> None:
    print("=" * 60)
    print("  BISIK WINDOWS PRODUCTION BUILD")
    print("  Author: Bari Hartanto Achmad")
    print("=" * 60)

    # 1. Compile PyInstaller
    print("\n[STEP 1/3] Compiling Bisik with PyInstaller...")
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "Bisik.spec"])

    # Ensure assets in dist/Bisik
    app_dist = DIST / "Bisik"
    for asset in ["kaze-icon.png", "bisik.ico", "settings.json"]:
        src = ROOT / asset
        if src.exists():
            shutil.copy2(src, app_dist / asset)
            print(f"[ASSET] Copied {asset} -> dist/Bisik/")

    # 2. Package Portable ZIP
    print("\n[STEP 2/3] Creating Portable ZIP archive...")
    zip_out = DIST / "Bisik-v1.1.0-Windows-Portable"
    shutil.make_archive(str(zip_out), "zip", app_dist)
    print(f"[SUCCESS] Portable ZIP: {zip_out}.zip")

    # 3. Inno Setup Compiler
    print("\n[STEP 3/3] Compiling Windows Installer (Inno Setup)...")
    iscc = find_iscc()
    if iscc:
        run([str(iscc), "bisik_installer.iss"])
        setup_exe = DIST / "Bisik-v1.1.0-Windows-Setup.exe"
        if setup_exe.exists():
            print(f"[SUCCESS] Windows Installer created: {setup_exe}")
    else:
        print("[WARNING] Inno Setup compiler (ISCC.exe) not found. Skipped installer compilation.")

    print("\n" + "=" * 60)
    print("  BUILD COMPLETE!")
    print(f"  Distribution directory: {DIST}")
    print("=" * 60)


if __name__ == "__main__":
    main()
