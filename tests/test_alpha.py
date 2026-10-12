import unittest
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt
from harness import df, Base, APP, load_json


class AlphaSaved(Base):
    def test_slider_click_and_keys_are_saved(self):
        m = df.Manager(APP)
        b = df.Box(m, {"uid": "a"})
        m.boxes.append(b)
        def cleanup():
            m._status_timer.stop(); b.close(); m._ipc.close(); m.tray.hide()
        self.addCleanup(cleanup)
        slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 255)
        slider.valueChanged.connect(b.set_alpha)
        slider.triggerAction(QtWidgets.QAbstractSlider.SliderAction.SliderPageStepAdd)  # track click
        self.assertTrue(m._save_timer.isActive())
        m._save_timer.stop()
        m._write()
        saved = load_json(df.CONFIG_PATH)["boxes"][0]["alpha"]
        self.assertEqual(saved, slider.value())
        self.assertNotEqual(saved, 140)


if __name__ == "__main__":
    unittest.main()
