from __future__ import annotations

import tkinter as tk
import ctypes
from ctypes import wintypes
import math
import time
from collections.abc import Callable
from .config import app_root

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
ULW_ALPHA = 0x02
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class LayeredSurface:
    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.hwnd = hwnd
        self.width = width
        self.height = height

        ex_style = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED | WS_EX_TOOLWINDOW)

        self._hdc_screen = user32.GetDC(0)
        self._hdc_mem = gdi32.CreateCompatibleDC(self._hdc_screen)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        self._bits = ctypes.c_void_p()
        self._hbitmap = gdi32.CreateDIBSection(
            self._hdc_screen, ctypes.byref(bmi), 0, ctypes.byref(self._bits), None, 0
        )
        self._old_bmp = gdi32.SelectObject(self._hdc_mem, self._hbitmap)
        self._blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        self._pt_src = POINT(0, 0)
        self._size = SIZE(width, height)

    def render(self, img: Image.Image) -> bool:
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
        arr = np.array(img, dtype=np.uint8)
        a = arr[:, :, 3].astype(np.uint16)
        r = (arr[:, :, 0].astype(np.uint16) * a // 255).astype(np.uint8)
        g = (arr[:, :, 1].astype(np.uint16) * a // 255).astype(np.uint8)
        b = (arr[:, :, 2].astype(np.uint16) * a // 255).astype(np.uint8)
        bgra = np.dstack([b, g, r, arr[:, :, 3]])

        ctypes.memmove(self._bits, bgra.tobytes(), self.width * self.height * 4)

        return bool(
            user32.UpdateLayeredWindow(
                self.hwnd,
                self._hdc_screen,
                None,
                ctypes.byref(self._size),
                self._hdc_mem,
                ctypes.byref(self._pt_src),
                0,
                ctypes.byref(self._blend),
                ULW_ALPHA,
            )
        )

    def close(self) -> None:
        if self._hdc_mem:
            gdi32.SelectObject(self._hdc_mem, self._old_bmp)
            gdi32.DeleteObject(self._hbitmap)
            gdi32.DeleteDC(self._hdc_mem)
            user32.ReleaseDC(0, self._hdc_screen)
            self._hdc_mem = None


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = ["segoeuib.ttf" if bold else "segoeui.ttf", "arialbd.ttf" if bold else "arial.ttf"]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


class LanguagePopup:
    def __init__(self, parent: tk.Tk, on_select: Callable[[str], None]) -> None:
        self.parent = parent
        self.on_select = on_select
        self.top = tk.Toplevel(parent)
        self.top.withdraw()
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)

        self.width = 192
        self.height = 118
        self.selected_lang = "auto"
        self.hovered_index = -1
        self.items = [("auto", "Auto Detect"), ("id", "Bahasa Indonesia (ID)"), ("en", "English (EN)")]
        self.font = get_font(11, bold=True)
        self.last_dismiss_time = 0.0

        self.top.update_idletasks()
        hwnd = self.top.winfo_id()
        self._surface = LayeredSurface(hwnd, self.width, self.height)

        self.top.bind("<Motion>", self._on_motion)
        self.top.bind("<Leave>", self._on_leave)
        self.top.bind("<Button-1>", self._on_click)
        self.top.bind("<FocusOut>", lambda _: self.hide())

    def show(self, x: int, y: int, current_lang: str) -> None:
        self.selected_lang = current_lang
        self.hovered_index = -1
        self.top.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.top.deiconify()
        self.top.focus_set()
        self._draw()

    def hide(self) -> None:
        if self.is_visible():
            self.last_dismiss_time = time.monotonic()
        self.top.withdraw()

    def is_visible(self) -> bool:
        return self.top.winfo_viewable() == 1

    def _on_motion(self, event: tk.Event) -> None:
        row_idx = (event.y - 10) // 32
        new_hover = row_idx if 0 <= row_idx < len(self.items) and 8 <= event.x <= self.width - 8 else -1
        if new_hover != self.hovered_index:
            self.hovered_index = new_hover
            self._draw()

    def _on_leave(self, event: tk.Event) -> None:
        if self.hovered_index != -1:
            self.hovered_index = -1
            self._draw()

    def _on_click(self, event: tk.Event) -> None:
        row_idx = (event.y - 10) // 32
        if 0 <= row_idx < len(self.items) and 8 <= event.x <= self.width - 8:
            selected_code = self.items[row_idx][0]
            self.hide()
            self.on_select(selected_code)

    def _draw(self) -> None:
        scale = 3
        w_scaled = self.width * scale
        h_scaled = self.height * scale
        im = Image.new("RGBA", (w_scaled, h_scaled), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)

        pad = 1 * scale
        draw.rounded_rectangle(
            (pad, pad, w_scaled - pad - 1, h_scaled - pad - 1),
            radius=14 * scale,
            fill=(18, 19, 23, 248),
            outline=(48, 52, 62, 220),
            width=scale,
        )

        for i, (code, _) in enumerate(self.items):
            row_y = (10 + i * 32) * scale
            is_hover = (i == self.hovered_index)
            is_selected = (code == self.selected_lang)

            if is_hover:
                draw.rounded_rectangle(
                    (8 * scale, row_y, (self.width - 8) * scale, row_y + 30 * scale),
                    radius=7 * scale,
                    fill=(38, 43, 55, 255),
                )
            elif is_selected:
                draw.rounded_rectangle(
                    (8 * scale, row_y, (self.width - 8) * scale, row_y + 30 * scale),
                    radius=7 * scale,
                    fill=(28, 33, 44, 255),
                )

        resized = im.resize((self.width, self.height), Image.Resampling.LANCZOS)
        text_draw = ImageDraw.Draw(resized)

        for i, (code, label) in enumerate(self.items):
            row_y = 10 + i * 32
            is_hover = (i == self.hovered_index)
            is_selected = (code == self.selected_lang)

            mark = "✓ " if is_selected else "   "
            color = (56, 189, 248, 255) if is_selected else ((255, 255, 255, 255) if is_hover else (148, 163, 184, 255))
            text_draw.text((18, row_y + 15), f"{mark}{label}", fill=color, font=self.font, anchor="lm")

        self._surface.render(resized)

    def close(self) -> None:
        self._surface.close()


class Overlay:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.width = 280
        self.height = 64
        self.target_width = 44.0
        self.target_height = 44.0
        self._draw_width = 44.0
        self._draw_height = 44.0

        self._level = 0.0
        self._phase = 0.0
        self._mode = "ready"
        self._language = "auto"
        self._duration_seconds = 0.0

        self._visible = True
        self._show_floating_icon = True
        self._animating = False
        self._hide_after_id: str | None = None

        self._close_handler: Callable[[], None] | None = None
        self._toggle_handler: Callable[[], None] | None = None
        self._language_handler: Callable[[str], None] | None = None
        self._menu_handler: Callable[[int, int], None] | None = None

        self._timer_font = get_font(11, bold=True)
        self._lang_font = get_font(10, bold=True)
        self._pill_cache: dict[tuple[int, int], Image.Image] = {}

        # Drag state
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._win_start_x = 0
        self._win_start_y = 0
        self._dragged = False
        self.custom_x: int | None = None
        self.custom_y: int | None = None

        mic_raw = Image.open(app_root() / "kaze-icon.png").convert("RGBA")
        self._mic_icon = mic_raw.resize((22, 22), Image.Resampling.LANCZOS)
        self._app_icon = ImageTk.PhotoImage(mic_raw.resize((32, 32), Image.Resampling.LANCZOS))
        self.root.iconphoto(True, self._app_icon)

        self.root.bind("<ButtonPress-1>", self._on_press)
        self.root.bind("<B1-Motion>", self._on_drag)
        self.root.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Button-3>", self._on_right_click)
        self.root.bind("<Motion>", self._on_hover)
        self.root.bind("<Leave>", lambda _: self.root.config(cursor=""))

        self.lang_popup = LanguagePopup(self.root, self._on_select_language)

        self.root.update_idletasks()
        hwnd = self.root.winfo_id()
        self._surface = LayeredSurface(hwnd, self.width, self.height)

        self._position()
        self._draw()

    def set_show_floating_icon(self, enabled: bool) -> None:
        self._show_floating_icon = bool(enabled)
        if not self._show_floating_icon and self._mode == "ready":
            self.hide()
        elif self._show_floating_icon and self._mode == "ready" and not self._visible:
            self.show_idle()

    def show_idle(self) -> None:
        self._mode = "ready"
        if not self._show_floating_icon:
            self.hide()
            return
        self._visible = True
        self.target_width = 44.0
        self.target_height = 44.0
        self.root.deiconify()
        self._wake_animation()

    def show(self, mode: str, hide_after_ms: int | None = None) -> None:
        self._mode = mode
        self._visible = True
        self.target_width = 240.0
        self.target_height = 42.0
        self.root.deiconify()

        if self._hide_after_id:
            try:
                self.root.after_cancel(self._hide_after_id)
            except Exception:
                pass
            self._hide_after_id = None

        if hide_after_ms:
            self._hide_after_id = self.root.after(hide_after_ms, self.show_idle)

        self._wake_animation()

    def hide(self) -> None:
        self._mode = "ready"
        self._visible = False
        self._animating = False
        if self._hide_after_id:
            try:
                self.root.after_cancel(self._hide_after_id)
            except Exception:
                pass
            self._hide_after_id = None
        if hasattr(self, "lang_popup") and self.lang_popup.is_visible():
            self.lang_popup.hide()
        self.root.withdraw()

    def _wake_animation(self) -> None:
        if not self._animating:
            self._animating = True
            self._tick()

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))

    def set_duration(self, seconds: float) -> None:
        self._duration_seconds = max(0.0, seconds)

    def set_language(self, language: str) -> None:
        self._language = language.strip().lower() or "auto"
        self._draw()

    def set_close_handler(self, callback: Callable[[], None]) -> None:
        self._close_handler = callback

    def set_toggle_handler(self, callback: Callable[[], None]) -> None:
        self._toggle_handler = callback

    def set_language_handler(self, callback: Callable[[str], None]) -> None:
        self._language_handler = callback

    def set_menu_handler(self, callback: Callable[[int, int], None]) -> None:
        self._menu_handler = callback

    def dispatch_later(self, callback: Callable[[], None], delay_ms: int = 0) -> None:
        self.root.after(delay_ms, callback)

    def _tick(self) -> None:
        if not self._visible:
            self._animating = False
            return

        self._phase += 0.22 if self._mode == "recording" else 0.12
        animating_size = self._animate_size()
        self._draw()

        if self._mode == "ready" and not animating_size:
            self._animating = False
            return

        self.root.after(16, self._tick)

    def _animate_size(self) -> bool:
        diff_w = abs(self.target_width - self._draw_width)
        diff_h = abs(self.target_height - self._draw_height)
        if diff_w < 0.3 and diff_h < 0.3:
            self._draw_width = self.target_width
            self._draw_height = self.target_height
            return False

        self._draw_width += (self.target_width - self._draw_width) * 0.28
        self._draw_height += (self.target_height - self._draw_height) * 0.28
        return True

    def _draw(self) -> None:
        if not self._visible:
            return

        x1 = (self.width - self._draw_width) / 2
        y1 = (self.height - self._draw_height) / 2
        x2 = x1 + self._draw_width
        y2 = y1 + self._draw_height
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2

        im = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))

        width = max(1, int(round(x2 - x1)))
        height = max(1, int(round(y2 - y1)))
        pill_img = self._get_cached_pill(width, height)
        im.alpha_composite(pill_img, (int(round(x1)), int(round(y1))))

        if self._mode == "ready" and self._draw_width < 70:
            mic_x = int(round(center_x - 11))
            mic_y = int(round(center_y - 11))
            im.alpha_composite(self._mic_icon, (mic_x, mic_y))
            self._surface.render(im)
            return

        if self._draw_width < 140:
            self._surface.render(im)
            return

        draw = ImageDraw.Draw(im)
        self._draw_status_indicator(draw, x1 + 18, center_y)
        self._draw_timer(draw, x1 + 44, center_y)
        self._draw_divider(draw, x1 + 68, center_y)
        self._draw_waveform(draw, x1 + 76, center_y)
        self._draw_divider(draw, x1 + 128, center_y)
        self._draw_language_button(draw, x1 + 168, center_y)
        self._draw_close(draw, x2 - 16, center_y)

        self._surface.render(im)

    def _get_cached_pill(self, width: int, height: int) -> Image.Image:
        cache_key = (width, height)
        if cache_key in self._pill_cache:
            return self._pill_cache[cache_key]

        scale = 3
        w_scaled = width * scale
        h_scaled = height * scale
        image = Image.new("RGBA", (w_scaled, h_scaled), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        radius = min(w_scaled, h_scaled) // 2

        pad = 1 * scale
        draw.rounded_rectangle(
            (pad, pad, w_scaled - pad - 1, h_scaled - pad - 1),
            radius=max(1, radius - pad),
            fill=(38, 41, 46, 255),
            outline=(68, 73, 82, 230),
            width=scale,
        )

        inset = scale
        draw.rounded_rectangle(
            (pad + inset, pad + inset, w_scaled - pad - inset - 1, h_scaled - pad - inset - 1),
            radius=max(1, radius - pad - inset),
            fill=(14, 15, 18, 252),
        )

        resized = image.resize((width, height), Image.Resampling.LANCZOS)
        if len(self._pill_cache) > 40:
            self._pill_cache.clear()
        self._pill_cache[cache_key] = resized
        return resized

    def _draw_status_indicator(self, draw: ImageDraw.ImageDraw, cx: float, cy: float) -> None:
        if self._mode == "recording":
            pulse = (math.sin(self._phase * 1.6) + 1.0) / 2.0
            r = 3.6 + pulse * 1.4
            draw.ellipse(
                (cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2),
                outline=(239, 68, 68, int(80 + pulse * 100)),
                width=1,
            )
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(239, 68, 68, 255))
        elif self._mode == "transcribing":
            start = int((self._phase * 120) % 360)
            draw.arc(
                (cx - 6, cy - 6, cx + 6, cy + 6),
                start=start,
                end=start + 280,
                fill=(56, 189, 248, 255),
                width=2,
            )
        elif self._mode == "done":
            draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=(34, 197, 94, 255))
        else:
            draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=(245, 158, 11, 255))

    def _draw_timer(self, draw: ImageDraw.ImageDraw, cx: float, cy: float) -> None:
        total_sec = int(self._duration_seconds)
        mins = total_sec // 60
        secs = total_sec % 60
        text = f"{mins:02d}:{secs:02d}"
        color = (226, 232, 240, 255) if self._mode != "error" else (245, 158, 11, 255)
        draw.text((cx, cy), text=text, fill=color, font=self._timer_font, anchor="mm")

    def _draw_divider(self, draw: ImageDraw.ImageDraw, x: float, cy: float) -> None:
        draw.line([(x, cy - 8), (x, cy + 8)], fill=(46, 51, 59, 255), width=1)

    def _draw_waveform(self, draw: ImageDraw.ImageDraw, start_x: float, cy: float) -> None:
        bar_count = 10
        spacing = 4.2
        max_height = 18.0

        for i in range(bar_count):
            bar_x = start_x + i * spacing
            if self._mode == "recording":
                wave_factor = (math.sin(self._phase + i * 0.45) + 1.0) / 2.0
                effective_level = max(0.12, self._level)
                h = 3.0 + max_height * effective_level * (0.35 + 0.65 * wave_factor)
                color = (255, 255, 255, 255)
            elif self._mode == "transcribing":
                shimmer = (math.sin(self._phase + i * 0.5) + 1.0) / 2.0
                h = 4.0 + shimmer * 9.0
                shade = int(140 + shimmer * 115)
                color = (shade, shade, shade, 255)
            else:
                h = 3.0
                color = (71, 85, 105, 255)

            draw.line([(bar_x, cy - h / 2), (bar_x, cy + h / 2)], fill=color, width=2)

    def _draw_language_button(self, draw: ImageDraw.ImageDraw, cx: float, cy: float) -> None:
        gx = cx - 18
        gy = cy
        r = 5.5
        color = (148, 163, 184, 255)
        draw.ellipse((gx - r, gy - r, gx + r, gy + r), outline=color, width=1)
        draw.line([(gx - r, gy), (gx + r, gy)], fill=color, width=1)
        draw.ellipse((gx - 2.5, gy - r, gx + 2.5, gy + r), outline=color, width=1)

        badge = (self._language.upper() if self._language != "auto" else "AUTO") + " ▾"
        draw.text((cx + 4, cy), text=badge, fill=color, font=self._lang_font, anchor="lm")

    def _draw_close(self, draw: ImageDraw.ImageDraw, cx: float, cy: float) -> None:
        size = 4
        color = (100, 116, 139, 255)
        draw.line([(cx - size, cy - size), (cx + size, cy + size)], fill=color, width=2)
        draw.line([(cx + size, cy - size), (cx - size, cy + size)], fill=color, width=2)

    def _on_press(self, event: tk.Event) -> None:
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._win_start_x = self.root.winfo_x()
        self._win_start_y = self.root.winfo_y()
        self._dragged = False

    def _on_drag(self, event: tk.Event) -> None:
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        if abs(dx) > 3 or abs(dy) > 3:
            self._dragged = True
            new_x = self._win_start_x + dx
            new_y = self._win_start_y + dy
            self.custom_x = new_x
            self.custom_y = new_y
            self.root.geometry(f"{self.width}x{self.height}+{new_x}+{new_y}")

    def _on_release(self, event: tk.Event) -> None:
        if self._dragged:
            return

        x1 = (self.width - self._draw_width) / 2
        y1 = (self.height - self._draw_height) / 2
        x2 = x1 + self._draw_width
        y2 = y1 + self._draw_height

        if self._mode == "ready":
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if self._toggle_handler:
                    self._toggle_handler()
            return

        if x2 - 28 <= event.x <= x2 - 4 and y1 <= event.y <= y2:
            if self._close_handler:
                self._close_handler()
            return

        if x1 + 130 <= event.x <= x2 - 30 and y1 <= event.y <= y2:
            if self.lang_popup.is_visible() or (time.monotonic() - self.lang_popup.last_dismiss_time < 0.25):
                self.lang_popup.hide()
            else:
                popup_x = self.root.winfo_x() + int(x2) - self.lang_popup.width
                screen_w = self.root.winfo_screenwidth()
                popup_x = max(10, min(screen_w - self.lang_popup.width - 10, popup_x))
                popup_y = (
                    self.root.winfo_y() - self.lang_popup.height - 8
                    if self.root.winfo_y() > 140
                    else self.root.winfo_y() + self.height + 8
                )
                self.lang_popup.show(popup_x, popup_y, self._language)
            return

        if x1 <= event.x <= x2 and y1 <= event.y <= y2 and self._mode == "recording":
            if self._toggle_handler:
                self._toggle_handler()

    def _on_hover(self, event: tk.Event) -> None:
        x1 = (self.width - self._draw_width) / 2
        y1 = (self.height - self._draw_height) / 2
        x2 = x1 + self._draw_width
        y2 = y1 + self._draw_height

        if x1 <= event.x <= x2 and y1 <= event.y <= y2:
            self.root.config(cursor="hand2")
        else:
            self.root.config(cursor="")

    def _on_right_click(self, event: tk.Event) -> None:
        if self._menu_handler:
            self._menu_handler(event.x_root, event.y_root)

    def _on_select_language(self, lang: str) -> None:
        self._language = lang.lower()
        self._draw()
        if self._language_handler:
            self._language_handler(self._language)

    def _position(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = self.custom_x if self.custom_x is not None else int((screen_w - self.width) / 2)
        y = self.custom_y if self.custom_y is not None else max(20, screen_h - self.height - 72)
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def close(self) -> None:
        self._surface.close()
        self.lang_popup.close()
        self.root.destroy()
