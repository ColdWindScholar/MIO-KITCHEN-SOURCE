# `pygpt` - Tools to read GPT Images

`pygpt` is primarily meant to be a library to make reading and extracting data
from GPT images (dumped from disks, raw flash, etc.) easy.

It wants to smell pythonic, so constructs like iterators are used extensively.

## Documentation

Someday there will be documentation.

## Usage

The `gpt_reader.py` file has a simple tool that reads an image, decodes the table,
then iterates through the partitions available. If you specify `-b` and, optionally
an output directory with `-O`, the partitions will be pulled out of the image and
written to disk, with a filename equivalent to the partition's name.

*Note:* If the partition names collide, the app will overwrite with the last partition
of that name. Probably not a desirable behaviour.

Invoke it simply with `python3 gpt_reader.py -O out_dir -b gpt_image_file.bin`.

Specify the `-v` flag if you really want to see what goes into the sausage.

## Robustness

This isn't super robust, yet. It will support using the backup GPT, and load the
partition table from there, if the primary GPT is busted. However, if any of the
CRC checks fail, or some of the basic sanity checks fail, the tool will stop. Eventually
the tool might support overriding these parameters.

