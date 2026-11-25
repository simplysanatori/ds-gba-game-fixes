# Widescreen

Widescreen hacks for DS games from [TWiLight Menu++](https://github.com/DS-Homebrew/TWiLightMenu). With one of them a game draws its 3D scenes for a 16:10 top screen. 2D pictures (menus, text, sprites) are stretched with the screen.

No hack is stored here. [twilight-index.tsv](twilight-index.tsv) lists them: the game code, the CRC16 of the game's header (`FFFF` fits every version of the game), the file in TWiLight Menu++'s repository at one commit, its size and checksums, and the game's name where TWiLight Menu++'s list has one for it. An app finds the game there and downloads that one file from TWiLight Menu++'s repository when you install it.

## Credits

The hacks are by RadDude McCoolguy, fintogive, KazoWAR, Vague Rant, [gamemasterplc](https://github.com/gamemasterplc), [Rocket Robz](https://github.com/RocketRobz), [ChampionLeake](https://github.com/ChampionLeake), [DeadSkullzJr](https://github.com/DeadSkullzJr), [spellboundtriangle](https://github.com/spellboundtriangle) and [LedyBacer](https://github.com/LedyBacer), as TWiLight Menu++'s README credits them. Its list of games also names CheatFreak47, deisuke1234 and icup321.

## Licence

TWiLight Menu++ is under the [GPL-3.0](https://github.com/DS-Homebrew/TWiLightMenu/blob/master/LICENSE). The index is derived from its repository and shared under the same licence. Changes: reduced to game code, CRC16, file name, size, checksums and name. Which of the list's names is a game code's comes from the titles in this repository's [cheats index](../cheats/README.md).

The tools in `tools/` are under this repository's own licence.

## Left out

- **New Super Mario Bros. (USA), Mario Kart DS (USA) and Super Mario 64 DS (USA) with an xdelta patch:** TWiLight Menu++'s list links these patches on Dropbox, with no author or licence given. Its repository has only an empty file for each patched ROM, which the index keeps with size 0. Mario Kart DS and Super Mario 64 DS have a normal hack too.
