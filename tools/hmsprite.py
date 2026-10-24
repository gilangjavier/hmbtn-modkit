#!/usr/bin/env python3
"""hmsprite: export, reskin and verify the game's sprite sets (.ANI files + image banks).

    python tools/hmsprite.py list
    python tools/hmsprite.py export ID OUTDIR [--gf 00_gf.bin]
    python tools/hmsprite.py check [ID ...]  [--gf 00_gf.bin]

`hm.py sprite ...` wraps this (and adds `import`, which writes the .xdelta of a mod).
The formats are described in docs/sprites.md. Standard library plus Pillow.

Everything here reads the player's own copy of the game (the original 00_gf.bin from
`hm.py extract`). Nothing is stored in the repository except this code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    raise SystemExit("hmsprite: Pillow is required (python -m pip install pillow)")

REPO = Path(__file__).resolve().parent.parent
DEFAULT_GF = REPO / ".hm" / "original" / "A_FILE" / "00_gf.bin"
FORMAT = 1                      # sprite.json "format"
ANI_MAGIC = 0xE
BANK_TYPE = 0x0D
NO_PARTS = 0xFFFD               # anim.h ANIM_NO_PARTS: AnimFrame.parts above this draws nothing
VRAM_W, VRAM_H = 1024, 512      # in 16-bit pixels


class SpriteError(Exception):
    """A problem the user can act on (bad input, does not fit, ...)."""


# --- the table of known sprite sets -------------------------------------------------
#
# All offsets are bytes into 00_gf.bin (member 0 of A_FILE.BIN starts at byte 0 of
# A_FILE.BIN, and the game addresses A_FILE.BIN by byte offset: afile_read_sectors).
# `pack` is where the loaded region starts, `size` how many bytes the game reads for
# it, `ani` = (start, length) of the .ANI file inside the region, `bank` = where the
# first image bank starts inside the region. More banks may follow it directly.

# farm_data.c farm_slot_toc_6 (slot "six": toys and chickens), loaded by farm_load_slot_six
# from 0x380B000, 0x5000 bytes. The texture pack starts at start[count].
SLOT6_TOC = [0, 1008, 3072, 3688, 4236, 5376]
# farm_data.c farm_slot_toc_0 (cows and sheep), loaded by farm_load_resource(0) from
# farm_slot_file_offsets[0..1] = 0x03810000..0x03833000.
SLOT0_TOC = [0, 2668, 5372, 6212, 8444, 10496, 12668, 13576, 15900, 18072, 24312]

SOURCES = {
    "slot6": "overlay/11_GF_FARM/farm_load.c farm_load_slot_six; farm_data.c farm_slot_toc_6; "
             "animals/chicken.c chicken_load_sprite (ANI index = kind slot - 1)",
    "slot0": "overlay/11_GF_FARM/farm_load.c farm_load_resource; farm_data.c farm_slot_toc_0; "
             "animals/livestock.c (LIVESTOCK_PACK_*; ANI index = pack - 1)",
    "anim8": "overlay/11_GF_FARM/farm_load.c farm_load_anim8 (copies the first 2592 / later 2104 "
             "bytes, the texture pack follows); animals/horse.c horse_load_sprite",
    "span": "overlay/11_GF_FARM/farm_load.c farm_load_span, farm_span_offsets; "
            "animals/dog.c dog_sprite_load (bank at +0x23C8 adult, +0x1420 young)",
    "player": "overlay/11_GF_FARM/farm_load.c farm_load_player_sprite (FARM_PLAYER_BANK_OFFSET "
              "0xBE08); overlay/27_GF_TITLE/title.c reads 0x49000 bytes at 0x2A800",
}


def _set(id_, name, source, pack, size, ani, bank, note=""):
    return {"id": id_, "name": name, "source": SOURCES[source], "pack": pack, "size": size,
            "ani": ani, "bank": bank, "note": note}


SETS = [
    _set("chick", "Chick (slot six, .ANI 0)", "slot6", 0x380B000, 0x5000,
         (SLOT6_TOC[0], SLOT6_TOC[1] - SLOT6_TOC[0]), SLOT6_TOC[5],
         "shares its image bank with chicken, the toys and the visitor"),
    _set("chicken", "Chicken (slot six, .ANI 1)", "slot6", 0x380B000, 0x5000,
         (SLOT6_TOC[1], SLOT6_TOC[2] - SLOT6_TOC[1]), SLOT6_TOC[5],
         "shares its image bank with chick, the toys and the visitor"),
    _set("calf", "Calf (slot 0, .ANI 0)", "slot0", 0x03810000, 0x23000,
         (SLOT0_TOC[0], SLOT0_TOC[1] - SLOT0_TOC[0]), SLOT0_TOC[10],
         "slot 1 (0x03833000) holds a second set with the same layout; not listed"),
    _set("cow", "Cow, also the young cow (slot 0, .ANI 1)", "slot0", 0x03810000, 0x23000,
         (SLOT0_TOC[1], SLOT0_TOC[2] - SLOT0_TOC[1]), SLOT0_TOC[10]),
    _set("sheep", "Sheep (slot 0, .ANI 5)", "slot0", 0x03810000, 0x23000,
         (SLOT0_TOC[5], SLOT0_TOC[6] - SLOT0_TOC[5]), SLOT0_TOC[10]),
    _set("lamb", "Lamb (slot 0, .ANI 4)", "slot0", 0x03810000, 0x23000,
         (SLOT0_TOC[4], SLOT0_TOC[5] - SLOT0_TOC[4]), SLOT0_TOC[10]),
    _set("horse", "Horse (anim8 part 0)", "anim8", 0x037E3800, 0xA000, (0, 2592), 2592),
    _set("pony", "Pony (anim8 part 1)", "anim8", 0x037ED800, 0x8000, (0, 2104), 2104),
    _set("dog", "Dog (span 0)", "span", 0x037F5800, 0x10000, (0, 0x23C8), 0x23C8),
    _set("puppy", "Young dog (span 1)", "span", 0x03805800, 0x5800, (0, 0x1420), 0x1420),
    _set("player", "Player (second sprite, farm load window)", "player", 0x2A800, 0x49000,
         (0, 0xBE08), 0xBE08),
]
SET_BY_ID = {s["id"]: s for s in SETS}


# --- run-length coding --------------------------------------------------------------
#
# texture_pack.c: a signed control byte. Negative -n: copy n literal bytes. n >= 0: repeat
# the next byte n times (0 and 1 both give one byte). The state carries across rows.

def rle_decode(src: bytes, pos: int, count: int) -> tuple[bytes, int]:
    """Decode `count` bytes starting at src[pos]; return (bytes, position after the data)."""
    out = bytearray()
    run = 0
    repeat = False
    fill = 0
    try:
        while len(out) < count:
            if run <= 0:
                c = src[pos]
                pos += 1
                if c >= 128:
                    c -= 256
                if c == -128:
                    raise SpriteError("RLE control byte -128 (the game's s8 overflows)")
                if c < 0:
                    repeat = False
                    run = -c
                else:
                    repeat = True
                    run = c
                    fill = src[pos]
                    pos += 1
            if repeat:
                out.append(fill)
            else:
                out.append(src[pos])
                pos += 1
            run -= 1
    except IndexError:
        raise SpriteError("RLE data runs past the end of the buffer") from None
    return bytes(out), pos


def rle_encode(data: bytes) -> bytes:
    """A minimal-size encoding (dynamic programming over literal and repeat runs)."""
    n = len(data)
    inf = 1 << 60
    cost = [inf] * (n + 1)
    step = [None] * (n + 1)
    cost[n] = 0
    # run length of equal bytes starting at i
    same = [1] * (n + 1)
    for i in range(n - 2, -1, -1):
        same[i] = same[i + 1] + 1 if data[i] == data[i + 1] else 1
    for i in range(n - 1, -1, -1):
        best = inf
        pick = None
        for length in range(1, min(127, n - i) + 1):      # a literal run: 1 + length bytes
            c = 1 + length + cost[i + length]
            if c < best:
                best, pick = c, ("lit", length)
        for length in range(2, min(127, same[i]) + 1):     # a repeat run: 2 bytes
            c = 2 + cost[i + length]
            if c < best:
                best, pick = c, ("rep", length)
        cost[i], step[i] = best, pick
    out = bytearray()
    i = 0
    while i < n:
        kind, length = step[i]
        if kind == "lit":
            out.append((-length) & 0xFF)
            out += data[i:i + length]
        else:
            out.append(length)
            out.append(data[i])
        i += length
    return bytes(out)


def column_order(raw: bytes, w: int, h: int) -> bytes:
    """Row-major VRAM bytes -> the column-major stream of flag bit 3: per halfword column,
    the low byte of every row, then the high byte of every row."""
    row = w * 2
    out = bytearray(len(raw))
    k = 0
    for c in range(w):
        for half in (0, 1):
            out[k:k + h] = raw[c * 2 + half::row][:h]
            k += h
    return bytes(out)


def column_unorder(stream: bytes, w: int, h: int) -> bytes:
    row = w * 2
    raw = bytearray(len(stream))
    k = 0
    for c in range(w):
        for half in (0, 1):
            raw[c * 2 + half::row] = stream[k:k + h]
            k += h
    return bytes(raw)


def mode_of(flags: int) -> str:
    """How texture_pack_upload reads an image's payload (flag bits 2-3)."""
    if flags & 0xC == 0:
        return "rle_row"
    if flags & 0x8:
        return "rle_col"
    return "raw"


MODE_BITS = {"rle_row": 0x0, "rle_col": 0x8, "raw": 0x4}


def decode_payload(data: bytes, img: dict) -> tuple[bytes, int]:
    """The image's VRAM bytes (row-major, w*2 per row) and how many payload bytes were read."""
    w, h = img["w"], img["h"]
    total = w * 2 * h
    start = img["data"]
    mode = mode_of(img["flags"])
    if mode == "raw":
        if img["size"] < total:
            raise SpriteError(f"raw image {img['gidx']} stores {img['size']} bytes, needs {total}")
        return data[start:start + total], total
    stream, end = rle_decode(data[: start + img["size"]], start, total)
    used = end - start
    if mode == "rle_col":
        stream = column_unorder(stream, w, h)
    return stream, used


def encode_payload(raw: bytes, w: int, h: int, mode: str) -> bytes:
    if mode == "raw":
        return raw
    if mode == "rle_row":
        return rle_encode(raw)
    return rle_encode(column_order(raw, w, h))


# --- .ANI files ---------------------------------------------------------------------

def parse_ani(data: bytes, start: int, length: int) -> dict:
    """anim.h AnimFile: magic, 0xC pad, five section offsets (images, part lists, parts,
    ranges, frames). Counts are not stored: they follow from the section extents."""
    if length < 0x20:
        raise SpriteError("an .ANI file is at least 0x20 bytes")
    magic = struct.unpack_from("<i", data, start)[0]
    if magic != ANI_MAGIC:
        raise SpriteError(f".ANI magic is {magic:#x} at {start:#x}, expected {ANI_MAGIC:#x}")
    sec = list(struct.unpack_from("<5i", data, start + 0x10))
    if sec != sorted(sec) or sec[0] < 0x24 - 4 or sec[-1] > length:
        raise SpriteError(f".ANI sections {sec} are not ascending inside {length:#x} bytes")
    ends = sec[1:] + [length]
    sizes = [8, 4, 12, 4, 10]
    counts = [(ends[i] - sec[i]) // sizes[i] for i in range(5)]
    ani = {"start": start, "length": length, "sections": sec, "counts": counts}
    base = start
    ani["images"] = [struct.unpack_from("<4h", data, base + sec[0] + 8 * i) for i in range(counts[0])]
    ani["part_lists"] = [struct.unpack_from("<hH", data, base + sec[1] + 4 * i) for i in range(counts[1])]
    ani["ranges"] = [struct.unpack_from("<hH", data, base + sec[3] + 4 * i) for i in range(counts[3])]
    animations = []
    for ai, (nframes, off) in enumerate(ani["ranges"]):
        frames = []
        if nframes < 0 or sec[4] + off + 10 * nframes > length:
            raise SpriteError(f"animation {ai}: {nframes} frames at {off} leave the .ANI file")
        for fi in range(nframes):
            parts_i, dx, dy, dur, ctl = struct.unpack_from("<HhhBB", data, base + sec[4] + off + 10 * fi)
            frame = {"parts": parts_i, "dx": dx, "dy": dy, "duration": dur, "control": ctl, "part_list": []}
            if parts_i <= NO_PARTS:
                if parts_i >= counts[1]:
                    raise SpriteError(f"animation {ai} frame {fi}: part list {parts_i} does not exist")
                pcount, poff = ani["part_lists"][parts_i]
                if pcount < 0 or sec[2] + poff + 12 * pcount > sec[3]:
                    raise SpriteError(f"part list {parts_i} leaves the parts section")
                for pi in range(pcount):
                    image, palette, pdx, pdy, attr, place = struct.unpack_from(
                        "<HHhhBB", data, base + sec[2] + poff + 12 * pi)
                    if image >= counts[0] or palette >= counts[0]:
                        raise SpriteError(f"part list {parts_i}: image/palette index out of range")
                    frame["part_list"].append({"image": image, "palette": palette, "dx": pdx, "dy": pdy,
                                               "attr": attr, "place": place})
            frames.append(frame)
        animations.append(frames)
    ani["animations"] = animations
    return ani


# --- image banks --------------------------------------------------------------------

def parse_banks(data: bytes, start: int, limit: int) -> list[dict]:
    """The ImageBank at `start`, and any further banks that follow it directly. Each image
    gets a global index `gidx`; `off` is its header, `data` its payload."""
    banks = []
    gidx = 0
    pos = start
    while pos + 4 <= limit:
        kind, _pad, count = struct.unpack_from("<BBH", data, pos)
        if kind != BANK_TYPE or count == 0 or count > 2000:
            break
        images = []
        p = pos + 4
        ok = True
        for i in range(count):
            if p + 12 > limit:
                ok = False
                break
            sf, x, y, w, h = struct.unpack_from("<IHHHH", data, p)
            size = sf & 0xFFFFFF
            end = p + 12 + (size + 3) // 4 * 4
            if end > limit or w == 0 or h == 0 or x + w > VRAM_W + 256 or y + h > VRAM_H + 256:
                ok = False
                break
            images.append({"gidx": gidx + i, "bank": len(banks), "index": i, "off": p, "data": p + 12,
                           "size": size, "flags": sf >> 24, "x": x, "y": y, "w": w, "h": h})
            p = end
        if not ok:
            if not banks:
                raise SpriteError(f"the image bank at {start:#x} is damaged (image {len(images)})")
            break
        banks.append({"offset": pos, "count": count, "end": p, "images": images})
        gidx += count
        pos = p
    if not banks:
        raise SpriteError(f"no image bank (type 0x0D) at {start:#x}")
    return banks


class Sprite:
    """One sprite set parsed out of 00_gf.bin."""

    def __init__(self, data: bytes, spec: dict):
        self.spec = spec
        self.data = data
        pack = spec["pack"]
        if pack + spec["size"] > len(data):
            raise SpriteError(f"00_gf.bin is too short for {spec['id']} (is it the original member?)")
        self.ani_start = pack + spec["ani"][0]
        self.limit = pack + spec["size"]
        self.ani = parse_ani(data, self.ani_start, spec["ani"][1])
        self.banks = parse_banks(data, pack + spec["bank"], self.limit)
        self.images = [im for b in self.banks for im in b["images"]]
        self.decoded: dict[int, bytes] = {}
        self.vram = bytearray(VRAM_W * VRAM_H * 2)
        for im in self.images:
            raw, used = decode_payload(data, im)
            if used > im["size"]:
                raise SpriteError(f"image {im['gidx']}: payload ({used} bytes) is longer than its size field")
            im["used"] = used
            self.decoded[im["gidx"]] = raw
            self._blit(im, raw)
        self._match()

    def _blit(self, im: dict, raw: bytes) -> None:
        x, y, w, h = im["x"], im["y"], im["w"], im["h"]
        if x + w > VRAM_W or y + h > VRAM_H:
            return
        for r in range(h):
            o = ((y + r) * VRAM_W + x) * 2
            self.vram[o:o + w * 2] = raw[r * w * 2:(r + 1) * w * 2]

    def _match(self) -> None:
        """anim_find_bank_image: an AnimImage's pixels are the bank image with the same
        {x, y, w, h}. Record the match, and each image's role from the parts using it."""
        by_rect: dict[tuple, dict] = {}
        for im in self.images:
            by_rect.setdefault((im["x"], im["y"], im["w"], im["h"]), im)
        self.anim_to_bank = []
        for rect in self.ani["images"]:
            self.anim_to_bank.append(by_rect.get(tuple(rect)))
        for im in self.images:
            im["role"] = "other"
            im["palettes"] = []
            im["depth"] = None
        self.unmatched = set()
        self.used_images = set()
        for frames in self.ani["animations"]:
            for frame in frames:
                for part in frame["part_list"]:
                    for key, role in (("image", "texture"), ("palette", "palette")):
                        ai = part[key]
                        self.used_images.add(ai)
                        im = self.anim_to_bank[ai]
                        if im is None:
                            self.unmatched.add(ai)
                            continue
                        if im["role"] not in ("other", role):
                            raise SpriteError(f"image {im['gidx']} is used both as texture and palette")
                        im["role"] = role
                        if role == "texture":
                            depth = part["attr"] >> 7
                            if im["depth"] not in (None, depth):
                                raise SpriteError(f"image {im['gidx']} is used with both 4 and 8 bits")
                            im["depth"] = depth
                            if part["palette"] not in im["palettes"]:
                                im["palettes"].append(part["palette"])

    # -- palettes and pixels

    def palette_words(self, anim_image: int, count: int) -> list[int]:
        x, y, w, h = self.ani["images"][anim_image]
        o = (y * VRAM_W + x) * 2
        return list(struct.unpack_from(f"<{count}H", self.vram, o))

    def texture_indices(self, im: dict) -> tuple[int, bytes]:
        """(width in pixels, one palette index per pixel) of a texture image."""
        return unpack_pixels(self.decoded[im["gidx"]], im["w"], im["h"], im["depth"])


def unpack_pixels(raw: bytes, w: int, h: int, depth: int) -> tuple[int, bytes]:
    """VRAM bytes -> palette indices. 4 bpp: the low nibble is the left pixel."""
    if depth:
        return w * 2, bytes(raw)
    out = bytearray(len(raw) * 2)
    out[0::2] = bytes(b & 15 for b in raw)
    out[1::2] = bytes(b >> 4 for b in raw)
    return w * 4, bytes(out)


def pack_pixels(idx: bytes, depth: int) -> bytes:
    if depth:
        return bytes(idx)
    return bytes(idx[i] | (idx[i + 1] << 4) for i in range(0, len(idx), 2))


def word_rgba(word: int) -> tuple[int, int, int, int]:
    """A PS1 16-bit color as RGBA. The word 0 is the transparent color; the STP bit
    (0x8000) is not shown in the picture, it is kept from the original on import."""
    r, g, b = word & 31, (word >> 5) & 31, (word >> 10) & 31
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2), 0 if word == 0 else 255)


def new_word(base: int, r8: int, g8: int, b8: int, alpha: int | None) -> int:
    """The color word for an edited PNG color. An unchanged color keeps `base` exactly."""
    if alpha is not None and alpha < 128:
        return 0
    rgb = (r8 >> 3) | ((g8 >> 3) << 5) | ((b8 >> 3) << 10)
    if rgb == (base & 0x7FFF):
        if base == 0 and alpha is not None:
            return 0x8000
        return base
    word = rgb | (base & 0x8000)
    return word if word != 0 else 0x8000


# --- export -------------------------------------------------------------------------

def indexed_png(path: Path, width: int, height: int, indices: bytes, words: list[int]) -> None:
    img = Image.frombytes("P", (width, height), indices)
    pal = []
    alpha = []
    for word in words:
        r, g, b, a = word_rgba(word)
        pal += [r, g, b]
        alpha.append(a)
    pal += [0] * (768 - len(pal))
    img.putpalette(pal)
    img.save(path, transparency=bytes(alpha))


def swatch_png(path: Path, w: int, h: int, words: list[int]) -> None:
    img = Image.new("RGBA", (w, h))
    img.putdata([word_rgba(x) for x in words])
    img.save(path)


def frame_boxes(sprite: Sprite):
    """Bounding box of every drawn part over all frames, for a uniform cell size."""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for frames in sprite.ani["animations"]:
        for frame in frames:
            for part in frame["part_list"]:
                x, y, w, h = sprite.ani["images"][part["image"]]
                pw = w * (2 if part["attr"] >> 7 else 4)
                x0 = frame["dx"] + part["dx"]
                y0 = frame["dy"] + part["dy"]
                xs0.append(x0)
                ys0.append(y0)
                xs1.append(x0 + pw)
                ys1.append(y0 + h)
    if not xs0:
        return 0, 0, 1, 1
    return min(xs0), min(ys0), max(xs1), max(ys1)


def render_part(sprite: Sprite, part: dict) -> Image.Image:
    x, y, w, h = sprite.ani["images"][part["image"]]
    depth = part["attr"] >> 7
    rows = bytearray()
    for r in range(h):
        o = ((y + r) * VRAM_W + x) * 2
        rows += sprite.vram[o:o + w * 2]
    pw, idx = unpack_pixels(bytes(rows), w, h, depth)
    colors = sprite.palette_words(part["palette"], 256 if depth else 16)
    rgba = [word_rgba(c) for c in colors]
    im = Image.new("RGBA", (pw, h))
    im.putdata([rgba[i] for i in idx])
    if part["attr"] & 1:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    if part["attr"] & 2:
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
    return im


def render_frame(sprite: Sprite, frame: dict, cell: tuple[int, int], origin: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", cell, (0, 0, 0, 0))
    # sprite_draw_frame queues the last part first and addPrim puts each in front of the
    # previous ones, so part 0 is drawn first (at the bottom).
    for part in frame["part_list"]:
        im = render_part(sprite, part)
        px = origin[0] + frame["dx"] + part["dx"]
        py = origin[1] + frame["dy"] + part["dy"]
        layer = Image.new("RGBA", cell, (0, 0, 0, 0))
        layer.paste(im, (px, py))
        canvas = Image.alpha_composite(canvas, layer)
    return canvas


def bank_report(sprite: Sprite) -> dict:
    return {"banks": [{"offset": b["offset"] - sprite.spec["pack"], "count": b["count"],
                       "end": b["end"] - sprite.spec["pack"]} for b in sprite.banks]}


def export_sprite(gf: bytes, id_: str, outdir: Path) -> dict:
    spec = SET_BY_ID[id_]
    sprite = Sprite(gf, spec)
    outdir.mkdir(parents=True, exist_ok=True)
    pack = spec["pack"]
    x0, y0, x1, y1 = frame_boxes(sprite)
    cell = (x1 - x0, y1 - y0)
    origin = (-x0, -y0)
    meta = {"format": FORMAT, "id": id_, "name": spec["name"], "source": spec["source"],
            "member": "00_gf.bin", "pack_offset": pack, "pack_size": spec["size"],
            "ani": {"offset": spec["ani"][0], "length": spec["ani"][1],
                    "sections": sprite.ani["sections"], "counts": sprite.ani["counts"]},
            "bank_offset": spec["bank"], **bank_report(sprite),
            "cell": {"width": cell[0], "height": cell[1], "origin_x": origin[0], "origin_y": origin[1]},
            "anim_images": [], "images": [], "animations": []}
    for i, rect in enumerate(sprite.ani["images"]):
        im = sprite.anim_to_bank[i]
        meta["anim_images"].append({"index": i, "x": rect[0], "y": rect[1], "w": rect[2], "h": rect[3],
                                    "bank_image": None if im is None else im["gidx"],
                                    "used": i in sprite.used_images})
    # texture and palette images used by this .ANI
    palette_used_by: dict[int, list[int]] = {}
    for im in sprite.images:
        for pa in im["palettes"]:
            bank_pal = sprite.anim_to_bank[pa]
            if bank_pal is not None:
                palette_used_by.setdefault(bank_pal["gidx"], []).append(im["gidx"])
    for im in sprite.images:
        entry = {"gidx": im["gidx"], "bank": im["bank"], "index": im["index"],
                 "offset": im["off"] - pack, "stored_size": im["size"], "flags": im["flags"],
                 "mode": mode_of(im["flags"]), "x": im["x"], "y": im["y"], "w": im["w"], "h": im["h"],
                 "role": im["role"]}
        if im["role"] == "texture":
            depth = im["depth"]
            width, idx = sprite.texture_indices(im)
            ncol = 256 if depth else 16
            primary = None
            for pa in im["palettes"]:
                if sprite.anim_to_bank[pa] is not None:
                    primary = sprite.anim_to_bank[pa]
                    break
            words = sprite.palette_words(im["palettes"][0], ncol) if im["palettes"] else [0] * ncol
            name = f"img_{im['gidx']}.png"
            indexed_png(outdir / name, width, im["h"], idx, words)
            entry.update({"file": name, "bpp": 8 if depth else 4, "pixel_width": width,
                          "palette_image": None if primary is None else primary["gidx"],
                          "palette_anim_images": im["palettes"]})
        elif im["role"] == "palette":
            name = f"pal_{im['gidx']}.png"
            words = list(struct.unpack_from(f"<{im['w'] * im['h']}H", sprite.decoded[im["gidx"]]))
            swatch_png(outdir / name, im["w"], im["h"], words)
            entry.update({"file": name, "colors": [f"{c:04x}" for c in words],
                          "used_by": sorted(set(palette_used_by.get(im["gidx"], [])))})
        meta["images"].append(entry)
    # animation sheets
    rows = []
    for ai, frames in enumerate(sprite.ani["animations"]):
        anim = {"index": ai, "frames": []}
        if frames:
            strip = Image.new("RGBA", (cell[0] * len(frames), cell[1]), (0, 0, 0, 0))
            for fi, frame in enumerate(frames):
                strip.paste(render_frame(sprite, frame, cell, origin), (cell[0] * fi, 0))
            name = f"anim_{ai:02d}.png"
            strip.save(outdir / name)
            anim["file"] = name
            rows.append(strip)
        for fi, frame in enumerate(frames):
            anim["frames"].append({"index": fi, "part_list": frame["parts"], "dx": frame["dx"],
                                   "dy": frame["dy"], "duration": frame["duration"],
                                   "control": frame["control"], "parts": frame["part_list"]})
        meta["animations"].append(anim)
    if rows:
        sheet = Image.new("RGBA", (cell[0] * max(r.width // cell[0] for r in rows), cell[1] * len(rows)),
                          (0, 0, 0, 0))
        for k, strip in enumerate(rows):
            sheet.paste(strip, (0, cell[1] * k))
        sheet.save(outdir / "sheet.png")
        meta["sheet"] = {"file": "sheet.png",
                         "rows": [a["index"] for a in meta["animations"] if a.get("file")]}
    (outdir / "sprite.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


# --- import -------------------------------------------------------------------------

def load_png_indices(path: Path, width: int, height: int, ncolors: int):
    """(indices, [(r, g, b, alpha or None)] for the first ncolors entries) of an indexed PNG."""
    im = Image.open(path)
    if im.mode != "P":
        raise SpriteError(f"{path.name}: must be an indexed (palette) PNG, not {im.mode}")
    if im.size != (width, height):
        raise SpriteError(f"{path.name}: is {im.size[0]}x{im.size[1]}, the game's image is "
                          f"{width}x{height} (sizes cannot change)")
    pal = im.getpalette() or []
    trns = im.info.get("transparency")
    colors = []
    for i in range(ncolors):
        r, g, b = (pal[3 * i:3 * i + 3] + [0, 0, 0])[:3]
        if isinstance(trns, (bytes, bytearray)):
            a = trns[i] if i < len(trns) else 255
        elif isinstance(trns, int):
            a = 0 if i == trns else 255
        else:
            a = None
        colors.append((r, g, b, a))
    idx = im.tobytes()
    if idx and max(idx) >= ncolors:
        raise SpriteError(f"{path.name}: uses palette index {max(idx)}, the game's palette has {ncolors} colors")
    return idx, colors


def candidates(raw: bytes, im: dict) -> dict:
    return {m: encode_payload(raw, im["w"], im["h"], m) for m in ("rle_row", "rle_col", "raw")}


def patch_set(gf: bytes, id_: str, indir: Path, force_reencode: bool = False) -> tuple[bytes, dict]:
    """Apply the PNGs in `indir` (an export of `id_`, edited) to a copy of 00_gf.bin.
    Returns (new bytes, report). Nothing is returned for the unchanged parts of the file."""
    spec = SET_BY_ID[id_]
    sprite = Sprite(gf, spec)
    meta_path = indir / "sprite.json"
    if not meta_path.is_file():
        raise SpriteError(f"{meta_path} does not exist: export the sprite first")
    meta = json.loads(meta_path.read_text())
    if meta.get("format") != FORMAT or meta.get("id") != id_:
        raise SpriteError(f"{meta_path} is not a format-{FORMAT} export of '{id_}'")
    if [(i["gidx"], i["x"], i["y"], i["w"], i["h"]) for i in meta["images"]] != \
            [(i["gidx"], i["x"], i["y"], i["w"], i["h"]) for i in
             ({"gidx": im["gidx"], "x": im["x"], "y": im["y"], "w": im["w"], "h": im["h"]} for im in sprite.images)]:
        raise SpriteError("sprite.json does not match the game's image bank (exported from another file?)")

    new_raw: dict[int, bytes] = {}      # gidx -> new VRAM bytes of changed images
    palette_edits: dict[int, list] = {}  # gidx of palette image -> [(source, words)]

    def propose_palette(pal_im: dict, source: str, new_words: list[int], old_words: list[int]):
        if new_words != old_words:
            palette_edits.setdefault(pal_im["gidx"], []).append((source, new_words))

    by_gidx = {im["gidx"]: im for im in sprite.images}
    for entry in meta["images"]:
        im = by_gidx[entry["gidx"]]
        if "file" not in entry:
            continue
        path = indir / entry["file"]
        if not path.is_file():
            continue
        if entry["role"] == "texture":
            ncol = 256 if im["depth"] else 16
            width, base_idx = sprite.texture_indices(im)
            idx, colors = load_png_indices(path, width, im["h"], ncol)
            raw = pack_pixels(idx, im["depth"])
            if raw != sprite.decoded[im["gidx"]]:
                new_raw[im["gidx"]] = raw
            primary = entry.get("palette_image")
            if primary is not None:
                pal_im = by_gidx[primary]
                old = list(struct.unpack_from(f"<{pal_im['w'] * pal_im['h']}H", sprite.decoded[primary]))
                new = list(old)
                for k, (r, g, b, a) in enumerate(colors):
                    new[k] = new_word(old[k], r, g, b, a)
                propose_palette(pal_im, entry["file"], new, old)
        elif entry["role"] == "palette":
            old = list(struct.unpack_from(f"<{im['w'] * im['h']}H", sprite.decoded[im["gidx"]]))
            pim = Image.open(path).convert("RGBA")
            if pim.size != (im["w"], im["h"]):
                raise SpriteError(f"{path.name}: is {pim.width}x{pim.height}, needs {im['w']}x{im['h']}")
            flat = pim.tobytes()
            new = [new_word(old[k], *flat[4 * k:4 * k + 4]) for k in range(im["w"] * im["h"])]
            propose_palette(im, entry["file"], new, old)
    for gidx, proposals in palette_edits.items():
        first = proposals[0][1]
        for source, words in proposals[1:]:
            if words != first:
                raise SpriteError(f"palette image {gidx} is changed differently by {proposals[0][0]} and "
                                  f"{source}: edit it in only one place")
        pim = by_gidx[gidx]
        new_raw[gidx] = struct.pack(f"<{len(first)}H", *first)

    if force_reencode:
        for im in sprite.images:
            new_raw.setdefault(im["gidx"], sprite.decoded[im["gidx"]])

    out = bytearray(gf)
    report = {"changed_images": sorted(new_raw), "banks": []}
    for bank in sprite.banks:
        changed = [im for im in bank["images"] if im["gidx"] in new_raw]
        if not changed:
            continue
        rep = write_bank(out, gf, sprite, bank, new_raw, force_reencode)
        report["banks"].append(rep)

    # verify: reparse and compare every image of every bank with what was intended
    check = Sprite(bytes(out), spec)
    for im in check.images:
        want = new_raw.get(im["gidx"], sprite.decoded[im["gidx"]])
        if check.decoded[im["gidx"]] != want:
            raise SpriteError(f"internal error: image {im['gidx']} does not decode to the intended pixels")
    return bytes(out), report


def write_bank(out: bytearray, gf: bytes, sprite: Sprite, bank: dict, new_raw: dict, force: bool) -> dict:
    """Write the changed images of one bank. First in place (each image keeps its size
    field, the payload is padded); if one does not fit, repack the whole bank into the
    original byte range."""
    images = bank["images"]
    in_place = {}
    failed = []
    for im in images:
        if im["gidx"] not in new_raw:
            continue
        cands = candidates(new_raw[im["gidx"]], im)
        fits = {m: p for m, p in cands.items() if len(p) <= im["size"]}
        if not fits:
            failed.append((im, min(len(p) for p in cands.values())))
            continue
        orig = mode_of(im["flags"])
        mode = orig if orig in fits else min(fits, key=lambda m: len(fits[m]))
        in_place[im["gidx"]] = (mode, fits[mode])
    rep = {"bank": bank["images"][0]["bank"], "strategy": "in-place", "images": len(in_place)}
    if not failed:
        for im in images:
            if im["gidx"] not in in_place:
                continue
            mode, payload = in_place[im["gidx"]]
            span = (im["size"] + 3) // 4 * 4
            out[im["data"]:im["data"] + span] = payload + bytes(span - len(payload))
            flags = (im["flags"] & ~0xC) | MODE_BITS[mode]
            struct.pack_into("<I", out, im["off"], im["size"] | (flags << 24))
        return rep

    # repack: sizes change, images shift, the bank keeps its start and must end at or before
    # its old end. Unchanged images keep their bytes; if that is too much, shrink them too.
    def layout(shrink_all: bool):
        blobs = []
        for im in images:
            if im["gidx"] in new_raw or shrink_all:
                raw = new_raw.get(im["gidx"], sprite.decoded[im["gidx"]])
                cands = candidates(raw, im)
                mode = min(cands, key=lambda m: len(cands[m]))
                flags = (im["flags"] & ~0xC) | MODE_BITS[mode]
                payload = cands[mode]
            else:
                flags = im["flags"]
                payload = bytes(gf[im["data"]:im["data"] + im["size"]])
            blobs.append((im, flags, payload))
        total = 4 + sum(12 + (len(p) + 3) // 4 * 4 for _, _, p in blobs)
        return blobs, total

    room = bank["end"] - bank["offset"]
    blobs, total = layout(False)
    rep["strategy"] = "repacked"
    if total > room:
        blobs, total = layout(True)
        rep["strategy"] = "repacked, all images re-encoded"
    if total > room:
        names = ", ".join(f"image {im['gidx']} (needs {need} bytes, has {im['size']})" for im, need in failed)
        raise SpriteError(f"the edited images do not fit: {names}. Even repacking the whole image bank "
                          f"needs {total} bytes, the original has {room}. Use fewer distinct pixels/colors "
                          f"(runs of equal bytes compress best) or change fewer images.")
    pos = bank["offset"] + 4
    for im, flags, payload in blobs:
        span = (len(payload) + 3) // 4 * 4
        struct.pack_into("<IHHHH", out, pos, len(payload) | (flags << 24), im["x"], im["y"], im["w"], im["h"])
        out[pos + 12:pos + 12 + span] = payload + bytes(span - len(payload))
        pos += 12 + span
    out[pos:bank["end"]] = bytes(bank["end"] - pos)
    rep["bytes_used"] = total
    rep["bytes_available"] = room
    return rep


# --- check --------------------------------------------------------------------------

def check_sprite(gf: bytes, id_: str, log=print) -> bool:
    """Structural checks, encoder round trip, and export -> import without edits."""
    spec = SET_BY_ID[id_]
    ok = True

    def fail(msg):
        nonlocal ok
        ok = False
        log(f"  FAIL {msg}")

    sprite = Sprite(gf, spec)
    ani = sprite.ani
    nanim = len(ani["animations"])
    nframes = sum(len(a) for a in ani["animations"])
    nparts = sum(len(f["part_list"]) for a in ani["animations"] for f in a)
    log(f"  .ANI {spec['ani'][1]} bytes: {ani['counts'][0]} images, {ani['counts'][1]} part lists, "
        f"{ani['counts'][2]} parts, {nanim} animations, {nframes} frames ({nparts} parts drawn)")
    log(f"  banks: " + ", ".join(f"{b['count']} images at +{b['offset'] - spec['pack']:#x}"
                                   f" .. +{b['end'] - spec['pack']:#x}" for b in sprite.banks))
    if sprite.unmatched:
        fail(f"{len(sprite.unmatched)} used AnimImage(s) have no bank image with the same rect: "
             f"{sorted(sprite.unmatched)}")
    else:
        log(f"  every used AnimImage ({len(sprite.used_images)}) has a bank image with the same rect")

    # encoder: decode -> encode -> decode, per image and per mode
    smaller = same = larger = 0
    for im in sprite.images:
        raw = sprite.decoded[im["gidx"]]
        for mode, payload in candidates(raw, im).items():
            fake = dict(im, flags=(im["flags"] & ~0xC) | MODE_BITS[mode], size=len(payload), data=0)
            back, used = decode_payload(bytes(payload), fake)
            if back != raw:
                fail(f"image {im['gidx']}: {mode} re-encoding does not decode to the same pixels")
        enc = encode_payload(raw, im["w"], im["h"], mode_of(im["flags"]))
        if mode_of(im["flags"]) == "raw":
            same += 1
        elif len(enc) < im["used"]:
            smaller += 1
        elif len(enc) == im["used"]:
            same += 1
        else:
            larger += 1
    log(f"  re-encoding decodes equal for all {len(sprite.images)} images x 3 modes; "
        f"vs the original payloads: {smaller} smaller, {same} equal, {larger} larger")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        export_sprite(gf, id_, tmpdir)
        new, rep = patch_set(gf, id_, tmpdir)
        if rep["changed_images"]:
            fail(f"unedited export reported changed images {rep['changed_images']}")
        if new != gf:
            fail("import without edits did not reproduce 00_gf.bin byte for byte")
        else:
            lo = sprite.banks[0]["offset"]
            hi = sprite.banks[-1]["end"]
            log(f"  export -> import without edits: 00_gf.bin identical ({len(gf)} bytes; bank bytes "
                f"{hi - lo} identical, sha1 {hashlib.sha1(gf[lo:hi]).hexdigest()[:12]})")

        # forced re-encode of every image of the bank (decode-equal, may reshuffle bytes)
        new, rep = patch_set(gf, id_, tmpdir, force_reencode=True)
        again = Sprite(new, spec)
        if any(again.decoded[k] != v for k, v in sprite.decoded.items()):
            fail("forced re-encode changed pixels")
        else:
            moved = sum(1 for k in range(spec['pack'], spec['pack'] + spec['size']) if gf[k] != new[k])
            strat = ",".join(b["strategy"] for b in rep["banks"])
            log(f"  forced re-encode of all {len(rep['changed_images'])} images ({strat}): decode-equal, "
                f"{moved} bytes differ from the original encoding, file size unchanged: {len(new) == len(gf)}")

        # an edit: one texture pixel and one palette color
        tex = next((e for e in json.loads((tmpdir / "sprite.json").read_text())["images"]
                    if e["role"] == "texture" and e.get("palette_image") is not None), None)
        if tex is not None:
            png = Image.open(tmpdir / tex["file"])
            pal = png.getpalette()
            pal[3:6] = [200, 40, 120]
            png.putpalette(pal)
            px = png.load()
            px[0, 0] = 1 if px[0, 0] != 1 else 2
            png.save(tmpdir / tex["file"], transparency=png.info.get("transparency"))
            new, rep = patch_set(gf, id_, tmpdir)
            after = Sprite(new, spec)
            im = next(i for i in after.images if i["gidx"] == tex["gidx"])
            _, idx = after.texture_indices(im)
            _, idx0 = sprite.texture_indices(sprite.images[tex["gidx"]])
            if idx[0] == idx0[0] or idx[1:] != idx0[1:]:
                fail("edited pixel did not round trip")
            wsrc = after.palette_words(tex["palette_anim_images"][0], 16)
            want = (200 >> 3) | ((40 >> 3) << 5) | ((120 >> 3) << 10)
            if wsrc[1] & 0x7FFF != want:
                fail(f"edited palette color is {wsrc[1]:#06x}, wanted {want:#06x}")
            lo = min(b["offset"] for b in sprite.banks)
            hi = max(b["end"] for b in sprite.banks)
            if gf[:lo] != new[:lo] or gf[hi:] != new[hi:]:
                fail("an edit changed bytes outside the image bank")
            outside = [k for k in range(lo, hi) if gf[k] != new[k]]
            log(f"  edit test (1 pixel + 1 palette color): decoded back as intended, {len(outside)} bytes "
                f"changed, all inside the bank ({rep['banks'][0]['strategy']})")
    return ok


# --- command line -------------------------------------------------------------------

def read_gf(path: str | None) -> bytes:
    p = Path(path) if path else DEFAULT_GF
    if not p.is_file():
        raise SpriteError(f"{p} does not exist: run `python hm.py extract` first (or pass --gf)")
    return p.read_bytes()


def cmd_list(_args) -> None:
    print(f"{'id':8} {'member':10} {'pack offset':>12} {'.ANI':>16} {'bank':>9}  description")
    for s in SETS:
        ani = f"+{s['ani'][0]:#x}/{s['ani'][1]:#x}"
        print(f"{s['id']:8} {'00_gf.bin':10} {s['pack']:#12x} {ani:>16} +{s['bank']:#x}".ljust(60)
              + f" {s['name']}")
    print("\nsource of each entry: python tools/hmsprite.py list --sources, docs/sprites.md")
    if _args.sources:
        for s in SETS:
            print(f"{s['id']}: {s['source']}" + (f" ({s['note']})" if s["note"] else ""))


def need(id_: str) -> str:
    if id_ not in SET_BY_ID:
        raise SpriteError(f"unknown sprite '{id_}' (known: {', '.join(SET_BY_ID)})")
    return id_


def cmd_export(args) -> None:
    meta = export_sprite(read_gf(args.gf), need(args.id), Path(args.outdir))
    tex = sum(1 for i in meta["images"] if i["role"] == "texture")
    pal = sum(1 for i in meta["images"] if i["role"] == "palette")
    print(f"exported {args.id}: {tex} texture images (img_N.png), {pal} palettes (pal_N.png), "
          f"{len(meta['animations'])} animations (anim_NN.png, sheet.png), sprite.json -> {args.outdir}")


def cmd_check(args) -> None:
    gf = read_gf(args.gf)
    ids = [need(i) for i in args.ids] or [s["id"] for s in SETS]
    bad = []
    for id_ in ids:
        print(f"{id_}:")
        try:
            good = check_sprite(gf, id_)
        except SpriteError as error:
            print(f"  FAIL {error}")
            good = False
        print("  " + ("ok" if good else "FAILED"))
        if not good:
            bad.append(id_)
    if bad:
        raise SystemExit(f"hmsprite: check failed for {', '.join(bad)}")
    print(f"all {len(ids)} sprite sets ok")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="hmsprite", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list")
    p.add_argument("--sources", action="store_true")
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("export")
    p.add_argument("id")
    p.add_argument("outdir")
    p.add_argument("--gf")
    p.set_defaults(func=cmd_export)
    p = sub.add_parser("check")
    p.add_argument("ids", nargs="*")
    p.add_argument("--gf")
    p.set_defaults(func=cmd_check)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except SpriteError as error:
        raise SystemExit(f"hmsprite: {error}") from None


if __name__ == "__main__":
    main()
