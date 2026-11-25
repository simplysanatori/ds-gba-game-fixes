#!/usr/bin/env python3
"""Tests for build_cheats_index.py. Run: python3 -I -m unittest discover -s tools"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_cheats_index as b  # noqa: E402

COMMIT = "f" * 40

DAT = '''clrmamepro (
	name "Nintendo - Nintendo DS"
)

game (
	name "007 - Blood Stone (France)"
	region "France"
	serial "BJBF"
	rom ( name "007 - Blood Stone (France).nds" size 67108864 crc 1fccf595 md5 AA sha1 BB serial "BJBF" )
)
game (
	name "007 - Blood Stone (Germany)"
	region "Germany"
	serial "BJBD"
	rom ( name "007 - Blood Stone (Germany).nds" size 67108864 crc 306109D2 md5 AA sha1 BB serial "BJBD" )
)
game (
	name "Game With Odd Serial (USA)"
	rom ( name "Game With Odd Serial (USA).nds" size 1 crc 00000001 serial "A/B\\x" )
)
game (
	name "No Rom Line (USA)"
)
'''


class Dat(unittest.TestCase):
    def test_parse(self):
        games = b.parse_dat(DAT)
        self.assertEqual([g["name"] for g in games],
                         ["007 - Blood Stone (France)", "007 - Blood Stone (Germany)",
                          "Game With Odd Serial (USA)"])
        self.assertEqual(games[0]["crc"], "1FCCF595")  # upper case
        self.assertEqual(games[0]["code"], "BJBF")
        self.assertEqual(games[2]["code"], "")  # not four letters or digits: none

    def test_garbage(self):
        self.assertEqual(b.parse_dat(""), [])
        self.assertEqual(b.parse_dat("game (\n\tname \"x\"\n)\n"), [])
        self.assertEqual(b.parse_dat("\x00\xff" * 100), [])


class Choose(unittest.TestCase):
    def test_exact_name_first(self):
        c = b.Chooser(["Game (USA)", "Game (USA) (Code Breaker)"], False)
        self.assertEqual(c.choose("Game (USA)"), "Game (USA)")

    def test_region_and_europe(self):
        c = b.Chooser(["007 - Blood Stone (Europe)", "007 - Blood Stone (USA)"], False)
        self.assertEqual(c.choose("007 - Blood Stone (France)"), "007 - Blood Stone (Europe)")
        self.assertEqual(c.choose("007 - Blood Stone (USA, Europe)"), "007 - Blood Stone (Europe)")
        self.assertIsNone(c.choose("007 - Blood Stone (Japan)"))

    def test_world_and_unknown_fit(self):
        c = b.Chooser(["Game (World) (Code Breaker)", "Other (Unknown)"], False)
        self.assertEqual(c.choose("Game (Japan)"), "Game (World) (Code Breaker)")
        self.assertEqual(c.choose("Other (USA)"), "Other (Unknown)")

    def test_no_region_only_for_game_boy(self):
        names = ["1942"]
        self.assertEqual(b.Chooser(names, True).choose("1942 (Japan, USA)"), "1942")
        self.assertIsNone(b.Chooser(names, False).choose("1942 (Japan, USA)"))

    def test_revisions_must_agree(self):
        c = b.Chooser(["Pokemon - FireRed Version (USA, Europe)",
                       "Pokemon - FireRed Version (USA, Europe) (Rev 1)"], False)
        self.assertEqual(c.choose("Pokemon - FireRed Version (USA) (Rev 1)"),
                         "Pokemon - FireRed Version (USA, Europe) (Rev 1)")
        self.assertEqual(c.choose("Pokemon - FireRed Version (USA)"),
                         "Pokemon - FireRed Version (USA, Europe)")
        self.assertIsNone(b.Chooser(["G (USA)"], False).choose("G (USA) (Rev 2)"))

    def test_other_title_never(self):
        c = b.Chooser(["Pokemon - FireRed Version (USA)"], False)
        self.assertIsNone(c.choose("Pokemon - LeafGreen Version (USA)"))
        self.assertIsNone(c.choose("Pokemon (USA)"))


class Build(unittest.TestCase):
    def build(self, names, dat=DAT, tag="nds"):
        return b.build(COMMIT, [(tag, dat, names)])

    def test_output_is_valid_and_sorted(self):
        text = self.build(["007 - Blood Stone (Germany)", "007 - Blood Stone (France)"])
        self.assertEqual(b.check(text), [])
        lines = [l for l in text.split("\n") if l and not l.startswith("#")]
        self.assertEqual(lines[0], b.MAGIC)
        self.assertEqual(lines[1], "libretro " + COMMIT)
        self.assertEqual(lines[2:], [
            "nds\tBJBF\t1FCCF595\t007 - Blood Stone (France)",
            "nds\tBJBD\t306109D2\t007 - Blood Stone (Germany)",
        ])
        self.assertEqual(text, self.build(["007 - Blood Stone (France)",
                                           "007 - Blood Stone (Germany)"]))  # same for any order

    def test_game_boy_has_no_code(self):
        dat = 'game (\n\tname "1942 (USA)"\n\trom ( name "1942 (USA).gb" size 1 crc 5449cac0 serial "ABCD" )\n)\n'
        text = self.build(["1942"], dat, "gb")
        self.assertIn("gb\t-\t5449CAC0\t1942\n", text)
        self.assertEqual(b.check(text), [])

    def test_refuses_names_with_a_path(self):
        dat = 'game (\n\tname "../x"\n\trom ( name "../x.nds" size 1 crc 00000001 )\n)\n'
        text = self.build(["../x", "a/b", ".hidden", "ok\x01"], dat)
        self.assertNotIn("../x", text)
        self.assertEqual(b.check(text), [])

    def test_commit_must_be_a_commit(self):
        for bad in ("main", "F" * 40, "f" * 39, ""):
            with self.assertRaises(ValueError):
                b.build(bad, [("nds", DAT, [])])
        with self.assertRaises(ValueError):
            b.build(COMMIT, [("n64", DAT, [])])

    def test_names_from_a_folder_and_a_list(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "cht"))
            for n in ("A (USA).cht", "B (USA).CHT", "notes.txt"):
                open(os.path.join(d, "cht", n), "w").close()
            self.assertEqual(b.read_cht_names(os.path.join(d, "cht")), ["A (USA)", "B (USA)"])
            lst = os.path.join(d, "names.txt")
            with open(lst, "w") as f:
                f.write("A (USA).cht\n\nB (USA)\n")
            self.assertEqual(b.read_cht_names(lst), ["A (USA)", "B (USA)"])


class Check(unittest.TestCase):
    GOOD = b.MAGIC + "\nlibretro " + COMMIT + "\nnds\tBJBF\t1FCCF595\tname\n"

    def test_good(self):
        self.assertEqual(b.check(self.GOOD), [])

    def test_bad(self):
        for text in ("", "x\n", b.MAGIC + "\n", b.MAGIC + "\nlibretro main\n",
                     self.GOOD + "nds\tBJBF\t1FCCF595\n",
                     self.GOOD + "n64\tBJBF\t1FCCF595\tn\n",
                     self.GOOD + "nds\tBJ\t1FCCF595\tn\n",
                     self.GOOD + "gb\tABCD\t1FCCF595\tn\n",
                     self.GOOD + "nds\tBJBF\t1FCCF59\tn\n",
                     self.GOOD + "nds\tBJBF\t1FCCF595\ta/b\n"):
            self.assertNotEqual(b.check(text), [], text)

    def test_example_index(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cheats",
                            "libretro-index.example.tsv")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(b.check(f.read()), [])


if __name__ == "__main__":
    unittest.main()
