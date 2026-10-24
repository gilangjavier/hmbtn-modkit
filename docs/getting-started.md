# Getting started

From a fresh machine to playing a modded game.

## 1. What you need

- **The game**: your own raw dump of the US disc, *Harvest Moon: Back to Nature*
  (`SLUS-01115`), as a single-track `.bin` (MODE2/2352) with sha1
  `cb26381fa1336bdd15f07469e59f1143ccf37b03`. Translated, patched, `.chd`, `.pbp` or `.iso`
  copies will not work. Convert a `.chd` back to `.bin/.cue` with `chdman extractcd` first.
- **Python 3.11 or newer** and **Git**.
- **Linux** (Debian or Ubuntu), or **Windows 10/11 with WSL**. The game's original
  compiler is a 32-bit Linux program, so builds always run on Linux.
- About 1 GB of disk space.

### Windows: WSL

In PowerShell, as administrator:

```powershell
wsl --install -d Debian
```

Restart, open "Debian" once to create your Linux user, and you are done. `hm.py` uses
your default WSL distribution. To pick another one: `python hm.py setup --distro Ubuntu`.
Setup installs packages inside WSL as root through `wsl -u root`, so it does not ask
for your Linux password.

## 2. Set up

```sh
git clone https://github.com/gilangjavier/hmbtn-modkit
cd hmbtn-modkit
python hm.py setup --disc "C:\Games\Harvest Moon - Back to Nature (USA).bin"
```

Setup:

1. Installs the build tools on the Linux side: MIPS binutils, CMake, Ninja, rsync,
   patch and xdelta3 through apt, plus GCC 2.95.2 for the PlayStation and the PSY-Q 4.7
   SDK into `/opt/psyq` (downloads checked by SHA-256).
2. Clones [hmbtn-decomp](https://github.com/coalslav/hmbtn-decomp) at the pinned commit
   into `.hm/decomp/` and applies the framework patches.
3. Saves your disc's path in `.hm/config.json` after checking its SHA-1.

Run setup again whenever `framework/` changes (after a `git pull`). It is safe to repeat.

## 3. Build the retail game

```sh
python hm.py build
```

This builds the unmodified game from source and compares every file with your disc:

```
all 17 files match the original
RAM: the mods use 0 of the 56208 bytes the game leaves free (0.0%)
```

If anything does not match, stop and open an issue: a mod build cannot be trusted on a
broken toolchain.

## 4. Build with mods

The easy way: pick mods once, then play.

```sh
python hm.py list                          # what is available; [x] = enabled
python hm.py enable cheat_pad daily_allowance
python hm.py disable cheat_pad             # or: disable --all
python hm.py play                          # build the enabled mods and start the emulator
```

Or build any set directly:

```sh
python hm.py build cheat_pad daily_allowance
python hm.py build --all                   # everything in mods/
```

Mods are applied in the order given (for `play`, the order you enabled them). That
matters only when two mods touch the same thing.

The result is `out/hmbtn-mod.bin` + `out/hmbtn-mod.cue` (choose the name with `-o`).
`out/hmbtn-mod.txt` lists the mods and versions it contains.

### Mods from other places

```sh
python hm.py add https://github.com/someone/their-mods          # every mod it contains
python hm.py add https://github.com/someone/their-mods --mod x  # just one
python hm.py add ../a-folder-with-mod.json
python hm.py remove x
```

`add` accepts a repository or folder that is a mod (has `mod.json`), or that holds mods
in `mods/*/` or `*/`. Each mod is validated before it is installed. Only add mods from
people you trust: a mod is C code compiled into your game.

## 5. Play

Open `out/hmbtn-mod.cue` in any PlayStation emulator, or burn it. To launch it from the
tool:

```sh
python hm.py setup --skip-toolchain --emulator "C:\Tools\pcsx-redux\pcsx-redux.exe"
python hm.py run
```

Saves are compatible with the retail game's, since mods do not change the save format
unless their README says so.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `is not the US retail disc` | Use a raw `.bin` of `SLUS-01115`. Check the SHA-1 above. |
| `stray '\' in program` while compiling | A file was checked out with CRLF line ends. Run `python hm.py setup` again; it re-fetches the decomp with LF. |
| `Value too large for defined data type` | The build ran on a Windows drive. `hm.py` avoids this by building in `~/.cache/hmbtn-modkit`; do not change `WORK`. |
| `the EXE and FARM are too big` | The mods do not fit in RAM: see [memory-budget.md](memory-budget.md). |
| `patch: ... FAILED` | Two mods patch the same source lines, or a mod's patch is stale. Build them separately to find which. |
| WSL asks for a password / no distribution | Install one with `wsl --install -d Debian`, or name it with `--distro`. |
