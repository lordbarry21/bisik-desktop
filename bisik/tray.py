from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import winreg
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path


WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_HOTKEY = 0x0312
WM_APP = 0x8000
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001
NIIF_USER = 0x00000004
NIIF_LARGE_ICON = 0x00000020
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
MOD_WIN = 0x0008

HOTKEY_ID = 42
TRAY_MESSAGE = WM_APP + 11
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
kernel32 = ctypes.windll.kernel32


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


class TrayIcon:
    def __init__(
        self,
        title: str,
        icon_path: Path,
        on_toggle: Callable[[], None],
        on_menu: Callable[[int, int], None],
        on_open: Callable[[], None],
        on_exit: Callable[[], None],
        is_recording: Callable[[], bool],
        hotkey: str = "win+o",
    ) -> None:
        self.title = title
        self.icon_path = icon_path
        self.on_toggle = on_toggle
        self.on_menu = on_menu
        self.on_open = on_open
        self.on_exit = on_exit
        self.is_recording = is_recording
        self.hotkey = hotkey.strip().lower() or "win+o"
        self._hwnd: int | None = None
        self._hicon: int | None = None
        self._keyboard_hotkey: object | None = None
        self._wndproc = WNDPROC(self._window_proc)
        self._thread = threading.Thread(target=self._run, name="BisikTray", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)

    def _run(self) -> None:
        hinstance = kernel32.GetModuleHandleW(None)
        class_name = "BisikTrayWindow"
        wnd_class = WNDCLASS(0, self._wndproc, 0, 0, hinstance, 0, 0, 0, None, class_name)
        user32.RegisterClassW(ctypes.byref(wnd_class))
        self._hwnd = user32.CreateWindowExW(0, class_name, self.title, 0, 0, 0, 0, 0, None, None, hinstance, None)
        self._add_icon()
        self._register_hotkey()
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _window_proc(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        if message == TRAY_MESSAGE:
            if lparam == WM_LBUTTONDBLCLK:
                self.on_open()
            elif lparam == WM_RBUTTONUP:
                point = POINT()
                user32.GetCursorPos(ctypes.byref(point))
                self.on_menu(point.x, point.y)
            return 0
        if message == WM_HOTKEY and wparam == HOTKEY_ID:
            self.on_toggle()
            return 0
        if message in (WM_CLOSE, WM_DESTROY):
            self._delete_icon()
            user32.UnregisterHotKey(hwnd, HOTKEY_ID)
            self._remove_keyboard_fallback()
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def _add_icon(self) -> None:
        self._hicon = user32.LoadImageW(None, str(self.icon_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not self._hicon:
            self._hicon = user32.LoadIconW(None, 32512)
        nid = self._notify_data()
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            logging.error("tray_icon_add_failed code=%s", kernel32.GetLastError())
        else:
            self.notify("Bisik is running", "Press Win+O to start or stop transcription.")

    def _delete_icon(self) -> None:
        if self._hwnd:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._notify_data()))

    def _notify_data(self) -> NOTIFYICONDATA:
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = self._hwnd or 0
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = TRAY_MESSAGE
        nid.hIcon = self._hicon or 0
        nid.szTip = self.title
        return nid

    def notify(self, title: str, message: str) -> None:
        nid = self._notify_data()
        nid.uFlags |= NIF_INFO
        nid.szInfoTitle = title[:63]
        nid.szInfo = message[:255]
        nid.dwInfoFlags = NIIF_USER | NIIF_LARGE_ICON
        nid.hBalloonIcon = self._hicon or 0
        if not shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)):
            logging.warning("tray_notify_failed code=%s", kernel32.GetLastError())

    def _register_hotkey(self) -> None:
        if not self._hwnd:
            return
        if self.hotkey in ("win+o", "windows+o"):
            if user32.RegisterHotKey(self._hwnd, HOTKEY_ID, MOD_WIN, ord("O")):
                logging.info("hotkey_registered_win_o")
                return
            logging.info("hotkey_win_o_reserved_by_windows_using_keyboard_hook")
        self._register_keyboard_fallback()

    def _register_keyboard_fallback(self) -> None:
        try:
            import keyboard

            target_key = "windows+o" if self.hotkey in ("win+o", "windows+o") else self.hotkey
            self._keyboard_hotkey = keyboard.add_hotkey(target_key, self.on_toggle, suppress=False)
            logging.info("hotkey_hook_fallback_registered key=%s", target_key)
        except Exception as exc:
            logging.error("hotkey_hook_fallback_failed key=%s error=%s", self.hotkey, type(exc).__name__)

    def _remove_keyboard_fallback(self) -> None:
        if self._keyboard_hotkey is None:
            return
        try:
            import keyboard

            keyboard.remove_hotkey(self._keyboard_hotkey)
        except Exception as exc:
            logging.warning("hotkey_hook_remove_failed code=%s", type(exc).__name__)

    def _startup_shortcut_path(self) -> Path:
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / f"{self.title}.lnk"

    def clean_duplicate_startup(self) -> None:
        try:
            shortcut = self._startup_shortcut_path()
            if shortcut.exists():
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                    value, _ = winreg.QueryValueEx(key, self.title)
                    if value:
                        shortcut.unlink()
                        logging.info("clean_duplicate_startup_shortcut path=%s", shortcut)
        except Exception:
            pass

    def toggle_startup(self) -> None:
        shortcut = self._startup_shortcut_path()
        if self.startup_enabled():
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    try:
                        winreg.DeleteValue(key, self.title)
                    except FileNotFoundError:
                        pass
            except OSError as exc:
                logging.error("startup_registry_delete_failed code=%s", exc.winerror)
            try:
                if shortcut.exists():
                    shortcut.unlink()
            except OSError as exc:
                logging.error("startup_shortcut_delete_failed code=%s", exc)
        else:
            try:
                if shortcut.exists():
                    shortcut.unlink()
            except OSError:
                pass
            try:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                    winreg.SetValueEx(key, self.title, 0, winreg.REG_SZ, self._startup_command())
            except OSError as exc:
                logging.error("startup_toggle_failed code=%s", exc.winerror)

    def startup_enabled(self) -> bool:
        if self._startup_shortcut_path().exists():
            return True
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, self.title)
                return bool(value)
        except FileNotFoundError:
            return False
        except OSError as exc:
            logging.warning("startup_query_failed code=%s", exc.winerror)
            return False

    def _startup_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}" --startup'
        return f'"{Path(sys.executable).resolve()}" "{Path(sys.argv[0]).resolve()}" --startup'
