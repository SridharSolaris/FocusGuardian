#!/usr/bin/env python3
"""
FocusGuardian — A Focus Distraction Preventor  (v1.0.0 — Enterprise Dark Theme)
==============================================================================

v3.0 changelog:
  Bug fixes:
    • Fixed 30 NameError crashes: bare 'root' → 'self.root' in all class method
      dialog calls (dark_showinfo, dark_showwarning, dark_showerror, dark_askyesno)
    • Fixed AttributeError: self.app_blocking_active not initialized in __init__
    • Fixed Win11Button visual corruption: _on_enter/_on_press now clear canvas
      before redrawing (was drawing on top of old shapes)
    • Removed dead code: unused text_h, self._padx, self._label variables
    • Removed dead imports: math, messagebox
  v2.9 features:
    • DWM rounded window corners (DWMWA_WINDOW_CORNER_PREFERENCE)
    • Win11Button: Canvas-based rounded button with hover/press states
    • Win11Toggle: Canvas-based toggle switch replacing all checkboxes
    • Win11 underline-style notebook tabs

Author: FocusGuardian
License: MIT
"""

import copy
import ctypes
import json
import logging
import os
import platform
import random
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, date, timedelta, time as dtime
from http.server import HTTPServer, BaseHTTPRequestHandler
from tkinter import ttk

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ---------------------------------------------------------------------------
# Configuration & paths
# ---------------------------------------------------------------------------

APP_NAME = "FocusGuardian"
APP_VERSION = "1.0.0"

if platform.system() == "Windows":
    CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
    HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
else:
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", APP_NAME)
    HOSTS_PATH = "/etc/hosts"

CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DB_FILE = os.path.join(CONFIG_DIR, "sessions.db")
HTML_FILE = os.path.join(CONFIG_DIR, "stay_focused.html")
LOG_FILE = os.path.join(CONFIG_DIR, "focus_guardian.log")

BEGIN_MARKER = "# >>> BEGIN FOCUS GUARDIAN BLOCKS >>>"
END_MARKER = "# <<< END FOCUS GUARDIAN BLOCKS <<<"

DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ═══════════════════════════════════════════════════════════════════════════
# Windows 11 Dark Theme — Color Palette (v3.0 — Settings App Style)
# Sourced from the Windows 11 Design System dark mode specifications.
# Tuned to match the Windows 11 Settings app dark theme exactly.
# ═══════════════════════════════════════════════════════════════════════════

C_BG         = "#1F1F1F"   # App background (Mica base — matches Settings)
C_BG_ALT     = "#1A1A1A"   # Slightly darker variant for nav pane
C_SURFACE    = "#2B2B2B"   # Card / elevated surface (Settings card bg)
C_SURFACE2   = "#323232"   # Hover / pressed surface
C_SURFACE3   = "#383838"   # Active nav item bg
C_CONTROL    = "#2D2D2D"   # Control fill (buttons, entries)
C_CONTROL_HV = "#383838"   # Control hover
C_PRIMARY    = "#4CC2FF"   # Accent (Win11 light blue)
C_ACCENT     = "#60CDFF"   # Accent hover
C_ACCENT_DK  = "#36C5F0"   # Accent pressed
C_ACCENT_BG  = "#083B5C"   # Accent subtle bg (selection highlight in nav)
C_SUCCESS    = "#6DCB6D"   # Green
C_WARNING    = "#FFA940"   # Orange
C_DANGER     = "#FF6B6B"   # Red
C_TEXT       = "#FFFFFF"   # Primary text
C_TEXT_DIM   = "#C5C5C5"   # Secondary text (Win11 uses lighter dim)
C_TEXT_DIM2  = "#8B8B8B"   # Tertiary text
C_BORDER     = "#404040"   # Control stroke / divider
C_BORDER_LT  = "#2A2A2A"   # Subtle divider (between nav and content)
C_LISTBG     = "#1C1C1C"   # Listbox / text area bg (darker than card)
C_SELECT     = "#083B5C"   # Selection bg (Win11 accent-tinted)
C_SELECT_FG  = "#FFFFFF"   # Selection text
C_ENTRY_BG   = "#1C1C1C"   # Entry field bg
C_SCROLLBAR  = "#3A3A3A"   # Scrollbar bg
C_NAV_BG     = "#1A1A1A"   # Navigation pane bg (darker than content)
C_NAV_HOVER  = "#2C2C2C"   # Nav item hover
C_NAV_ACTIVE = "#333333"   # Nav item active (selected)
C_CARD_BDR   = "#2D2D2D"   # Card border (very subtle)


# ═══════════════════════════════════════════════════════════════════════════
# DWM Dark Title Bar — Native Win11 dark title bar via DWM API
# ═══════════════════════════════════════════════════════════════════════════

DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Windows 10 2004+, Windows 11


def _apply_dwm_dark(hwnd):
    """Apply all DWM dark-mode attributes to a given HWND. Returns True on success."""
    try:
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value)
        )
        DWMWA_CAPTION_COLOR = 35
        caption_color = ctypes.c_uint32(0x001F1F1F)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR,
            ctypes.byref(caption_color), ctypes.sizeof(caption_color)
        )
        DWMWA_TEXT_COLOR = 36
        text_color = ctypes.c_uint32(0x00FFFFFF)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_TEXT_COLOR,
            ctypes.byref(text_color), ctypes.sizeof(text_color)
        )
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        corner_pref = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner_pref), ctypes.sizeof(corner_pref)
        )
        DWMWA_BORDER_COLOR = 34
        border_color = ctypes.c_uint32(0x002D2D2D)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR,
            ctypes.byref(border_color), ctypes.sizeof(border_color)
        )
        return True
    except Exception as e:
        logger.debug(f"DWM dark apply failed: {e}")
        return False


def enable_dark_titlebar(window, _retries=0):
    """Make the native window title bar dark using the DWM API.
    Waits for window visibility before applying, with retry logic."""
    if platform.system() != "Windows":
        return

    def _do_apply():
        try:
            window.update_idletasks()
            hwnd = window.winfo_id()
            if not hwnd:
                if _retries < 5:
                    window.after(100, lambda: enable_dark_titlebar(window, _retries + 1))
                return
            for _ in range(5):
                parent = ctypes.windll.user32.GetParent(hwnd)
                if not parent:
                    break
                hwnd = parent
            ok = _apply_dwm_dark(hwnd)
            if not ok and _retries < 5:
                window.after(100, lambda: enable_dark_titlebar(window, _retries + 1))
        except Exception as e:
            logger.debug(f"Dark titlebar failed (non-critical): {e}")
            if _retries < 5:
                window.after(100, lambda: enable_dark_titlebar(window, _retries + 1))

    try:
        window.wait_visibility()
    except Exception:
        pass
    _do_apply()


def enable_mica_backdrop(window):
    """Enable Mica backdrop on Windows 11 (build 22000+).
    This makes the window background semi-transparent with the system accent.
    Falls back gracefully on older Windows."""
    if platform.system() != "Windows":
        return
    try:
        hwnd = window.winfo_id()
        for _ in range(5):
            parent = ctypes.windll.user32.GetParent(hwnd)
            if not parent:
                break
            hwnd = parent
        # DWMWA_SYSTEMBACKDROP_TYPE = 38 (Windows 11 22H2+)
        # DWMSBT_MAINWINDOW = 2 (Mica)
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        backdrop = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(backdrop), ctypes.sizeof(backdrop)
        )
    except Exception as e:
        logger.debug(f"Mica backdrop failed (non-critical): {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Theme application — configure every ttk style for Win11 Settings dark mode
# ═══════════════════════════════════════════════════════════════════════════

def apply_win11_dark_theme(style):
    """Configure every ttk style for Windows 11 Settings-app dark appearance.
    Uses 'clam' as base since 'vista'/'xpnative' ignore dark colors."""

    style.theme_use("clam")

    # Root — everything inherits from here
    style.configure(".", background=C_BG, foreground=C_TEXT,
                    font=("Segoe UI Variable", 10), borderwidth=0)
    style.configure("TFrame", background=C_BG)
    style.configure("Card.TFrame", background=C_SURFACE, relief="solid",
                    borderwidth=1, bordercolor=C_CARD_BDR)
    style.configure("Nav.TFrame", background=C_NAV_BG)
    style.configure("Content.TFrame", background=C_BG)
    style.configure("TNotebook", background=C_BG, borderwidth=0, tabmargins=(0, 0, 0, 0))

    # Notebook tabs — kept for potential fallback, but main UI uses nav pane
    style.configure("TNotebook.Tab",
                    background=C_BG, foreground=C_TEXT_DIM,
                    padding=(20, 10), borderwidth=0,
                    font=("Segoe UI Variable", 10))
    style.map("TNotebook.Tab",
              background=[("selected", C_BG), ("active", C_SURFACE2)],
              foreground=[("selected", C_PRIMARY), ("active", C_TEXT)])

    # Labels
    style.configure("TLabel", background=C_BG, foreground=C_TEXT)
    style.configure("Header.TLabel",
                    font=("Segoe UI Variable", 22, "bold"),
                    foreground=C_TEXT, background=C_BG)
    style.configure("SubHeader.TLabel",
                    font=("Segoe UI Variable", 14, "bold"),
                    foreground=C_TEXT, background=C_BG)
    style.configure("Big.TLabel",
                    font=("Segoe UI Variable", 48, "bold"), background=C_BG)
    style.configure("Mode.TLabel",
                    font=("Segoe UI Variable", 12), background=C_BG, foreground=C_TEXT)
    style.configure("Small.TLabel",
                    font=("Segoe UI Variable", 9), background=C_BG, foreground=C_TEXT_DIM)
    style.configure("Hint.TLabel",
                    font=("Segoe UI Variable", 10, "italic"), background=C_BG, foreground=C_TEXT_DIM)
    style.configure("AdminOK.TLabel",
                    font=("Segoe UI Variable", 9), foreground=C_SUCCESS, background=C_BG)
    style.configure("AdminWarn.TLabel",
                    font=("Segoe UI Variable", 9), foreground=C_DANGER, background=C_BG)
    style.configure("SchedActive.TLabel",
                    font=("Segoe UI Variable", 9, "bold"), foreground=C_PRIMARY, background=C_BG)
    style.configure("StatHdr.TLabel",
                    font=("Segoe UI Variable", 12, "bold"), foreground=C_PRIMARY, background=C_LISTBG)
    style.configure("Dim.TLabel", foreground=C_TEXT_DIM, background=C_BG)
    style.configure("Card.TLabel", background=C_SURFACE, foreground=C_TEXT)
    style.configure("CardDim.TLabel", background=C_SURFACE, foreground=C_TEXT_DIM)
    style.configure("Nav.TLabel", background=C_NAV_BG, foreground=C_TEXT)
    style.configure("NavActive.TLabel", background=C_NAV_BG, foreground=C_PRIMARY,
                    font=("Segoe UI Variable", 10, "bold"))
    style.configure("CardTitle.TLabel",
                    font=("Segoe UI Variable", 12, "bold"), background=C_SURFACE, foreground=C_TEXT)

    # Buttons — Win11 style: subtle fill, no heavy border, hover lightens
    style.configure("TButton",
                    background=C_CONTROL, foreground=C_TEXT,
                    borderwidth=1, relief="solid",
                    bordercolor=C_BORDER,
                    padding=(16, 9), font=("Segoe UI Variable", 10))
    style.map("TButton",
              background=[("active", C_CONTROL_HV), ("pressed", C_SURFACE2),
                          ("disabled", C_SURFACE)],
              foreground=[("disabled", C_TEXT_DIM2)],
              bordercolor=[("focus", C_PRIMARY), ("active", C_BORDER)])

    # Accent button (primary action)
    style.configure("Accent.TButton",
                    background=C_PRIMARY, foreground="#000000",
                    borderwidth=0, padding=(18, 9),
                    font=("Segoe UI Variable", 10, "bold"))
    style.map("Accent.TButton",
              background=[("active", C_ACCENT), ("pressed", C_ACCENT_DK),
                          ("disabled", C_SURFACE)],
              foreground=[("disabled", C_TEXT_DIM2)])

    # Danger button
    style.configure("Danger.TButton",
                    background=C_DANGER, foreground="#FFFFFF",
                    borderwidth=0, padding=(16, 9),
                    font=("Segoe UI Variable", 10))
    style.map("Danger.TButton",
              background=[("active", "#E55555"), ("pressed", "#CC4444"),
                          ("disabled", C_SURFACE)],
              foreground=[("disabled", C_TEXT_DIM2)])

    # Entries — dark field, subtle border, accent on focus
    style.configure("TEntry",
                    fieldbackground=C_ENTRY_BG, foreground=C_TEXT,
                    borderwidth=1, relief="solid",
                    bordercolor=C_BORDER,
                    insertcolor=C_TEXT, padding=(8, 7))
    style.map("TEntry",
              bordercolor=[("focus", C_PRIMARY)],
              fieldbackground=[("readonly", C_ENTRY_BG)])

    # Combobox
    style.configure("TCombobox",
                    fieldbackground=C_ENTRY_BG, foreground=C_TEXT,
                    background=C_CONTROL, arrowcolor=C_TEXT,
                    borderwidth=1, relief="solid",
                    bordercolor=C_BORDER, padding=(8, 6))
    style.map("TCombobox",
              fieldbackground=[("readonly", C_ENTRY_BG)],
              bordercolor=[("focus", C_PRIMARY)],
              foreground=[("readonly", C_TEXT)],
              selectbackground=[("readonly", C_SELECT)],
              selectforeground=[("readonly", C_SELECT_FG)])

    # Checkbutton
    style.configure("TCheckbutton",
                    background=C_BG, foreground=C_TEXT,
                    indicatorbackground=C_ENTRY_BG,
                    indicatorforeground=C_PRIMARY,
                    bordercolor=C_BORDER, focuscolor=C_BG, padding=(4, 4))
    style.map("TCheckbutton",
              background=[("active", C_BG)],
              indicatorbackground=[("selected", C_PRIMARY)],
              indicatorforeground=[("selected", "#000000")])

    # Progressbar
    style.configure("TProgressbar",
                    background=C_PRIMARY, troughcolor=C_SURFACE,
                    borderwidth=0, thickness=6)

    # Scrollbar — Win11 style: subtle, appears on hover
    style.configure("TScrollbar",
                    background=C_SCROLLBAR, troughcolor=C_BG,
                    arrowcolor=C_TEXT_DIM, borderwidth=0,
                    gripcount=0, arrowsize=15)
    style.map("TScrollbar",
              background=[("active", C_BORDER)])

    # Treeview
    style.configure("Treeview",
                    background=C_LISTBG, foreground=C_TEXT,
                    fieldbackground=C_LISTBG, borderwidth=0,
                    font=("Segoe UI Variable", 10), rowheight=34)
    style.configure("Treeview.Heading",
                    background=C_SURFACE, foreground=C_TEXT,
                    font=("Segoe UI Variable", 10, "bold"),
                    borderwidth=0, relief="flat", padding=(10, 10))
    style.map("Treeview",
              background=[("selected", C_SELECT)],
              foreground=[("selected", C_SELECT_FG)])
    style.map("Treeview.Heading",
              background=[("active", C_SURFACE2)])

    # Separator
    style.configure("TSeparator", background=C_BORDER)

    # Spinbox
    style.configure("TSpinbox",
                    fieldbackground=C_ENTRY_BG, foreground=C_TEXT,
                    borderwidth=1, relief="solid",
                    bordercolor=C_BORDER, arrowcolor=C_TEXT)

    # Sizegrip
    style.configure("TSizegrip", background=C_BG)


def configure_dark_tk_widgets(root):
    """Set default colors for raw tk widgets (Listbox, Text, Menu, Canvas).
    ttk styles don't cover these — they need explicit configuration."""

    root.option_add("*Background", C_BG)
    root.option_add("*Foreground", C_TEXT)
    root.option_add("*selectBackground", C_SELECT)
    root.option_add("*selectForeground", C_SELECT_FG)
    root.option_add("*Entry.background", C_ENTRY_BG)
    root.option_add("*Entry.foreground", C_TEXT)
    root.option_add("*Entry.insertBackground", C_TEXT)
    root.option_add("*Listbox.background", C_LISTBG)
    root.option_add("*Listbox.foreground", C_TEXT)
    root.option_add("*Listbox.selectBackground", C_SELECT)
    root.option_add("*Listbox.selectForeground", C_SELECT_FG)
    root.option_add("*Text.background", C_LISTBG)
    root.option_add("*Text.foreground", C_TEXT)
    root.option_add("*Text.insertBackground", C_TEXT)
    root.option_add("*Text.selectBackground", C_SELECT)
    root.option_add("*Text.selectForeground", C_SELECT_FG)
    root.option_add("*Menu.background", C_SURFACE)
    root.option_add("*Menu.foreground", C_TEXT)
    root.option_add("*Menu.activeBackground", C_SURFACE2)
    root.option_add("*Menu.activeForeground", C_PRIMARY)
    root.option_add("*Menu.activeBorderWidth", 0)
    root.option_add("*Menu.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.background", C_LISTBG)
    root.option_add("*TCombobox*Listbox.foreground", C_TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", C_SELECT)
    root.option_add("*TCombobox*Listbox.selectForeground", C_SELECT_FG)


# ═══════════════════════════════════════════════════════════════════════════
# Win11 custom widgets — Canvas-based rounded button & toggle switch
# ═══════════════════════════════════════════════════════════════════════════

class Win11Button(tk.Canvas):
    """Canvas-based button with rounded corners, hover and press states.
    Mimics the Windows 11 Fluent Design button look.

    Styles: 'default', 'accent', 'danger'
    """

    _STYLE_COLORS = {
        "default": {
            "bg": C_CONTROL, "hover": C_CONTROL_HV, "press": C_SURFACE2,
            "fg": C_TEXT, "border": C_BORDER, "disabled_bg": C_SURFACE, "disabled_fg": C_TEXT_DIM2,
        },
        "accent": {
            "bg": C_PRIMARY, "hover": C_ACCENT, "press": C_ACCENT_DK,
            "fg": "#000000", "border": C_PRIMARY, "disabled_bg": C_SURFACE, "disabled_fg": C_TEXT_DIM2,
        },
        "danger": {
            "bg": C_DANGER, "hover": "#E55555", "press": "#CC4444",
            "fg": "#FFFFFF", "border": C_DANGER, "disabled_bg": C_SURFACE, "disabled_fg": C_TEXT_DIM2,
        },
    }

    def __init__(self, parent, text="", command=None, style="default",
                 width=None, height=34, padx=18, font=None, **kwargs):
        tmp_font = font or ("Segoe UI Variable", 10)
        try:
            from tkinter import font as tkfont
            f = tkfont.Font(font=tmp_font)
            text_w = f.measure(text)
        except Exception:
            text_w = len(text) * 7

        btn_w = width or (text_w + padx * 2)
        btn_h = height

        bg = kwargs.pop("background", C_BG)
        super().__init__(parent, width=btn_w, height=btn_h, bg=bg,
                        highlightthickness=0, borderwidth=0)

        self._text = text
        self._command = command
        self._style_name = style
        self._font = font or ("Segoe UI Variable", 10)
        self._enabled = True
        self._radius = 6
        self._btn_w = btn_w
        self._btn_h = btn_h
        self._colors = self._STYLE_COLORS.get(style, self._STYLE_COLORS["default"])

        self._draw()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _draw(self):
        self.delete("all")
        c = self._colors
        bg = c["bg"] if self._enabled else c["disabled_bg"]
        fg = c["fg"] if self._enabled else c["disabled_fg"]
        border = c["border"] if self._enabled else C_BORDER

        self._rounded_rect(1, 1, self._btn_w - 1, self._btn_h - 1,
                           self._radius, fill=bg, outline=border, width=1)
        self.create_text(self._btn_w // 2, self._btn_h // 2,
                         text=self._text, fill=fg, font=self._font)

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        max_r = min((x2 - x1) // 2, (y2 - y1) // 2)
        r = max(0, min(r, max_r))
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_enter(self, event):
        if self._enabled:
            self.delete("all")
            c = self._colors
            self._rounded_rect(1, 1, self._btn_w - 1, self._btn_h - 1,
                               self._radius, fill=c["hover"], outline=c["border"], width=1)
            self.create_text(self._btn_w // 2, self._btn_h // 2,
                             text=self._text, fill=c["fg"], font=self._font)

    def _on_leave(self, event):
        self._draw()

    def _on_press(self, event):
        if self._enabled:
            self.delete("all")
            c = self._colors
            self._rounded_rect(1, 1, self._btn_w - 1, self._btn_h - 1,
                               self._radius, fill=c["press"], outline=c["border"], width=1)
            self.create_text(self._btn_w // 2, self._btn_h // 2,
                             text=self._text, fill=c["fg"], font=self._font)

    def _on_release(self, event):
        self._draw()
        if self._enabled and self._command:
            self._command()

    def configure(self, **kwargs):
        if "text" in kwargs:
            self._text = kwargs.pop("text")
        if "state" in kwargs:
            s = kwargs.pop("state")
            self._enabled = (s != "disabled")
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "style" in kwargs:
            self._style_name = kwargs.pop("style")
            self._colors = self._STYLE_COLORS.get(self._style_name, self._STYLE_COLORS["default"])
        super().configure(**kwargs)
        self._draw()

    config = configure


class Win11Toggle(tk.Canvas):
    """Canvas-based toggle switch mimicking the Windows 11 Fluent toggle.
    Works like a Checkbutton — has a BooleanVar, calls command on change.
    """

    def __init__(self, parent, variable=None, command=None, width=44, height=22,
                 label=None, **kwargs):
        bg = kwargs.pop("background", C_BG)
        super().__init__(parent, width=width, height=height, bg=bg,
                        highlightthickness=0, borderwidth=0)

        self._var = variable or tk.BooleanVar()
        self._command = command
        self._tw = width
        self._th = height
        self._track_off = C_SURFACE2
        self._track_on = C_PRIMARY
        self._thumb = "#FFFFFF"

        self._draw()

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        if variable:
            self._var.trace_add("write", lambda *_: self._draw())

    def _draw(self, hover=False):
        self.delete("all")
        on = self._var.get()
        track_color = self._track_on if on else self._track_off
        if hover:
            track_color = C_ACCENT if on else C_BORDER

        avail_h = self._th - 2
        r = min(self._th // 2, avail_h // 2)
        self._rounded_rect(1, 1, self._tw - 1, self._th - 1, r,
                          fill=track_color, outline="", width=0)

        thumb_r = max(2, r - 3)
        if on:
            cx = self._tw - thumb_r - 3
        else:
            cx = thumb_r + 3
        cy = self._th // 2
        self.create_oval(cx - thumb_r, cy - thumb_r, cx + thumb_r, cy + thumb_r,
                        fill=self._thumb, outline="")

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        max_r = min((x2 - x1) // 2, (y2 - y1) // 2)
        r = max(0, min(r, max_r))
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_click(self, event):
        self._var.set(not self._var.get())
        self._draw()
        if self._command:
            self._command()

    def _on_enter(self, event):
        self._draw(hover=True)

    def _on_leave(self, event):
        self._draw()


# ═══════════════════════════════════════════════════════════════════════════
# Win11 Navigation Pane — Settings-style left sidebar
# ═══════════════════════════════════════════════════════════════════════════

class NavItem(tk.Frame):
    """A single navigation item in the left pane — like Win11 Settings nav items."""

    def __init__(self, parent, icon, text, page_index, callback, **kwargs):
        bg = kwargs.pop("background", C_NAV_BG)
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)

        self._page_index = page_index
        self._callback = callback
        self._icon = icon
        self._text = text
        self._selected = False
        self._bg_normal = C_NAV_BG
        self._bg_hover = C_NAV_HOVER
        self._bg_selected = C_NAV_ACTIVE

        self._icon_label = tk.Label(self, text=icon, font=("Segoe UI Variable", 14),
                                    bg=bg, fg=C_TEXT_DIM)
        self._icon_label.pack(side="left", padx=(14, 10), pady=10)

        self._text_label = tk.Label(self, text=text, font=("Segoe UI Variable", 10),
                                    bg=bg, fg=C_TEXT_DIM)
        self._text_label.pack(side="left", pady=10)

        # Make the whole frame clickable
        for widget in [self, self._icon_label, self._text_label]:
            widget.bind("<Button-1>", self._on_click)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_click(self, event=None):
        if self._callback:
            self._callback(self._page_index)

    def _on_enter(self, event=None):
        if not self._selected:
            self._set_bg(self._bg_hover)

    def _on_leave(self, event=None):
        if not self._selected:
            self._set_bg(self._bg_normal)

    def _set_bg(self, color):
        self.configure(bg=color)
        self._icon_label.configure(bg=color)
        self._text_label.configure(bg=color)

    def set_selected(self, selected):
        self._selected = selected
        if selected:
            self._set_bg(self._bg_selected)
            self._icon_label.configure(fg=C_PRIMARY)
            self._text_label.configure(fg=C_TEXT, font=("Segoe UI Variable", 10, "bold"))
            if not hasattr(self, '_indicator'):
                self._indicator = tk.Frame(self, width=3, bg=C_PRIMARY)
                self._indicator.place(x=0, y=8, relheight=1.0, height=-16)
            else:
                self._indicator.configure(bg=C_PRIMARY)
        else:
            self._set_bg(self._bg_normal)
            self._icon_label.configure(fg=C_TEXT_DIM)
            self._text_label.configure(fg=C_TEXT_DIM, font=("Segoe UI Variable", 10))
            if hasattr(self, '_indicator'):
                self._indicator.configure(bg=C_NAV_BG)


class NavPane(tk.Frame):
    """Left navigation pane — Win11 Settings app style."""

    def __init__(self, parent, items, on_select, **kwargs):
        bg = kwargs.pop("background", C_NAV_BG)
        super().__init__(parent, bg=bg, width=220, highlightthickness=0, bd=0)
        self.pack_propagate(False)
        self._on_select = on_select
        self._items = []

        # App title at top
        title_frame = tk.Frame(self, bg=bg)
        title_frame.pack(fill="x", pady=(16, 12), padx=16)
        tk.Label(title_frame, text="FocusGuardian",
                 font=("Segoe UI Variable", 14, "bold"),
                 bg=bg, fg=C_TEXT).pack(side="left")
        tk.Label(title_frame, text=f"  v{APP_VERSION}",
                 font=("Segoe UI Variable", 9),
                 bg=bg, fg=C_TEXT_DIM2).pack(side="left", pady=(2, 0))

        # Separator
        tk.Frame(self, height=1, bg=C_BORDER_LT).pack(fill="x", padx=0)

        # Scrollable nav items container
        nav_container = tk.Frame(self, bg=bg)
        nav_container.pack(fill="both", expand=True, padx=0, pady=(4, 0))

        for i, (icon, text) in enumerate(items):
            item = NavItem(nav_container, icon, text, i, self._handle_select, background=bg)
            item.pack(fill="x")
            self._items.append(item)

        # Separator before admin status at bottom
        tk.Frame(self, height=1, bg=C_BORDER_LT).pack(fill="x")

        # Bottom admin indicator placeholder
        self._bottom_frame = tk.Frame(self, bg=bg)
        self._bottom_frame.pack(fill="x", padx=12, pady=8)
        self._admin_nav_label = tk.Label(self._bottom_frame, text="",
                                         font=("Segoe UI Variable", 9),
                                         bg=bg, fg=C_TEXT_DIM2)
        self._admin_nav_label.pack(side="left")

    def _handle_select(self, page_index):
        for i, item in enumerate(self._items):
            item.set_selected(i == page_index)
        if self._on_select:
            self._on_select(page_index)

    def select(self, page_index):
        self._handle_select(page_index)

    def set_admin_status(self, text, is_admin):
        self._admin_nav_label.config(text=text,
                                     fg=C_SUCCESS if is_admin else C_WARNING)


# ---------------------------------------------------------------------------
# Default profiles & config
# ---------------------------------------------------------------------------

DEFAULT_PROFILES = [
    {
        "name": "Social Media",
        "blocklist": [
            "youtube.com", "www.youtube.com",
            "facebook.com", "www.facebook.com",
            "twitter.com", "www.twitter.com",
            "x.com", "www.x.com",
            "instagram.com", "www.instagram.com",
            "reddit.com", "www.reddit.com",
            "tiktok.com", "www.tiktok.com",
        ],
        "app_blocklist": ["discord.exe", "whatsapp.exe", "telegram.exe"],
    },
    {
        "name": "Deep Work",
        "blocklist": [
            "youtube.com", "www.youtube.com",
            "facebook.com", "www.facebook.com",
            "twitter.com", "www.twitter.com",
            "x.com", "www.x.com",
            "instagram.com", "www.instagram.com",
            "reddit.com", "www.reddit.com",
            "tiktok.com", "www.tiktok.com",
            "netflix.com", "www.netflix.com",
            "amazon.com", "www.amazon.com",
        ],
        "app_blocklist": [
            "steam.exe", "discord.exe", "epicgameslauncher.exe",
            "battle.net.exe", "spotify.exe", "whatsapp.exe",
            "telegram.exe", "robloxplayerbeta.exe",
        ],
    },
    {
        "name": "Games Only",
        "blocklist": [],
        "app_blocklist": [
            "steam.exe", "epicgameslauncher.exe",
            "battle.net.exe", "robloxplayerbeta.exe",
        ],
    },
]

DEFAULT_CONFIG = {
    "work_duration_min": 25,
    "short_break_min": 5,
    "long_break_min": 15,
    "sessions_before_long_break": 4,
    "eye_rest_interval_min": 20,
    "profiles": copy.deepcopy(DEFAULT_PROFILES),
    "active_profile": 0,
    "schedules": [],
    "strict_mode": False,
    "server_port": 80,
    "app_check_interval_sec": 3,
    "sound_enabled": True,
}


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(APP_NAME)


def setup_logging():
    ensure_config_dir()
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info(f"=== {APP_NAME} v{APP_VERSION} started ===")


# ---------------------------------------------------------------------------
# Config load / save
# ---------------------------------------------------------------------------

def load_config():
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not cfg.get("profiles") and (cfg.get("blocklist") or cfg.get("app_blocklist")):
                merged = copy.deepcopy(DEFAULT_CONFIG)
                merged.update(cfg)
                # Use the 3 new default profiles (they contain the same sites)
                merged["profiles"] = copy.deepcopy(DEFAULT_PROFILES)
                merged["active_profile"] = 0
                merged.pop("blocklist", None)
                merged.pop("app_blocklist", None)
                logger.info("Migrated flat blocklists to profile model")
            else:
                merged = copy.deepcopy(DEFAULT_CONFIG)
                merged.update(cfg)
            if not merged.get("profiles"):
                merged["profiles"] = copy.deepcopy(DEFAULT_PROFILES)
                merged["active_profile"] = 0
            if merged["active_profile"] >= len(merged["profiles"]):
                merged["active_profile"] = 0
            if "schedules" not in merged:
                merged["schedules"] = []
            return merged
        except Exception as e:
            logger.error(f"Config load error: {e}")
            return copy.deepcopy(DEFAULT_CONFIG)
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(cfg):
    ensure_config_dir()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        logger.error(f"Config save error: {e}")


# ---------------------------------------------------------------------------
# Motivational HTML page
# ---------------------------------------------------------------------------

MOTIVATIONAL_QUOTES = [
    '"The successful warrior is the average man, with laser-like focus." — Bruce Lee',
    '"Concentrate all your thoughts upon the work at hand. The sun\'s rays do not burn until brought to a focus." — Alexander Graham Bell',
    '"Where focus goes, energy flows." — Tony Robbins',
    '"Don\'t watch the clock; do what it does. Keep going." — Sam Levenson',
    '"It is during our darkest moments that we must focus to see the light." — Aristotle',
    '"The mind is everything. What you think you become." — Buddha',
    '"Success is not final, failure is not fatal: it is the courage to continue that counts." — Winston Churchill',
    '"Quality is not an act, it is a habit." — Aristotle',
]

MOTIVATIONAL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stay Focused — FocusGuardian</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    background: #202020;
    color: #FFFFFF;
  }
  .card {
    text-align: center; padding: 3rem 2.5rem; max-width: 560px;
    background: #2B2B2B;
    border-radius: 12px;
    border: 1px solid #404040;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }
  .emoji { font-size: 4.5rem; margin-bottom: 1rem; }
  h1 { font-size: 2.2rem; margin-bottom: 0.8rem; font-weight: 600; color: #4CC2FF; }
  .subtitle { font-size: 1.1rem; opacity: 0.8; margin-bottom: 1.5rem; line-height: 1.6; }
  .quote {
    font-style: italic; font-size: 1.02rem; opacity: 0.6;
    border-left: 3px solid #4CC2FF;
    padding-left: 1rem; text-align: left; margin: 1.2rem auto; max-width: 420px;
  }
  .blocked-site { font-size: 0.82rem; opacity: 0.35; margin-top: 1.5rem; }
  .pulse { animation: pulse 2s ease-in-out infinite; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
</style>
</head>
<body>
  <div class="card">
    <div class="emoji pulse">🎯</div>
    <h1>Stay Focused</h1>
    <p class="subtitle">This site is blocked during your focus session.<br>
       You're doing great — keep going!</p>
    <div class="quote">__QUOTE__</div>
    <p class="blocked-site">Blocked by FocusGuardian • __SITE__</p>
  </div>
</body>
</html>
"""


def get_motivational_html(blocked_site=""):
    quote = random.choice(MOTIVATIONAL_QUOTES)
    html = (MOTIVATIONAL_HTML_TEMPLATE
            .replace("__QUOTE__", quote)
            .replace("__SITE__", blocked_site or "this site"))
    try:
        ensure_config_dir()
        if not os.path.exists(HTML_FILE):
            with open(HTML_FILE, "w", encoding="utf-8") as f:
                f.write(MOTIVATIONAL_HTML_TEMPLATE
                        .replace("__QUOTE__", "{quote}")
                        .replace("__SITE__", "{site}"))
    except Exception:
        pass
    return html


# ---------------------------------------------------------------------------
# Local HTTP server
# ---------------------------------------------------------------------------

class MotivationalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        site = self.headers.get("Host", "this site")
        html = get_motivational_html(site)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class MotivationalServer:
    def __init__(self, port=80):
        self.port = port
        self.httpd = None
        self.thread = None
        self._running = False

    def start(self):
        if self._running:
            return True
        try:
            self.httpd = HTTPServer(("127.0.0.1", self.port), MotivationalHandler)
        except (PermissionError, OSError) as e:
            logger.warning(f"Cannot bind port {self.port}: {e}")
            return False
        self._running = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        if self.httpd and self._running:
            self.httpd.shutdown()
            self.httpd.server_close()
            self._running = False


# ---------------------------------------------------------------------------
# Hosts file manager
# ---------------------------------------------------------------------------

class HostsManager:
    def __init__(self):
        self.path = HOSTS_PATH

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return f.read()
        except PermissionError:
            raise PermissionError(f"Cannot read hosts file ({self.path}). Run as administrator.")
        except OSError as e:
            raise OSError(f"Cannot read hosts file: {e}")

    def _clear_readonly(self):
        if platform.system() == "Windows":
            try:
                os.chmod(self.path, 0o666)
            except Exception as e:
                logger.warning(f"os.chmod failed: {e}")
            try:
                subprocess.run(["attrib", "-R", self.path], capture_output=True, timeout=10)
            except Exception as e:
                logger.warning(f"attrib -R failed: {e}")

    def _write(self, content):
        self._clear_readonly()
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(content)

    def has_orphaned_blocks(self):
        try:
            return BEGIN_MARKER in self._read()
        except Exception:
            return False

    def apply_blocks(self, sites):
        try:
            content = self._read()
        except (PermissionError, OSError) as e:
            logger.error(f"Hosts read failed: {e}")
            return False, f"Cannot read hosts file: {e}"
        content = self._strip_blocks(content)
        lines = [f"127.0.0.1  {s}" for s in sites]
        block_section = f"\n{BEGIN_MARKER}\n" + "\n".join(lines) + f"\n{END_MARKER}\n"
        content = content.rstrip() + "\n" + block_section
        try:
            self._write(content)
            self._flush_dns()
            logger.info(f"Blocked {len(sites)} site(s) in hosts file")
            return True, f"Blocked {len(sites)} site(s)."
        except (PermissionError, OSError) as e:
            logger.error(f"Hosts write failed: {e}")
            return False, (f"Cannot write to hosts file: {e}\n\n"
                           "Possible causes:\n"
                           "  • Windows Defender Tamper Protection is ON\n"
                           "  • Antivirus is blocking hosts file changes\n"
                           "  • The file is locked by another process\n"
                           "  • Run as Administrator")

    def remove_blocks(self):
        try:
            content = self._read()
        except (PermissionError, OSError) as e:
            logger.error(f"Hosts read failed: {e}")
            return False, f"Cannot read hosts file: {e}"
        content = self._strip_blocks(content)
        try:
            self._write(content)
            self._flush_dns()
            logger.info("Removed blocks from hosts file")
            return True, "Blocks removed."
        except (PermissionError, OSError) as e:
            logger.error(f"Hosts write failed: {e}")
            return False, f"Cannot write to hosts file: {e}"

    @staticmethod
    def _flush_dns():
        if platform.system() == "Windows":
            try:
                subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
            except Exception:
                pass

    @staticmethod
    def _strip_blocks(content):
        begin = content.find(BEGIN_MARKER)
        end = content.find(END_MARKER)
        if begin != -1 and end != -1:
            end_after = end + len(END_MARKER)
            if end_after < len(content) and content[end_after] == "\n":
                end_after += 1
            content = content[:begin].rstrip() + "\n" + content[end_after:]
        return content


# ---------------------------------------------------------------------------
# App / process blocker
# ---------------------------------------------------------------------------

class AppBlocker:
    def __init__(self, app_blocklist, on_kill=None, check_interval=3):
        self.app_blocklist = [a.lower().strip() for a in app_blocklist]
        self.on_kill = on_kill
        self.check_interval = max(1, check_interval)
        self._running = False
        self._thread = None
        self._killed_count = 0
        self._killed_names = []

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _monitor_loop(self):
        while self._running:
            try:
                self._scan_and_kill()
            except Exception as e:
                logger.error(f"AppBlocker scan error: {e}")
            slept = 0
            while slept < self.check_interval and self._running:
                time.sleep(0.5)
                slept += 0.5

    @staticmethod
    def _matches(proc_name, blocked_entry):
        proc_name = proc_name.lower()
        blocked = blocked_entry.lower()
        if proc_name == blocked:
            return True
        if not blocked.endswith(".exe") and proc_name == blocked + ".exe":
            return True
        if blocked.endswith(".exe") and proc_name == blocked[:-4]:
            return True
        return False

    def _scan_and_kill(self):
        if HAS_PSUTIL:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    proc_name = (proc.info["name"] or "").lower()
                    if not proc_name:
                        continue
                    for blocked in self.app_blocklist:
                        if self._matches(proc_name, blocked):
                            proc.kill()
                            proc.wait(timeout=3)
                            self._killed_count += 1
                            self._killed_names.append(proc_name)
                            if self.on_kill:
                                self.on_kill(proc_name)
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        else:
            if platform.system() != "Windows":
                return
            try:
                result = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=10)
                for line in result.stdout.strip().split("\n"):
                    parts = line.strip().strip('"').split('","')
                    if not parts:
                        continue
                    proc_name = parts[0].lower()
                    for blocked in self.app_blocklist:
                        if self._matches(proc_name, blocked):
                            subprocess.run(["taskkill", "/F", "/IM", parts[0]],
                                            capture_output=True, timeout=10)
                            self._killed_count += 1
                            self._killed_names.append(proc_name)
                            if self.on_kill:
                                self.on_kill(proc_name)
                            break
            except Exception as e:
                logger.error(f"AppBlocker fallback error: {e}")

    @staticmethod
    def list_running_processes():
        procs = []
        if HAS_PSUTIL:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    name = proc.info["name"] or ""
                    pid = proc.info["pid"]
                    if name:
                        procs.append((name, pid))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        elif platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=10)
                for line in result.stdout.strip().split("\n"):
                    parts = line.strip().strip('"').split('","')
                    if len(parts) >= 2:
                        try:
                            procs.append((parts[0], int(parts[1])))
                        except ValueError:
                            continue
            except Exception:
                pass
        seen = {}
        for name, pid in procs:
            if name.lower() not in seen:
                seen[name.lower()] = (name, pid)
        return sorted(seen.values(), key=lambda x: x[0].lower())


# ---------------------------------------------------------------------------
# Session tracker
# ---------------------------------------------------------------------------

class SessionTracker:
    def __init__(self):
        ensure_config_dir()
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self._lock = threading.Lock()
        self.conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_ts TEXT NOT NULL, end_ts TEXT NOT NULL,
            duration_sec INTEGER NOT NULL, mode TEXT NOT NULL,
            completed INTEGER DEFAULT 0)""")
        self.conn.commit()

    def log_session(self, start_dt, end_dt, duration_sec, mode, completed=1):
        with self._lock:
            self.conn.execute(
                "INSERT INTO sessions (start_ts, end_ts, duration_sec, mode, completed) VALUES (?, ?, ?, ?, ?)",
                (start_dt.isoformat(), end_dt.isoformat(), duration_sec, mode, completed))
            self.conn.commit()

    def get_today_stats(self):
        today = date.today().isoformat()
        with self._lock:
            cur = self.conn.execute(
                "SELECT mode, SUM(duration_sec), COUNT(*) FROM sessions WHERE date(start_ts) = ? GROUP BY mode", (today,))
            rows = cur.fetchall()
        return {m: {"seconds": s or 0, "count": c} for m, s, c in rows}

    def get_today_work_count(self):
        today = date.today().isoformat()
        with self._lock:
            cur = self.conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE mode = 'work' AND completed = 1 AND date(start_ts) = ?", (today,))
            return cur.fetchone()[0] or 0

    def get_last_n_days(self, n=7):
        with self._lock:
            cur = self.conn.execute(
                "SELECT date(start_ts) as d, SUM(duration_sec) FROM sessions WHERE mode = 'work' GROUP BY d ORDER BY d DESC LIMIT ?", (n,))
            return cur.fetchall()

    def get_total_stats(self):
        with self._lock:
            cur = self.conn.execute("SELECT COUNT(*), SUM(duration_sec) FROM sessions WHERE mode = 'work'")
            row = cur.fetchone()
        return {"total_sessions": row[0] or 0, "total_seconds": row[1] or 0}

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------------
# Schedule engine
# ---------------------------------------------------------------------------

class ScheduleEngine:
    def __init__(self, app_ref, check_interval=30):
        self.app = app_ref
        self.check_interval = check_interval
        self._running = False
        self._thread = None
        self._active_schedule = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("ScheduleEngine started")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def trigger_check_now(self):
        try:
            self._check_schedules()
        except Exception as e:
            logger.error(f"ScheduleEngine immediate check error: {e}")

    def _loop(self):
        while self._running:
            try:
                self._check_schedules()
            except Exception as e:
                logger.error(f"ScheduleEngine error: {e}")
            slept = 0
            while slept < self.check_interval and self._running:
                time.sleep(1)
                slept += 1

    def _check_schedules(self):
        schedules = self.app.cfg.get("schedules", [])
        now = datetime.now()
        now_day = now.weekday()
        now_time = now.time()
        active = None
        for sched in schedules:
            if not sched.get("enabled", True):
                continue
            days = sched.get("days", [0, 1, 2, 3, 4, 5, 6])
            if now_day not in days:
                continue
            start = self._parse_time(sched.get("start_time", "09:00"))
            end = self._parse_time(sched.get("end_time", "17:00"))
            if start <= end:
                if start <= now_time <= end:
                    active = sched
                    break
            else:
                if now_time >= start or now_time <= end:
                    active = sched
                    break
        sched_name = active["name"] if active else None
        if sched_name != self._active_schedule:
            old = self._active_schedule
            self._active_schedule = sched_name
            logger.info(f"Schedule changed: '{old}' -> '{sched_name}'")
            self.app.root.after(0, self.app._on_schedule_changed, sched_name, active)

    @staticmethod
    def _parse_time(time_str):
        try:
            parts = time_str.strip().split(":")
            return dtime(int(parts[0]), int(parts[1]))
        except Exception:
            return dtime(9, 0)

    @staticmethod
    def format_days(days):
        if not days:
            return "Never"
        if len(days) == 7:
            return "Every day"
        if days == [0, 1, 2, 3, 4]:
            return "Weekdays"
        if days == [5, 6]:
            return "Weekends"
        return ", ".join(DAYS_OF_WEEK[d] for d in sorted(days))


# ---------------------------------------------------------------------------
# Sound helper
# ---------------------------------------------------------------------------

def play_bell():
    try:
        if platform.system() == "Windows":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONINFORMATION)
        elif platform.system() == "Darwin":
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], capture_output=True, timeout=5)
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
    except Exception:
        try:
            sys.stdout.write("\a")
            sys.stdout.flush()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Dark widget helpers
# ---------------------------------------------------------------------------

def make_dark_listbox(parent, **kwargs):
    """Create a Listbox with Win11 dark colors baked in."""
    defaults = dict(
        bg=C_LISTBG, fg=C_TEXT,
        selectbackground=C_SELECT, selectforeground=C_SELECT_FG,
        activestyle="none", borderwidth=0, relief="flat",
        highlightthickness=1, highlightbackground=C_CARD_BDR,
        highlightcolor=C_CARD_BDR,
        disabledforeground=C_TEXT_DIM2,
    )
    defaults.update(kwargs)
    return tk.Listbox(parent, **defaults)


def make_dark_text(parent, **kwargs):
    """Create a Text widget with Win11 dark colors baked in."""
    defaults = dict(
        bg=C_LISTBG, fg=C_TEXT,
        insertbackground=C_TEXT,
        selectbackground=C_SELECT, selectforeground=C_SELECT_FG,
        borderwidth=0, relief="flat", highlightthickness=1,
        highlightbackground=C_CARD_BDR, highlightcolor=C_CARD_BDR,
        padx=15, pady=15,
    )
    defaults.update(kwargs)
    return tk.Text(parent, **defaults)


def make_dark_menu(parent, **kwargs):
    """Create a Menu with Win11 dark colors."""
    defaults = dict(
        tearoff=0, bg=C_SURFACE, fg=C_TEXT,
        activebackground=C_SURFACE2, activeforeground=C_PRIMARY,
        activeborderwidth=0, borderwidth=0,
        disabledforeground=C_TEXT_DIM2,
    )
    defaults.update(kwargs)
    return tk.Menu(parent, **defaults)


def make_dark_toplevel(parent, title, w, h):
    """Create a Toplevel dialog with dark title bar + dark bg."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(f"{w}x{h}")
    win.transient(parent)
    win.grab_set()
    win.configure(bg=C_BG)
    win.resizable(False, False)
    win.after(50, lambda: enable_dark_titlebar(win))
    return win


def make_card(parent, **kwargs):
    """Create a Win11 Settings-style card frame — rounded, elevated surface."""
    card = tk.Frame(parent, bg=C_SURFACE, highlightbackground=C_CARD_BDR,
                    highlightthickness=1, bd=0, **kwargs)
    return card


# ---------------------------------------------------------------------------
# Dark dialog replacements for messagebox (keeps everything dark-themed)
# ---------------------------------------------------------------------------

def _dark_dialog(parent, title, message, dialog_type="info", buttons=("OK",)):
    """Create a custom dark-themed dialog replacing messagebox.
    dialog_type: 'info', 'warning', 'error', 'question'
    Returns the text of the clicked button."""
    icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "question": "❓"}
    icon = icons.get(dialog_type, "ℹ️")

    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg=C_BG)
    win.transient(parent)
    win.grab_set()
    win.resizable(False, False)
    win.after(50, lambda: enable_dark_titlebar(win))

    lines = message.split("\n")
    max_line = max(len(l) for l in lines) if lines else 40
    w = min(max(420, max_line * 9 + 120), 620)
    h = min(max(160, len(lines) * 22 + 160), 400)
    win.geometry(f"{w}x{h}")

    parent.update_idletasks()
    px = parent.winfo_rootx() + parent.winfo_width() // 2
    py = parent.winfo_rooty() + parent.winfo_height() // 2
    win.geometry(f"+{px - w // 2}+{py - h // 2}")

    result = [None]
    content = ttk.Frame(win)
    content.pack(fill="both", expand=True, padx=28, pady=24)

    msg_frame = ttk.Frame(content)
    msg_frame.pack(fill="both", expand=True)
    ttk.Label(msg_frame, text=icon, font=("Segoe UI Variable", 28)).pack(side="left", padx=(0, 18))
    ttk.Label(msg_frame, text=message, wraplength=w - 130, justify="left",
              font=("Segoe UI Variable", 11)).pack(side="left", fill="both", expand=True)

    btn_frame = ttk.Frame(content)
    btn_frame.pack(pady=(20, 0))

    def _close(val):
        result[0] = val
        win.destroy()

    for i, label in enumerate(buttons):
        style = "Accent.TButton" if i == 0 else "TButton"
        ttk.Button(btn_frame, text=label, style=style,
                   command=lambda v=label: _close(v)).pack(side="right", padx=8)

    win.protocol("WM_DELETE_WINDOW", lambda: _close(buttons[-1]))
    parent.wait_window(win)
    return result[0]


def dark_showinfo(parent, title, message):
    _dark_dialog(parent, title, message, "info", ("OK",))

def dark_showwarning(parent, title, message):
    _dark_dialog(parent, title, message, "warning", ("OK",))

def dark_showerror(parent, title, message):
    _dark_dialog(parent, title, message, "error", ("OK",))

def dark_askyesno(parent, title, message):
    return _dark_dialog(parent, title, message, "question", ("Yes", "No")) == "Yes"


# ---------------------------------------------------------------------------
# Main application — v3.0 with Win11 Settings-style left navigation pane
# ---------------------------------------------------------------------------

class FocusGuardianApp:

    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.tracker = SessionTracker()
        self.hosts = HostsManager()
        self.server = MotivationalServer(self.cfg.get("server_port", 80))

        # Timer state
        self.timer_running = False
        self.timer_thread = None
        self.current_mode = "work"
        self.session_count = self.tracker.get_today_work_count()
        self.remaining_sec = self.cfg["work_duration_min"] * 60
        self.session_start = None
        self.paused_duration = 0
        self.pause_start = None
        self.is_paused = False
        self.eye_rest_after = self.cfg["eye_rest_interval_min"] * 60
        self.app_blocker = None
        self._is_admin = is_admin()
        self.app_blocking_active = False

        # Blocking state
        self.session_blocking = False
        self.schedule_blocking = False
        self.active_schedule_profile = None
        self.blocking_active = False
        self._applied_sites = set()
        self._applied_apps = set()

        # Schedule engine
        self.scheduler = ScheduleEngine(self)

        # Current page tracking
        self._current_page = 0

        self._build_ui()
        self._refresh_profile_display()
        self._refresh_blocklist_display()
        self._refresh_app_blocklist_display()
        self._refresh_schedules_display()
        self._update_timer_display()
        self._update_admin_indicator()
        self._update_next_hint()

        self.server.start()
        self._cleanup_orphaned_blocks()
        self.scheduler.start()

        self.root.bind("<space>", self._on_space_key)
        self.root.bind("<Escape>", self._on_escape_key)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- Profile helpers ----

    def _get_active_profile(self):
        idx = self.cfg.get("active_profile", 0)
        profiles = self.cfg.get("profiles", DEFAULT_PROFILES)
        if idx < 0 or idx >= len(profiles):
            idx = 0
        return profiles[idx]

    def _get_blocking_sites(self):
        if self.schedule_blocking and self.active_schedule_profile is not None:
            for p in self.cfg.get("profiles", []):
                if p["name"] == self.active_schedule_profile:
                    return p.get("blocklist", [])
            return self._get_active_profile().get("blocklist", [])
        if self.session_blocking:
            return self._get_active_profile().get("blocklist", [])
        return []

    def _get_blocking_apps(self):
        if self.schedule_blocking and self.active_schedule_profile is not None:
            for p in self.cfg.get("profiles", []):
                if p["name"] == self.active_schedule_profile:
                    return p.get("app_blocklist", [])
            return self._get_active_profile().get("app_blocklist", [])
        if self.session_blocking:
            return self._get_active_profile().get("app_blocklist", [])
        return []

    def _get_blocking_profile_name(self):
        if self.schedule_blocking and self.active_schedule_profile is not None:
            return self.active_schedule_profile
        if self.session_blocking:
            return self._get_active_profile()["name"]
        return None

    # ---- Dual-source blocking state ----

    def _update_blocking_state(self):
        should_block = self.session_blocking or self.schedule_blocking
        sites = self._get_blocking_sites() if should_block else []
        apps = self._get_blocking_apps() if should_block else []
        sites_set = set(s.lower() for s in sites)
        apps_set = set(a.lower() for a in apps)

        if should_block and (sites or apps):
            if sites_set != self._applied_sites:
                ok, msg = self.hosts.apply_blocks(sites)
                if ok:
                    self.blocking_active = True
                    self._applied_sites = sites_set
                else:
                    self.blocking_active = False
                    self._applied_sites = set()
                self._update_block_status(ok, msg)
            elif not self.blocking_active and sites:
                ok, msg = self.hosts.apply_blocks(sites)
                if ok:
                    self.blocking_active = True
                    self._applied_sites = sites_set
                self._update_block_status(ok, msg)

            if apps_set != self._applied_apps:
                self._deactivate_app_blocking()
                if apps:
                    self._activate_app_blocking(apps)
                    self._applied_apps = apps_set
                else:
                    self._applied_apps = set()
            elif apps and not self.app_blocking_active:
                self._activate_app_blocking(apps)
                self._applied_apps = apps_set
            self._update_app_block_status(apps)
        else:
            if self.blocking_active or self._applied_sites:
                self.hosts.remove_blocks()
                self.blocking_active = False
                self._applied_sites = set()
            self.block_status.config(text="⚪  Website blocking: inactive", foreground=C_TEXT_DIM)
            if self._applied_apps or self.app_blocking_active:
                self._deactivate_app_blocking()
                self._applied_apps = set()
            self.app_block_status.config(text="⚪  App blocking: inactive", foreground=C_TEXT_DIM)

    def _update_block_status(self, ok, error_msg=""):
        profile_name = self._get_blocking_profile_name()
        source_tags = []
        if self.session_blocking:
            source_tags.append("session")
        if self.schedule_blocking:
            source_tags.append("schedule")
        tag_str = f" [{', '.join(source_tags)}]" if source_tags else ""
        sites = self._get_blocking_sites()
        if ok and sites:
            self.block_status.config(
                text=f"🔴  Blocking {len(sites)} site(s){tag_str}  •  {profile_name}", foreground=C_DANGER)
        else:
            short_err = error_msg.split("\n")[0] if error_msg else "needs admin"
            self.block_status.config(
                text=f"⚠  Website blocking failed: {short_err}", foreground=C_WARNING)

    def _update_app_block_status(self, apps):
        profile_name = self._get_blocking_profile_name()
        source_tags = []
        if self.session_blocking:
            source_tags.append("session")
        if self.schedule_blocking:
            source_tags.append("schedule")
        tag_str = f" [{', '.join(source_tags)}]" if source_tags else ""
        if apps:
            self.app_block_status.config(
                text=f"🔴  Monitoring {len(apps)} app(s){tag_str}  •  {profile_name}", foreground=C_DANGER)
        else:
            self.app_block_status.config(
                text=f"⚪  No apps to monitor  •  {profile_name}", foreground=C_TEXT_DIM)

    # ---- UI construction ----

    def _build_ui(self):
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.configure(bg=C_BG)

        style = ttk.Style()
        apply_win11_dark_theme(style)
        configure_dark_tk_widgets(self.root)

        # Window size — Win11 Settings app proportions
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = min(int(sw * 0.82), 960)
        h = min(int(sh * 0.88), 760)
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(720, 600)

        # Dark title bar + Mica backdrop
        self.root.after(50, lambda: enable_dark_titlebar(self.root))

        # Main layout: left nav pane | right content area
        self._main_frame = tk.Frame(self.root, bg=C_BG)
        self._main_frame.pack(fill="both", expand=True)

        # Navigation pane (left)
        nav_items = [
            ("⏱", "Timer"),
            ("🌐", "Websites"),
            ("🛑", "Desktop Apps"),
            ("📁", "Profiles"),
            ("📅", "Schedules"),
            ("📊", "Stats"),
            ("⚙", "Settings"),
        ]
        self.nav_pane = NavPane(self._main_frame, nav_items, self._switch_page, background=C_NAV_BG)
        self.nav_pane.pack(side="left", fill="y")

        # Vertical separator between nav and content
        sep = tk.Frame(self._main_frame, width=1, bg=C_BORDER_LT)
        sep.pack(side="left", fill="y")

        # Content area (right) — scrollable
        self._content_outer = tk.Frame(self._main_frame, bg=C_BG)
        self._content_outer.pack(side="left", fill="both", expand=True)

        # Canvas + scrollbar for scrollable content
        self._content_canvas = tk.Canvas(self._content_outer, bg=C_BG,
                                          highlightthickness=0, bd=0)
        self._content_scrollbar = ttk.Scrollbar(self._content_outer, orient="vertical",
                                                 command=self._content_canvas.yview)
        self._content_canvas.configure(yscrollcommand=self._content_scrollbar.set)
        self._content_scrollbar.pack(side="right", fill="y")
        self._content_canvas.pack(side="left", fill="both", expand=True)

        self._content_window = self._content_canvas.create_window(0, 0, anchor="nw")
        self._content_frame = tk.Frame(self._content_canvas, bg=C_BG)
        self._content_canvas.itemconfig(self._content_window, window=self._content_frame)

        # Bind configure to update scrollregion
        self._content_frame.bind("<Configure>", self._on_content_configure)
        self._content_canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel scrolling
        self._content_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._content_canvas.bind("<Enter>", lambda e: self._bind_mousewheel())
        self._content_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())

        # Build all pages
        self._pages = []
        self._build_timer_page()
        self._build_sites_page()
        self._build_apps_page()
        self._build_profiles_page()
        self._build_schedules_page()
        self._build_stats_page()
        self._build_settings_page()

        # Show first page
        self._show_page(0)
        self.nav_pane.select(0)

    def _on_content_configure(self, event):
        self._content_canvas.configure(scrollregion=self._content_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._content_canvas.itemconfig(self._content_window, width=event.width)

    def _on_mousewheel(self, event):
        self._content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_mousewheel(self):
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self):
        self.root.unbind_all("<MouseWheel>")

    def _switch_page(self, page_index):
        self._show_page(page_index)

    def _show_page(self, page_index):
        for widget in self._content_frame.winfo_children():
            widget.pack_forget()
        if 0 <= page_index < len(self._pages):
            self._pages[page_index].pack(fill="both", expand=True)
            self._current_page = page_index
            if page_index == 5:  # Stats
                self.refresh_stats()
            elif page_index == 4:  # Schedules
                self._refresh_schedules_display()
            elif page_index == 3:  # Profiles
                self._refresh_profile_display()

    def _make_page(self):
        """Create a new page frame."""
        page = tk.Frame(self._content_frame, bg=C_BG)
        self._pages.append(page)
        return page

    def _page_header(self, parent, text, subtitle=None):
        """Create a Win11 Settings-style page header with title and optional subtitle."""
        header = tk.Frame(parent, bg=C_BG)
        header.pack(fill="x", padx=32, pady=(28, 20))
        tk.Label(header, text=text, font=("Segoe UI Variable", 22, "bold"),
                 bg=C_BG, fg=C_TEXT).pack(anchor="w")
        if subtitle:
            tk.Label(header, text=subtitle, font=("Segoe UI Variable", 10),
                     bg=C_BG, fg=C_TEXT_DIM).pack(anchor="w", pady=(4, 0))
        return header

    def _make_card(self, parent, title=None):
        """Create a Win11 Settings-style card with optional title."""
        card = make_card(parent)
        card.pack(fill="x", padx=32, pady=(0, 10))
        if title:
            lbl = tk.Label(card, text=title, font=("Segoe UI Variable", 11, "bold"),
                          bg=C_SURFACE, fg=C_TEXT)
            lbl.pack(anchor="w", padx=20, pady=(16, 8))
        return card

    # ---- Timer Page ----

    def _build_timer_page(self):
        page = self._make_page()
        self._page_header(page, "Timer", "Start a Pomodoro focus session.")

        # Top bar — admin + schedule status
        top_bar = tk.Frame(page, bg=C_BG)
        top_bar.pack(fill="x", padx=32, pady=(0, 8))
        self.admin_label = ttk.Label(top_bar, text="", style="AdminOK.TLabel")
        self.admin_label.pack(side="left")
        self.schedule_status_label = ttk.Label(top_bar, text="", style="SchedActive.TLabel")
        self.schedule_status_label.pack(side="right")

        # Profile selector card
        prof_card = self._make_card(page, "Focus Profile")
        prof_inner = tk.Frame(prof_card, bg=C_SURFACE)
        prof_inner.pack(fill="x", padx=20, pady=(0, 14))
        ttk.Label(prof_inner, text="Active profile:", style="CardDim.TLabel").pack(side="left", padx=(0, 8))
        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(prof_inner, textvariable=self.profile_var,
                                          state="readonly", width=22)
        self.profile_combo.pack(side="left")
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_selected)

        # Timer card — the big circular timer
        timer_card = self._make_card(page)
        timer_inner = tk.Frame(timer_card, bg=C_SURFACE)
        timer_inner.pack(fill="both", expand=True, padx=20, pady=16)

        self.mode_label = ttk.Label(timer_inner, text="🔵  Work Time", style="Mode.TLabel",
                                     font=("Segoe UI Variable", 14, "bold"))
        self.mode_label.pack(pady=(0, 8))

        self.timer_canvas = tk.Canvas(timer_inner, width=200, height=200, bg=C_SURFACE, highlightthickness=0)
        self.timer_canvas.pack(pady=(4, 4))
        self._draw_timer_ring()

        self.next_hint_label = ttk.Label(timer_inner, text="", style="Hint.TLabel")
        self.next_hint_label.pack(pady=(0, 8))

        # Control buttons
        btn_frame = tk.Frame(timer_inner, bg=C_SURFACE)
        btn_frame.pack(pady=(4, 8))
        self.btn_start = ttk.Button(btn_frame, text="▶  Start", width=12, style="Accent.TButton", command=self.start_timer)
        self.btn_start.grid(row=0, column=0, padx=6)
        self.btn_pause = ttk.Button(btn_frame, text="⏸  Pause", width=12, command=self.pause_timer, state="disabled")
        self.btn_pause.grid(row=0, column=1, padx=6)
        self.btn_stop = ttk.Button(btn_frame, text="⏹  Stop", width=12, command=self.stop_timer, state="disabled")
        self.btn_stop.grid(row=0, column=2, padx=6)
        self.btn_skip = ttk.Button(btn_frame, text="⏭  Skip", width=12, command=self.skip_break, state="disabled")
        self.btn_skip.grid(row=0, column=3, padx=6)

        # Status card
        status_card = self._make_card(page)
        status_inner = tk.Frame(status_card, bg=C_SURFACE)
        status_inner.pack(fill="x", padx=20, pady=16)

        self.session_counter_label = ttk.Label(status_inner,
            text=f"✅  Completed today: {self.session_count}", style="Mode.TLabel", foreground=C_SUCCESS)
        self.session_counter_label.pack(anchor="w", pady=(0, 4))
        self.block_status = ttk.Label(status_inner, text="⚪  Website blocking: inactive",
                                       style="Mode.TLabel", foreground=C_TEXT_DIM)
        self.block_status.pack(anchor="w", pady=2)
        self.app_block_status = ttk.Label(status_inner, text="⚪  App blocking: inactive",
                                           style="Mode.TLabel", foreground=C_TEXT_DIM)
        self.app_block_status.pack(anchor="w", pady=2)
        self.kill_log_label = ttk.Label(status_inner, text="", style="Small.TLabel")
        self.kill_log_label.pack(anchor="w", pady=2)

        # Manual controls card
        manual_card = self._make_card(page)
        manual_inner = tk.Frame(manual_card, bg=C_SURFACE)
        manual_inner.pack(fill="x", padx=20, pady=16)
        ttk.Button(manual_inner, text="🔒  Block Now", command=self.manual_block).pack(side="left", padx=6)
        ttk.Button(manual_inner, text="🔓  Unblock All", command=self.manual_unblock).pack(side="left", padx=6)

        # Hint
        tk.Label(page, text="💡  Space = Start/Pause  •  Esc = Stop",
                 font=("Segoe UI Variable", 9), bg=C_BG, fg=C_TEXT_DIM).pack(pady=(8, 28))

    # ---- Websites Page ----

    def _build_sites_page(self):
        page = self._make_page()
        self._page_header(page, "Blocked Websites", "Sites that will be redirected during focus sessions.")
        self.sites_profile_label = ttk.Label(page, text="", style="Dim.TLabel")
        self.sites_profile_label.pack(anchor="w", padx=32, pady=(0, 8))

        list_card = self._make_card(page)
        list_inner = tk.Frame(list_card, bg=C_SURFACE)
        list_inner.pack(fill="both", expand=True, padx=20, pady=16)
        list_inner.columnconfigure(0, weight=1)
        list_inner.rowconfigure(0, weight=1)
        self.blocklist_box = make_dark_listbox(list_inner, selectmode="extended", font=("Cascadia Code", 11))
        self.blocklist_box.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(list_inner, orient="vertical", command=self.blocklist_box.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.blocklist_box.config(yscrollcommand=sb.set)
        self.site_context_menu = make_dark_menu(self.blocklist_box)
        self.site_context_menu.add_command(label="  🗑  Remove  ", command=self.remove_sites)
        self.blocklist_box.bind("<Button-3>", self._show_site_context_menu)

        add_card = self._make_card(page)
        add_inner = tk.Frame(add_card, bg=C_SURFACE)
        add_inner.pack(fill="x", padx=20, pady=16)
        ttk.Label(add_inner, text="Add:", style="CardDim.TLabel").grid(row=0, column=0, padx=(0, 8), pady=4)
        self.add_entry = ttk.Entry(add_inner, width=28)
        self.add_entry.grid(row=0, column=1, padx=6, pady=4)
        self.add_entry.bind("<Return>", lambda e: self.add_site())
        ttk.Button(add_inner, text="Add", style="Accent.TButton", command=self.add_site).grid(row=0, column=2, padx=6, pady=4)
        ttk.Button(add_inner, text="Remove", command=self.remove_sites).grid(row=0, column=3, padx=6, pady=4)

    # ---- Desktop Apps Page ----

    def _build_apps_page(self):
        page = self._make_page()
        self._page_header(page, "Blocked Desktop Apps", "Applications that will be killed during focus sessions.")
        self.apps_profile_label = ttk.Label(page, text="", style="Dim.TLabel")
        self.apps_profile_label.pack(anchor="w", padx=32, pady=(0, 8))

        list_card = self._make_card(page)
        list_inner = tk.Frame(list_card, bg=C_SURFACE)
        list_inner.pack(fill="both", expand=True, padx=20, pady=16)
        list_inner.columnconfigure(0, weight=1)
        list_inner.rowconfigure(0, weight=1)
        self.app_blocklist_box = make_dark_listbox(list_inner, selectmode="extended", font=("Cascadia Code", 11))
        self.app_blocklist_box.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(list_inner, orient="vertical", command=self.app_blocklist_box.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.app_blocklist_box.config(yscrollcommand=sb.set)
        self.app_context_menu = make_dark_menu(self.app_blocklist_box)
        self.app_context_menu.add_command(label="  🗑  Remove  ", command=self.remove_apps)
        self.app_blocklist_box.bind("<Button-3>", self._show_app_context_menu)

        add_card = self._make_card(page)
        add_inner = tk.Frame(add_card, bg=C_SURFACE)
        add_inner.pack(fill="x", padx=20, pady=16)
        ttk.Label(add_inner, text="Add:", style="CardDim.TLabel").grid(row=0, column=0, padx=(0, 8), pady=4)
        self.app_add_entry = ttk.Entry(add_inner, width=28)
        self.app_add_entry.grid(row=0, column=1, padx=6, pady=4)
        self.app_add_entry.bind("<Return>", lambda e: self.add_app())
        ttk.Button(add_inner, text="Add", style="Accent.TButton", command=self.add_app).grid(row=0, column=2, padx=6, pady=4)
        ttk.Button(add_inner, text="Remove", command=self.remove_apps).grid(row=0, column=3, padx=6, pady=4)

        picker_card = self._make_card(page)
        picker_inner = tk.Frame(picker_card, bg=C_SURFACE)
        picker_inner.pack(fill="x", padx=20, pady=16)
        ttk.Button(picker_inner, text="📋  Pick from Running Processes",
                   command=self.pick_running_process).pack(anchor="w")

    # ---- Profiles Page ----

    def _build_profiles_page(self):
        page = self._make_page()
        self._page_header(page, "Focus Profiles",
                         "Each profile has its own website and app blocklist.\nSwitch from the Timer page or use Schedules to auto-activate.")

        list_card = self._make_card(page)
        list_inner = tk.Frame(list_card, bg=C_SURFACE)
        list_inner.pack(fill="both", expand=True, padx=20, pady=16)
        list_inner.columnconfigure(0, weight=1)
        list_inner.rowconfigure(0, weight=1)
        self.profile_listbox = make_dark_listbox(list_inner, font=("Segoe UI Variable", 12), selectmode="single")
        self.profile_listbox.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(list_inner, orient="vertical", command=self.profile_listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.profile_listbox.config(yscrollcommand=sb.set)
        self.profile_listbox.bind("<Double-Button-1>", lambda e: self.edit_profile())

        btn_card = self._make_card(page)
        btn_inner = tk.Frame(btn_card, bg=C_SURFACE)
        btn_inner.pack(fill="x", padx=20, pady=16)
        ttk.Button(btn_inner, text="➕  New", style="Accent.TButton", command=self.new_profile).pack(side="left", padx=4)
        ttk.Button(btn_inner, text="✏  Edit", command=self.edit_profile).pack(side="left", padx=4)
        ttk.Button(btn_inner, text="📋  Duplicate", command=self.duplicate_profile).pack(side="left", padx=4)
        ttk.Button(btn_inner, text="🗑  Delete", style="Danger.TButton", command=self.delete_profile).pack(side="left", padx=4)
        ttk.Button(btn_inner, text="⭐  Set Active", command=self.set_active_profile).pack(side="left", padx=4)

    # ---- Schedules Page ----

    def _build_schedules_page(self):
        page = self._make_page()
        self._page_header(page, "Schedules",
                         "Schedules automatically activate a profile at specific times.\nThey work independently of the Pomodoro timer.")

        list_card = self._make_card(page)
        list_inner = tk.Frame(list_card, bg=C_SURFACE)
        list_inner.pack(fill="both", expand=True, padx=20, pady=16)
        list_inner.columnconfigure(0, weight=1)
        list_inner.rowconfigure(0, weight=1)
        cols = ("name", "profile", "days", "time", "enabled")
        self.sched_tree = ttk.Treeview(list_inner, columns=cols, show="headings", height=8)
        self.sched_tree.heading("name", text="Name")
        self.sched_tree.heading("profile", text="Profile")
        self.sched_tree.heading("days", text="Days")
        self.sched_tree.heading("time", text="Time")
        self.sched_tree.heading("enabled", text="On?")
        self.sched_tree.column("name", width=120)
        self.sched_tree.column("profile", width=120)
        self.sched_tree.column("days", width=120)
        self.sched_tree.column("time", width=130)
        self.sched_tree.column("enabled", width=50)
        self.sched_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(list_inner, orient="vertical", command=self.sched_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.sched_tree.config(yscrollcommand=sb.set)
        self.sched_empty_label = ttk.Label(page, text="", style="Hint.TLabel")

        btn_card = self._make_card(page)
        btn_inner = tk.Frame(btn_card, bg=C_SURFACE)
        btn_inner.pack(fill="x", padx=20, pady=16)
        ttk.Button(btn_inner, text="➕  Add", style="Accent.TButton", command=self.add_schedule).pack(side="left", padx=4)
        ttk.Button(btn_inner, text="✏  Edit", command=self.edit_schedule).pack(side="left", padx=4)
        ttk.Button(btn_inner, text="🗑  Delete", style="Danger.TButton", command=self.delete_schedule).pack(side="left", padx=4)
        ttk.Button(btn_inner, text="🔄  Toggle", command=self.toggle_schedule).pack(side="left", padx=4)

    # ---- Stats Page ----

    def _build_stats_page(self):
        page = self._make_page()
        self._page_header(page, "Focus Statistics", "Your productivity at a glance.")

        tiles_card = self._make_card(page)
        tiles_inner = tk.Frame(tiles_card, bg=C_SURFACE)
        tiles_inner.pack(fill="x", padx=20, pady=16)
        for i in range(3):
            tiles_inner.columnconfigure(i, weight=1, uniform="tile")
        self._stat_tile_focus = self._make_stat_tile(tiles_inner, "Focus Time", "0m", C_PRIMARY, 0)
        self._stat_tile_breaks = self._make_stat_tile(tiles_inner, "Break Time", "0m", C_SUCCESS, 1)
        self._stat_tile_sessions = self._make_stat_tile(tiles_inner, "Sessions", "0", C_WARNING, 2)

        alltime_card = self._make_card(page, "All Time")
        alltime_inner = tk.Frame(alltime_card, bg=C_SURFACE)
        alltime_inner.pack(fill="x", padx=20, pady=(0, 16))
        for i in range(2):
            alltime_inner.columnconfigure(i, weight=1, uniform="at")
        self._stat_tile_total = self._make_stat_tile(alltime_inner, "Total Focus", "0m", C_PRIMARY, 0)
        self._stat_tile_total_sess = self._make_stat_tile(alltime_inner, "Total Sessions", "0", C_SUCCESS, 1)

        chart_card = self._make_card(page, "Last 7 Days")
        chart_inner = tk.Frame(chart_card, bg=C_SURFACE)
        chart_inner.pack(fill="x", padx=20, pady=(0, 16))
        self._stats_chart_canvas = tk.Canvas(chart_inner, height=180, bg=C_SURFACE,
                                              highlightthickness=0, bd=0)
        self._stats_chart_canvas.pack(fill="x")
        self._stats_chart_canvas.bind("<Configure>",
            lambda e: self._draw_stats_chart(self.tracker.get_last_n_days(7)))
        ttk.Button(page, text="🔄  Refresh", style="Accent.TButton",
                   command=self.refresh_stats).pack(pady=(0, 24))

    def _make_stat_tile(self, parent, label, value, color, col):
        """Create a metric tile with accent left border."""
        tile = tk.Frame(parent, bg=C_SURFACE, highlightbackground=C_CARD_BDR,
                        highlightthickness=1, bd=0)
        tile.grid(row=0, column=col, sticky="nsew",
                  padx=(0 if col == 0 else 8, 8 if col < 2 else 0), pady=4)
        accent = tk.Frame(tile, width=3, bg=color)
        accent.pack(side="left", fill="y")
        content = tk.Frame(tile, bg=C_SURFACE)
        content.pack(side="left", fill="both", expand=True, padx=16, pady=14)
        val_label = tk.Label(content, text=value, font=("Segoe UI Variable", 22, "bold"),
                             bg=C_SURFACE, fg=color)
        val_label.pack(anchor="w")
        lbl_label = tk.Label(content, text=label, font=("Segoe UI Variable", 9),
                             bg=C_SURFACE, fg=C_TEXT_DIM)
        lbl_label.pack(anchor="w", pady=(4, 0))
        tile._val_label = val_label
        return tile

    def _draw_stats_chart(self, last7):
        """Draw a clean bar chart on Canvas showing focus minutes for last 7 days."""
        c = self._stats_chart_canvas
        c.delete("all")
        c.update_idletasks()
        w = c.winfo_width()
        if w <= 1:
            w = 400
        h = 180
        pad_left, pad_right, pad_top, pad_bottom = 12, 12, 20, 36
        chart_w = w - pad_left - pad_right
        chart_h = h - pad_top - pad_bottom
        today_str = date.today().isoformat()
        last7_dict = {d: s for d, s in last7}
        max_secs = max([s for _, s in last7] + [3600])
        bar_gap = 10
        bar_w = max(8, (chart_w - bar_gap * 6) // 7)
        for i in range(6, -1, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            secs = last7_dict.get(d, 0)
            mins = secs / 60
            bar_h = max(2, int((secs / max_secs) * chart_h)) if secs > 0 else 2
            x = pad_left + (6 - i) * (bar_w + bar_gap)
            y_top = pad_top + chart_h - bar_h
            y_bot = pad_top + chart_h
            is_today = (d == today_str)
            if is_today:
                bar_color = C_PRIMARY
            elif mins > 50:
                bar_color = C_SUCCESS
            elif mins > 20:
                bar_color = C_WARNING
            else:
                bar_color = C_SURFACE2
            r = min(4, bar_w // 2, bar_h // 2)
            self._draw_rounded_bar(c, x, y_top, x + bar_w, y_bot, r, bar_color)
            day_label = d[8:10] + "/" + d[5:7]
            c.create_text(x + bar_w / 2, h - 18, text=day_label,
                          font=("Segoe UI Variable", 8), fill=C_TEXT_DIM2, anchor="n")
            if secs > 0:
                val_text = f"{int(mins)}m" if mins < 60 else f"{mins/60:.1f}h"
                c.create_text(x + bar_w / 2, y_top - 8, text=val_text,
                              font=("Segoe UI Variable", 8, "bold"),
                              fill=bar_color, anchor="s")
            if is_today:
                c.create_text(x + bar_w / 2, h - 4, text="Today",
                              font=("Segoe UI Variable", 7, "bold"),
                              fill=C_PRIMARY, anchor="n")
        c.create_line(pad_left, pad_top + chart_h, w - pad_right, pad_top + chart_h,
                      fill=C_BORDER, width=1)

    @staticmethod
    def _draw_rounded_bar(canvas, x1, y1, x2, y2, r, color):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2, x2, y2, x2, y2,
            x1, y2, x1, y2, x1, y1 + r,
            x1, y1, x1 + r, y1,
        ]
        canvas.create_polygon(points, smooth=True, fill=color, outline="")

    # ---- Settings Page ----

    def _build_settings_page(self):
        page = self._make_page()
        self._page_header(page, "Settings", "Customize your focus session parameters.")

        # Durations card
        dur_card = self._make_card(page, "Pomodoro Durations")
        dur_inner = tk.Frame(dur_card, bg=C_SURFACE)
        dur_inner.pack(fill="x", padx=20, pady=(0, 16))
        dur_inner.columnconfigure(0, weight=1)
        dur_inner.columnconfigure(1, weight=0)
        dur_inner.columnconfigure(2, weight=0)
        self.settings_vars = {}
        row = 0
        for key, label, suffix in [
            ("work_duration_min", "Work duration", "min"), ("short_break_min", "Short break", "min"),
            ("long_break_min", "Long break", "min"), ("sessions_before_long_break", "Sessions before long break", ""),
            ("eye_rest_interval_min", "Eye-rest reminder interval", "min"), ("server_port", "Block page server port", ""),
            ("app_check_interval_sec", "App scan interval", "sec"),
        ]:
            ttk.Label(dur_inner, text=label + ":", style="CardDim.TLabel").grid(row=row, column=0, sticky="w", pady=8)
            var = tk.IntVar(value=self.cfg[key])
            ttk.Entry(dur_inner, textvariable=var, width=8).grid(row=row, column=1, sticky="w", padx=8, pady=8)
            if suffix:
                ttk.Label(dur_inner, text=suffix, style="CardDim.TLabel").grid(row=row, column=2, sticky="w")
            self.settings_vars[key] = var
            row += 1

        # Toggles card
        tog_card = self._make_card(page, "Options")
        tog_inner = tk.Frame(tog_card, bg=C_SURFACE)
        tog_inner.pack(fill="x", padx=20, pady=(0, 16))
        self.sound_var = tk.BooleanVar(value=self.cfg.get("sound_enabled", True))
        sound_frame = tk.Frame(tog_inner, bg=C_SURFACE)
        sound_frame.pack(fill="x", pady=6)
        Win11Toggle(sound_frame, variable=self.sound_var, background=C_SURFACE).pack(side="left", padx=(0, 10))
        ttk.Label(sound_frame, text="🔔  Play sound on session complete", style="Card.TLabel").pack(side="left")

        self.strict_var = tk.BooleanVar(value=self.cfg["strict_mode"])
        strict_frame = tk.Frame(tog_inner, bg=C_SURFACE)
        strict_frame.pack(fill="x", pady=6)
        Win11Toggle(strict_frame, variable=self.strict_var, background=C_SURFACE).pack(side="left", padx=(0, 10))
        ttk.Label(strict_frame, text="🔒  Strict mode (harder to stop mid-session)", style="Card.TLabel").pack(side="left")

        # Actions card
        act_card = self._make_card(page, "Actions")
        act_inner = tk.Frame(act_card, bg=C_SURFACE)
        act_inner.pack(fill="x", padx=20, pady=(0, 16))
        ttk.Button(act_inner, text="💾  Save Settings", style="Accent.TButton",
                   command=self.save_settings).pack(anchor="w", pady=5)
        ttk.Button(act_inner, text="📋  View Log", command=self.view_log).pack(anchor="w", pady=5)
        ttk.Button(act_inner, text="🗑  Reset All Data", style="Danger.TButton",
                   command=self.reset_all_data).pack(anchor="w", pady=5)

        # Info card
        info_card = self._make_card(page, "File Locations")
        info_inner = tk.Frame(info_card, bg=C_SURFACE)
        info_inner.pack(fill="x", padx=20, pady=(0, 16))
        ttk.Label(info_inner, text=f"Config: {CONFIG_FILE}", style="CardDim.TLabel").pack(anchor="w")
        ttk.Label(info_inner, text=f"Log: {LOG_FILE}", style="CardDim.TLabel").pack(anchor="w")

    # ---- Timer ring drawing ----

    def _draw_timer_ring(self):
        c = self.timer_canvas
        c.delete("all")
        cx, cy = 100, 100
        r = 80
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=C_SURFACE2, width=8, fill="")
        max_sec = self.cfg["work_duration_min"] * 60 if self.current_mode == "work" else \
                  self.cfg.get("long_break_min", 15) * 60 if self.current_mode == "long_break" else \
                  self.cfg.get("short_break_min", 5) * 60
        if max_sec <= 0:
            max_sec = 1
        progress = max(0, min(1, 1.0 - (max(0, self.remaining_sec) / max_sec)))
        if progress > 0:
            arc_color = C_PRIMARY if self.current_mode == "work" else C_SUCCESS
            if self.current_mode == "work" and self.remaining_sec <= 120:
                arc_color = C_DANGER
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-360 * progress,
                        style="arc", outline=arc_color, width=8)
        m, s = divmod(max(0, self.remaining_sec), 60)
        time_str = f"{m:02d}:{s:02d}"
        text_color = C_PRIMARY
        if self.current_mode == "work":
            text_color = C_DANGER if self.remaining_sec <= 120 else C_PRIMARY
        else:
            text_color = C_SUCCESS
        c.create_text(cx, cy - 8, text=time_str, font=("Segoe UI Variable", 32, "bold"), fill=text_color)
        mode_text = "WORK" if self.current_mode == "work" else "LONG BREAK" if self.current_mode == "long_break" else "SHORT BREAK"
        c.create_text(cx, cy + 22, text=mode_text, font=("Segoe UI Variable", 9), fill=C_TEXT_DIM)

    # ---- Context menus ----

    def _show_site_context_menu(self, event):
        self.blocklist_box.selection_clear(0, tk.END)
        idx = self.blocklist_box.nearest(event.y)
        if idx >= 0:
            self.blocklist_box.selection_set(idx)
            self.site_context_menu.tk_popup(event.x_root, event.y_root)

    def _show_app_context_menu(self, event):
        self.app_blocklist_box.selection_clear(0, tk.END)
        idx = self.app_blocklist_box.nearest(event.y)
        if idx >= 0:
            self.app_blocklist_box.selection_set(idx)
            self.app_context_menu.tk_popup(event.x_root, event.y_root)

    # ---- Keyboard shortcuts ----

    def _on_space_key(self, event):
        if self.timer_running:
            self.pause_timer()
        elif self.btn_start["state"] == "normal":
            self.start_timer()

    def _on_escape_key(self, event):
        if self.btn_stop["state"] == "normal":
            self.stop_timer()

    # ---- Admin / schedule indicators ----

    def _update_admin_indicator(self):
        if self._is_admin:
            self.admin_label.config(text="🟢  Administrator", style="AdminOK.TLabel")
            self.nav_pane.set_admin_status("🟢 Administrator", True)
        else:
            self.admin_label.config(text="⚠  Limited mode", style="AdminWarn.TLabel")
            self.nav_pane.set_admin_status("⚠ Limited mode", False)

    def _update_schedule_status(self):
        if self.schedule_blocking and self.active_schedule_profile:
            self.schedule_status_label.config(text=f"📅  Schedule: {self.active_schedule_profile}")
        else:
            self.schedule_status_label.config(text="")

    def _cleanup_orphaned_blocks(self):
        try:
            if self.hosts.has_orphaned_blocks():
                logger.warning("Orphaned blocks detected in hosts file")
                self.root.after(1000, lambda: dark_showwarning(self.root,
                    "Orphaned Blocks Detected",
                    "FocusGuardian found leftover website blocks from a previous session\n"
                    "(the app may have crashed or been force-closed).\n\n"
                    "These blocks have been cleaned up automatically."))
                ok, msg = self.hosts.remove_blocks()
                if ok:
                    logger.info("Orphaned blocks cleaned up")
        except Exception as e:
            logger.error(f"Orphaned block cleanup error: {e}")

    # ---- Profile management ----

    def _refresh_profile_display(self):
        profiles = self.cfg.get("profiles", [])
        active_idx = self.cfg.get("active_profile", 0)
        self.profile_listbox.delete(0, tk.END)
        for i, p in enumerate(profiles):
            n_sites = len(p.get("blocklist", []))
            n_apps = len(p.get("app_blocklist", []))
            marker = "  ⭐" if i == active_idx else ""
            self.profile_listbox.insert(tk.END, f"{p['name']}  ({n_sites} sites, {n_apps} apps){marker}")
        names = [p["name"] for p in profiles]
        self.profile_combo.config(values=names)
        if 0 <= active_idx < len(names):
            self.profile_combo.current(active_idx)
        active = self._get_active_profile()
        self.sites_profile_label.config(text=f"Editing: {active['name']}  ({len(active.get('blocklist', []))} sites)")
        self.apps_profile_label.config(text=f"Editing: {active['name']}  ({len(active.get('app_blocklist', []))} apps)")

    def _on_profile_selected(self, event):
        idx = self.profile_combo.current()
        if idx >= 0:
            self.cfg["active_profile"] = idx
            save_config(self.cfg)
            self._refresh_profile_display()
            self._refresh_blocklist_display()
            self._refresh_app_blocklist_display()
            if self.session_blocking:
                self._update_blocking_state()

    def new_profile(self):
        name = self._ask_string("New Profile", "Enter profile name:")
        if not name:
            return
        if any(p["name"] == name for p in self.cfg["profiles"]):
            dark_showwarning(self.root, "Duplicate", f"A profile named '{name}' already exists.")
            return
        self.cfg["profiles"].append({"name": name, "blocklist": [], "app_blocklist": []})
        save_config(self.cfg)
        self._refresh_profile_display()

    def edit_profile(self):
        sel = self.profile_listbox.curselection()
        if not sel:
            dark_showinfo(self.root, "Select", "Select a profile to edit.")
            return
        idx = sel[0]
        prof = self.cfg["profiles"][idx]
        name = self._ask_string("Edit Profile", "Profile name:", initialvalue=prof["name"])
        if not name or name == prof["name"]:
            return
        if any(p["name"] == name for p in self.cfg["profiles"] if p is not prof):
            dark_showwarning(self.root, "Duplicate", f"A profile named '{name}' already exists.")
            return
        old_name = prof["name"]
        prof["name"] = name
        for sched in self.cfg.get("schedules", []):
            if sched.get("profile") == old_name:
                sched["profile"] = name
        save_config(self.cfg)
        self._refresh_profile_display()
        self._refresh_schedules_display()
        if self.active_schedule_profile == old_name:
            self.active_schedule_profile = name
        if self.session_blocking or self.schedule_blocking:
            self._update_blocking_state()

    def duplicate_profile(self):
        sel = self.profile_listbox.curselection()
        if not sel:
            dark_showinfo(self.root, "Select", "Select a profile to duplicate.")
            return
        idx = sel[0]
        prof = self.cfg["profiles"][idx]
        new_prof = copy.deepcopy(prof)
        new_prof["name"] = f"{prof['name']} (copy)"
        self.cfg["profiles"].append(new_prof)
        save_config(self.cfg)
        self._refresh_profile_display()

    def delete_profile(self):
        if len(self.cfg["profiles"]) <= 1:
            dark_showwarning(self.root, "Cannot delete", "You must have at least one profile.")
            return
        sel = self.profile_listbox.curselection()
        if not sel:
            dark_showinfo(self.root, "Select", "Select a profile to delete.")
            return
        idx = sel[0]
        name = self.cfg["profiles"][idx]["name"]
        if not dark_askyesno(self.root, "Delete", f"Delete profile '{name}'?\nThis cannot be undone."):
            return
        del self.cfg["profiles"][idx]
        if self.cfg["active_profile"] >= len(self.cfg["profiles"]):
            self.cfg["active_profile"] = 0
        self.cfg["schedules"] = [s for s in self.cfg.get("schedules", []) if s.get("profile") != name]
        save_config(self.cfg)
        self._refresh_profile_display()
        self._refresh_blocklist_display()
        self._refresh_app_blocklist_display()
        self._refresh_schedules_display()
        self.scheduler.trigger_check_now()

    def set_active_profile(self):
        sel = self.profile_listbox.curselection()
        if not sel:
            dark_showinfo(self.root, "Select", "Select a profile to set as active.")
            return
        self.cfg["active_profile"] = sel[0]
        save_config(self.cfg)
        self._refresh_profile_display()
        self._refresh_blocklist_display()
        self._refresh_app_blocklist_display()
        if self.session_blocking:
            self._update_blocking_state()

    def _ask_string(self, title, prompt, initialvalue=""):
        win = make_dark_toplevel(self.root, title, 380, 160)
        content = ttk.Frame(win)
        content.pack(fill="both", expand=True, padx=24, pady=20)
        ttk.Label(content, text=prompt).pack(pady=(0, 8))
        var = tk.StringVar(value=initialvalue)
        entry = ttk.Entry(content, textvariable=var, width=30)
        entry.pack(pady=4)
        entry.focus_set()
        result = [None]
        def _ok():
            result[0] = var.get().strip()
            win.destroy()
        def _cancel():
            win.destroy()
        entry.bind("<Return>", lambda e: _ok())
        entry.bind("<Escape>", lambda e: _cancel())
        btn_frame = ttk.Frame(content)
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="OK", style="Accent.TButton", command=_ok).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side="left", padx=8)
        self.root.wait_window(win)
        return result[0]

    # ---- Timer logic ----

    def start_timer(self):
        if self.timer_running:
            return
        self.timer_running = True
        self.is_paused = False
        if self.pause_start:
            self.paused_duration += (datetime.now() - self.pause_start).total_seconds()
            self.pause_start = None
        elif self.session_start is None:
            self.session_start = datetime.now()
        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal")
        self.btn_stop.config(state="normal")
        if self.current_mode == "work":
            self.session_blocking = True
            self._update_blocking_state()
        if self.current_mode in ("short_break", "long_break"):
            self.btn_skip.config(state="normal")
        else:
            self.btn_skip.config(state="disabled")
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()

    def _timer_loop(self):
        while self.timer_running and self.remaining_sec > 0:
            time.sleep(1)
            if not self.timer_running:
                break
            self.remaining_sec -= 1
            self.root.after(0, self._update_timer_display)
            if self.current_mode == "work":
                self.eye_rest_after -= 1
                if self.eye_rest_after <= 0:
                    self.eye_rest_after = self.cfg["eye_rest_interval_min"] * 60
                    self.root.after(0, self._eye_rest_reminder)
        if self.remaining_sec <= 0 and self.timer_running:
            self.root.after(0, self._session_complete)

    def pause_timer(self):
        if not self.timer_running:
            return
        self.timer_running = False
        self.is_paused = True
        self.pause_start = datetime.now()
        self.btn_start.config(state="normal", text="▶  Resume")
        self.btn_pause.config(state="disabled")
        self._update_next_hint()

    def stop_timer(self):
        if self.cfg["strict_mode"] and self.current_mode == "work":
            if not dark_askyesno(self.root, "Strict Mode", "Strict mode is ON. Stop this focus session early?"):
                return
        was_running = self.timer_running
        self.timer_running = False
        self.is_paused = False
        self.btn_start.config(state="normal", text="▶  Start")
        self.btn_pause.config(state="disabled")
        self.btn_stop.config(state="disabled")
        self.btn_skip.config(state="disabled")
        if was_running and self.session_start:
            elapsed = int((datetime.now() - self.session_start).total_seconds() - self.paused_duration)
            if elapsed >= 5:
                self.tracker.log_session(self.session_start, datetime.now(), elapsed, self.current_mode, completed=0)
        self.session_blocking = False
        self._update_blocking_state()
        self._reset_timer_state()

    def _reset_timer_state(self):
        self.current_mode = "work"
        self.remaining_sec = self.cfg["work_duration_min"] * 60
        self.session_start = None
        self.paused_duration = 0
        self.pause_start = None
        self.is_paused = False
        self.eye_rest_after = self.cfg["eye_rest_interval_min"] * 60
        self.mode_label.config(text="🔵  Work Time", foreground=C_PRIMARY)
        self._update_timer_display()
        self._update_next_hint()

    def skip_break(self):
        if self.current_mode not in ("short_break", "long_break"):
            return
        self.timer_running = False
        self.btn_start.config(state="normal", text="▶  Start")
        self.btn_pause.config(state="disabled")
        self.btn_stop.config(state="disabled")
        self.btn_skip.config(state="disabled")
        if self.session_start:
            elapsed = int((datetime.now() - self.session_start).total_seconds() - self.paused_duration)
            if elapsed >= 5:
                self.tracker.log_session(self.session_start, datetime.now(), elapsed, self.current_mode, completed=0)
        self._reset_timer_state()
        self.refresh_stats()

    def _session_complete(self):
        self.timer_running = False
        end_dt = datetime.now()
        if self.session_start:
            actual_duration = int((end_dt - self.session_start).total_seconds() - self.paused_duration)
        else:
            mode_key = {"work": "work_duration_min", "short_break": "short_break_min", "long_break": "long_break_min"}.get(self.current_mode, "work_duration_min")
            actual_duration = self.cfg[mode_key] * 60
        if self.cfg.get("sound_enabled", True):
            play_bell()
        if self.current_mode == "work":
            self.tracker.log_session(self.session_start, end_dt, actual_duration, "work", completed=1)
            self.session_count += 1
            self.session_counter_label.config(text=f"✅  Completed today: {self.session_count}")
            self.session_blocking = False
            self._update_blocking_state()
            dark_showinfo(self.root, "Session Complete!", "🎉  Great job! Time for a break.\n\nStand up, stretch, and step away.")
            sbl = max(1, self.cfg["sessions_before_long_break"])
            if self.session_count % sbl == 0:
                self.current_mode = "long_break"
                self.remaining_sec = self.cfg["long_break_min"] * 60
                self.mode_label.config(text="🟢  Long Break", foreground=C_SUCCESS)
            else:
                self.current_mode = "short_break"
                self.remaining_sec = self.cfg["short_break_min"] * 60
                self.mode_label.config(text="🟡  Short Break", foreground=C_WARNING)
        else:
            self.tracker.log_session(self.session_start, end_dt, actual_duration, self.current_mode, completed=1)
            dark_showinfo(self.root, "Break Over", "⚡  Break's over! Ready to focus again?")
            self.current_mode = "work"
            self.remaining_sec = self.cfg["work_duration_min"] * 60
            self.mode_label.config(text="🔵  Work Time", foreground=C_PRIMARY)
        self.session_start = None
        self.paused_duration = 0
        self.pause_start = None
        self.is_paused = False
        self.btn_start.config(state="normal", text="▶  Start")
        self.btn_pause.config(state="disabled")
        self.btn_stop.config(state="disabled")
        self.btn_skip.config(state="disabled")
        self._update_timer_display()
        self._update_next_hint()
        self.refresh_stats()

    def _update_timer_display(self):
        self._draw_timer_ring()
        mode_icon = "🔵" if self.current_mode == "work" else "🟢"
        if self.timer_running:
            m, s = divmod(max(0, self.remaining_sec), 60)
            self.root.title(f"{mode_icon} {m:02d}:{s:02d} — {APP_NAME}")
        else:
            self.root.title(f"{APP_NAME} {APP_VERSION}")

    def _update_next_hint(self):
        if self.is_paused:
            self.next_hint_label.config(text="⏸  Paused — press ▶ Resume to continue")
        elif self.timer_running:
            if self.current_mode == "work":
                sbl = max(1, self.cfg["sessions_before_long_break"])
                remaining = sbl - (self.session_count % sbl)
                if remaining == 0:
                    remaining = sbl
                if remaining == 1:
                    self.next_hint_label.config(text="Next: Long Break")
                else:
                    self.next_hint_label.config(text=f"Next: Short Break  •  {remaining} until long break")
            else:
                self.next_hint_label.config(text="Next: Focus Session")
        else:
            self.next_hint_label.config(text="Press ▶ Start to begin a focus session")

    def _eye_rest_reminder(self):
        dark_showinfo(self.root, "👁  Eye Rest Reminder",
            "Look at something 20 feet away for 20 seconds.\n\nFollow the 20-20-20 rule:\nEvery 20 min, look 20 feet away for 20 sec.")

    # ---- App blocking ----

    def _activate_app_blocking(self, apps=None):
        if apps is None:
            apps = self._get_blocking_apps()
        if self.app_blocker and self.app_blocking_active:
            return
        if not apps:
            return
        self.app_blocker = AppBlocker(apps, on_kill=self._on_app_killed,
                                     check_interval=self.cfg.get("app_check_interval_sec", 3))
        self.app_blocker.start()
        self.app_blocking_active = True

    def _deactivate_app_blocking(self):
        if self.app_blocker:
            killed = self.app_blocker._killed_count
            killed_names = list(self.app_blocker._killed_names)
            self.app_blocker.stop()
            self.app_blocker = None
            if killed > 0:
                names_str = ", ".join(sorted(set(killed_names))[:5])
                self.kill_log_label.config(text=f"⛔  Killed {killed} process(es): {names_str}", foreground=C_DANGER)
        self.app_blocking_active = False

    def _on_app_killed(self, app_name):
        self.root.after(0, lambda: self.kill_log_label.config(text=f"⛔  Killed: {app_name}", foreground=C_DANGER))

    def manual_block(self):
        self.session_blocking = True
        self._update_blocking_state()

    def manual_unblock(self):
        self.session_blocking = False
        self._update_blocking_state()

    def _on_schedule_changed(self, sched_name, sched):
        if sched:
            self.schedule_blocking = True
            self.active_schedule_profile = sched.get("profile", "")
        else:
            self.schedule_blocking = False
            self.active_schedule_profile = None
        self._update_schedule_status()
        self._update_blocking_state()

    # ---- Website blocklist management ----

    def _refresh_blocklist_display(self):
        self.blocklist_box.delete(0, tk.END)
        prof = self._get_active_profile()
        for site in sorted(prof.get("blocklist", [])):
            self.blocklist_box.insert(tk.END, site)

    @staticmethod
    def _normalise_site(site):
        site = site.strip().lower()
        if site.startswith("http://"):
            site = site[7:]
        elif site.startswith("https://"):
            site = site[8:]
        site = site.split("/")[0]
        if not site or "." not in site:
            return ""
        return site

    def add_site(self):
        site = self._normalise_site(self.add_entry.get().strip().lower())
        if not site:
            dark_showwarning(self.root, "Invalid", "Enter a valid domain (e.g. youtube.com)")
            return
        prof = self._get_active_profile()
        if site in prof.get("blocklist", []):
            dark_showinfo(self.root, "Already blocked", f"{site} is already in this profile.")
            return
        prof.setdefault("blocklist", []).append(site)
        save_config(self.cfg)
        self._refresh_blocklist_display()
        self._refresh_profile_display()
        self.add_entry.delete(0, tk.END)
        if self.session_blocking or self.schedule_blocking:
            self._update_blocking_state()

    def remove_sites(self):
        selection = self.blocklist_box.curselection()
        if not selection:
            return
        prof = self._get_active_profile()
        for idx in reversed(selection):
            site = self.blocklist_box.get(idx)
            if site in prof.get("blocklist", []):
                prof["blocklist"].remove(site)
        save_config(self.cfg)
        self._refresh_blocklist_display()
        self._refresh_profile_display()
        if self.session_blocking or self.schedule_blocking:
            self._update_blocking_state()

    def _refresh_app_blocklist_display(self):
        self.app_blocklist_box.delete(0, tk.END)
        prof = self._get_active_profile()
        for app in sorted(prof.get("app_blocklist", [])):
            self.app_blocklist_box.insert(tk.END, app)

    def add_app(self):
        app = self.app_add_entry.get().strip().lower()
        if not app:
            dark_showwarning(self.root, "Invalid", "Enter an app name (e.g. discord.exe)")
            return
        if platform.system() == "Windows" and not app.endswith(".exe"):
            app = app + ".exe"
        prof = self._get_active_profile()
        if app in prof.get("app_blocklist", []):
            dark_showinfo(self.root, "Already blocked", f"{app} is already in this profile.")
            return
        prof.setdefault("app_blocklist", []).append(app)
        save_config(self.cfg)
        self._refresh_app_blocklist_display()
        self._refresh_profile_display()
        self.app_add_entry.delete(0, tk.END)
        if self.session_blocking or self.schedule_blocking:
            self._update_blocking_state()

    def remove_apps(self):
        selection = self.app_blocklist_box.curselection()
        if not selection:
            return
        prof = self._get_active_profile()
        for idx in reversed(selection):
            app = self.app_blocklist_box.get(idx)
            if app in prof.get("app_blocklist", []):
                prof["app_blocklist"].remove(app)
        save_config(self.cfg)
        self._refresh_app_blocklist_display()
        self._refresh_profile_display()
        if self.session_blocking or self.schedule_blocking:
            self._update_blocking_state()

    def pick_running_process(self):
        def _do_pick():
            procs = AppBlocker.list_running_processes()
            self.root.after(0, lambda: self._show_process_picker(procs))
        threading.Thread(target=_do_pick, daemon=True).start()

    def _show_process_picker(self, procs):
        if not procs:
            dark_showinfo(self.root, "No processes", "Could not list running processes.")
            return
        win = make_dark_toplevel(self.root, "Pick a Process", 500, 580)
        win.resizable(True, True)
        enable_dark_titlebar(win)
        content = ttk.Frame(win)
        content.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(content, text="Search and select a process to block:").pack(pady=(0, 6))
        search_frame = ttk.Frame(content)
        search_frame.pack(fill="x", pady=4)
        ttk.Label(search_frame, text="🔍").grid(row=0, column=0, padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.grid(row=0, column=1, sticky="ew")
        search_frame.columnconfigure(1, weight=1)
        list_frame = ttk.Frame(content)
        list_frame.pack(fill="both", expand=True, pady=6)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        proc_box = make_dark_listbox(list_frame, font=("Cascadia Code", 10), selectmode="single")
        proc_box.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=proc_box.yview)
        sb.grid(row=0, column=1, sticky="ns")
        proc_box.config(yscrollcommand=sb.set)
        all_procs = procs
        def _filter(*args):
            query = search_var.get().lower().strip()
            proc_box.delete(0, tk.END)
            for name, pid in all_procs:
                if not query or query in name.lower():
                    proc_box.insert(tk.END, f"{name}  (PID {pid})")
        search_var.trace_add("write", _filter)
        _filter()
        def _add_selected():
            sel = proc_box.curselection()
            if not sel:
                return
            text = proc_box.get(sel[0])
            app_name = text.split("  (PID")[0].strip().lower()
            if platform.system() == "Windows" and not app_name.endswith(".exe"):
                app_name = app_name + ".exe"
            prof = self._get_active_profile()
            if app_name not in prof.get("app_blocklist", []):
                prof.setdefault("app_blocklist", []).append(app_name)
                save_config(self.cfg)
                self._refresh_app_blocklist_display()
                self._refresh_profile_display()
                if self.session_blocking or self.schedule_blocking:
                    self._update_blocking_state()
            win.destroy()
        proc_box.bind("<Double-Button-1>", lambda e: _add_selected())
        search_entry.bind("<Return>", lambda e: _add_selected())
        btn_frame = ttk.Frame(content)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Add", style="Accent.TButton", command=_add_selected).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="left", padx=8)
        search_entry.focus_set()

    # ---- Schedule management ----

    def _refresh_schedules_display(self):
        for item in self.sched_tree.get_children():
            self.sched_tree.delete(item)
        schedules = self.cfg.get("schedules", [])
        for i, sched in enumerate(schedules):
            days_str = ScheduleEngine.format_days(sched.get("days", []))
            time_str = f"{sched.get('start_time', '09:00')} - {sched.get('end_time', '17:00')}"
            enabled_str = "✅" if sched.get("enabled", True) else "❌"
            self.sched_tree.insert("", tk.END, iid=str(i),
                values=(sched["name"], sched.get("profile", ""), days_str, time_str, enabled_str))
        if not schedules:
            self.sched_empty_label.config(text="No schedules configured. Click '➕ Add' to create one.")
            self.sched_empty_label.pack(anchor="w", padx=32, pady=5)
        else:
            self.sched_empty_label.pack_forget()

    def add_schedule(self):
        self._edit_schedule_dialog(None)

    def edit_schedule(self):
        sel = self.sched_tree.selection()
        if not sel:
            dark_showinfo(self.root, "Select", "Select a schedule to edit.")
            return
        self._edit_schedule_dialog(int(sel[0]))

    @staticmethod
    def _validate_time(time_str):
        try:
            parts = time_str.strip().split(":")
            if len(parts) != 2:
                return False
            h, m = int(parts[0]), int(parts[1])
            return 0 <= h <= 23 and 0 <= m <= 59
        except Exception:
            return False

    def _edit_schedule_dialog(self, idx):
        is_edit = idx is not None
        sched = self.cfg["schedules"][idx] if is_edit else {"name": "", "profile": "", "start_time": "09:00", "end_time": "17:00", "days": [0, 1, 2, 3, 4], "enabled": True}
        win = make_dark_toplevel(self.root, "Edit Schedule" if is_edit else "New Schedule", 480, 620)
        win.resizable(True, True)
        content = ttk.Frame(win)
        content.pack(fill="both", expand=True, padx=24, pady=20)
        form_frame = ttk.Frame(content)
        form_frame.pack(fill="both", expand=True)
        ttk.Label(form_frame, text="Schedule Name:").grid(row=0, column=0, sticky="w", pady=6)
        name_var = tk.StringVar(value=sched["name"])
        ttk.Entry(form_frame, textvariable=name_var, width=25).grid(row=0, column=1, padx=8, pady=6)
        ttk.Label(form_frame, text="Profile:").grid(row=1, column=0, sticky="w", pady=6)
        profile_names = [p["name"] for p in self.cfg.get("profiles", [])]
        prof_var = tk.StringVar(value=sched.get("profile", profile_names[0] if profile_names else ""))
        ttk.Combobox(form_frame, textvariable=prof_var, values=profile_names, state="readonly", width=22).grid(row=1, column=1, padx=8, pady=6)
        ttk.Label(form_frame, text="Start Time:").grid(row=2, column=0, sticky="w", pady=6)
        start_var = tk.StringVar(value=sched.get("start_time", "09:00"))
        ttk.Entry(form_frame, textvariable=start_var, width=10).grid(row=2, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(form_frame, text="(HH:MM)", style="Dim.TLabel").grid(row=2, column=2, sticky="w")
        ttk.Label(form_frame, text="End Time:").grid(row=3, column=0, sticky="w", pady=6)
        end_var = tk.StringVar(value=sched.get("end_time", "17:00"))
        ttk.Entry(form_frame, textvariable=end_var, width=10).grid(row=3, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(form_frame, text="(HH:MM)", style="Dim.TLabel").grid(row=3, column=2, sticky="w")
        ttk.Label(form_frame, text="Days:").grid(row=4, column=0, sticky="nw", pady=6)
        day_vars = []
        day_frame = ttk.Frame(form_frame)
        day_frame.grid(row=4, column=1, padx=8, pady=6, sticky="w")
        for i, day_name in enumerate(DAYS_OF_WEEK):
            v = tk.BooleanVar(value=i in sched.get("days", []))
            df = ttk.Frame(day_frame)
            df.grid(row=i // 4, column=i % 4, sticky="w", padx=2, pady=2)
            Win11Toggle(df, variable=v, width=36, height=18).pack(side="left", padx=(0, 4))
            ttk.Label(df, text=day_name, style="Small.TLabel").pack(side="left")
            day_vars.append(v)
        quick_frame = ttk.Frame(form_frame)
        quick_frame.grid(row=5, column=1, padx=8, pady=4, sticky="w")
        def _set_weekdays():
            for i in range(5): day_vars[i].set(True)
            for i in range(5, 7): day_vars[i].set(False)
        def _set_weekends():
            for i in range(5): day_vars[i].set(False)
            for i in range(5, 7): day_vars[i].set(True)
        def _set_everyday():
            for v in day_vars: v.set(True)
        ttk.Button(quick_frame, text="Weekdays", command=_set_weekdays).grid(row=0, column=0, padx=2)
        ttk.Button(quick_frame, text="Weekends", command=_set_weekends).grid(row=0, column=1, padx=2)
        ttk.Button(quick_frame, text="Every day", command=_set_everyday).grid(row=0, column=2, padx=2)
        enabled_var = tk.BooleanVar(value=sched.get("enabled", True))
        enabled_frame = ttk.Frame(form_frame)
        enabled_frame.grid(row=6, column=0, columnspan=2, sticky="w", pady=10)
        Win11Toggle(enabled_frame, variable=enabled_var).pack(side="left", padx=(0, 8))
        ttk.Label(enabled_frame, text="Enabled").pack(side="left")
        def _save():
            name = name_var.get().strip()
            if not name:
                dark_showwarning(win, "Invalid", "Enter a schedule name.")
                return
            if not self._validate_time(start_var.get().strip()):
                dark_showwarning(win, "Invalid", "Start time must be HH:MM.")
                return
            if not self._validate_time(end_var.get().strip()):
                dark_showwarning(win, "Invalid", "End time must be HH:MM.")
                return
            days = [i for i, v in enumerate(day_vars) if v.get()]
            if not days:
                dark_showwarning(win, "Invalid", "Select at least one day.")
                return
            if not prof_var.get():
                dark_showwarning(win, "Invalid", "Select a profile.")
                return
            sched["name"] = name
            sched["profile"] = prof_var.get()
            sched["start_time"] = start_var.get().strip()
            sched["end_time"] = end_var.get().strip()
            sched["days"] = days
            sched["enabled"] = enabled_var.get()
            if not is_edit:
                self.cfg["schedules"].append(sched)
            save_config(self.cfg)
            self._refresh_schedules_display()
            self.scheduler.trigger_check_now()
            win.destroy()
        btn_frame = ttk.Frame(content)
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="Save", style="Accent.TButton", command=_save).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="left", padx=10)

    def delete_schedule(self):
        sel = self.sched_tree.selection()
        if not sel:
            dark_showinfo(self.root, "Select", "Select a schedule to delete.")
            return
        idx = int(sel[0])
        name = self.cfg["schedules"][idx]["name"]
        if dark_askyesno(self.root, "Delete", f"Delete schedule '{name}'?"):
            del self.cfg["schedules"][idx]
            save_config(self.cfg)
            self._refresh_schedules_display()
            self.scheduler.trigger_check_now()

    def toggle_schedule(self):
        sel = self.sched_tree.selection()
        if not sel:
            dark_showinfo(self.root, "Select", "Select a schedule to toggle.")
            return
        idx = int(sel[0])
        self.cfg["schedules"][idx]["enabled"] = not self.cfg["schedules"][idx].get("enabled", True)
        save_config(self.cfg)
        self._refresh_schedules_display()
        self.scheduler.trigger_check_now()

    # ---- Stats ----

    def refresh_stats(self):
        today = self.tracker.get_today_stats()
        total = self.tracker.get_total_stats()
        last7 = self.tracker.get_last_n_days(7)
        work_today = today.get("work", {}).get("seconds", 0)
        breaks_today = today.get("short_break", {}).get("seconds", 0) + today.get("long_break", {}).get("seconds", 0)
        work_sessions_today = today.get("work", {}).get("count", 0)
        self._stat_tile_focus._val_label.config(text=self._fmt_dur(work_today))
        self._stat_tile_breaks._val_label.config(text=self._fmt_dur(breaks_today))
        self._stat_tile_sessions._val_label.config(text=str(work_sessions_today))
        self._stat_tile_total._val_label.config(text=self._fmt_dur(total['total_seconds']))
        self._stat_tile_total_sess._val_label.config(text=str(total['total_sessions']))
        self._draw_stats_chart(last7)

    @staticmethod
    def _fmt_dur(seconds):
        if not seconds:
            return "0m"
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m" if h else f"{m}m"

    # ---- Settings ----

    def save_settings(self):
        old_interval = self.cfg.get("app_check_interval_sec", 3)
        for key, var in self.settings_vars.items():
            try:
                val = var.get()
                if key in ("work_duration_min", "short_break_min", "long_break_min") and val < 1:
                    raise ValueError(f"{key} must be >= 1")
                if key == "sessions_before_long_break" and val < 1:
                    raise ValueError("sessions_before_long_break must be >= 1")
                if key == "app_check_interval_sec" and val < 1:
                    raise ValueError("app_check_interval_sec must be >= 1")
                if key == "server_port" and (val < 1 or val > 65535):
                    raise ValueError("server_port must be 1-65535")
                if key == "eye_rest_interval_min" and val < 1:
                    raise ValueError("eye_rest_interval_min must be >= 1")
                self.cfg[key] = val
            except tk.TclError:
                dark_showerror(self.root, "Invalid", f"Enter a valid number for {key}")
                return
            except ValueError as e:
                dark_showerror(self.root, "Invalid", str(e))
                return
        self.cfg["strict_mode"] = self.strict_var.get()
        self.cfg["sound_enabled"] = self.sound_var.get()
        save_config(self.cfg)
        if self.server.port != self.cfg["server_port"]:
            self.server.stop()
            self.server = MotivationalServer(self.cfg["server_port"])
            self.server.start()
        if not self.timer_running:
            self.remaining_sec = self.cfg["work_duration_min"] * 60
            self._update_timer_display()
            self._update_next_hint()
        new_interval = self.cfg.get("app_check_interval_sec", 3)
        if old_interval != new_interval and self.app_blocking_active:
            self._applied_apps = set()
            self._update_blocking_state()
        dark_showinfo(self.root, "Saved", "Settings saved successfully.")

    def view_log(self):
        win = make_dark_toplevel(self.root, "FocusGuardian Log", 720, 520)
        win.resizable(True, True)
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        text = make_dark_text(frame, wrap="word", font=("Cascadia Code", 10), padx=12, pady=12)
        sb = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.read().strip().split("\n")
                if len(lines) > 500:
                    lines = lines[-500:]
                text.insert("1.0", "\n".join(lines))
        except FileNotFoundError:
            text.insert("1.0", "No log file found.")
        text.config(state="disabled")

    def reset_all_data(self):
        if not dark_askyesno(self.root, "Reset All Data", "This deletes ALL settings, profiles, schedules, and history.\n\nSure?"):
            return
        if not dark_askyesno(self.root, "Confirm", "Last chance — this cannot be undone. Reset?"):
            return
        self.session_blocking = False
        self.schedule_blocking = False
        self.active_schedule_profile = None
        self._update_blocking_state()
        self.scheduler.stop()
        self.server.stop()
        self.tracker.close()
        try:
            for f in [CONFIG_FILE, DB_FILE, LOG_FILE, HTML_FILE]:
                if os.path.exists(f):
                    os.remove(f)
        except Exception as e:
            dark_showerror(self.root, "Error", f"Could not delete: {e}")
            return
        dark_showinfo(self.root, "Reset", "All data reset. App will restart.")
        self.root.destroy()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _on_close(self):
        if self.timer_running:
            if not dark_askyesno(self.root, "Quit", "A timer is running. Quit anyway?\n(Blocks removed, partial session saved.)"):
                return
        if self.timer_running and self.session_start:
            elapsed = int((datetime.now() - self.session_start).total_seconds() - self.paused_duration)
            if elapsed >= 5:
                self.tracker.log_session(self.session_start, datetime.now(), elapsed, self.current_mode, completed=0)
        self.timer_running = False
        self.session_blocking = False
        self.schedule_blocking = False
        self.active_schedule_profile = None
        self.scheduler.stop()
        if self.timer_thread and self.timer_thread.is_alive():
            self.timer_thread.join(timeout=3)
        self._update_blocking_state()
        self.server.stop()
        self.tracker.close()
        logger.info(f"=== {APP_NAME} shutdown ===")
        self.root.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def is_admin():
    try:
        if platform.system() == "Windows":
            import ctypes as _ctypes
            return _ctypes.windll.shell32.IsUserAnAdmin()
        else:
            return os.geteuid() == 0
    except Exception:
        return False


def main():
    # Crash handler — pythonw.exe has no console, so write errors to a file
    # AND show a Windows MessageBox so the user knows what happened
    try:
        setup_logging()
        root = tk.Tk()
        app = FocusGuardianApp(root)
        if not app._is_admin:
            root.after(500, lambda: dark_showwarning(root,
                "Limited mode",
                f"{APP_NAME} is running without administrator privileges.\n\n"
                "Timer, reminders, stats, profiles, and schedules work.\n"
                "Website blocking requires admin/root:\n"
                "  • Windows: right-click → Run as administrator\n"
                "  • macOS/Linux: sudo python3 focus_guardian.py"))
        root.mainloop()
    except Exception:
        import traceback
        tb = traceback.format_exc()
        # Write crash log to file
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(os.path.join(CONFIG_DIR, "crash.log"), "w", encoding="utf-8") as f:
                f.write(f"FocusGuardian v{APP_VERSION} crashed:\n\n{tb}")
        except Exception:
            pass
        # Show a visible error dialog (pythonw.exe has no console)
        try:
            if platform.system() == "Windows":
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"FocusGuardian v{APP_VERSION} crashed on startup.\n\n"
                    f"Error details written to:\n{os.path.join(CONFIG_DIR, 'crash.log')}\n\n"
                    f"{tb[:500]}",
                    "FocusGuardian — Startup Error",
                    0x10,  # MB_ICONERROR
                )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
