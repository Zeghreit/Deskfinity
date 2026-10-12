import os, unittest
from PyQt6 import QtGui
from harness import df, Base, APP, load_json

ALT, CTRL, SHIFT, WIN = 1, 2, 4, 8


class Parse(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(df.hotkey_to_win("Ctrl+Alt+F"), (CTRL | ALT, 0x46))
        self.assertEqual(df.hotkey_to_win("Ctrl+Shift+F5"), (CTRL | SHIFT, 0x74))
        self.assertEqual(df.hotkey_to_win("Meta+D"), (WIN, 0x44))
        self.assertEqual(df.hotkey_to_win("Alt+7"), (ALT, 0x37))
        self.assertEqual(df.hotkey_to_win("Ctrl+Alt+Space"), (CTRL | ALT, 0x20))
        self.assertEqual(df.hotkey_to_win("Shift+F24"), (SHIFT, 0x87))
        self.assertEqual(df.hotkey_to_win("Ctrl+Alt+F, Ctrl+B"), (CTRL | ALT, 0x46))

    def test_unusable(self):
        for text in ("", "F", "F5", "Ctrl+", "Ctrl+Alt+É", "garbage+++"):
            self.assertIsNone(df.hotkey_to_win(text), text)


class Settings(Base):
    def manager(self):
        m = df.Manager(APP)
        def cleanup():
            m._status_timer.stop(); m.sorter._timer.stop()
            [b.close() for b in m.boxes]; m._ipc.close(); m.tray.hide()
        self.addCleanup(cleanup)
        return m

    def test_default_and_change_persist(self):
        m = self.manager()
        self.assertEqual(m.hotkey_text(), "Ctrl+Alt+F")
        self.assertFalse(m.set_hotkey("K"))
        self.assertEqual(m.hotkey_text(), "Ctrl+Alt+F")
        self.assertTrue(m.set_hotkey("Ctrl+Shift+K"))
        m._write()
        self.assertEqual(load_json(df.CONFIG_PATH)["settings"]["hotkey"], "Ctrl+Shift+K")
        m2 = self.manager()
        self.assertEqual(m2.hotkey_text(), "Ctrl+Shift+K")

    def test_old_config_without_settings(self):
        os.makedirs(df.CONFIG_DIR, exist_ok=True)
        with open(df.CONFIG_PATH, "w") as fh:
            fh.write('{"version": 1, "boxes": [{"uid": "a"}]}')
        m = self.manager()
        self.assertEqual(m.settings, {})
        self.assertEqual(len(m.boxes), 1)

    def test_dialog_takes_first_chord(self):
        dlg = df.HotkeyDialog("Ctrl+Alt+F")
        self.addCleanup(dlg.close)
        self.assertEqual(dlg.text(), "Ctrl+Alt+F")
        dlg.edit.setKeySequence(QtGui.QKeySequence("Ctrl+Shift+J, Ctrl+K"))
        self.assertEqual(dlg.text(), "Ctrl+Shift+J")
        dlg.edit.clear()
        self.assertEqual(dlg.text(), "")


if __name__ == "__main__":
    unittest.main()
