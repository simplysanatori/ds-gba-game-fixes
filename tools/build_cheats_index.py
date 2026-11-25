#!/usr/bin/env python3
"""Builds cheats/libretro-index.tsv: which libretro-database cheat file belongs to which ROM.

The app (Azahar VR / Azahar for Frame) downloads the index from this repo at a pinned commit, finds
the player's game in it by game code and the CRC32 of the whole ROM file, and fetches that one
cheat file from libretro-database at the commit the index names. Nothing of libretro's is copied
here: the index holds only game codes, checksums and file names.

Inputs, all from one libretro-database checkout (or its GitHub listing), read offline:
  * metadat/no-intro/<system>.dat   clrmamepro DAT: the games, their CRC32 and serial (game code)
  * cht/<system>/                   the folder of cheat files (only the names are read)

A DAT game gets the cheat file with its own name; failing that, the file for the same title
(everything before the first "(") whose region tags fit and whose revision tag is the same.
"World" and "Unknown" fit any region, "Europe" fits each European country. A file with no region
tag fits any region on Game Boy and Game Boy Color only (their files rarely name one); on DS and
GBA a code is for one region's memory layout.

Usage:
  build_cheats_index.py --libretro-commit <40 hex> \
      --system nds "Nintendo - Nintendo DS.dat" cht/"Nintendo - Nintendo DS" \
      --system gba ... --system gbc ... --system gb ... --out cheats/libretro-index.tsv
  build_cheats_index.py --check cheats/libretro-index.tsv

The cheat-file argument is a folder, or a text file with one file name a line.

Index format, as read by the app (frame_cores/cheat_db.cpp):
  azahar-cheat-index 1
  libretro <40 hex>
  <nds|gba|gb|gbc> TAB <game code or -> TAB <8 hex CRC32> TAB <cht file name, no .cht>
"""
import argparse
import os
import re
import sys

MAGIC = "azahar-cheat-index 1"
SYSTEMS = ("nds", "gba", "gb", "gbc")
HAS_CODE = ("nds", "gba")
MAX_NAME = 200  # as the app: longer names are refused

REGIONS = {
    "world", "usa", "europe", "japan", "asia", "australia", "brazil", "canada", "china", "france",
    "germany", "hong kong", "italy", "korea", "mexico", "netherlands", "russia", "scandinavia",
    "spain", "sweden", "taiwan", "uk", "unknown", "denmark", "finland", "norway", "poland",
    "portugal", "greece", "india", "ireland", "israel", "new zealand", "south africa",
    "switzerland", "turkey", "ukraine",
}
REGION_ANY = {"world", "unknown"}
# libretro names one file "(Europe)" where No-Intro has a game for each country
EUROPE = {"europe", "denmark", "finland", "france", "germany", "greece", "ireland", "italy",
          "netherlands", "norway", "poland", "portugal", "russia", "scandinavia", "spain", "sweden",
          "switzerland", "uk"}


def valid_name(name):
    """A name the app accepts: no folder part, no control characters, not hidden."""
    if not name or len(name.encode("utf-8")) > MAX_NAME or name.startswith("."):
        return False
    return not any(ord(c) < 0x20 or ord(c) == 0x7F or c in "/\\" for c in name)


def squash(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def split_name(name):
    """(title, region set, other tags) of "Pokemon - X (USA, Europe) (Rev 1) (Code Breaker)"."""
    title = name.split("(", 1)[0].strip()
    regions, others = set(), []
    for tag in re.findall(r"\(([^)]*)\)", name):
        parts = [p.strip().lower() for p in tag.split(",")]
        if parts and all(p in REGIONS for p in parts):
            regions.update(parts)
        else:
            others.append(tag.strip().lower())
    return title, regions, others


def revision(others):
    return sorted(t for t in others if re.fullmatch(r"rev [0-9a-z]+|v[0-9][0-9.]*", t))


def parse_dat(text):
    """The games of a clrmamepro DAT: [{name, code, crc}], one per ROM with a CRC32."""
    games = []
    for block in re.split(r"^game \(\s*$", text, flags=re.M)[1:]:
        name = re.search(r'^\s*name "(.*)"\s*$', block, flags=re.M)
        rom = re.search(r'^\s*rom \( name "(?:.*)" size \d+ crc ([0-9A-Fa-f]{8})\b(.*)\)\s*$',
                        block, flags=re.M)
        if not name or not rom:
            continue
        serial = re.search(r'\bserial "([^"]*)"', rom.group(2)) or re.search(
            r'^\s*serial "([^"]*)"', block, flags=re.M)
        code = serial.group(1) if serial else ""
        games.append({
            "name": name.group(1),
            "code": code if re.fullmatch(r"[A-Za-z0-9]{4}", code) else "",
            "crc": rom.group(1).upper(),
        })
    return games


def read_cht_names(path):
    """The cheat files' names (without .cht), from a folder or a text file."""
    if os.path.isdir(path):
        raw = [n for n in os.listdir(path) if n.lower().endswith(".cht")]
    else:
        with open(path, encoding="utf-8") as f:
            raw = [line.strip("\r\n") for line in f if line.strip()]
    return sorted({n[:-4] if n.lower().endswith(".cht") else n for n in raw})


class Chooser:
    """Which cheat file a DAT game gets."""

    def __init__(self, cht_names, any_region_ok):
        self.any_region_ok = any_region_ok
        self.names = set(cht_names)
        self.by_title = {}
        for n in sorted(cht_names):
            title, regions, others = split_name(n)
            self.by_title.setdefault(squash(title), []).append((n, regions, revision(others)))

    def choose(self, game_name):
        if game_name in self.names:
            return game_name
        title, regions, others = split_name(game_name)
        want_rev = revision(others)
        best = None
        for n, cht_regions, cht_rev in self.by_title.get(squash(title), []):
            if cht_rev != want_rev:
                continue
            if not cht_regions:
                if not self.any_region_ok:
                    continue
                rank = 3
            elif cht_regions & REGION_ANY:
                rank = 2
            elif cht_regions & regions or ("europe" in cht_regions and regions & EUROPE):
                rank = 1
            else:
                continue
            if best is None or rank < best[0]:
                best = (rank, n)
        return best[1] if best else None


def build(commit, systems):
    """The index text. `systems` is [(tag, dat text, cht names)]."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("the libretro commit must be 40 lower-case hex digits")
    rows = set()
    stats = []
    for tag, dat, cht_names in systems:
        if tag not in SYSTEMS:
            raise ValueError("unknown system " + tag)
        chooser = Chooser(cht_names, tag not in HAS_CODE)
        games = parse_dat(dat)
        matched = 0
        for g in games:
            name = chooser.choose(g["name"])
            if name is None or not valid_name(name):
                continue
            code = g["code"] if tag in HAS_CODE and g["code"] else "-"
            rows.add((tag, name, g["crc"], code))
            matched += 1
        stats.append("# %s: %d of %d games, %d cheat files" % (tag, matched, len(games), len(cht_names)))
    lines = [MAGIC, "libretro " + commit,
             "# Built by tools/build_cheats_index.py from libretro-database",
             "# (https://github.com/libretro/libretro-database, CC-BY-SA-4.0) at the commit above:",
             "# its No-Intro DATs (metadat/no-intro) and the names of its cht files.",
             "# Changes: reduced to game code, CRC32 and cht file name, matched by name.",
             "# Shared under CC-BY-SA-4.0, as that licence requires; no cheat file is copied here."]
    lines += stats
    for tag, name, crc, code in sorted(rows, key=lambda r: (SYSTEMS.index(r[0]), r[1], r[2])):
        lines.append("\t".join((tag, code, crc, name)))
    return "\n".join(lines) + "\n"


def check(text):
    """Problems in an index, by the app's rules ([] when it is fine)."""
    problems = []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    body = [(i + 1, l) for i, l in enumerate(lines) if l and not l.startswith("#")]
    if len(body) < 2 or body[0][1] != MAGIC:
        return ["first line is not %r" % MAGIC]
    if not re.fullmatch(r"libretro [0-9a-f]{40}", body[1][1]):
        problems.append("line %d: not a libretro commit" % body[1][0])
    for n, line in body[2:]:
        f = line.split("\t")
        if len(f) != 4:
            problems.append("line %d: not four fields" % n)
        elif f[0] not in SYSTEMS:
            problems.append("line %d: unknown system" % n)
        elif not (f[1] == "-" or re.fullmatch(r"[A-Za-z0-9]{4}", f[1])):
            problems.append("line %d: bad game code" % n)
        elif f[0] not in HAS_CODE and f[1] != "-":
            problems.append("line %d: a Game Boy game has no code" % n)
        elif not re.fullmatch(r"[0-9A-Fa-f]{8}", f[2]):
            problems.append("line %d: bad CRC32" % n)
        elif not valid_name(f[3]):
            problems.append("line %d: bad file name" % n)
    if len(text.encode("utf-8")) > 4 * 1024 * 1024 or len(body) > 30000:
        problems.append("over the app's limits")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--libretro-commit")
    ap.add_argument("--system", nargs=3, action="append", metavar=("TAG", "DAT", "CHT"), default=[])
    ap.add_argument("--out")
    ap.add_argument("--check", metavar="INDEX")
    a = ap.parse_args(argv)
    if a.check:
        with open(a.check, encoding="utf-8") as f:
            problems = check(f.read())
        for p in problems:
            print(p, file=sys.stderr)
        return 1 if problems else 0
    if not a.libretro_commit or not a.system or not a.out:
        ap.error("--libretro-commit, --system and --out are needed")
    systems = []
    for tag, dat, cht in a.system:
        with open(dat, encoding="utf-8", errors="replace") as f:
            systems.append((tag, f.read(), read_cht_names(cht)))
    text = build(a.libretro_commit, systems)
    problems = check(text)
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    sys.stdout.write("".join(l + "\n" for l in text.split("\n") if l.startswith("# ") and ": " in l))
    return 0


if __name__ == "__main__":
    sys.exit(main())
