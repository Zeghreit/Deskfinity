import os, subprocess, sys, time, unittest
from harness import df, Base, APP

SECOND = """
import sys, os
sys.dont_write_bytecode = True
sys.path.insert(0, %r)
import deskfinity
deskfinity.main()
print("second-exited")
""" % os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SingleInstance(Base):
    def manager(self):
        m = df.Manager(APP)
        def cleanup():
            for b in m.boxes:
                b.close()
            m._ipc.close()
            m.tray.hide()
        self.addCleanup(cleanup)
        return m

    def test_no_instance_means_free(self):
        self.assertFalse(df.another_instance_running())

    def test_running_instance_is_detected_and_shows_boxes(self):
        m = self.manager()
        m.boxes.append(df.Box(m, {"uid": "x"}))
        m.hide_all()
        self.assertFalse(m.boxes[0].isVisible())
        self.assertTrue(df.another_instance_running())
        self.spin(100)
        self.assertTrue(m.boxes[0].isVisible())

    def test_second_process_exits_and_first_keeps_running(self):
        m = self.manager()
        m.boxes.append(df.Box(m, {"uid": "y"}))
        m.hide_all()
        env = dict(os.environ, APPDATA=self.root)
        p = subprocess.Popen([sys.executable, "-c", SECOND], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        deadline = time.time() + 30
        while p.poll() is None and time.time() < deadline:
            self.spin(50)
        if p.poll() is None:
            p.kill()
            self.fail("second instance did not exit")
        out = p.communicate()[0]
        self.assertEqual(p.returncode, 0, out)
        self.assertIn("second-exited", out)
        self.assertIn("Already running", out)
        self.assertTrue(m._ipc.isListening())
        self.spin(50)
        self.assertTrue(m.boxes[0].isVisible(), "knock from the other process was lost")

    def test_after_first_closes_a_new_one_may_start(self):
        m = self.manager()
        m._ipc.close()
        self.assertFalse(df.another_instance_running())


if __name__ == "__main__":
    unittest.main()
