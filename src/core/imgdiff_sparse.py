#!/usr/bin/env python3
"""
imgdiff_sparse.py - turn "one file changed in a 1.3 GB partition" into a sparse
image that carries ONLY the changed blocks, flashable with fastboot/fastbootd.

The emitted file is a standard Android sparse image (libsparse format):
  * changed blocks   -> RAW chunks (0xCAC1)
  * unchanged blocks -> DONT_CARE chunks (0xCAC3), i.e. "skip, do not write"
  * changed-to-zero  -> FILL chunks (0xCAC2) with pattern 0

Because DONT_CARE blocks are not part of the transferred payload, the image is
as small as the delta. Flashing it writes only the RAW/FILL ranges.

Sparse format reference (verified against AOSP
system/core/libsparse/sparse_format.h):
  file header, 28 bytes:
    u32 magic = 0xED26FF3A, u16 major = 1, u16 minor = 0,
    u16 file_hdr_sz = 28, u16 chunk_hdr_sz = 12,
    u32 blk_sz, u32 total_blks, u32 total_chunks, u32 image_checksum (0 = none)
  chunk header, 12 bytes:
    u16 type, u16 reserved, u32 chunk_sz (in blocks), u32 total_sz (incl. header)
    RAW        -> chunk_sz*blk_sz bytes of data follow
    FILL       -> 4 bytes of fill pattern follow
    DONT_CARE  -> nothing follows
    CRC32      -> 4 bytes follow

Usage:
  imgdiff_sparse.py OLD.img NEW.img -o changed.simg [--bs 4096] [--verify]
                    [--extents] [--emit-dd DIR] [--no-fill] [--max-chunk-blocks N]

Exit codes: 0 ok, 1 usage/format error, 2 verification mismatch.
"""

import argparse
import hashlib
import os
import struct
import sys
import tempfile

SPARSE_MAGIC = 0xED26FF3A
CHUNK_RAW = 0xCAC1
CHUNK_FILL = 0xCAC2
CHUNK_DONT_CARE = 0xCAC3
CHUNK_CRC32 = 0xCAC4

FILE_HDR_SZ = 28
CHUNK_HDR_SZ = 12


# ---------------------------------------------------------------- sparse I/O

def is_sparse(path):
    with open(path, "rb") as f:
        head = f.read(4)
    return len(head) == 4 and struct.unpack("<I", head)[0] == SPARSE_MAGIC


def unsparse_to(src, dst):
    """Expand a sparse image to a raw file. Returns (nbytes, blk_sz)."""
    with open(src, "rb") as f, open(dst, "wb") as out:
        (magic, _maj, _min, fhdr, chdr, blk_sz, total_blks,
         total_chunks, _csum) = struct.unpack("<IHHHHIIII", f.read(28))
        if magic != SPARSE_MAGIC:
            raise SystemExit("not a sparse image: %s" % src)
        f.seek(fhdr)  # tolerate extended headers
        written = 0
        for _ in range(total_chunks):
            ctype, _res, chunk_sz, total_sz = struct.unpack("<HHII", f.read(12))
            payload = total_sz - chdr
            nblocks_bytes = chunk_sz * blk_sz
            if ctype == CHUNK_RAW:
                if payload != nblocks_bytes:
                    raise SystemExit("bad RAW chunk length in %s" % src)
                remaining = payload
                while remaining:
                    buf = f.read(min(1 << 20, remaining))
                    if not buf:
                        raise SystemExit("truncated sparse image: %s" % src)
                    out.write(buf)
                    remaining -= len(buf)
                written += nblocks_bytes
            elif ctype == CHUNK_FILL:
                pat = f.read(4)
                out.write(pat * (nblocks_bytes // 4))
                written += nblocks_bytes
            elif ctype == CHUNK_DONT_CARE:
                zero = b"\0" * (1 << 20)
                left = nblocks_bytes
                while left:
                    n = min(len(zero), left)
                    out.write(zero[:n])
                    left -= n
                written += nblocks_bytes
            elif ctype == CHUNK_CRC32:
                f.read(4)
            else:
                raise SystemExit("unknown sparse chunk type 0x%04X in %s" % (ctype, src))
            # skip any padding the writer added
            consumed = {CHUNK_RAW: payload, CHUNK_FILL: 4, CHUNK_CRC32: 4}.get(ctype, 0)
            if chdr + consumed < total_sz:
                f.seek(total_sz - consumed - chdr, 1)
        return written, blk_sz


class RawReader:
    """Reads a raw image; transparently expands sparse inputs to a temp file."""

    def __init__(self, path):
        self.tmp = None
        if is_sparse(path):
            fd, tmp = tempfile.mkstemp(prefix="unsparse_", suffix=".bin")
            os.close(fd)
            self.size, _bs = unsparse_to(path, tmp)
            self.tmp = tmp
            self.path = tmp
            self.was_sparse = True
        else:
            self.path = path
            self.size = os.path.getsize(path)
            self.was_sparse = False
        self.f = open(self.path, "rb")

    def close(self):
        self.f.close()
        if self.tmp:
            try:
                os.unlink(self.tmp)
            except OSError:
                pass


# ---------------------------------------------------------------- diff engine

def diff(old_path, new_path, out_path, blk_sz, max_chunk_blocks,
         use_fill=True, want_extents=False):
    old_rd = RawReader(old_path)
    new_rd = RawReader(new_path)

    old_blocks = old_rd.size // blk_sz
    new_blocks = new_rd.size // blk_sz
    total_blks = new_blocks
    grew = new_rd.size > old_rd.size
    shrank = new_rd.size < old_rd.size

    counts = {"raw": 0, "fill": 0, "dont": 0}
    changed_blocks = 0
    extents = []          # (first_block, nblocks) of changed ranges
    run_start = None

    out = open(out_path, "wb")
    out.write(b"\0" * FILE_HDR_SZ)          # placeholder header, fixed up later
    total_chunks = 0
    raw_buf = bytearray()                   # pending RAW payload
    raw_blocks = 0
    fill_run = 0                            # pending FILL-zero blocks
    dont_run = 0                            # pending DONT_CARE blocks

    def flush_raw():
        nonlocal raw_buf, raw_blocks, total_chunks
        if raw_blocks:
            out.write(struct.pack("<HHII", CHUNK_RAW, 0, raw_blocks,
                                  CHUNK_HDR_SZ + len(raw_buf)))
            out.write(raw_buf)
            counts["raw"] += 1
            total_chunks += 1
            raw_buf = bytearray()
            raw_blocks = 0

    def flush_fill():
        nonlocal fill_run, total_chunks
        if fill_run:
            out.write(struct.pack("<HHII", CHUNK_FILL, 0, fill_run, CHUNK_HDR_SZ + 4))
            out.write(b"\0\0\0\0")
            counts["fill"] += 1
            total_chunks += 1
            fill_run = 0

    def flush_dont():
        nonlocal dont_run, total_chunks
        if dont_run:
            out.write(struct.pack("<HHII", CHUNK_DONT_CARE, 0, dont_run, CHUNK_HDR_SZ))
            counts["dont"] += 1
            total_chunks += 1
            dont_run = 0

    def flush_all():
        flush_raw(); flush_fill(); flush_dont()

    old_rd.f.seek(0)
    new_rd.f.seek(0)
    buf_old = b""
    buf_new = b""
    chunk_bytes = 8 << 20
    blk = blk_sz

    try:
        pos_blk = 0
        while pos_blk < total_blks:
            n = min(chunk_bytes // blk, total_blks - pos_blk)
            want = n * blk
            cur_old = old_rd.f.read(want) if pos_blk < old_blocks else b""
            cur_new = new_rd.f.read(want)
            if len(cur_new) != want:
                raise SystemExit("short read on new image at block %d" % pos_blk)
            if len(cur_old) < want:  # new is longer than old
                cur_old = cur_old + b"\0" * (want - len(cur_old))

            i = 0
            while i < n:
                off = i * blk
                ob = cur_old[off:off + blk]
                nb = cur_new[off:off + blk]
                if ob == nb:
                    if run_start is not None:
                        extents.append((run_start, pos_blk + i - run_start))
                        run_start = None
                    flush_raw(); flush_fill()
                    dont_run += 1
                else:
                    if dont_run:
                        flush_dont()
                    changed_blocks += 1
                    if run_start is None:
                        run_start = pos_blk + i
                    if use_fill and nb == b"\0" * blk:
                        flush_raw()
                        fill_run += 1
                    else:
                        flush_fill()
                        raw_buf += nb
                        raw_blocks += 1
                        if raw_blocks >= max_chunk_blocks:
                            flush_raw()
                i += 1
            pos_blk += n
        if run_start is not None:
            extents.append((run_start, total_blks - run_start))
        flush_all()

        # fix up the header now that chunk/block counts are known
        end = out.tell()
        out.seek(0)
        out.write(struct.pack("<IHHHHIIII", SPARSE_MAGIC, 1, 0, FILE_HDR_SZ,
                              CHUNK_HDR_SZ, blk_sz, total_blks, total_chunks, 0))
        out.seek(end)
    finally:
        out.close()
        old_rd.close()
        new_rd.close()

    return {
        "blk_sz": blk_sz,
        "total_blks": total_blks,
        "total_chunks": total_chunks,
        "counts": counts,
        "changed_blocks": changed_blocks,
        "extents": extents if want_extents else [],
        "grew": grew,
        "shrank": shrank,
        "old_size": os.path.getsize(old_path) if not old_rd.was_sparse else None,
        "new_blocks": new_blocks,
        "old_blocks": old_blocks,
    }


# ---------------------------------------------------------------- verification

def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def verify(out_path, old_path, new_path, blk_sz):
    """Apply the emitted sparse image over OLD and compare hashes with NEW.

    This is the check that matters: it proves the sparse image, interpreted the
    way libsparse interprets it, reproduces the new image byte-for-byte.
    """
    old_rd = RawReader(old_path)
    new_rd = RawReader(new_path)
    fd, tmp = tempfile.mkstemp(prefix="reconstruct_", suffix=".bin")
    os.close(fd)
    try:
        # seed the reconstruction with the current (old) contents
        with open(old_rd.path, "rb") as s, open(tmp, "wb") as d:
            while True:
                b = s.read(1 << 22)
                if not b:
                    break
                d.write(b)
        if os.path.getsize(tmp) != new_rd.size:     # image grew or shrank
            with open(tmp, "r+b") as d:
                d.truncate(new_rd.size)

        with open(out_path, "rb") as f, open(tmp, "r+b") as dst:
            (magic, _ma, _mi, fhdr, chdr, blk, _tb, nchunks,
             _cs) = struct.unpack("<IHHHHIIII", f.read(28))
            if magic != SPARSE_MAGIC:
                raise SystemExit("emitted file is not sparse")
            f.seek(fhdr)
            pos = 0
            for _ in range(nchunks):
                ctype, _r, chunk_sz, total_sz = struct.unpack("<HHII", f.read(12))
                nbytes = chunk_sz * blk
                extra = 0
                if ctype == CHUNK_RAW:
                    remaining = nbytes
                    dst.seek(pos)
                    while remaining:
                        b = f.read(min(1 << 20, remaining))
                        if not b:
                            raise SystemExit("truncated emitted sparse image")
                        dst.write(b)
                        remaining -= len(b)
                    pos += nbytes
                    extra = nbytes
                elif ctype == CHUNK_FILL:
                    pat = f.read(4)
                    dst.seek(pos)
                    dst.write(pat * (nbytes // 4))
                    pos += nbytes
                    extra = 4
                elif ctype == CHUNK_DONT_CARE:
                    pos += nbytes
                elif ctype == CHUNK_CRC32:
                    f.read(4)
                    extra = 4
                else:
                    raise SystemExit("unknown chunk type 0x%04X in emitted image" % ctype)
                pad = total_sz - chdr - extra
                if pad > 0:
                    f.seek(pad, 1)

        got = _sha(tmp)
        want = _sha(new_rd.path)
        return got, want, got == want
    finally:
        old_rd.close()
        new_rd.close()
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ---------------------------------------------------------------- dd emission

def emit_dd(out_path, image_path, old_path, report, dd_dir):
    """Write changed.bin + apply.sh: dd the changed extents over the block dev."""
    os.makedirs(dd_dir, exist_ok=True)
    bin_path = os.path.join(dd_dir, "changed.bin")
    sh_path = os.path.join(dd_dir, "apply.sh")
    blk = report["blk_sz"]
    extents = report["extents"]
    with open(image_path, "rb") as s, open(bin_path, "wb") as d:
        off = 0
        for first, n in extents:
            s.seek(first * blk)
            d.write(s.read(n * blk))
            off += n * blk
    with open(sh_path, "w") as f:
        f.write("#!/system/bin/sh\n")
        f.write("# apply changed extents of a partition image over the live block device\n")
        f.write("# usage: sh apply.sh /dev/block/by-name/vendor   (partition MUST be unmounted)\n")
        f.write('set -e\nDEV="${1:?usage: apply.sh <block-dev>}"\n')
        f.write('SRC="$(dirname "$0")/changed.bin"\n')
        cur = 0
        for first, n in extents:
            f.write("dd if=$SRC of=$DEV bs=%d skip=%d count=%d seek=%d conv=fsync,notrunc\n"
                    % (blk, cur, n, first))
            cur += n
        f.write("sync\n")
    os.chmod(sh_path, 0o755)
    return bin_path, sh_path


# ---------------------------------------------------------------- CLI

def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f %s" % (n, unit)
        n /= 1024.0


def main():
    ap = argparse.ArgumentParser(description="changed-blocks-only sparse image generator")
    ap.add_argument("old", help="current image on the device (raw or sparse)")
    ap.add_argument("new", help="rebuilt image")
    ap.add_argument("-o", "--out", default="changed.simg", help="output sparse image")
    ap.add_argument("--bs", type=int, default=4096, help="block size (default 4096)")
    ap.add_argument("--max-chunk-blocks", type=int, default=4096,
                    help="max blocks per RAW chunk (default 4096 = 16 MiB @4k)")
    ap.add_argument("--no-fill", action="store_true", help="do not use FILL for zeroed runs")
    ap.add_argument("--verify", action="store_true",
                    help="apply the result over OLD and compare sha256 with NEW")
    ap.add_argument("--extents", action="store_true", help="print changed extents")
    ap.add_argument("--emit-dd", metavar="DIR", help="also emit changed.bin + apply.sh")
    ap.add_argument("--report", metavar="FILE", help="write a text report")
    ap.add_argument("--allow-shrink", action="store_true",
                    help="allow NEW smaller than OLD (DONT_CARE up to the new size)")
    args = ap.parse_args()

    for p in (args.old, args.new):
        if not os.path.isfile(p):
            raise SystemExit("no such file: %s" % p)
    if args.bs & (args.bs - 1):
        raise SystemExit("--bs must be a power of two")

    new_size = os.path.getsize(args.new)
    old_size = os.path.getsize(args.old)
    if new_size % args.bs or old_size % args.bs:
        print("WARN: image size not a multiple of %d; the tail blocks are compared padded"
              % args.bs, file=sys.stderr)

    r = diff(args.old, args.new, args.out, args.bs, args.max_chunk_blocks,
             use_fill=not args.no_fill, want_extents=(args.extents or bool(args.emit_dd)))

    if r["shrank"] and not args.allow_shrink:
        raise SystemExit("NEW is smaller than OLD (%d < %d bytes); pass --allow-shrink if intended"
                         % (new_size, old_size))

    out_size = os.path.getsize(args.out)
    changed_bytes = r["changed_blocks"] * args.bs
    lines = []
    lines.append("old image        : %s (%s)" % (args.old, human(old_size)))
    lines.append("new image        : %s (%s)" % (args.new, human(new_size)))
    lines.append("block size       : %d" % args.bs)
    lines.append("blocks total     : %d (%s)" % (r["total_blks"], human(r["total_blks"] * args.bs)))
    lines.append("blocks changed   : %d (%s of data)" % (r["changed_blocks"], human(changed_bytes)))
    lines.append("chunks           : %d (raw %d, fill %d, dont-care %d)"
                 % (r["total_chunks"], r["counts"]["raw"], r["counts"]["fill"], r["counts"]["dont"]))
    lines.append("sparse image     : %s" % human(out_size))
    if new_size:
        lines.append("transfer saving  : %.2f%% vs full image"
                     % (100.0 * (1 - out_size / float(new_size))))
    if r["grew"]:
        lines.append("NOTE             : new image is larger; trailing blocks are RAW")
    if r["extents"]:
        ex = r["extents"]
        lines.append("changed extents  : %d runs, largest %d blocks @ block %d"
                     % (len(ex), max(n for _f, n in ex), max(ex, key=lambda t: t[1])[0]))

    if args.verify:
        got, want, ok = verify(args.out, args.old, args.new, args.bs)
        lines.append("verify           : %s" % ("PASS" if ok else "FAIL"))
        lines.append("  reconstructed  : sha256 %s" % got)
        lines.append("  new image      : sha256 %s" % want)
        print("\n".join(lines))
        if args.extents:
            print("\nchanged extents (first_block, nblocks):")
            for first, n in r["extents"][:200]:
                print("  %10d  %6d  (byte offset %d, %s)" % (first, n, first * args.bs, human(n * args.bs)))
            if len(r["extents"]) > 200:
                print("  ... %d more" % (len(r["extents"]) - 200))
        if args.report:
            with open(args.report, "w") as f:
                f.write("\n".join(lines) + "\n")
        if not ok:
            return 2
    else:
        print("\n".join(lines))
        if args.extents:
            print("\nchanged extents (first_block, nblocks):")
            for first, n in r["extents"][:200]:
                print("  %10d  %6d  (byte offset %d, %s)" % (first, n, first * args.bs, human(n * args.bs)))
        if args.report:
            with open(args.report, "w") as f:
                f.write("\n".join(lines) + "\n")

    if args.emit_dd:
        b, s = emit_dd(args.out, args.new, args.old, r, args.emit_dd)
        print("dd payload       : %s + %s" % (b, s))
    print("output           : %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
