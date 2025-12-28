import io
import os
import subprocess
import tarfile
import tempfile

import pytest

import PySquashfsImage


def _createFile(tarArchive, name, contents):
    tinfo = tarfile.TarInfo(name)
    tinfo.size = len(contents)
    tarArchive.addfile(tinfo, io.BytesIO(contents.encode()))


@pytest.mark.parametrize("compression", ["", "gzip", "lz4", "lzma", "lzo", "xz", "zstd"])
def test_compressions(compression):
    with tempfile.TemporaryDirectory() as tmpdir:
        tarPath = os.path.join(tmpdir, "foo.tar")
        with tarfile.open(name=tarPath, mode='w:') as tarArchive:
            _createFile(tarArchive, "foo", "bar")

        squashfsPath = os.path.join(tmpdir, f"foo.{compression if compression else 'no-compression'}.squashfs")
        compressionOptions = ["-comp", compression] if compression else ["-noI", "-noId", "-noD", "-noF", "-noX"]
        process = subprocess.Popen(
            ["sqfstar"] + compressionOptions + [squashfsPath], stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        with open(tarPath, 'rb') as file:
            process.communicate(file.read())

        with open(squashfsPath, 'rb') as file, PySquashfsImage.SquashFsImage(file) as image:
            entries = list(iter(image))
            assert len(entries) == 2
            assert entries[0].path == "/"
            assert entries[1].path == "/foo"
            assert image.read_file(entries[1].inode) == b"bar"
