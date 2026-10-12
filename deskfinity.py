#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deskfinity - a lightweight desktop icon organizer for Windows.

Draws resizable, named boxes on the desktop wallpaper that hold groups of
shortcuts in a proportional grid.

Features
--------
* Draw a rectangle on the desktop to create a box (Tray -> New box, or Ctrl+Alt+F).
* Drag & drop files / folders / shortcuts from Explorer into a box.
* Each box keeps icons in a proportional auto-reflowing grid.
* Editable group title (double click on the header).
* Editable background colour, opacity, corner radius, icon size.
* Boxes stay pinned behind all other windows (desktop layer).
* Everything is persisted to %APPDATA%\\Deskfinity\\boxes.json

Requires: Python 3.9+, PyQt6   (pip install PyQt6)
"""

import os
import sys
import json
import uuid
import shutil
import ctypes
import time
import getpass
import logging
import threading
import subprocess
from ctypes import wintypes
from logging.handlers import RotatingFileHandler

from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets
from PyQt6.QtCore import Qt, QRect, QPoint, QSize

IS_WINDOWS = sys.platform.startswith("win")

APP_NAME = "Deskfinity"
CONFIG_DIR = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME
)
CONFIG_PATH = os.path.join(CONFIG_DIR, "boxes.json")
STORE_DIR = os.path.join(CONFIG_DIR, "storage")

LOG_PATH = os.path.join(CONFIG_DIR, "deskfinity.log")

log = logging.getLogger(APP_NAME)

HEADER_H = 26
EDGE = 7          # resize hit zone
MIN_W, MIN_H = 160, 110
BACKUPS = 3       # boxes.json.bak1 .. bak3, taken at startup


# --------------------------------------------------------------------------- #
#  Logging - pythonw has no console, so errors go to a file
# --------------------------------------------------------------------------- #
def setup_logging():
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        fh = RotatingFileHandler(
            LOG_PATH, maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        log.addHandler(fh)
    except Exception:
        pass
    if sys.stderr is not None:  # running under python.exe
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        log.addHandler(sh)

    # Without a custom hook PyQt6 aborts the process on any exception raised
    # inside a slot; log it and keep running instead.
    def _excepthook(etype, value, tb):
        log.error("Unhandled exception", exc_info=(etype, value, tb))

    sys.excepthook = _excepthook


# --------------------------------------------------------------------------- #
#  Windows shell icon extraction (jumbo icons + HICON -> QImage)
# --------------------------------------------------------------------------- #
if IS_WINDOWS:
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    IID_IImageList = GUID(
        0x46EB5926, 0x582E, 0x4017,
        (ctypes.c_ubyte * 8)(0x9F, 0xDF, 0xE8, 0x99, 0x8D, 0xAA, 0x09, 0x50),
    )

    class SHFILEINFOW(ctypes.Structure):
        _fields_ = [
            ("hIcon", ctypes.c_void_p),
            ("iIcon", ctypes.c_int),
            ("dwAttributes", wintypes.DWORD),
            ("szDisplayName", ctypes.c_wchar * 260),
            ("szTypeName", ctypes.c_wchar * 80),
        ]

    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", wintypes.BOOL),
            ("xHotspot", wintypes.DWORD),
            ("yHotspot", wintypes.DWORD),
            ("hbmMask", ctypes.c_void_p),
            ("hbmColor", ctypes.c_void_p),
        ]

    class BITMAP(ctypes.Structure):
        _fields_ = [
            ("bmType", ctypes.c_long),
            ("bmWidth", ctypes.c_long),
            ("bmHeight", ctypes.c_long),
            ("bmWidthBytes", ctypes.c_long),
            ("bmPlanes", ctypes.c_ushort),
            ("bmBitsPixel", ctypes.c_ushort),
            ("bmBits", ctypes.c_void_p),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long),
            ("biPlanes", ctypes.c_ushort),
            ("biBitCount", ctypes.c_ushort),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    SHGFI_SYSICONINDEX = 0x00004000
    SHGFI_USEFILEATTRIBUTES = 0x00000010
    FILE_ATTRIBUTE_NORMAL = 0x80
    FILE_ATTRIBUTE_DIRECTORY = 0x10
    ILD_TRANSPARENT = 0x00000001
    DIB_RGB_COLORS = 0
    BI_RGB = 0

    # SHIL_LARGE=0 SHIL_SMALL=1 SHIL_EXTRALARGE=2 SHIL_SYSSMALL=3 SHIL_JUMBO=4
    SHIL_EXTRALARGE = 2
    SHIL_JUMBO = 4

    def _hicon_to_qimage(hicon):
        """Convert an HICON into a 32-bit ARGB QImage (alpha preserved)."""
        info = ICONINFO()
        if not user32.GetIconInfo(ctypes.c_void_p(hicon), ctypes.byref(info)):
            return None
        try:
            bm = BITMAP()
            if not gdi32.GetObjectW(
                ctypes.c_void_p(info.hbmColor), ctypes.sizeof(BITMAP), ctypes.byref(bm)
            ):
                return None
            w, h = int(bm.bmWidth), int(bm.bmHeight)
            if w <= 0 or h <= 0:
                return None

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = w
            bmi.bmiHeader.biHeight = -h          # top-down
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = BI_RGB

            buf = ctypes.create_string_buffer(w * h * 4)
            hdc = user32.GetDC(None)
            try:
                got = gdi32.GetDIBits(
                    hdc, ctypes.c_void_p(info.hbmColor), 0, h,
                    buf, ctypes.byref(bmi), DIB_RGB_COLORS,
                )
            finally:
                user32.ReleaseDC(None, hdc)
            if not got:
                return None

            raw = bytearray(buf.raw)
            # If the icon carries no alpha channel, rebuild it from the mask.
            if raw[3::4].count(0) == w * h:
                mbmi = BITMAPINFO()
                mbmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                mbmi.bmiHeader.biWidth = w
                mbmi.bmiHeader.biHeight = -h
                mbmi.bmiHeader.biPlanes = 1
                mbmi.bmiHeader.biBitCount = 32
                mbmi.bmiHeader.biCompression = BI_RGB
                mbuf = ctypes.create_string_buffer(w * h * 4)
                hdc = user32.GetDC(None)
                try:
                    gdi32.GetDIBits(
                        hdc, ctypes.c_void_p(info.hbmMask), 0, h,
                        mbuf, ctypes.byref(mbmi), DIB_RGB_COLORS,
                    )
                finally:
                    user32.ReleaseDC(None, hdc)
                raw[3::4] = _alpha_from_mask(mbuf.raw)

            img = QtGui.QImage(
                bytes(raw), w, h, QtGui.QImage.Format.Format_ARGB32
            ).copy()
            return img
        finally:
            if info.hbmColor:
                gdi32.DeleteObject(ctypes.c_void_p(info.hbmColor))
            if info.hbmMask:
                gdi32.DeleteObject(ctypes.c_void_p(info.hbmMask))

    def shell_icon(path, want=256):
        """Return a QPixmap of the shell icon for *path*, or None."""
        try:
            info = SHFILEINFOW()
            flags = SHGFI_SYSICONINDEX
            attrs = 0
            if not os.path.exists(path):
                flags |= SHGFI_USEFILEATTRIBUTES
                attrs = FILE_ATTRIBUTE_NORMAL
            res = shell32.SHGetFileInfoW(
                ctypes.c_wchar_p(path), attrs,
                ctypes.byref(info), ctypes.sizeof(info), flags,
            )
            if not res:
                return None
            idx = info.iIcon

            order = [SHIL_JUMBO, SHIL_EXTRALARGE] if want > 48 else [SHIL_EXTRALARGE]
            for shil in order:
                pil = ctypes.c_void_p()
                hr = shell32.SHGetImageList(
                    shil, ctypes.byref(IID_IImageList), ctypes.byref(pil)
                )
                if hr != 0 or not pil:
                    continue
                try:
                    vtbl = ctypes.cast(
                        pil, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
                    )[0]
                    GetIcon = ctypes.WINFUNCTYPE(
                        ctypes.c_long, ctypes.c_void_p, ctypes.c_int,
                        ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p),
                    )(vtbl[10])
                    hicon = ctypes.c_void_p()
                    if GetIcon(pil, idx, ILD_TRANSPARENT, ctypes.byref(hicon)) != 0:
                        continue
                    if not hicon:
                        continue
                    try:
                        img = _hicon_to_qimage(hicon.value)
                    finally:
                        user32.DestroyIcon(hicon)
                    if img is None or img.isNull():
                        continue
                    # jumbo slots are 256x256 but small icons sit in the corner
                    trimmed = img.copy(_content_rect(img))
                    return QtGui.QPixmap.fromImage(
                        trimmed if not trimmed.isNull() else img
                    )
                finally:
                    Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
                        ctypes.cast(
                            pil, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
                        )[0][2]
                    )
                    Release(pil)
        except Exception:
            pass
        return None

else:  # non-Windows fallback so the file at least imports elsewhere
    def shell_icon(path, want=256):
        return None


# Per-pixel work goes through bytes.translate()/find(), which run in C -
# a Python loop over a 256x256 jumbo icon costs tens of milliseconds.
_VISIBLE = bytes(0 if a <= 8 else 1 for a in range(256))
_MASK_TO_ALPHA = bytes([255] + [0] * 255)   # AND mask: 0 = opaque


def _alpha_from_mask(mask_bgra):
    """Alpha bytes rebuilt from a 32-bit icon AND mask (white = clear)."""
    return mask_bgra[0::4].translate(_MASK_TO_ALPHA)


def _content_rect(img):
    """Bounding box of non-transparent pixels (jumbo icons are padded)."""
    w, h = img.width(), img.height()
    try:
        ptr = img.constBits()
        ptr.setsize(img.sizeInBytes())
        data = bytes(ptr)
        bpl = img.bytesPerLine()
    except Exception:
        return QRect(0, 0, w, h)

    left, top, right, bottom = w, -1, -1, -1
    for y in range(h):
        base = y * bpl
        row = data[base + 3:base + w * 4:4].translate(_VISIBLE)
        first = row.find(1)
        if first < 0:
            continue
        if top < 0:
            top = y
        bottom = y
        left = min(left, first)
        right = max(right, row.rfind(1))
    if right < 0:
        return QRect(0, 0, w, h)
    left = max(0, left - 1)
    top = max(0, top - 1)
    right = min(w - 1, right + 1)
    bottom = min(h - 1, bottom + 1)
    return QRect(left, top, right - left + 1, bottom - top + 1)


# --------------------------------------------------------------------------- #
#  File relocation helpers
# --------------------------------------------------------------------------- #
def _shell_folder(csidl):
    """Filesystem path of a CSIDL shell folder, or None."""
    if IS_WINDOWS:
        try:
            buf = ctypes.create_unicode_buffer(260)
            # SHGFP_TYPE_CURRENT = 0
            if shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0:
                return buf.value
        except Exception:
            pass
    return None


def desktop_dir():
    """Real filesystem path of the user's Desktop (locale-independent)."""
    # CSIDL_DESKTOPDIRECTORY = 0x0010
    return _shell_folder(0x0010) or os.path.join(os.path.expanduser("~"), "Desktop")


def desktop_dirs():
    """The user's and the shared (Public) Desktop folders, normalised."""
    # CSIDL_COMMON_DESKTOPDIRECTORY = 0x0019
    dirs = [desktop_dir(), _shell_folder(0x0019)]
    return {os.path.normcase(os.path.abspath(d)) for d in dirs if d}


def on_desktop(path):
    """True if *path* sits directly on one of the Desktop folders."""
    try:
        parent = os.path.dirname(os.path.abspath(path))
        return os.path.normcase(parent) in desktop_dirs()
    except Exception:
        return False


def unique_target(folder, name):
    """A non-colliding path inside *folder* for a file called *name*."""
    target = os.path.join(folder, name)
    if not os.path.exists(target):
        return target
    stem, ext = os.path.splitext(name)
    n = 2
    while True:
        target = os.path.join(folder, f"{stem} ({n}){ext}")
        if not os.path.exists(target):
            return target
        n += 1


def _ps_literal(text):
    """*text* as a PowerShell single-quoted string literal."""
    return "'" + text.replace("'", "''") + "'"


def _elevation_command(script):
    """PowerShell command that runs *script* elevated and waits for it."""
    return (
        "Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden "
        "-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass',"
        "'-File',%s" % _ps_literal('"%s"' % script)
    )


def elevated_move(pairs, parent=None):
    """Move (src, dst) pairs with an admin prompt. Returns pairs that landed."""
    if not IS_WINDOWS or not pairs:
        return []
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        script = os.path.join(CONFIG_DIR, "_elevated_move.ps1")
        lines = ["$ErrorActionPreference = 'Continue'"]
        for src, dst in pairs:
            lines.append(
                "try { Move-Item -LiteralPath %s -Destination %s -Force } "
                "catch { }" % (_ps_literal(src), _ps_literal(dst))
            )
        with open(script, "w", encoding="utf-8-sig") as fh:
            fh.write("\n".join(lines))

        subprocess.run(
            ["powershell", "-NoProfile", "-Command", _elevation_command(script)],
            creationflags=0x08000000, timeout=180,
        )
    except Exception:
        log.exception("Elevated move failed")
        return []
    landed = [(s, d) for s, d in pairs if os.path.exists(d)]
    for s, d in landed:
        log.info("Moved (elevated) %s -> %s", s, d)
    return landed


# --------------------------------------------------------------------------- #
#  Icon cache
# --------------------------------------------------------------------------- #
class IconCache:
    def __init__(self):
        self._cache = {}
        self._provider = QtWidgets.QFileIconProvider()

    def get(self, path, size, dpr=1.0):
        """Icon of *size* logical px, rendered for a screen scale of *dpr*."""
        key = (path.lower(), size, dpr)
        pm = self._cache.get(key)
        if pm is not None:
            return pm

        px = max(1, round(size * dpr))  # physical pixels - sharp at 125/150 %
        src = shell_icon(path, want=px)
        if src is None or src.isNull():
            info = QtCore.QFileInfo(path)
            icon = self._provider.icon(info)
            if icon.isNull():
                icon = self._provider.icon(QtWidgets.QFileIconProvider.IconType.File)
            src = icon.pixmap(QSize(px, px))

        if src.isNull():
            src = QtGui.QPixmap(px, px)
            src.fill(QtGui.QColor(120, 120, 120, 160))

        pm = src.scaled(
            px, px,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        pm.setDevicePixelRatio(dpr)
        self._cache[key] = pm
        return pm

    def clear(self):
        self._cache.clear()


ICONS = None  # created after QApplication exists

# path -> (exists, is_dir). Filled by Manager on a worker thread: on an
# offline network path os.path.exists() can block for seconds, so it must
# never run inside paintEvent.
STATUS = {}
STATUS_INTERVAL_MS = 4000


# --------------------------------------------------------------------------- #
#  Screens
# --------------------------------------------------------------------------- #
def screen_areas():
    """Available desktop areas of all monitors, the primary one first."""
    primary = QtGui.QGuiApplication.primaryScreen()
    screens = sorted(
        QtGui.QGuiApplication.screens(), key=lambda s: s is not primary
    )
    return [s.availableGeometry() for s in screens]


def header_visible(rect, areas):
    """True if enough of the header strip of *rect* is on some screen."""
    header = QRect(rect.x(), rect.y(), rect.width(), HEADER_H)
    for a in areas:
        r = header.intersected(a)
        if r.width() >= 40 and r.height() >= HEADER_H // 2:
            return True
    return False


# --------------------------------------------------------------------------- #
#  A single box window
# --------------------------------------------------------------------------- #
class Box(QtWidgets.QWidget):

    def __init__(self, manager, data=None):
        super().__init__(None)
        self.manager = manager

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnBottomHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

        d = data or {}
        self.uid = d.get("uid") or uuid.uuid4().hex[:12]
        self.title = d.get("title", "Новая группа")
        self.move_files = bool(d.get("move_files", True))
        self.items = list(d.get("items", []))
        c = d.get("color", [24, 26, 32])
        self.bg_color = QtGui.QColor(c[0], c[1], c[2])
        self.bg_alpha = int(d.get("alpha", 140))
        self.icon_size = int(d.get("icon_size", 48))
        self.radius = int(d.get("radius", 10))
        self.label_color = QtGui.QColor(*d.get("label_color", [235, 235, 240]))
        self.collapsed = bool(d.get("collapsed", False))
        self.locked = bool(d.get("locked", False))

        g = d.get("geometry", [200, 200, 320, 260])
        self._expanded_h = g[3]
        self.setGeometry(g[0], g[1], max(MIN_W, g[2]), max(MIN_H, g[3]))
        if self.collapsed:
            self.resize(self.width(), HEADER_H)

        # interaction state
        self._mode = None            # 'move' | 'resize' | None
        self._resize_dir = ""
        self._press_pos = QPoint()
        self._press_geo = QRect()
        self._hover_index = -1
        self._drag_index = -1
        self._drag_pos = QPoint()
        self._dragging_item = False
        self._scroll = 0
        self._drop_hint = False
        self._home = None            # real spot while parked on a visible screen

        self._rects = []
        self._cols = 1
        self._content_h = 0

    # ---------------------------------------------------------------- data
    def to_dict(self):
        g = self.geometry()
        h = self._expanded_h if self.collapsed else g.height()
        pos = self._home or g.topLeft()
        return {
            "uid": self.uid,
            "title": self.title,
            "move_files": self.move_files,
            "items": self.items,
            "geometry": [pos.x(), pos.y(), g.width(), h],
            "color": [self.bg_color.red(), self.bg_color.green(), self.bg_color.blue()],
            "alpha": self.bg_alpha,
            "icon_size": self.icon_size,
            "radius": self.radius,
            "label_color": [
                self.label_color.red(),
                self.label_color.green(),
                self.label_color.blue(),
            ],
            "collapsed": self.collapsed,
            "locked": self.locked,
        }

    # ------------------------------------------------------- file relocation
    def store_dir(self):
        d = os.path.join(STORE_DIR, self.uid)
        os.makedirs(d, exist_ok=True)
        return d

    def _in_store(self, path):
        try:
            return os.path.normcase(os.path.dirname(os.path.abspath(path))) == \
                os.path.normcase(self.store_dir())
        except Exception:
            return False

    def _ingest(self, path):
        """Physically move *path* into this box. Returns (new_path, pending).

        Only items lying directly on the Desktop are moved; anything dropped
        from another folder or drive stays where it is and is kept as a link.
        """
        if (
            not self.move_files
            or not os.path.exists(path)
            or self._in_store(path)
            or not on_desktop(path)
        ):
            return path, None
        target = unique_target(self.store_dir(), os.path.basename(path))
        try:
            shutil.move(path, target)
            log.info("Moved %s -> %s", path, target)
            return target, None
        except Exception as e:
            # typically C:\Users\Public\Desktop - needs elevation
            log.warning("Could not move %s: %s", path, e)
            return path, (path, target)

    def _eject(self, path):
        """Move a stored file back out onto the desktop. True on success."""
        if not self._in_store(path) or not os.path.exists(path):
            return True
        target = unique_target(desktop_dir(), os.path.basename(path))
        try:
            shutil.move(path, target)
            log.info("Moved %s -> %s", path, target)
            return True
        except Exception as e:
            log.warning("Could not move %s back to the desktop: %s", path, e)
            return False

    def _resolve_pending(self, pending):
        """Offer an elevated retry for items that could not be moved."""
        if not pending:
            return {}
        names = "\n".join("• " + os.path.basename(s) for s, _ in pending[:12])
        more = f"\n… и ещё {len(pending) - 12}" if len(pending) > 12 else ""
        ans = QtWidgets.QMessageBox.question(
            self, APP_NAME,
            f"Не удалось перенести {len(pending)} элемент(ов) — они лежат в общей "
            f"папке рабочего стола и требуют прав администратора:\n\n{names}{more}\n\n"
            "Повторить с повышением прав?",
        )
        if ans != QtWidgets.QMessageBox.StandardButton.Yes:
            return {}
        return {src: dst for src, dst in elevated_move(pending, self)}

    def _apply_resolved(self, resolved):
        n = 0
        for src, dst in resolved.items():
            for i, it in enumerate(self.items):
                if os.path.normcase(it) == os.path.normcase(src):
                    self.items[i] = dst
                    n += 1
        return n

    def add_paths(self, paths):
        existing = {p.lower() for p in self.items}
        added, pending = 0, []
        for p in paths:
            p = os.path.normpath(p)
            if p.lower() in existing:
                continue
            new_path, pend = self._ingest(p)
            if pend:
                pending.append(pend)
            self.items.append(new_path)
            existing.add(new_path.lower())
            added += 1

        self._apply_resolved(self._resolve_pending(pending))

        if added:
            self.update()
            self.manager.save()
        return added

    def migrate_originals(self):
        """Move already-listed files that still sit outside the box."""
        pending, moved = [], 0
        for i, it in enumerate(self.items):
            if self._in_store(it) or not os.path.exists(it):
                continue
            new_path, pend = self._ingest(it)
            if pend:
                pending.append(pend)
            if new_path != it:
                self.items[i] = new_path
                moved += 1

        moved += self._apply_resolved(self._resolve_pending(pending))

        self.update()
        self.manager.save()
        QtWidgets.QMessageBox.information(
            self, APP_NAME, f"Перенесено в бокс: {moved}"
        )

    def toggle_move_files(self):
        self.move_files = not self.move_files
        self.manager.save()

    def open_store(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(self.store_dir())
        )

    # -------------------------------------------------------------- layout
    def _cell_size(self):
        return self.icon_size + 26, self.icon_size + 34

    def _relayout(self):
        self._rects = []
        cw, ch = self._cell_size()
        pad = 8
        avail = max(1, self.width() - 2 * pad)
        cols = max(1, avail // cw)
        self._cols = cols
        gap = (avail - cols * cw) / (cols + 1)
        top = HEADER_H + 4

        for i in range(len(self.items)):
            c, r = i % cols, i // cols
            x = pad + gap * (c + 1) + c * cw
            y = top + r * ch - self._scroll
            self._rects.append(QRect(int(x), int(y), cw, ch))

        rows = (len(self.items) + cols - 1) // cols
        self._content_h = rows * ch + top + 6
        max_scroll = max(0, self._content_h - self.height())
        if self._scroll > max_scroll:
            self._scroll = max_scroll
            self._relayout()

    # --------------------------------------------------------------- paint
    def paintEvent(self, ev):
        self._relayout()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        bg = QtGui.QColor(self.bg_color)
        bg.setAlpha(self.bg_alpha)

        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        p.fillPath(path, bg)

        border = QtGui.QColor(255, 255, 255, 40 if not self._drop_hint else 180)
        p.setPen(QtGui.QPen(border, 1.4 if self._drop_hint else 1.0))
        p.drawPath(path)

        # header
        hdr = QtGui.QColor(255, 255, 255, 18)
        hpath = QtGui.QPainterPath()
        hrect = QtCore.QRectF(0, 0, self.width(), HEADER_H)
        hpath.addRoundedRect(rect, self.radius, self.radius)
        p.save()
        p.setClipRect(hrect)
        p.fillPath(hpath, hdr)
        p.restore()

        f = p.font()
        f.setPointSizeF(9.5)
        f.setBold(True)
        p.setFont(f)
        p.setPen(self.label_color)
        tr = QRect(10, 0, self.width() - 20, HEADER_H)
        fm = QtGui.QFontMetrics(f)
        p.drawText(
            tr,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            fm.elidedText(self.title, Qt.TextElideMode.ElideRight, tr.width()),
        )

        if self.collapsed:
            return

        # items
        p.setClipRect(QRect(0, HEADER_H, self.width(), self.height() - HEADER_H))
        f.setBold(False)
        f.setPointSizeF(8.5)
        p.setFont(f)
        fm = QtGui.QFontMetrics(f)
        dpr = p.device().devicePixelRatio()

        for i, r in enumerate(self._rects):
            if r.bottom() < HEADER_H or r.top() > self.height():
                continue
            path_i = self.items[i]

            if i == self._hover_index and not self._dragging_item:
                hp = QtGui.QPainterPath()
                hp.addRoundedRect(QtCore.QRectF(r.adjusted(2, 2, -2, -2)), 6, 6)
                p.fillPath(hp, QtGui.QColor(255, 255, 255, 34))

            pm = ICONS.get(path_i, self.icon_size, dpr)
            pw = round(pm.width() / pm.devicePixelRatio())
            ph = round(pm.height() / pm.devicePixelRatio())
            ix = r.x() + (r.width() - pw) // 2
            iy = r.y() + 5 + (self.icon_size - ph) // 2
            exists, is_dir = STATUS.get(path_i, (None, False))
            if exists is None:
                self.manager.request_status()
            elif not exists:
                p.setOpacity(0.45)
            p.drawPixmap(ix, iy, pm)
            p.setOpacity(1.0)

            base = os.path.basename(path_i)
            # hide file extensions like Explorer does, but keep "my.project"
            name = (base if is_dir else os.path.splitext(base)[0]) or path_i
            lr = QRect(r.x() + 2, r.y() + self.icon_size + 8, r.width() - 4, 28)
            p.setPen(QtGui.QColor(0, 0, 0, 130))
            self._draw_wrapped(p, lr.translated(0, 1), name, fm)
            p.setPen(self.label_color)
            self._draw_wrapped(p, lr, name, fm)

        if self._dragging_item and 0 <= self._drag_index < len(self.items):
            tgt = self._insert_index(self.mapFromGlobal(QtGui.QCursor.pos()))
            self._draw_insert_marker(p, tgt)

        if not self.items:
            p.setPen(QtGui.QColor(255, 255, 255, 110))
            p.drawText(
                QRect(0, HEADER_H, self.width(), self.height() - HEADER_H),
                int(Qt.AlignmentFlag.AlignCenter),
                "Перетащи сюда файлы\nили ярлыки",
            )

    def _draw_wrapped(self, p, rect, text, fm):
        lines = []
        words = text.split()
        cur = ""
        for w in words:
            t = (cur + " " + w).strip()
            if fm.horizontalAdvance(t) <= rect.width() or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
            if len(lines) == 2:
                break
        if cur and len(lines) < 2:
            lines.append(cur)
        if not lines:
            lines = [text]
        if len(lines) == 2 and fm.horizontalAdvance(lines[1]) > rect.width():
            lines[1] = fm.elidedText(lines[1], Qt.TextElideMode.ElideRight, rect.width())
        elif len(words) > sum(len(l.split()) for l in lines):
            lines[-1] = fm.elidedText(
                lines[-1] + "…", Qt.TextElideMode.ElideRight, rect.width()
            )
        y = rect.y()
        for ln in lines[:2]:
            p.drawText(
                QRect(rect.x(), y, rect.width(), fm.height()),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                ln,
            )
            y += fm.height()

    def _draw_insert_marker(self, p, idx):
        if not self._rects:
            return
        if idx >= len(self._rects):
            r = self._rects[-1]
            x = r.right()
        else:
            r = self._rects[idx]
            x = r.left()
        p.setPen(QtGui.QPen(QtGui.QColor(120, 190, 255, 220), 2))
        p.drawLine(x, r.top() + 3, x, r.bottom() - 3)

    # --------------------------------------------------------------- mouse
    def _hit_item(self, pos):
        for i, r in enumerate(self._rects):
            if r.contains(pos):
                return i
        return -1

    def _insert_index(self, pos):
        for i, r in enumerate(self._rects):
            if r.contains(pos):
                return i if pos.x() < r.center().x() else i + 1
        # nearest row fallback
        best, bd = len(self.items), None
        for i, r in enumerate(self._rects):
            d = (r.center() - pos).manhattanLength()
            if bd is None or d < bd:
                bd, best = d, i + (0 if pos.x() < r.center().x() else 1)
        return best

    def _edge_at(self, pos):
        if self.locked:
            return ""
        d = ""
        if not self.collapsed:  # a collapsed box is all header: width only
            if pos.y() <= EDGE:
                d += "t"
            elif pos.y() >= self.height() - EDGE:
                d += "b"
        if pos.x() <= EDGE:
            d += "l"
        elif pos.x() >= self.width() - EDGE:
            d += "r"
        return d

    def mouseMoveEvent(self, ev):
        pos = ev.position().toPoint()

        if self._mode == "move":
            self.move(ev.globalPosition().toPoint() - self._press_pos)
            return
        if self._mode == "resize":
            self._do_resize(ev.globalPosition().toPoint())
            return
        if self._drag_index >= 0 and not self._dragging_item:
            if (pos - self._drag_pos).manhattanLength() > 8:
                self._dragging_item = True
        if self._dragging_item:
            self.update()
            return

        d = self._edge_at(pos)
        cursors = {
            "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
            "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
            "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
        }
        self.setCursor(cursors.get(d, Qt.CursorShape.ArrowCursor))

        idx = -1 if (d or pos.y() < HEADER_H) else self._hit_item(pos)
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()
        if idx >= 0:
            self.setToolTip(self.items[idx])
        else:
            self.setToolTip("")

    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        pos = ev.position().toPoint()
        self._press_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
        self._press_geo = self.geometry()

        d = self._edge_at(pos)
        if d:
            self._mode = "resize"
            self._resize_dir = d
            self._press_pos = ev.globalPosition().toPoint()
            return
        if pos.y() < HEADER_H:
            if not self.locked:
                self._mode = "move"
            return
        idx = self._hit_item(pos)
        if idx >= 0 and not self.locked:
            self._drag_index = idx
            self._drag_pos = pos

    def mouseReleaseEvent(self, ev):
        if self._dragging_item and self._drag_index >= 0:
            tgt = self._insert_index(ev.position().toPoint())
            item = self.items.pop(self._drag_index)
            if tgt > self._drag_index:
                tgt -= 1
            tgt = max(0, min(len(self.items), tgt))
            self.items.insert(tgt, item)
            self.manager.save()
        elif self._mode in ("move", "resize"):
            self._home = None  # the user picked a new spot
            self.manager.save()
        self._mode = None
        self._resize_dir = ""
        self._drag_index = -1
        self._dragging_item = False
        self.update()

    def mouseDoubleClickEvent(self, ev):
        pos = ev.position().toPoint()
        if pos.y() < HEADER_H:
            self.rename()
            return
        idx = self._hit_item(pos)
        if idx >= 0:
            self.open_item(idx)

    def wheelEvent(self, ev):
        if self.collapsed:
            return
        max_scroll = max(0, self._content_h - self.height())
        if max_scroll <= 0:
            return
        self._scroll = max(
            0, min(max_scroll, self._scroll - ev.angleDelta().y() // 2)
        )
        self.update()

    def leaveEvent(self, ev):
        self._hover_index = -1
        self.update()

    def _do_resize(self, gpos):
        delta = gpos - self._press_pos
        g = QRect(self._press_geo)
        # clamp the dragged edge so the opposite one never moves
        if "l" in self._resize_dir:
            g.setLeft(min(g.left() + delta.x(), g.right() - MIN_W + 1))
        if "r" in self._resize_dir:
            g.setRight(max(g.right() + delta.x(), g.left() + MIN_W - 1))
        if "t" in self._resize_dir:
            g.setTop(min(g.top() + delta.y(), g.bottom() - MIN_H + 1))
        if "b" in self._resize_dir:
            g.setBottom(max(g.bottom() + delta.y(), g.top() + MIN_H - 1))
        if self.collapsed:
            g.setHeight(HEADER_H)
        else:
            self._expanded_h = g.height()
        self.setGeometry(g)

    def fit_to_screens(self, areas):
        """Keep the header reachable when monitors are added or removed.

        A box that ends up off every screen is parked on the primary one; its
        real spot stays in _home (and in the saved config) and it moves back
        as soon as that spot is visible again.
        """
        if not areas:
            return
        if self._home is not None and header_visible(
            QRect(self._home, self.size()), areas
        ):
            self.move(self._home)
            self._home = None
            return
        if header_visible(self.geometry(), areas):
            return
        if self._home is None:
            self._home = self.geometry().topLeft()
        a = areas[0]
        x = max(a.left(), min(self.x(), a.right() - self.width() + 1))
        y = max(a.top(), min(self.y(), a.bottom() - self.height() + 1))
        self.move(x, y)
        log.info("Box %s parked on screen (was at %d,%d)",
                 self.uid, self._home.x(), self._home.y())

    # ------------------------------------------------------------ drag&drop
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()
            self._drop_hint = True
            self.update()

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dragLeaveEvent(self, ev):
        self._drop_hint = False
        self.update()

    def dropEvent(self, ev):
        self._drop_hint = False
        paths = [
            u.toLocalFile() for u in ev.mimeData().urls() if u.toLocalFile()
        ]
        if paths:
            self.add_paths(paths)
            ev.acceptProposedAction()
        self.update()

    # ------------------------------------------------------------- actions
    def open_item(self, idx):
        path = self.items[idx]
        try:
            if IS_WINDOWS:
                os.startfile(path)  # noqa
            else:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Не удалось открыть:\n{e}")

    def rename(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Название группы", "Название:", text=self.title
        )
        if ok:
            self.title = name.strip() or self.title
            self.update()
            self.manager.save()

    def pick_color(self):
        col = QtWidgets.QColorDialog.getColor(
            self.bg_color, self, "Цвет подложки"
        )
        if col.isValid():
            self.bg_color = col
            self.update()
            self.manager.save()

    def pick_label_color(self):
        col = QtWidgets.QColorDialog.getColor(
            self.label_color, self, "Цвет текста"
        )
        if col.isValid():
            self.label_color = col
            self.update()
            self.manager.save()

    def set_alpha(self, v):
        self.bg_alpha = int(v)
        self.update()
        self.manager.save()  # debounced; also covers clicks and arrow keys

    def set_icon_size(self, v):
        self.icon_size = int(v)
        self._scroll = 0
        self.update()
        self.manager.save()

    def toggle_collapse(self):
        if self.collapsed:
            self.collapsed = False
            self.resize(self.width(), self._expanded_h)
        else:
            self._expanded_h = self.height()
            self.collapsed = True
            self.resize(self.width(), HEADER_H)
        self.update()
        self.manager.save()

    def sort_items(self, by="name"):
        if by == "name":
            self.items.sort(key=lambda p: os.path.basename(p).lower())
        elif by == "type":
            self.items.sort(
                key=lambda p: (
                    os.path.splitext(p)[1].lower(),
                    os.path.basename(p).lower(),
                )
            )
        self.update()
        self.manager.save()

    def clean_missing(self):
        before = len(self.items)
        self.items = [p for p in self.items if os.path.exists(p)]
        self.update()
        self.manager.save()
        self.manager.request_status()
        QtWidgets.QMessageBox.information(
            self, APP_NAME, f"Удалено битых ссылок: {before - len(self.items)}"
        )

    def add_via_dialog(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Добавить в группу", os.path.expanduser("~")
        )
        if files:
            self.add_paths(files)

    # -------------------------------------------------------------- menu
    def _context_menu(self, pos):
        idx = self._hit_item(pos) if pos.y() >= HEADER_H else -1
        m = QtWidgets.QMenu(self)

        if idx >= 0:
            m.addAction("Открыть", lambda: self.open_item(idx))
            m.addAction(
                "Показать в проводнике",
                lambda: self._reveal(self.items[idx]),
            )
            m.addSeparator()
            m.addAction(
                "Вынести на рабочий стол", lambda: self._remove(idx)
            )
            m.addSeparator()

        m.addAction("Переименовать группу…", self.rename)
        m.addAction("Добавить файлы…", self.add_via_dialog)
        m.addSeparator()

        a = m.addAction("Переносить файлы со стола в бокс")
        a.setCheckable(True)
        a.setChecked(self.move_files)
        a.triggered.connect(self.toggle_move_files)
        m.addAction("Перенести оригиналы со стола в бокс", self.migrate_originals)
        m.addAction("Открыть папку бокса", self.open_store)
        m.addSeparator()

        m.addAction("Цвет подложки…", self.pick_color)
        m.addAction("Цвет текста…", self.pick_label_color)

        alpha_menu = m.addMenu("Прозрачность")
        wa = QtWidgets.QWidgetAction(alpha_menu)
        slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 255)
        slider.setValue(self.bg_alpha)
        slider.setFixedWidth(180)
        slider.valueChanged.connect(self.set_alpha)
        wa.setDefaultWidget(slider)
        alpha_menu.addAction(wa)

        size_menu = m.addMenu("Размер иконок")
        for s in (32, 40, 48, 64, 80, 96):
            a = size_menu.addAction(f"{s} px")
            a.setCheckable(True)
            a.setChecked(s == self.icon_size)
            a.triggered.connect(lambda _=False, v=s: self.set_icon_size(v))

        rad_menu = m.addMenu("Скругление углов")
        for r in (0, 6, 10, 16, 24):
            a = rad_menu.addAction(str(r))
            a.setCheckable(True)
            a.setChecked(r == self.radius)
            a.triggered.connect(lambda _=False, v=r: self._set_radius(v))

        m.addSeparator()
        sort_menu = m.addMenu("Сортировать")
        sort_menu.addAction("По имени", lambda: self.sort_items("name"))
        sort_menu.addAction("По типу", lambda: self.sort_items("type"))

        a = m.addAction("Свернуть в заголовок")
        a.setCheckable(True)
        a.setChecked(self.collapsed)
        a.triggered.connect(self.toggle_collapse)

        a = m.addAction("Зафиксировать")
        a.setCheckable(True)
        a.setChecked(self.locked)
        a.triggered.connect(self._toggle_lock)

        m.addAction("Убрать битые ссылки", self.clean_missing)
        m.addSeparator()
        m.addAction("Новая группа рядом", self.manager.begin_draw)
        m.addAction("Удалить группу", self._delete_self)

        m.exec(self.mapToGlobal(pos))

    def _set_radius(self, v):
        self.radius = v
        self.update()
        self.manager.save()

    def _toggle_lock(self):
        self.locked = not self.locked
        self.manager.save()

    def _remove(self, idx):
        if not self._eject(self.items[idx]):
            QtWidgets.QMessageBox.warning(
                self, APP_NAME,
                "Не удалось вынести файл на рабочий стол — он занят или нет "
                "прав. Элемент оставлен в боксе.",
            )
            return
        del self.items[idx]
        self.update()
        self.manager.save()

    def _reveal(self, path):
        if IS_WINDOWS and os.path.exists(path):
            ctypes.windll.shell32.ShellExecuteW(
                None, "open", "explorer.exe", f'/select,"{path}"', None, 1
            )

    def _delete_self(self):
        stored = [p for p in self.items if self._in_store(p)]
        if stored:
            dlg = QtWidgets.QMessageBox(self)
            dlg.setWindowTitle(APP_NAME)
            dlg.setText(
                f"Удалить бокс «{self.title}»?\n\n"
                f"Внутри лежит файлов: {len(stored)}."
            )
            eject = dlg.addButton(
                "Вынести на рабочий стол",
                QtWidgets.QMessageBox.ButtonRole.AcceptRole,
            )
            keep = dlg.addButton(
                "Оставить в хранилище",
                QtWidgets.QMessageBox.ButtonRole.DestructiveRole,
            )
            dlg.addButton("Отмена", QtWidgets.QMessageBox.ButtonRole.RejectRole)
            dlg.exec()
            clicked = dlg.clickedButton()
            if clicked is eject:
                failed = [p for p in stored if not self._eject(p)]
                if failed:
                    QtWidgets.QMessageBox.warning(
                        self, APP_NAME,
                        f"Не удалось вынести файлов: {len(failed)}. "
                        "Они остались в папке бокса.",
                    )
            elif clicked is not keep:
                return
        elif (
            QtWidgets.QMessageBox.question(
                self, APP_NAME, f"Удалить бокс «{self.title}»?"
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return
        self.manager.remove_box(self)

    # ------------------------------------------------- keep behind windows
    def nativeEvent(self, eventType, message):
        if IS_WINDOWS and eventType == b"windows_generic_MSG":
            msg = ctypes.cast(
                int(message), ctypes.POINTER(wintypes.MSG)
            ).contents
            if msg.message == 0x0046:  # WM_WINDOWPOSCHANGING
                class WINDOWPOS(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", ctypes.c_void_p),
                        ("hwndInsertAfter", ctypes.c_void_p),
                        ("x", ctypes.c_int), ("y", ctypes.c_int),
                        ("cx", ctypes.c_int), ("cy", ctypes.c_int),
                        ("flags", ctypes.c_uint),
                    ]
                wp = ctypes.cast(msg.lParam, ctypes.POINTER(WINDOWPOS)).contents
                wp.hwndInsertAfter = ctypes.c_void_p(1)   # HWND_BOTTOM
                wp.flags &= ~0x0004                        # clear SWP_NOZORDER
        return False, 0


# --------------------------------------------------------------------------- #
#  Fullscreen overlay used to draw a new box
# --------------------------------------------------------------------------- #
class DrawOverlay(QtWidgets.QWidget):
    finished = QtCore.pyqtSignal(QRect)

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        geo = QRect()
        for s in QtWidgets.QApplication.screens():
            geo = geo.united(s.geometry())
        self.setGeometry(geo)
        self._origin = QPoint()
        self._rect = QRect()
        self._active = False

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 70))
        p.setPen(QtGui.QColor(255, 255, 255, 200))
        p.drawText(
            QRect(0, 40, self.width(), 40),
            int(Qt.AlignmentFlag.AlignHCenter),
            "Выдели область для новой группы  •  Esc — отмена",
        )
        if self._rect.isValid():
            p.setCompositionMode(
                QtGui.QPainter.CompositionMode.CompositionMode_Clear
            )
            p.fillRect(self._rect, Qt.GlobalColor.transparent)
            p.setCompositionMode(
                QtGui.QPainter.CompositionMode.CompositionMode_SourceOver
            )
            p.fillRect(self._rect, QtGui.QColor(90, 150, 220, 45))
            p.setPen(QtGui.QPen(QtGui.QColor(140, 200, 255), 1.5))
            p.drawRect(self._rect)
            p.drawText(
                self._rect.adjusted(6, 4, 0, 0),
                int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft),
                f"{self._rect.width()} × {self._rect.height()}",
            )

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._origin = ev.position().toPoint()
            self._active = True
            self._rect = QRect(self._origin, QSize())

    def mouseMoveEvent(self, ev):
        if self._active:
            self._rect = QRect(self._origin, ev.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, ev):
        if not self._active:
            return
        self._active = False
        r = self._rect
        self.close()
        if r.width() >= 60 and r.height() >= 50:
            self.finished.emit(
                QRect(
                    r.x() + self.x(), r.y() + self.y(),
                    max(MIN_W, r.width()), max(MIN_H, r.height()),
                )
            )

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.close()


# --------------------------------------------------------------------------- #
#  Single instance
# --------------------------------------------------------------------------- #
_INSTANCE_MUTEX = None  # held for the lifetime of the process


def _instance_key():
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return f"{APP_NAME}-{user}"


def _claim_mutex():
    """Windows: own a per-session named mutex. False if someone else does."""
    global _INSTANCE_MUTEX
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR
        ]
        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, "Local\\" + _instance_key())
        if not handle:
            return True  # cannot tell - do not block startup
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            return False
        _INSTANCE_MUTEX = handle
    except Exception:
        log.exception("Single-instance mutex failed")
    return True


def _ping_instance():
    """Knock on a running instance's local server. True if it answered."""
    sock = QtNetwork.QLocalSocket()
    sock.connectToServer(_instance_key())
    if not sock.waitForConnected(500):
        return False
    sock.disconnectFromServer()
    return True


def another_instance_running():
    """True if Deskfinity already runs for this user (it is asked to show)."""
    if IS_WINDOWS and not _claim_mutex():
        _ping_instance()
        return True
    return _ping_instance()


# --------------------------------------------------------------------------- #
#  Manager / tray
# --------------------------------------------------------------------------- #
class Manager(QtCore.QObject):
    _status_ready = QtCore.pyqtSignal(object)  # emitted from a worker thread

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.boxes = []
        self._unloaded = []       # raw entries that failed to load - kept as is
        self.load_notice = None   # set when the config needed rescuing
        self._overlay = None
        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._write)

        self._status_busy = False
        self._status_again = False
        self._status_ready.connect(self._apply_status)
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setInterval(STATUS_INTERVAL_MS)
        self._status_timer.timeout.connect(self.request_status)

        # monitors come and go: re-fit boxes once things settle
        self._fit_timer = QtCore.QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(500)
        self._fit_timer.timeout.connect(self.fit_boxes)
        app.screenAdded.connect(self._on_screen_added)
        app.screenRemoved.connect(lambda *_: self._fit_timer.start())
        app.primaryScreenChanged.connect(lambda *_: self._fit_timer.start())
        for scr in app.screens():
            self._watch_screen(scr)

        self._listen_for_instances()
        self.hotkey_ok = self._install_hotkey()
        self._build_tray()
        self.load()
        self.fit_boxes()
        self.request_status()
        self._status_timer.start()

    # ------------------------------------------------------------- screens
    def _watch_screen(self, scr):
        scr.availableGeometryChanged.connect(lambda *_: self._fit_timer.start())

    def _on_screen_added(self, scr):
        self._watch_screen(scr)
        self._fit_timer.start()

    def fit_boxes(self):
        areas = screen_areas()
        for b in self.boxes:
            b.fit_to_screens(areas)

    # --------------------------------------------------------- item status
    def request_status(self):
        """Re-check which items exist, off the UI thread. Cheap to call."""
        if self._status_busy:
            self._status_again = True
            return
        self._status_busy = True
        self._status_again = False
        paths = {p for b in self.boxes for p in b.items}
        threading.Thread(
            target=self._check_status, args=(paths,), daemon=True
        ).start()

    def _check_status(self, paths):
        result = {}
        for p in paths:
            try:
                result[p] = (os.path.exists(p), os.path.isdir(p))
            except Exception:
                result[p] = (False, False)
        self._status_ready.emit(result)

    def _apply_status(self, result):
        self._status_busy = False
        changed = any(STATUS.get(p) != v for p, v in result.items())
        STATUS.update(result)
        if changed:
            for b in self.boxes:
                b.update()
        if self._status_again:
            self.request_status()

    # ----------------------------------------------------- single instance
    def _listen_for_instances(self):
        """Later launches knock here instead of starting a second copy."""
        key = _instance_key()
        QtNetwork.QLocalServer.removeServer(key)  # stale socket after a crash
        self._ipc = QtNetwork.QLocalServer(self)
        if self._ipc.listen(key):
            self._ipc.newConnection.connect(self._on_instance_knock)
        else:
            log.warning("Single-instance server: %s", self._ipc.errorString())

    def _on_instance_knock(self):
        while self._ipc.hasPendingConnections():
            conn = self._ipc.nextPendingConnection()
            conn.disconnected.connect(conn.deleteLater)
        self.show_all()
        self.tray.showMessage(
            APP_NAME, "Deskfinity уже запущен — он здесь, в трее.",
            QtWidgets.QSystemTrayIcon.MessageIcon.Information, 4000,
        )

    # ------------------------------------------------------------- hotkey
    def _install_hotkey(self):
        """Global Ctrl+Alt+F -> start drawing a new box. True on success."""
        self._hotkey_filter = None
        if not IS_WINDOWS:
            return False
        MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
        VK_F = 0x46
        ok = user32.RegisterHotKey(
            None, 1, MOD_ALT | MOD_CONTROL | MOD_NOREPEAT, VK_F
        )
        if not ok:
            log.warning(
                "Ctrl+Alt+F is already taken by another program (error %d)",
                ctypes.get_last_error(),
            )
            return False

        manager = self

        class _Filter(QtCore.QAbstractNativeEventFilter):
            def nativeEventFilter(self, eventType, message):
                if eventType == b"windows_generic_MSG":
                    try:
                        msg = ctypes.cast(
                            int(message), ctypes.POINTER(wintypes.MSG)
                        ).contents
                        if msg.message == 0x0312 and msg.wParam == 1:  # WM_HOTKEY
                            QtCore.QTimer.singleShot(0, manager.begin_draw)
                    except Exception:
                        pass
                return False, 0

        self._hotkey_filter = _Filter()
        self.app.installNativeEventFilter(self._hotkey_filter)
        return True

    # ---------------------------------------------------------------- tray
    def _tray_icon(self):
        pm = QtGui.QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setBrush(QtGui.QColor(60, 130, 200, 220))
        p.setPen(QtGui.QPen(QtGui.QColor(230, 240, 255), 4))
        p.drawRoundedRect(6, 6, 52, 52, 10, 10)
        p.setBrush(QtGui.QColor(240, 245, 255))
        p.setPen(Qt.PenStyle.NoPen)
        for x in (17, 35):
            for y in (18, 36):
                p.drawRoundedRect(x, y, 12, 12, 3, 3)
        p.end()
        return QtGui.QIcon(pm)

    def _build_tray(self):
        self.tray = QtWidgets.QSystemTrayIcon(self._tray_icon())
        self.tray.setToolTip(APP_NAME)
        m = QtWidgets.QMenu()
        m.addAction(
            "Новая группа (Ctrl+Alt+F)" if self.hotkey_ok else "Новая группа",
            self.begin_draw,
        )
        m.addSeparator()
        m.addAction("Показать все", self.show_all)
        m.addAction("Скрыть все", self.hide_all)
        m.addSeparator()
        m.addAction("Обновить иконки", self.refresh_icons)
        m.addAction("Открыть папку настроек", self.open_config_dir)
        m.addAction("Восстановить файлы из хранилища…", self.recover_storage)
        a = m.addAction("Запускать с Windows")
        a.setCheckable(True)
        a.setChecked(self._autostart_enabled())
        a.triggered.connect(self._toggle_autostart)
        m.addSeparator()
        m.addAction("Выход", self.quit)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(self._tray_click)
        self.tray.show()

    def _tray_click(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self.begin_draw()

    # --------------------------------------------------------------- boxes
    def begin_draw(self):
        if self._overlay:
            return
        self._overlay = DrawOverlay()
        self._overlay.finished.connect(self._create_from_rect)
        self._overlay.destroyed.connect(lambda: setattr(self, "_overlay", None))
        self._overlay.show()
        self._overlay.raise_()
        self._overlay.activateWindow()
        self._overlay.setFocus()

    def _create_from_rect(self, rect):
        self._overlay = None
        f = Box(self, {"geometry": [rect.x(), rect.y(), rect.width(), rect.height()]})
        self.boxes.append(f)
        f.show()
        f.rename()
        self.save()

    def remove_box(self, box):
        if box in self.boxes:
            self.boxes.remove(box)
        box.close()
        box.deleteLater()
        self.save()

    def show_all(self):
        for f in self.boxes:
            f.show()

    def hide_all(self):
        for f in self.boxes:
            f.hide()

    def refresh_icons(self):
        ICONS.clear()
        for f in self.boxes:
            f.update()

    def open_config_dir(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(CONFIG_DIR))

    # ------------------------------------------------------------ autostart
    def _run_key(self):
        import winreg
        return winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_ALL_ACCESS,
        )

    def _autostart_enabled(self):
        if not IS_WINDOWS:
            return False
        try:
            import winreg
            with self._run_key() as k:
                winreg.QueryValueEx(k, APP_NAME)
            return True
        except Exception:
            return False

    def _toggle_autostart(self, checked):
        if not IS_WINDOWS:
            return
        import winreg
        try:
            with self._run_key() as k:
                if checked:
                    exe = sys.executable
                    if exe.lower().endswith("python.exe"):
                        exe = exe[:-10] + "pythonw.exe"
                    cmd = f'"{exe}" "{os.path.abspath(__file__)}"'
                    winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
                else:
                    winreg.DeleteValue(k, APP_NAME)
        except Exception as e:
            QtWidgets.QMessageBox.warning(None, APP_NAME, str(e))

    # ------------------------------------------------------------ persist
    def save(self):
        self._save_timer.start()

    def _write(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            boxes = [f.to_dict() for f in self.boxes] + self._unloaded
            data = {"version": 1, "boxes": boxes}
            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, CONFIG_PATH)
        except Exception:
            log.exception("Could not save %s", CONFIG_PATH)

    @staticmethod
    def _read_entries(path):
        """Box entries from a config file. Raises if the file is unusable."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        entries = data.get("boxes", data.get("fences", []))
        if not isinstance(entries, list):
            raise ValueError("'boxes' is not a list")
        return entries

    def _backup(self):
        """Rotate boxes.json.bak1..N, skipping copies identical to the last."""
        try:
            newest = CONFIG_PATH + ".bak1"
            if os.path.exists(newest):
                with open(CONFIG_PATH, "rb") as a, open(newest, "rb") as b:
                    if a.read() == b.read():
                        return
            for i in range(BACKUPS - 1, 0, -1):
                older = f"{CONFIG_PATH}.bak{i}"
                if os.path.exists(older):
                    os.replace(older, f"{CONFIG_PATH}.bak{i + 1}")
            shutil.copy2(CONFIG_PATH, newest)
        except Exception:
            log.exception("Could not back up %s", CONFIG_PATH)

    def _quarantine(self, path):
        """Keep a copy of an unreadable config before it can be overwritten."""
        kept = f"{path}.broken-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            shutil.copy2(path, kept)
            log.error("Unreadable config saved as %s", kept)
        except Exception:
            log.exception("Could not keep a copy of %s", path)
        return kept

    def load(self):
        path = CONFIG_PATH
        if not os.path.exists(path):
            path = self._legacy_config()
            if not path:
                return
        try:
            entries = self._read_entries(path)
            if path == CONFIG_PATH:
                self._backup()
        except Exception:
            log.exception("Could not load %s", path)
            kept = os.path.basename(self._quarantine(path))
            entries = None
            for i in range(1, BACKUPS + 1):
                bak = f"{CONFIG_PATH}.bak{i}"
                try:
                    entries = self._read_entries(bak)
                except Exception:
                    continue
                log.warning("Restored the layout from %s", bak)
                self.load_notice = (
                    f"Файл настроек повреждён (копия: {kept}). "
                    f"Раскладка восстановлена из резервной копии "
                    f"{os.path.basename(bak)}."
                )
                break
            if entries is None:
                self.load_notice = (
                    f"Файл настроек повреждён и не прочитан (копия: {kept}). "
                    "Файлы боксов целы — верни их через трей: "
                    "«Восстановить файлы из хранилища»."
                )
                return

        for d in entries:
            try:
                f = Box(self, d)
            except Exception:
                log.exception("Box failed to load, keeping it untouched: %r", d)
                self._unloaded.append(d)
                continue
            self.boxes.append(f)
            f.show()
        if self._unloaded and not self.load_notice:
            self.load_notice = (
                f"Не удалось загрузить боксов: {len(self._unloaded)}. "
                "Их данные сохранены в boxes.json без изменений, "
                "подробности — в deskfinity.log."
            )
        if path != CONFIG_PATH and self.boxes:
            self._write()  # migrate to the new location

    def recover_storage(self):
        """Bring back storage folders that no box owns any more."""
        owned = {b.uid for b in self.boxes}
        owned |= {d.get("uid") for d in self._unloaded if isinstance(d, dict)}
        found = []
        try:
            names = sorted(os.listdir(STORE_DIR))
        except OSError:
            names = []
        for uid in names:
            folder = os.path.join(STORE_DIR, uid)
            if uid in owned or not os.path.isdir(folder):
                continue
            items = [os.path.join(folder, n) for n in sorted(os.listdir(folder))]
            if items:
                found.append((uid, items))

        if not found:
            QtWidgets.QMessageBox.information(
                None, APP_NAME, "В хранилище нет файлов без бокса."
            )
            return

        avail = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        for k, (uid, items) in enumerate(found):
            # reusing the folder name as uid makes the new box own those files
            box = Box(self, {
                "uid": uid,
                "title": "Восстановлено",
                "items": items,
                "geometry": [
                    avail.x() + 60 + 40 * k, avail.y() + 60 + 40 * k, 340, 280
                ],
            })
            self.boxes.append(box)
            box.show()
            log.info("Recovered storage folder %s (%d items)", uid, len(items))
        self.save()
        QtWidgets.QMessageBox.information(
            None, APP_NAME,
            f"Восстановлено боксов: {len(found)}, "
            f"файлов: {sum(len(i) for _, i in found)}.",
        )

    @staticmethod
    def _legacy_config():
        """Pick up a layout saved by an earlier build under a different name."""
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        candidates = [
            ("Gridesk", "boxes.json"),
            ("FenceLite", "fences.json"),
        ]
        for folder, name in candidates:
            old = os.path.join(base, folder, name)
            if os.path.exists(old):
                return old
        return None

    def quit(self):
        self._write()
        if IS_WINDOWS and getattr(self, "_hotkey_filter", None):
            try:
                user32.UnregisterHotKey(None, 1)
            except Exception:
                pass
        self.tray.hide()
        self.app.quit()


# --------------------------------------------------------------------------- #
def main():
    global ICONS

    if IS_WINDOWS:
        # Note: do NOT call SetProcessDpiAwareness here. Qt6 already opts into
        # PER_MONITOR_AWARE_V2, which is strictly better; setting awareness
        # first makes Qt's own call fail with an access-denied warning.
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "deskfinity.app"
            )
        except Exception:
            pass

    setup_logging()
    log.info("Starting %s", APP_NAME)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    if another_instance_running():
        log.info("Already running - not starting a second copy")
        return

    ICONS = IconCache()
    mgr = Manager(app)

    if mgr.load_notice:
        mgr.tray.showMessage(
            APP_NAME, mgr.load_notice,
            QtWidgets.QSystemTrayIcon.MessageIcon.Critical,
            15000,
        )
    elif IS_WINDOWS and not mgr.hotkey_ok:
        mgr.tray.showMessage(
            APP_NAME,
            "Сочетание Ctrl+Alt+F занято другой программой. "
            "Новую группу можно создать кликом по иконке в трее.",
            QtWidgets.QSystemTrayIcon.MessageIcon.Warning,
            8000,
        )
    elif not mgr.boxes:
        mgr.tray.showMessage(
            APP_NAME,
            "Клик по иконке в трее — создать новую группу.",
            QtWidgets.QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
