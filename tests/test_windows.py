"""Checks of the WinAPI code paths. They run on the Windows CI runner and
are skipped everywhere else."""
import ctypes, os, unittest
from harness import df, Base, FakeManager

NOTEPAD = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "notepad.exe")


@unittest.skipUnless(df.IS_WINDOWS, "Windows only")
class WindowsApi(Base):
    def test_jumbo_shell_icon(self):
        pm = df.shell_icon(NOTEPAD, want=96)
        self.assertIsNotNone(pm)
        self.assertFalse(pm.isNull())
        self.assertGreaterEqual(max(pm.width(), pm.height()), 32)

    def test_icon_for_missing_file_comes_from_its_type(self):
        pm = df.shell_icon(r"C:\does-not-exist\report.pdf", want=48)
        self.assertIsNotNone(pm)
        self.assertFalse(pm.isNull())

    def test_icon_cache_at_150_percent(self):
        pm = df.ICONS.get(NOTEPAD, 48, 1.5)
        self.assertEqual(max(pm.width(), pm.height()), 72)
        self.assertAlmostEqual(pm.devicePixelRatio(), 1.5)

    def test_desktop_folders(self):
        df.desktop_dir = self._orig_desktop_dir   # the real ones
        folders = df.desktop_folders()
        self.assertEqual(len(folders), 2, folders)   # user + Public
        for f in folders:
            self.assertTrue(os.path.isdir(f), f)

    def test_single_instance_mutex(self):
        self.assertTrue(df._claim_mutex())
        self.assertFalse(df._claim_mutex())          # now someone owns it

    def test_hidden_and_system_files_are_not_sorted(self):
        normal = self.touch("Desktop", "report.pdf")
        hidden = self.touch("Desktop", "secret.pdf")
        ctypes.windll.kernel32.SetFileAttributesW(hidden, 0x2)   # HIDDEN
        self.assertFalse(df.skip_for_sorting(normal))
        self.assertTrue(df.skip_for_sorting(hidden))

    def test_hotkey_registers_and_unregisters(self):
        mods, vk = df.hotkey_to_win("Ctrl+Alt+Shift+F12")
        ok = df.user32.RegisterHotKey(None, 77, mods | 0x4000, vk)
        if ok:
            self.assertTrue(df.user32.UnregisterHotKey(None, 77))
        else:   # some CI desktops refuse hotkeys; that is not our bug
            self.skipTest("RegisterHotKey unavailable: %d" % ctypes.get_last_error())

    def test_box_shows_and_paints_on_the_real_platform(self):
        b = df.Box(FakeManager(), {"items": [NOTEPAD], "geometry": [100, 100, 300, 200]})
        self.addCleanup(b.close)
        b.show()
        self.spin(200)
        b.repaint()
        self.assertTrue(b.isVisible())


if __name__ == "__main__":
    unittest.main()
