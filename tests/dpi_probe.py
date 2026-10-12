import os, sys, tempfile
sys.dont_write_bytecode = True
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ["DESKFINITY_DATA"] = os.environ["APPDATA"]
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import deskfinity as df
from PyQt6 import QtWidgets
app = QtWidgets.QApplication([])
df.ICONS = df.IconCache()
f = os.path.join(tempfile.mkdtemp(), "c.txt"); open(f, "w").close()
class M:
    def save(self): pass
    def request_status(self): pass
box = df.Box(M(), {"items": [f], "geometry": [0, 0, 300, 200]})
box.show(); app.processEvents(); box.repaint(); app.processEvents()
keys = [k for k in df.ICONS._cache if k[0] == f.lower()]
print("screen dpr", box.devicePixelRatio(), "keys", [(k[1], k[2]) for k in keys],
      "px", [df.ICONS._cache[k].width() for k in keys])
