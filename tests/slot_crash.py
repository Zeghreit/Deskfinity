import os, sys
sys.dont_write_bytecode = True
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["APPDATA"] = sys.argv[1]
os.environ["DESKFINITY_DATA"] = os.path.join(sys.argv[1], "Deskfinity")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import deskfinity as df
from PyQt6 import QtWidgets, QtCore
app = QtWidgets.QApplication([])
if sys.argv[2] == "hook":
    df.setup_logging()
def boom():
    raise RuntimeError("boom in slot")
QtCore.QTimer.singleShot(0, boom)
QtCore.QTimer.singleShot(50, app.quit)
app.exec()
print("alive")
