# Dynamic Partition Tools

## lpmake

lpmake is a command-line tool for generating a "super" partition image. It can currently generate two types of images:
* Sparse images, for traditional fastboot.
* Metadata-only images, for the lpflash utility.

The following command-line arguments are required:

* `-d,--device-size` - The size of the "super" partition on the device. It must match exactly, and it must be evenly divisible by the sector size (512 bytes).
* `-m,--metadata-size` - The maximum size that partition metadata may consume. A partition entry uses 64 bytes and an extent entry uses 16 bytes. The minimum size is 512 bytes.
* `-s,--metadata-slots` - The number of slots available for storing metadata. This should match the number of update slots on the device, 2 for A/B devices and 1 for non-A/B.
* `-p,--partition=DATA` - Add a partition to the metadata. At least one partition must be defined. The format for the data string is `<name>:<GUID>:<attributes>:<size>`. The attributes must be either `none` or `readonly`. The size will be rounded up to the nearest aligned block (see below).
* `-o,--output=FILE` - The output file for writing the image.

Optional arguments:

* `--alignment=N` - By default, lpmake will align partitions to 1MiB boundaries. However, an alternate alignment can be specified if desired. This is useful for devices with a minimum I/O request size where mis-aligned partition boundaries could be a performance issue.
* `--alignment-offset=N` - In some cases, the "super" partition is misaligned within its parent block device. This offset can be used to correct for that.
* `--sparse` - If set, the output image will be in sparse format for flashing with fastboot. Otherwise, by default, the image will be a minimal format usable with lpdump and lpflash.
* `-b,--block-size=N` - When writing a sparse image, the device may require a specific block size. That block size can be specified here. The alignment must be a multiple of the block size. By default the block size is 4096.
* `-i,--image=[NAME=FILE]` - When writing a sparse image, include the contents of FILE as the data for the partition named NAME. The file can be a normal file or a sparse image, but the destination size must be less than or equal to the partition size. This option is only available when creating sparse images.

Example usage. This specifies a 10GB super partition for an A/B device, with a single 64MiB "cache" partition.

```
lpmake --device-size 10240000000 \
       --metadata-size 65536     \
       --metadata-slots 2        \
       -o /tmp/super.img         \
       -p "cache:2da85788-f0e1-4fda-9ee7-e5177eab184b:none:67108864" \
       -i "cache=out/target/hikey960/cache.img"
```

## lpdump

lpdump displays pretty-printed partition metadata. It accepts a single argument, which can be:

* A path to a non-sparse image from lpmake.
* A path to a filesystem image or block device.

It also accepts an optional argument `-s,--slot=N` which can dump a specific metadata slot (the default is 0).

Usage: `lpdump [-s,--slot=N] PATH`

## lpadd

lpadd is a command-line tool for adding images to a super.img file, or a partition to a super\_empty.img file. This is useful for mixed or split builds involving dynamic partitions. The syntax is:

```
lpadd [options] SUPER_FILE PART_NAME GROUP_NAME [IMAGE_FILE]
```

The parameters are:
* `--readonly` - The partition should be mapped as read-only.
* `SUPER_FILE` - The `super.img` or `super_empty.img` file. If the image is sparsed, it will be temporarily unsparsed, and re-sparsed at the end.
* `PART_NAME` - The partition name. It must not already exist.
* `GROUP_NAME` - The updateable group name for the partition.
* `IMAGE_FILE` - If specified, the contents of the image will be embedded in the given super.img. This does not work for a `super_empty.img` file. If the source image is sparsed, the unsparsed content will be embedded. The new partition size will be the smallest block-aligned size capable of holding the entire image.

Note that when interacting with sparsed images, `lpadd` can consume a great deal of space in `TMPDIR`. If `TMPDIR` does not have enough free space, it can be set in the environment, eg:

```
TMPDIR=/path/to/temp lpadd ...
```

## lpflash

lpflash writes a non-sparse image from lpmake to a block device. It is intended to be run on the device itself.

Usage: `lpflash /dev/block/sdX /path/to/image/file`
