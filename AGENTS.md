# AGENTS.md

Technical detail kept out of the README: how the repo is laid out and how a fix is added. Each game's own `AGENTS.md` explains its fix. The layout follows [3ds-game-fixes](https://github.com/simplysanatori/3ds-game-fixes) wherever the systems allow it.

## Layout

```
games/<ds|gba|gb>/<game>-<region>/
  README.md                        short page for players
  AGENTS.md                        how the fix was found and how it works
  patch/<game code>/<name>.<ips|bps|ups|xdelta>
  cheats/<game code>.cht           RetroArch .cht format
  images/                          before/after screenshots
catalog/mods.json                  list of mods and patches an app can install
cheats/libretro-index.tsv          which libretro-database cheat file is which ROM (built, see below)
tools/build_cheats_index.py        builds that index offline; tools/test_build_cheats_index.py tests it
catalog/textures.json              list of texture packs an app can install
docs/USER_GUIDE.md                 patches and cheats, shared by all games
```

- `gb` holds Game Boy and Game Boy Color games.
- Folder names are lowercase, with the region last, as in 3ds-game-fixes.
- A DS or GBA game is named by its 4-letter game code (`ADAE`). Where one code covers several revisions, the game's `README.md` gives the revision and the CRC32 of the whole file. Game Boy games have no reliable code: use the CRC32.
- Add each new game to the **Games** list in `README.md`.
- Texture packs get a page in `docs/`. The packs themselves are never in this repo.

## Catalogues

Both start empty. They keep the top-level shape of the ones in 3ds-game-fixes (`schema`, `mods` and `versions`; `schema` and `packs`), so the same tools can read them. Entries name games with `game_codes` in place of `title_ids`. Nothing reads them yet, so the entry format may still change.

## Cheat index

The apps' Cheats tab downloads cheats for DS, GBA and Game Boy games from [libretro-database](https://github.com/libretro/libretro-database) (`cht/`, CC-BY-SA-4.0). No cheat file of libretro's is stored here. The index is derived from libretro-database's No-Intro DATs and the names of its cht files, so it is shared under CC-BY-SA-4.0 (its header says so, names the source and the commit, and states the change: reduced to game code, CRC32 and file name). The repository's MIT licence covers the tools, not the index. `cheats/libretro-index.tsv` says which of its files belongs to which ROM: one line a game, `<nds|gba|gb|gbc> TAB <game code or -> TAB <CRC32 of the whole ROM file> TAB <cht file name>`, under a header naming the libretro commit it was built for. The app pins both this repo's commit and that one, and reads the index only from the pinned commit.

To rebuild it, take a libretro-database checkout at the commit to pin, and run `python3 -I tools/build_cheats_index.py --libretro-commit <commit> --system nds "<metadat/no-intro/Nintendo - Nintendo DS.dat>" "<cht/Nintendo - Nintendo DS>" ...` for `nds`, `gba`, `gbc` and `gb`, with `--out cheats/libretro-index.tsv`. `--check <file>` checks an index by the app's rules. `cheats/libretro-index.example.tsv` is a short real example. After a rebuild, push, then pin the new commit in the app (`kFixesCommit` and `kLibretroCommit` in `frame_cores/cheat_db.h`).

## Rules for a fix

- **Cheats:** use standard Action Replay codes on DS, so they work in melonDS, DeSmuME, TWiLight Menu++ and flash cartridges. Say the code type on GBA and Game Boy.
- **Guards:** where the format allows it, compare the original value before writing, so the code does nothing on another version.
- **Version:** name the game code, the region and the revision the fix targets.
- **Testing:** test in at least one emulator, with before/after screenshots of the same scene. List what wasn't tested in the game's README.
- **Other people's work:** link to the author's page. Copy a file here only with the author's permission or a licence that allows it, with credit.
- **Never:** game files, or patches that carry a game's own data beyond what the change needs.

## How this was made

I started this project and used AI (Claude) to speed up development. I write, review and fix code by hand all the way through, keep the AI's work checked and reined in, and aim to keep the patches as lightweight as possible.
