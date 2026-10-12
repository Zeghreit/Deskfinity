"""Headless harness: imports deskfinity with a throwaway APPDATA per test."""
import os, sys, tempfile, shutil, unittest
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="df-appdata-")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import deskfinity as df
from PyQt6 import QtWidgets, QtCore

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
df.ICONS = df.IconCache()


class FakeManager:
    def __init__(self):
        self.saves = 0
    def save(self):
        self.saves += 1
    def begin_draw(self):
        pass
    def request_status(self):
        pass
    def placed_on_desktop(self, path, hold_s=0):
        self.placed = path
    def clear_selection(self, keep=None):
        pass
    boxes = ()


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="df-test-")
        cfg = os.path.join(self.root, "appdata", "Deskfinity")
        df.CONFIG_DIR = cfg
        df.CONFIG_PATH = os.path.join(cfg, "boxes.json")
        df.STORE_DIR = os.path.join(cfg, "storage")
        self.desktop = os.path.join(self.root, "Desktop")
        os.makedirs(self.desktop)
        self._orig_desktop_dir = df.desktop_dir
        df.desktop_dir = lambda: self.desktop
        # never block on modal dialogs
        self._mb = {}
        for name in ("information", "warning", "question"):
            self._mb[name] = getattr(QtWidgets.QMessageBox, name)
            setattr(QtWidgets.QMessageBox, name,
                    staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.No))

    def tearDown(self):
        df.desktop_dir = self._orig_desktop_dir
        for name, fn in self._mb.items():
            setattr(QtWidgets.QMessageBox, name, fn)
        shutil.rmtree(self.root, ignore_errors=True)

    def touch(self, *parts, data=b"x"):
        p = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
        return p

    def spin(self, ms=50):
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(ms, loop.quit)
        loop.exec()
