# Memory budget

The PlayStation has 2 MB of RAM, and the game fills almost all of it.

## The retail layout

```
0x80010000  the executable (code, data)           ─┐ mods' code and data go here, at the end
0x8005E374  the executable's .bss                  ─┘
0x800B7E20  overlay_low:  FARM, minigames, title (one at a time)
0x8012DDE8  overlay_high: save/load, wind (FARM's image ends here)
0x8012DE20  farm image window (0x49000 bytes)
0x80176E20  farm section buffer (largest section: 0x39800 bytes)
   ...      free: event scripts load here in the background
0x801BE1B0  frame work region: ordering tables, primitives
0x801FFFF0  stack
```

In the retail game `overlay_low` and `overlay_high` were fixed addresses. The framework
makes the linker compute them: `overlay_low` is wherever the executable now ends, and
`overlay_high` is wherever FARM now ends. Every byte a mod adds to the executable, or
to FARM through a patch, moves everything above it up by that much.

## The limit

The largest farm section has to fit between the farm's image window and the work
region at `0x801BE1B0`. In the retail game that leaves **0xDB90 = 56,208 bytes**, and that
is the total every mod in a build can add. The linker checks it:

```
the EXE and FARM are too big: the largest farm section would overrun the work region at 0x801BE1B0
```

`hm.py build` reports the use:

```
RAM: the mods use 600 of the 56208 bytes the game leaves free (1.1%)
```

## Spend it carefully

The same free space is where the game loads event scripts in the background. With less
of it, more events load in the foreground instead. That is still correct, but it can add
a short pause when an event starts. So:

- Aim for a few KB per mod. Hundreds of bytes is typical for a hook-based mod.
- Avoid large tables in C: `static const` data counts too.
- Large data belongs in A_FILE (load it when needed), not in the executable.
- `python hm.py build --all` must stay well under the limit. CI reports it.
