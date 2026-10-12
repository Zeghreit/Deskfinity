import unittest
from harness import df, Base

ORIGINAL = ("Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden "
            "-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass',"
            "'-File','\"%s\"'")


def ps_single_quoted_tokens(cmd):
    """Parse PowerShell single-quoted literals; fail on an unterminated one."""
    out, i = [], 0
    while True:
        i = cmd.find("'", i)
        if i < 0:
            return out
        j, buf = i + 1, []
        while True:
            if j >= len(cmd):
                raise ValueError("unterminated literal")
            if cmd[j] == "'":
                if j + 1 < len(cmd) and cmd[j + 1] == "'":
                    buf.append("'"); j += 2; continue
                break
            buf.append(cmd[j]); j += 1
        out.append("".join(buf))
        i = j + 1


class PsQuoting(Base):
    def test_plain_path_unchanged_from_original(self):
        p = r"C:\Users\Anna\AppData\Roaming\Deskfinity\_elevated_move.ps1"
        self.assertEqual(df._elevation_command(p), ORIGINAL % p)

    def test_apostrophe_path_survives(self):
        p = r"C:\Users\O'Brien\AppData\Roaming\Deskfinity\_elevated_move.ps1"
        toks = ps_single_quoted_tokens(df._elevation_command(p))
        self.assertEqual(toks[-1], '"%s"' % p)
        with self.assertRaises(ValueError):  # what the old code produced
            ps_single_quoted_tokens(ORIGINAL % p)

    def test_literal(self):
        self.assertEqual(df._ps_literal("it's"), "'it''s'")
        self.assertEqual(ps_single_quoted_tokens(df._ps_literal("a''b'")), ["a''b'"])


if __name__ == "__main__":
    unittest.main()
