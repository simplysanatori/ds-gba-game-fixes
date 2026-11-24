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

## Rules for a fix

- **Cheats:** use standard Action Replay codes on DS, so they work in melonDS, DeSmuME, TWiLight Menu++ and flash cartridges. Say the code type on GBA and Game Boy.
- **Guards:** where the format allows it, compare the original value before writing, so the code does nothing on another version.
- **Version:** name the game code, the region and the revision the fix targets.
- **Testing:** test in at least one emulator, with before/after screenshots of the same scene. List what wasn't tested in the game's README.
- **Other people's work:** link to the author's page. Copy a file here only with the author's permission or a licence that allows it, with credit.
- **Never:** game files, or patches that carry a game's own data beyond what the change needs.

## How this was made

I started this project and used AI (Claude) to speed up development. I write, review and fix code by hand all the way through, keep the AI's work checked and reined in, and aim to keep the patches as lightweight as possible.
