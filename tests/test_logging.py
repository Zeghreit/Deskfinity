import os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class Logging(unittest.TestCase):
    def run_script(self, mode):
        appdata = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, os.path.join(HERE, "slot_crash.py"), appdata, mode],
                           capture_output=True, text=True, timeout=60)
        return r, os.path.join(appdata, "Deskfinity", "deskfinity.log")

    def test_slot_exception_is_logged_and_survived(self):
        r, logp = self.run_script("hook")
        self.assertIn("alive", r.stdout, r.stderr)
        with open(logp, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("Unhandled exception", text)
        self.assertIn("boom in slot", text)


if __name__ == "__main__":
    unittest.main()
