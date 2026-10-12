import os, sys, tempfile, unittest
from harness import df


class Portable(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self._env = os.environ.pop("DESKFINITY_DATA", None)
        self._frozen = getattr(sys, "frozen", None)
        self._exe = sys.executable

    def tearDown(self):
        if self._env is not None:
            os.environ["DESKFINITY_DATA"] = self._env
        if self._frozen is None:
            sys.__dict__.pop("frozen", None)
        else:
            sys.frozen = self._frozen
        sys.executable = self._exe

    def frozen_at(self, *parts):
        sys.frozen = True
        sys.executable = os.path.join(self.root, *parts)

    def test_data_folder_next_to_exe(self):
        os.makedirs(os.path.join(self.root, "DeskfinityData"))
        self.frozen_at("Deskfinity.exe")
        self.assertEqual(df.data_dir(), os.path.join(self.root, "DeskfinityData"))

    def test_exe_in_dist_uses_folder_one_level_up(self):
        os.makedirs(os.path.join(self.root, "DeskfinityData"))
        self.frozen_at("dist", "Deskfinity.exe")
        self.assertEqual(df.data_dir(), os.path.join(self.root, "DeskfinityData"))

    def test_no_folder_means_appdata(self):
        self.frozen_at("dist", "Deskfinity.exe")
        self.assertEqual(df.data_dir(),
                         os.path.join(os.environ["APPDATA"], "Deskfinity"))

    def test_env_overrides(self):
        os.makedirs(os.path.join(self.root, "DeskfinityData"))
        self.frozen_at("Deskfinity.exe")
        os.environ["DESKFINITY_DATA"] = "/somewhere/else"
        try:
            self.assertEqual(df.data_dir(), "/somewhere/else")
        finally:
            del os.environ["DESKFINITY_DATA"]

    def test_script_mode_uses_script_folder(self):
        sys.__dict__.pop("frozen", None)
        self.assertEqual(df.program_path(), os.path.abspath(df.__file__))


if __name__ == "__main__":
    unittest.main()
