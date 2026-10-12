"""Headless harness: imports deskfinity with a throwaway APPDATA per test."""
import os, sys, tempfile, shutil, unittest
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="df-appdata-")
# never the real data folder, even next to a portable install
os.environ["DESKFINITY_DATA"] = os.path.join(os.environ["APPDATA"], "Deskfinity")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import deskfinity as df
from PyQt6 import QtWidgets, QtCore

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
df.ICONS = df.IconCache()


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return __import__("json").load(fh)


# Every Manager a test creates is shut down in Base.tearDown, so no timer,
# watcher or worker thread of one test can leak into the next.
_MANAGERS = []
_manager_init = df.Manager.__init__


def _tracking_init(self, *args, **kwargs):
    _MANAGERS.append(self)
    _manager_init(self, *args, **kwargs)


df.Manager.__init__ = _tracking_init


def shutdown_managers():
    while _MANAGERS:
        m = _MANAGERS.pop()
        for name in ("_status_timer", "_fit_timer", "_save_timer"):
            t = getattr(m, name, None)
            if t is not None:
                t.stop()
        sorter = getattr(m, "sorter", None)
        if sorter is not None:
            sorter._timer.stop()
            if sorter._watcher.directories():
                sorter._watcher.removePaths(sorter._watcher.directories())
        if getattr(m, "_ipc", None) is not None:
            m._ipc.close()
        for b in m.boxes:
            b.close()
        if getattr(m, "tray", None) is not None:
            m.tray.hide()


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
        shutdown_managers()
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
