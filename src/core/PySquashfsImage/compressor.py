from .const import Compression


class Compressor:
    name = "none"

    def uncompress(self, src, size, outsize):
        return src


class ZlibCompressor(Compressor):
    name = "gzip"

    def __init__(self):
        import zlib
        self._lib = zlib

    def uncompress(self, src, size, outsize):
        return self._lib.decompress(src)


class LZOCompressor(Compressor):
    name = "lzo"

    def __init__(self):
        import lzo
        self._lib = lzo

    def uncompress(self, src, size, outsize):
        return self._lib.decompress(src, False, outsize)


class LZMACompressor(Compressor):
    name = "lzma"

    def __init__(self):
        try:
            import lzma
        except ImportError:
            from backports import lzma
        self._lib = lzma

    def uncompress(self, src, size, outsize):
        # https://github.com/plougher/squashfs-tools/blob/a04910367d64a5220f623944e15be282647d77ba/squashfs-tools/
        #   lzma_wrapper.c#L40
        # res = LzmaCompress(dest + LZMA_HEADER_SIZE, &outlen, src, size, dest,
        #                    &props_size, 5, block_size, 3, 0, 2, 32, 1);
        # https://github.com/jljusten/LZMA-SDK/blob/781863cdf592da3e97420f50de5dac056ad352a5/C/LzmaLib.h#L96
        # -> level=5, dictSize=block_size, lc=3, lp=0, pb=2, fb=32, numThreads=1
        # https://github.com/plougher/squashfs-tools/blob/a04910367d64a5220f623944e15be282647d77ba/squashfs-tools/
        #   lzma_wrapper.c#L30
        # For some reason, squashfs does not store raw lzma but adds a custom header of 5 B and 8 B little-endian
        # uncompressed size, which can be read with struct.unpack('<Q', src[5:5+8]))
        LZMA_PROPS_SIZE = 5
        LZMA_HEADER_SIZE = LZMA_PROPS_SIZE + 8
        return self._lib.decompress(
            src[LZMA_HEADER_SIZE:],
            format=self._lib.FORMAT_RAW,
            filters=[{"id": self._lib.FILTER_LZMA1, 'lc': 3, 'lp': 0, 'pb': 2}],
        )


class XZCompressor(Compressor):
    name = "xz"

    def __init__(self):
        try:
            import lzma
        except ImportError:
            from backports import lzma
        self._lib = lzma

    def uncompress(self, src, size, outsize):
        return self._lib.decompress(src)


class LZ4Compressor(Compressor):
    name = "lz4"

    def __init__(self):
        import lz4.block
        self._lib = lz4.block

    def uncompress(self, src, size, outsize):
        return self._lib.decompress(src, outsize)


class ZSTDCompressor(Compressor):
    name = "zstd"

    def __init__(self):
        import zstandard
        self._lib = zstandard.ZstdDecompressor()

    def uncompress(self, src, size, outsize):
        return self._lib.decompress(src)


compressors = {
    Compression.NO: Compressor,
    Compression.ZLIB: ZlibCompressor,
    Compression.LZMA: LZMACompressor,
    Compression.LZO: LZOCompressor,
    Compression.XZ: XZCompressor,
    Compression.LZ4: LZ4Compressor,
    Compression.ZSTD: ZSTDCompressor
}
