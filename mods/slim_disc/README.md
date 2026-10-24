# Slim Disc

Replaces `DUMMY.DAT` with an empty file, making the disc image about 33 MB smaller
(214 MB → 176 MB).

`DUMMY.DAT` is filler at the end of the disc. Its contents are copies of pieces of
`A_FILE.BIN` (its first sectors are identical to the start of `02_messege0.bin`). The
game's code never opens it: it finds files by name, and `grep -rn DUMMY .hm/decomp/src`
finds nothing.

Contains no code, so it uses no RAM. Works with any other mod.
