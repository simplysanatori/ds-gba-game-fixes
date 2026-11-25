#!/usr/bin/env python3
"""Builds widescreen/twilight-index.tsv: which of TWiLight Menu++'s widescreen hacks fits which DS ROM.

The app (Azahar VR / Azahar for Frame) finds the player's game in the index by game code and the
CRC16 of its header, and downloads that one hack from TWiLight Menu++'s own repository at the commit
the index names, when the player asks. Nothing of it is copied here: the index holds file names,
sizes and checksums.

Inputs, all at the commit to pin:
  * the GitHub API's tree of resources/widescreen (one request):
    https://api.github.com/repos/DS-Homebrew/TWiLightMenu/git/trees/<commit>:resources%2Fwidescreen
  * resources/widescreen/ from a checkout, read for the files' SHA-256 (checked against the tree)
  * "7zfile/3DS - CFW users/Games supported with widescreen.txt", for the games' names
  * cheats/libretro-index.tsv of this repository: that list has no game codes, so a code's title
    there says which of its lines is the game's

A file is <game code>-<CRC16 of the header>.bin; FFFF fits every version of the game that has no
file of its own. Its content is Action Replay code, and a file that is anything else than the codes
the app runs is left out. An empty file stands for a ROM that a separate patch made wide already:
it is kept in the index with size 0, so that the app offers nothing for that ROM.

Usage:
  build_widescreen_index.py --commit <40 hex> --tree tree.json --files resources/widescreen \\
      --list "Games supported with widescreen.txt" --codes cheats/libretro-index.tsv \\
      --out widescreen/twilight-index.tsv
  build_widescreen_index.py --check widescreen/twilight-index.tsv

Index format, as read by the app (frame_cores/widescreen.cpp):
  azahar-widescreen-index 1
  twilight <40 hex>
  <game code> TAB <4 hex CRC16> TAB <file name> TAB <size> TAB <git blob SHA-1> TAB <SHA-256>
      TAB <name or ->
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys
import unicodedata

MAGIC = "azahar-widescreen-index 1"
MAX_FILE = 4096  # as the app
MAX_NAME = 200
MAX_ROWS = 5000
NAME_RE = re.compile(r"([A-Z0-9]{4})-([0-9A-F]{1,4})\.bin")

# The Action Replay codes the hacks use: 32, 16 and 8 bit writes; "if equal", "if not equal" and
# "if equal" on 16 bits; load an offset, add to it; end if, end all; copy what follows.
CODES = {0x0, 0x1, 0x2, 0x5, 0x6, 0x9, 0xB, 0xE}
CODES_D = {0xD0, 0xD2, 0xDC}

# The fourth letter of a game code, as the list names the regions
REGIONS = {
    "E": ("usa",), "P": ("europe",), "J": ("japan",), "K": ("korea",), "D": ("germany", "europe"),
    "F": ("france", "europe"), "S": ("spain", "europe"), "I": ("italy", "europe"),
    "O": ("usa", "europe"), "V": ("europe", "australia"), "X": ("europe",), "Y": ("europe",),
    "Z": ("europe",), "U": ("australia",), "C": ("china",), "H": ("netherlands", "europe"),
    "T": ("usa", "australia"), "L": ("usa",), "A": ("asia",), "R": ("russia", "europe"),
}


def why_not_codes(data):
    """"" when the file is whole Action Replay code of the kinds the app runs, else why not."""
    if not data:
        return "empty"
    if len(data) % 8:
        return "not whole codes"
    if len(data) > MAX_FILE:
        return "too large"
    words = struct.unpack("<%dI" % (len(data) // 4), data)
    i = 0
    while i < len(words):
        a, b = words[i], words[i + 1]
        i += 2
        if a >> 28 == 0xE:
            if b > MAX_FILE:
                return "a copy past the end"
            i += (b + 7) // 8 * 2
            if i > len(words):
                return "a copy past the end"
        elif a >> 28 == 0xD:
            if a >> 24 not in CODES_D:
                return "code type %02X" % (a >> 24)
        elif a >> 28 not in CODES:
            return "code type %X" % (a >> 28)
    return ""


def blob_sha1(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def squash(title):
    """Letters and digits only, with "Legend, The" as "The Legend" and no accents."""
    t = "".join(c for c in unicodedata.normalize("NFKD", title) if ord(c) < 128).strip()
    m = re.match(r"(.*?), (The|A|An)\b(.*)", t)
    if m:
        t = m.group(2) + " " + m.group(1) + m.group(3)
    return re.sub(r"[^a-z0-9]", "", t.lower())


def valid_name(name):
    return bool(name) and len(name.encode("utf-8")) <= MAX_NAME and \
        not any(ord(c) < 0x20 or ord(c) == 0x7F for c in name)


def titles_of(title):
    """"A - Diamond/Pearl Version" is two games: each squashed title."""
    m = re.search(r"([^ /]+)/([^ /]+)", title)
    if not m:
        return [squash(title)]
    return [squash(title[:m.start()] + t + title[m.end():]) for t in m.groups()]


def parse_list(text):
    """The list's games: [(squashed title, region text, the line's own name)]. One line may name a
    game by several titles: "X-Scape (USA)/3D Space Tank (Europe, Australia)". Names go without
    their revision: a file is for the header CRC16 in its name."""
    games = []
    for line in text.lstrip("﻿").splitlines():
        line = line.strip()
        if line == "NOTES:":
            break
        line = re.sub(r"\s*\((?:Optional|Requires) xdelta patch[^()]*(?:\([^()]*\))?[^()]*\)", "", line)
        if not line:
            continue
        for part in re.split(r"(?<=\))/", line):
            title, _, rest = part.partition("(")
            name = re.sub(r" \(Rev \d+\)", "", part.strip())
            games += [(t, rest.lower(), name) for t in titles_of(title)]
    return games


def parse_codes(text):
    """{game code: titles} of a libretro index's DS games."""
    out = {}
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) == 4 and f[0] == "nds" and f[1] != "-":
            out.setdefault(f[1], set()).add(squash(f[3].split("(", 1)[0]))
    return out


def game_name(code, titles, games):
    """The list's line for a game code, "" when no one line is its."""
    # The same game in another region has the same first three letters
    wanted = set(titles.get(code, ()))
    if not wanted:
        for other, t in titles.items():
            if other[:3] == code[:3]:
                wanted |= t
    lines = [g for g in games if g[0] in wanted]
    for region in REGIONS.get(code[3], ()):
        fits = [g for g in lines if re.search(r"\b%s\b" % region, g[1])
                and "translation" not in g[1] and "hack" not in g[1]]
        if fits:
            return fits[0][2]
    return lines[0][2] if len(lines) == 1 else ""


def build(commit, tree, files_dir, list_text, codes_text):
    """The index text, and what was left out [(file, why)]."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("the commit must be 40 lower-case hex digits")
    if tree.get("truncated"):
        raise ValueError("the tree is not whole")
    games, titles = parse_list(list_text), parse_codes(codes_text)
    rows, left_out, seen = [], [], set()
    for entry in sorted(tree["tree"], key=lambda e: e["path"]):
        name = entry["path"]
        m = NAME_RE.fullmatch(name)
        if entry.get("type") != "blob" or not m:
            left_out.append((name, "not a hack's file name"))
            continue
        with open(os.path.join(files_dir, name), "rb") as f:
            data = f.read()
        if len(data) != entry["size"] or blob_sha1(data) != entry["sha"]:
            raise ValueError("%s is not the tree's file" % name)
        why = why_not_codes(data)
        if why and why != "empty":
            left_out.append((name, why))
            continue
        code, crc = m.group(1), int(m.group(2), 16)
        if (code, crc) in seen:
            raise ValueError("%s: that game has a file already" % name)
        seen.add((code, crc))
        rows.append((code, "%04X" % crc, name, str(len(data)), entry["sha"],
                     hashlib.sha256(data).hexdigest(),
                     game_name(code, titles, games) if data else "-"))
        if why:
            left_out.append((name, "empty: for a ROM a separate patch made wide already"))
    rows = [r[:6] + (r[6] if valid_name(r[6]) else "-",) for r in rows]
    hacks = [r for r in rows if r[3] != "0"]
    lines = [MAGIC, "twilight " + commit,
             "# Built by tools/build_widescreen_index.py from TWiLight Menu++",
             "# (https://github.com/DS-Homebrew/TWiLightMenu, GPL-3.0) at the commit above: the file",
             "# list of resources/widescreen and the names in its \"Games supported with widescreen\".",
             "# Shared under GPL-3.0, as TWiLight Menu++; no hack is copied here.",
             "# Widescreen hacks: RadDude McCoolguy, fintogive, KazoWAR, Vague Rant, gamemasterplc,",
             "# Rocket Robz, ChampionLeake, DeadSkullzJr, spellboundtriangle, LedyBacer, CheatFreak47,",
             "# deisuke1234, icup321 (TWiLight Menu++'s README.md and its list of games).",
             "# %d hacks for %d game codes, %d for any version, %d with a name"
             % (len(hacks), len({r[0] for r in hacks}), sum(r[1] == "FFFF" for r in hacks),
                sum(r[6] != "-" for r in hacks))]
    lines += ["# left out: %s (%s)" % x for x in left_out]
    lines += ["\t".join(r) for r in rows]
    return "\n".join(lines) + "\n", left_out


def check(text):
    """Problems in an index, by the app's rules ([] when it is fine)."""
    problems, seen = [], set()
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    body = [(i + 1, l) for i, l in enumerate(lines) if l and not l.startswith("#")]
    if len(body) < 2 or body[0][1] != MAGIC:
        return ["first line is not %r" % MAGIC]
    if not re.fullmatch(r"twilight [0-9a-f]{40}", body[1][1]):
        problems.append("line %d: not a TWiLight Menu++ commit" % body[1][0])
    for n, line in body[2:]:
        f = line.split("\t")
        if len(f) != 7:
            problems.append("line %d: not seven fields" % n)
            continue
        m = NAME_RE.fullmatch(f[2])
        if not m or m.group(1) != f[0] or not re.fullmatch(r"[0-9A-F]{4}", f[1]) or \
                int(m.group(2), 16) != int(f[1], 16):
            problems.append("line %d: bad game code, CRC16 or file name" % n)
        elif (f[0], f[1]) in seen:
            problems.append("line %d: that game has a line already" % n)
        elif not re.fullmatch(r"[0-9]{1,4}", f[3]) or int(f[3]) > MAX_FILE or int(f[3]) % 8:
            problems.append("line %d: bad size" % n)
        elif not re.fullmatch(r"[0-9a-f]{40}", f[4]) or not re.fullmatch(r"[0-9a-f]{64}", f[5]):
            problems.append("line %d: bad checksum" % n)
        elif not valid_name(f[6]):
            problems.append("line %d: bad name" % n)
        seen.add((f[0], f[1]))
    if len(text.encode("utf-8")) > 1024 * 1024 or len(body) > MAX_ROWS:
        problems.append("over the app's limits")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    for name in ("commit", "tree", "files", "list", "codes", "out"):
        ap.add_argument("--" + name)
    ap.add_argument("--check", metavar="INDEX")
    a = ap.parse_args(argv)
    if a.check:
        with open(a.check, encoding="utf-8") as f:
            problems = check(f.read())
        for p in problems:
            print(p, file=sys.stderr)
        return 1 if problems else 0
    if not all((a.commit, a.tree, a.files, a.list, a.codes, a.out)):
        ap.error("--commit, --tree, --files, --list, --codes and --out are needed")
    with open(a.tree, encoding="utf-8") as f:
        tree = json.load(f)
    with open(a.list, encoding="utf-8") as f:
        list_text = f.read()
    with open(a.codes, encoding="utf-8") as f:
        codes_text = f.read()
    text, _ = build(a.commit, tree, a.files, list_text, codes_text)
    problems = check(text)
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    sys.stdout.write("".join(l + "\n" for l in text.split("\n") if l.startswith("# ")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
