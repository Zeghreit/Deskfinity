import json, os, unittest
from PyQt6.QtCore import QRect
from harness import df, Base, FakeManager, APP

ONE = [QRect(0, 0, 800, 800)]
TWO = [QRect(0, 0, 800, 800), QRect(800, 0, 1920, 1080)]


class Screens(Base):
    def box(self, x, y, w=300, h=250):
        b = df.Box(FakeManager(), {"geometry": [x, y, w, h]})
        self.addCleanup(b.close)
        return b

    def test_unplugged_monitor_parks_box_and_keeps_home(self):
        b = self.box(2000, 100)
        b.fit_to_screens(ONE)
        self.assertEqual((b.x(), b.y()), (500, 100))
        self.assertEqual(b.to_dict()["geometry"][:2], [2000, 100])

    def test_monitor_returns_box_goes_home(self):
        b = self.box(2000, 100)
        b.fit_to_screens(ONE)
        b.fit_to_screens(ONE)  # repeated signal: stays parked
        self.assertEqual(b.x(), 500)
        b.fit_to_screens(TWO)
        self.assertEqual((b.x(), b.y()), (2000, 100))
        self.assertIsNone(b._home)

    def test_partly_visible_box_is_left_alone(self):
        b = self.box(700, 300)  # 100 px of header still on screen
        b.fit_to_screens(ONE)
        self.assertEqual((b.x(), b.y()), (700, 300))
        self.assertIsNone(b._home)

    def test_header_above_screen_is_pulled_down(self):
        b = self.box(100, -200)
        b.fit_to_screens(ONE)
        self.assertEqual((b.x(), b.y()), (100, 0))

    def test_box_wider_than_screen(self):
        b = self.box(5000, 10, w=1000)
        b.fit_to_screens(ONE)
        self.assertEqual(b.x(), 0)

    def test_user_move_while_parked_sticks(self):
        b = self.box(2000, 100)
        b.fit_to_screens(ONE)
        b._mode = "move"
        b.move(50, 60)
        b.mouseReleaseEvent(None)
        self.assertEqual(b.to_dict()["geometry"][:2], [50, 60])
        b.fit_to_screens(TWO)
        self.assertEqual((b.x(), b.y()), (50, 60))

    def test_home_at_origin_is_saved(self):
        # taskbar at the top: (0,0) is under it, so the box gets parked
        b = self.box(0, 0)
        b.fit_to_screens([QRect(0, 40, 800, 760)])
        self.assertEqual(b.y(), 40)
        self.assertEqual(b.to_dict()["geometry"][:2], [0, 0])

    def test_manager_fits_on_load_but_saves_home(self):
        os.makedirs(df.CONFIG_DIR, exist_ok=True)
        with open(df.CONFIG_PATH, "w") as fh:
            json.dump({"boxes": [{"uid": "far", "geometry": [5000, 50, 300, 250]}]}, fh)
        m = df.Manager(APP)
        def cleanup():
            m._status_timer.stop(); [b.close() for b in m.boxes]; m._ipc.close(); m.tray.hide()
        self.addCleanup(cleanup)
        b = m.boxes[0]
        self.assertTrue(df.header_visible(b.geometry(), df.screen_areas()))
        m._write()
        with open(df.CONFIG_PATH) as fh:
            self.assertEqual(json.load(fh)["boxes"][0]["geometry"][:2], [5000, 50])


if __name__ == "__main__":
    unittest.main()
