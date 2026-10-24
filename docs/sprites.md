# Sprites: export, reskin, verify

`hm.py sprite` decodes the game's animated sprites (chickens, cows, the dog, the player, ...)
into PNGs and turns edited PNGs back into an `.xdelta` patch of `00_gf.bin`. It is a reskin
tool: sizes, animations and frame data do not change, only pixels and palettes.

```sh
python hm.py extract                                  # once
python hm.py sprite list                              # the known sprite sets (--sources: where from)
python hm.py sprite export chicken ~/edits/chicken    # PNGs + sprite.json
#   ... edit the PNGs (see below) ...
python hm.py new my_mod --author NAME                 # delete its C file and "sources"/"hooks" if art only
python hm.py sprite import my_mod chicken ~/edits/chicken   # -> mods/my_mod/afile/00_gf.bin.xdelta
python hm.py sprite check [ID ...]                    # verify decoders and the round trip
python hm.py build my_mod
```

`hm.py sprite import` can be run once per sprite for the same mod: it applies the mod's
existing patch first and adds the new change. Delete `afile/00_gf.bin.xdelta` to start over.
The tool itself is `tools/hmsprite.py` (standard library and Pillow); `python tools/hmsprite.py -h`
runs everything except `import` without `hm.py`.

## What export writes

| File | Contents |
|------|----------|
| `img_N.png` | Texture image N of the image bank, as an indexed PNG (4 or 8 bits per pixel) with the palette the sprite uses it with. Color word 0 is transparent. |
| `pal_N.png` | Palette image N as one RGBA pixel per color (a swatch strip). |
| `anim_NN.png` | Animation NN: its frames left to right, in cells of one common size. |
| `sheet.png` | All animations, one per row (`sprite.json` `sheet.rows` maps rows to animations). |
| `sprite.json` | The parsed structure: sections, AnimImages and the bank image each matches, bank images with offsets, flags and roles, animations, frames and parts. |

`anim_*.png` and `sheet.png` are previews: import ignores them. Preview limits: semi-transparency
(`attr` bit 4, `ANIM_FLAG_SEMI_TRANSPARENT`) is drawn opaque, per-sprite page and CLUT offsets
(`anim_set_offsets`) are not applied, and parts are drawn first to last (the game queues the last part
first and `addPrim` puts each new primitive in front of the others).

## Editing rules

- **Same sizes.** `img_N.png` must keep its width and height. It must be an indexed PNG whose indices stay
  below the game's palette size (16 or 256); other modes are rejected.
- **Colors.** Edit the palette inside `img_N.png` or the strip `pal_N.png` (or both, if they agree). A
  palette used by several textures should be changed in one place only; conflicting edits are an error.
  Colors have 5 bits per channel: the low 3 bits of each 8-bit channel are dropped. Alpha below 128 means the
  transparent word 0; a new opaque black becomes `0x8000`. The STP bit of an entry is kept from the original
  (`new_word` in `tools/hmsprite.py`).
- **Pixels.** Changed pixels are re-encoded. Repeated bytes compress best; noisy images can be larger than
  the original encoding.
- **Everything must fit the original bytes** (next section).

## Limits

The game addresses its data by compiled-in byte offsets (`farm_data.c`, `farm_load.c`,
`animals/dog.c`, ...), so nothing may move or grow.

1. Each edited bank image is first re-encoded **in place**: row RLE, column RLE or raw, whichever fits in
   the image's stored size (the original encoding is preferred). The size field is kept and the rest is
   zero padded.
2. If one image does not fit, the whole bank is **repacked** inside the original byte range of the bank (the
   images keep their order and the bank its start); unchanged images are re-encoded smaller too if needed.
   Repacking has been verified by decoding only, not in an emulator.
3. If it still does not fit, import stops with the needed and available bytes. Nothing is written.
4. A bank is shared: `chick` and `chicken` use one bank; `calf`, `cow`, `lamb` and `sheep` another.
5. **VRAM rectangle matching.** An `AnimImage` finds its pixels and palette by an exact `{x, y, w, h}` match
   with a bank image (`anim_find_bank_image`); a missing match hangs the game. Import never changes
   rectangles, which is why only pixels and palette colors are editable. `check` requires that every
   AnimImage used by a part has a matching bank image.
6. Adding or removing images, frames, parts or animations is not supported.
7. Only `00_gf.bin` is patched; the mod ships the delta, never the data.

## Formats (with sources)

All integers are little endian; source paths are under `.hm/decomp/src/`.

**.ANI** (`main/graphics/anim.h` `AnimFile`, `anim.c` `anim_bind_file`): `s32 magic` (0xE), 0xC bytes of
padding, five `s32` section offsets from the file start: images, part lists, parts, ranges, frames. Counts
are not stored; they follow from the section sizes (the last section ends at the file length).

| Record | Size | Fields |
|--------|------|--------|
| `AnimImage` | 8 | `s16 x, y, w, h` (w in halfwords) |
| `AnimPartList` | 4 | `s16 count; u16 offset` (byte offset into parts) |
| `AnimPart` | 12 | `u16 image, palette` (AnimImage indices), `s16 dx, dy`, `u8 attr` (bits 0-1 U/V mirror, bit 4 semi-transparent, bit 7 8 bpp), `u8 place`, 2 pad |
| `AnimRange` | 4 | `s16 frames; u16 offset` (byte offset into frames) |
| `AnimFrame` | 10 | `u16 parts` (above 0xFFFD: none), `s16 dx, dy`, `u8 duration, control`, 2 pad |

**Image bank** (`main/graphics/texture_pack.h`, `texture_pack.c`): `u8 type = 0x0D; u8 pad; u16 count`, then
`count` images. Image: `u32 sizeFlags` (low 24 bits stored bytes, flags in the top 8), `u16 x, y, w, h`,
payload, padded to 4 bytes; the next image follows (`BANK_NEXT`). Flags bits 2-3 pick the payload: 0 row-major
RLE, 8 column-major RLE (per halfword column: the low byte of every row, then the high byte of every row),
4 raw. Bits 0-1 equal to 2 mean "alternate destination" (used only when a loader passes an offset; these
packs load at their own position). RLE: a signed control byte; -n copies n literal bytes, n >= 0 repeats the
next byte n times (0 and 1 both give one byte); runs cross row and column boundaries. The encoder never
emits -128 (it overflows the game's `s8`). Pixels are 4 bpp (low nibble is the left pixel) or 8 bpp; palette
entries are 16-bit words (5-5-5, STP in bit 15, word 0 transparent).

**Packs** (`anim.h` `AnimPackToc`, `ANIM_PACK_START`): `count` .ANI files, then the image bank(s). `A_FILE.BIN`
is addressed by byte (`afile_read_sectors`) and member 0 (`00_gf.bin`) starts at byte 0, so the loaders'
constants are byte offsets into `00_gf.bin`.

| Id | Pack at | .ANI (in pack) | Bank | Source |
|----|---------|---------------|------|--------|
| `chick`, `chicken` | 0x380B000 | .ANI 0, 1 (`farm_slot_toc_6`) | +0x1500 | `farm_load_slot_six`, `chicken_load_sprite` |
| `calf`, `cow`, `lamb`, `sheep` | 0x3810000 | .ANI 0, 1, 4, 5 (`farm_slot_toc_0`) | +0x5EF8 | `farm_load_resource`, `livestock.c` |
| `horse`, `pony` | 0x37E3800, 0x37ED800 | +0, 2592 / 2104 bytes | right after the .ANI | `farm_load_anim8`, `horse_load_sprite` |
| `dog`, `puppy` | 0x37F5800, 0x3805800 | +0 | +0x23C8, +0x1420 | `farm_load_span`, `dog_sprite_load` |
| `player` | 0x2A800 | +0, 0xBE08 bytes | +0xBE08 | `farm_load_player_sprite`, `title.c` (0x49000-byte window) |

Not listed: the second livestock pack in slot 1 (0x3833000), the pregnant and shorn variants (.ANI 3, 7, 8 of
the livestock pack; they can be added to `SETS`), the season art, items, villagers and the other resource packs.

## Verification

`hm.py sprite check [ID]` parses every listed set and checks: the .ANI sections and indices; that every used
AnimImage matches a bank image; that each bank image re-encoded in all three modes decodes to the same
pixels; that export followed by import without edits reproduces `00_gf.bin` byte for byte; that re-encoding
every image of the bank decodes equal; and that an edit (one pixel and one palette color) lands as intended
and changes bytes only inside the bank. It takes about 30 seconds per set (it compares the 64 MB file).
