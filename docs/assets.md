# Changing game data

The game keeps nearly all of its data in one archive on the disc, `A_FILE.BIN`, with 32
members. Their names, in order, are in `.hm/decomp/disc/a_file.txt`:

| Member | Contents (as far as is known) |
|--------|-------------------------------|
| `00_gf.bin` | The farm's world data, in sections: maps, models, scripts |
| `01_face.bin` | Character portraits |
| `02_messege0.bin` … `06_messege4.bin` | Dialogue text banks |
| `07_Font_all.tex` | The font |
| `09_sound.stm` | Sound banks |
| `12_event_s.bin` | Event (cutscene) scripts |
| `13_evch.bin`, `29_MesEv.Bin` | Event characters and event messages |
| `14_Status.Bin`, `16_Slp.Bin` | Status screen and sleep screen data |
| `18_MG1.Bin` … `26_MG5.Bin` | Minigame data |
| `08`, `10`, `11`, `15`, `17`, `19`, `21`, `23`, `25`, `27`, `28`, `30`, `31` | **Code overlays**: built from source. Change them with C and patches, not here. |

The game reads the archive's table of contents (`A_FILE.HDT`) at run time, so a member
may change size.

## Making an asset patch

1. Extract the originals (once):

   ```sh
   python hm.py extract
   ```

   This writes the disc's files to `.hm/original/disc/` and every A_FILE member to
   `.hm/original/A_FILE/`. `.hm/` is git-ignored. These are the game's own files: never
   commit them.

2. Copy the member somewhere outside the repository and edit the copy with whatever
   tool fits (a hex editor, a TIM editor, a text tool, ...).

3. Turn your edit into a patch for your mod:

   ```sh
   python hm.py xdelta my_mod 07_Font_all.tex ~/edits/Font_all.tex
   ```

   This writes `mods/my_mod/afile/07_Font_all.tex.xdelta`, which holds only the
   difference. At build time it is applied to the player's own original.

4. Build: `python hm.py build my_mod`.

## Sprites

For animated sprites (animals, the dog, the player) use `python hm.py sprite`: it exports
them as PNGs and writes the `.xdelta` of `00_gf.bin` for you. See [sprites.md](sprites.md).

## Whole files

A file in `mods/<id>/afile/` without `.xdelta` replaces that member as is. Use this only
for data that is entirely your own work. `hm.py validate` rejects whole files over 64 KB,
and a whole file derived from the game's data will not be accepted (see CONTRIBUTING).

`mods/<id>/disc/<path>` replaces a file of the disc (for example `SYSTEM.CNF`) the same way.

When two mods change the same member, the mod given last wins.
