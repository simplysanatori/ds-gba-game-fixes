#!/usr/bin/env python3
"""Tests for build_widescreen_index.py. Run: python3 -I -m unittest discover -s tools"""
import hashlib
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_widescreen_index as b  # noqa: E402

COMMIT = "f" * 40
# An "if equal", a 16 bit write, end all. No hack's own addresses.
HACK = struct.pack("<6I", 0x92000010, 0x1555, 0x12000010, 0x199A, 0xD2000000, 0)
LIST = ("﻿A Game (USA/Europe)\nA Game (Japan) (Rev 1)\n"
        "Other (USA)/Another Name (Europe, Australia)\n"
        "Pokémon - Diamond/Pearl Version (USA)\n"
        "Patched Game (USA) (Requires xdelta patch here: https://example.org/x.xdelta?dl=0)\n"
        "\nNOTES:\n* A Game (Korea)\n")
CODES = ("azahar-cheat-index 1\nlibretro " + COMMIT + "\n"
         "nds\tAAAE\t00000001\tA Game (USA)\nnds\tBBBV\t00000002\tAnother Name (Europe, Australia)\n"
         "nds\tPPAE\t00000003\tPokemon - Pearl Version (USA)\ngba\tCCCE\t00000004\tA Game (USA)\n")


def codes(*words):
    return struct.pack("<%dI" % len(words), *words)


class Codes(unittest.TestCase):
    def test_hack(self):
        self.assertEqual(b.why_not_codes(HACK), "")
        for kind in (0x0, 0x1, 0x2, 0x5, 0x6, 0x9, 0xB):
            self.assertEqual(b.why_not_codes(codes(kind << 28, 0)), "")
        for kind in (0xD0, 0xD2, 0xDC):
            self.assertEqual(b.why_not_codes(codes(kind << 24, 0)), "")

    def test_copy(self):
        self.assertEqual(b.why_not_codes(codes(0xE2000000, 8, 1, 2)), "")
        self.assertEqual(b.why_not_codes(codes(0xE2000000, 0x44, *range(18))), "")  # rounded up
        self.assertEqual(b.why_not_codes(codes(0xE2000000, 9, 1, 2)), "a copy past the end")
        self.assertEqual(b.why_not_codes(codes(0xE2000000, 0xFFFFFFFF)), "a copy past the end")

    def test_not_codes(self):
        self.assertEqual(b.why_not_codes(b""), "empty")
        self.assertEqual(b.why_not_codes(HACK[:-4]), "not whole codes")
        self.assertEqual(b.why_not_codes(bytes(b.MAX_FILE + 8)), "too large")
        for a in (0x30000000, 0x40000000, 0x70000000, 0xA0000000, 0xC0000000, 0xC4000000,
                  0xD1000000, 0xD3000000, 0xF0000000):
            self.assertIn("code type", b.why_not_codes(codes(a, 0)))


class Names(unittest.TestCase):
    def setUp(self):
        self.games, self.titles = b.parse_list(LIST), b.parse_codes(CODES)

    def name(self, code):
        return b.game_name(code, self.titles, self.games)

    def test_region(self):
        self.assertEqual(self.name("AAAE"), "A Game (USA/Europe)")
        self.assertEqual(self.name("AAAP"), "A Game (USA/Europe)")  # by the first three letters
        self.assertEqual(self.name("AAAJ"), "A Game (Japan)")  # without its revision
        self.assertEqual(self.name("AAAK"), "")  # what follows NOTES is no game

    def test_lines(self):
        self.assertEqual(self.name("BBBV"), "Another Name (Europe, Australia)")
        self.assertEqual(self.name("PPAE"), "Pokémon - Diamond/Pearl Version (USA)")
        self.assertEqual(self.name("CCCE"), "")  # a GBA game
        self.assertEqual(self.name("ZZZE"), "")
        self.assertIn("Patched Game (USA)", [g[2] for g in self.games])

    def test_garbage(self):
        self.assertEqual(b.parse_list(""), [])
        self.assertEqual(b.parse_codes("\x00\xff\n\t\t\t\n"), {})


class Build(unittest.TestCase):
    def build(self, files, sha=None):
        with tempfile.TemporaryDirectory() as d:
            tree = {"tree": []}
            for name, data in files.items():
                with open(os.path.join(d, name), "wb") as f:
                    f.write(data)
                tree["tree"].append({"path": name, "type": "blob", "size": len(data),
                                     "sha": sha or b.blob_sha1(data)})
            return b.build(COMMIT, tree, d, LIST, CODES)

    def test_rows(self):
        text, left = self.build({"AAAE-38D.bin": HACK, "AAAE-FFFF.bin": HACK})
        self.assertEqual(b.check(text), [])
        self.assertEqual(left, [])
        rows = [l.split("\t") for l in text.split("\n") if l and not l.startswith("#")][2:]
        sha256 = hashlib.sha256(HACK).hexdigest()
        self.assertEqual(rows[0], ["AAAE", "038D", "AAAE-38D.bin", "24", b.blob_sha1(HACK), sha256,
                                   "A Game (USA/Europe)"])
        self.assertEqual(rows[1][1:3], ["FFFF", "AAAE-FFFF.bin"])
        self.assertIn("# 2 hacks for 1 game codes, 1 for any version", text)

    def test_empty_stays_without_a_hack(self):
        text, left = self.build({"AAAE-1234.bin": b"", "AAAE-FFFF.bin": HACK})
        self.assertEqual(b.check(text), [])
        self.assertIn("AAAE\t1234\tAAAE-1234.bin\t0\t", text)
        self.assertEqual([x[0] for x in left], ["AAAE-1234.bin"])
        self.assertIn("# 1 hacks", text)

    def test_left_out(self):
        text, left = self.build({"AAAE-1234.bin": codes(0xC0000000, 5), "notes.txt": b"x",
                                 "AAAE-12345.bin": HACK})
        self.assertEqual(sorted(x[0] for x in left),
                         ["AAAE-1234.bin", "AAAE-12345.bin", "notes.txt"])
        self.assertIn("# 0 hacks", text)
        self.assertIn("# left out: AAAE-1234.bin (code type C)", text)

    def test_refuses(self):
        with self.assertRaises(ValueError):
            self.build({"AAAE-1234.bin": HACK}, sha="0" * 40)  # not the tree's file
        with self.assertRaises(ValueError):
            self.build({"AAAE-0012.bin": HACK, "AAAE-12.bin": HACK})  # the same game twice
        for commit in ("main", "F" * 40, ""):
            with self.assertRaises(ValueError):
                b.build(commit, {"tree": []}, ".", "", "")
        with self.assertRaises(ValueError):
            b.build(COMMIT, {"tree": [], "truncated": True}, ".", "", "")


class Check(unittest.TestCase):
    ROW = "\t".join(("AAAE", "038D", "AAAE-38D.bin", "24", "a" * 40, "b" * 64, "A Game")) + "\n"
    HEAD = b.MAGIC + "\ntwilight " + COMMIT + "\n"

    def test_good(self):
        self.assertEqual(b.check(self.HEAD + "# a note\n" + self.ROW), [])

    def test_bad(self):
        for text in ("", "x\n", b.MAGIC + "\n", b.MAGIC + "\ntwilight main\n", self.HEAD + "a\tb\n",
                     self.HEAD + self.ROW * 2,
                     self.HEAD + self.ROW.replace("AAAE-38D.bin", "../AAAE-38D.bin"),
                     self.HEAD + self.ROW.replace("AAAE-38D.bin", "AAAP-38D.bin"),
                     self.HEAD + self.ROW.replace("038D", "038E", 1),
                     self.HEAD + self.ROW.replace("\t24\t", "\t25\t"),
                     self.HEAD + self.ROW.replace("\t24\t", "\t9992\t"),
                     self.HEAD + self.ROW.replace("a" * 40, "a" * 39),
                     self.HEAD + self.ROW.replace("b" * 64, "B" * 64),
                     self.HEAD + self.ROW.replace("A Game", "")):
            self.assertNotEqual(b.check(text), [], text)

    def test_the_index(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "widescreen",
                            "twilight-index.tsv")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(b.check(f.read()), [])


if __name__ == "__main__":
    unittest.main()
