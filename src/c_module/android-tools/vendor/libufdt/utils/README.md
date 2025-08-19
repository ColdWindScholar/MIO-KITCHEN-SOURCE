libufdt `utils` folder
=====================

This folder contains utilities for device tree overlay.

mkdtimg (DEPRECATED, use mkdtboimg.py instead.)
-------

If your DTB/DTBO is in an unique partition, e.g. `dtb` and `dtbo` partition.
`mkdtimg` is a tool for creating the `dtb`/`dtbo` image.
You can use `mkdtimg` to pack one or more DTB/DTBO files into an image.

### Image Format

This is the layout for `dtb`/`dtbo` image:

```txt
  +---------------------------+  - -   -                    -
  |      dt_table_header      |  ^ |   v dt_entries_offset  | header_size
  +===========================+  | | - -                    -
  |      dt_table_entry #0    |  | | ^ | dt_entry_size
  +---------------------------+  | | | -
  |      dt_table_entry #1    |  | | |
  +---------------------------+  | | |
  |            ...            |  | | | dt_entry_size * dt_entry_count
  +---------------------------+  | | |
  |      dt_table_entry #N    |  | | v
  +===========================+  | | -
  | +-----------------------+ |  | |
  | |    fdt_header     #0  | |  | |
  + +-----------------------+ |  | |  dt_offset
  |      DTBO           #0    |  | v (dt_entry_entry #1)
  +===========================+  | _
  | +-----------------------+ |  | ^
  | |    fdt_header     #1  | |  | |
  + +-----------------------+ |  | |  dt_size
  |      DTBO           #1    |  | v (dt_entry_entry #1)
  +===========================+  | -
  |            ...            |  |
  +===========================+  |
  | +-----------------------+ |  |
  | |    fdt_header     #N  | |  | total_size
  + +-----------------------+ |  |
  |      DTBO           #N    |  v
  +---------------------------+  -
```

You can find the data structure `dt_table_header` and `dt_table_entry`
in file `src/dt_table.h`

### Build `mkdtimg`

Assume that you are at the root directory of the Android source.

1. `source build/envsetup.sh`
2. `lunch`
3. `mmma system/libufdt/util/src`

### Using `mkdtimg`

`mkdtimg` supports several commands, including `create`, `cfg_create`,
and `dump`.

#### `create` Command

Use the `create` command to create a `dtb`/`dtbo` image:

```sh
$mkdtimg create <image_filename> (<global-option>...) \
  <ftb1_filename> (<entry1_option>...) \
  <ftb2_filename> (<entry2_option>...) \
  ...
```

Each dtb/dtbo `ftbX_filename` will generate a `dt_table_entry` in image.
`entryX_options` are the values to assign to `dt_table_entry`. These values
can be any of the following:

```sh
  --id=<number|path>
  --rev=<number|path>
  --custom0=<number|path>
  --custom1=<number|path>
  --custom2=<number|path>
  --custom3=<number|path>
```

Number values can be a 32-bit digit (such as `68000`) or a hex number
(such as `0x6800`). Alternatively, you can specify a path using the format:

```
<full_node_path>:<property_name>
```

For example, `/board/:id`. `mkdtimg` will read the value from the path in
the DTB/DTBO file and assign into relative property in `dt_table_entry`.
It should be a 32-bits value.

You can also give a `global_option` as a default option for all entries.
The default value of `page_size` in `dt_table_header` is `2048`. You can
use `global_option` `--page_size=<number>` to assign a different value.

Example:

```dts
[board1.dts]

/dts-v1/;
/plugin/;

/ {
  compatible = "board_manufacturer,board_model";
  board_id = <0x00010000>;
  board_rev = <0x00010001>;
  another_hw_information = "some_data";
  ...
};

&device@0 {
  value = <0x1>;
  status = "okay";
};
```

```sh
$mkdtimg create dtbo.img --id=/:board_id --rev=/:board_rev --custom0=0xabc \
  board1.dtbo \
  board2.dtbo --id=0x6800 \
  board3.dtbo --id=0x6801 --custom0=0x123
```

* First `dt_table_entry` (`board1.dtbo`) `id` is `0x00010000` and `custom[0]`
  is `0x00000abc.`
* Second `id` is `0x00006800` and `custom[0]` is `0x00000abc`.
* Third `id` is `0x00006801` and `custom[0]` is `0x00000123`.
* All others use the default value (0).

#### `cfg_create` Command

The `cfg_create` command creates an image with a config file in the following
format:

```sh
# global options
  <global_option>
  ...
# entries
<ftb1_filename>     # comment
  <entry1_option>   # comment
  ...
<ftb2_filename>
  <entry2_option>
  ...
...
```

The `global_options` and `entryX_options` must start with one or more space
characters (these options are the same as create options, without the `--`
prefix). Empty lines or lines beginning with `#` are ignored.

Example:

```sh
[dtboimg.cfg]

# global options
  id=/:board_id
  rev=/:board_rev
  custom0=0xabc

board1.dtbo

board2.dtbo
  id=0x6800 # override the value of id in global options

board2.dtbo
```

```sh
$mkdtimg cfg_create dtbo.img dtboimg.cfg
```

#### `dump` Command

For `dtb`/`dtbo` images, use the `dump` command to print the information in
the image. Example:

```sh
$mkdtimg dump dtbo.img
dt_table_header:
               magic = d7b7ab1e
          total_size = 1300
         header_size = 32
       dt_entry_size = 32
      dt_entry_count = 3
   dt_entries_offset = 32
           page_size = 2048
             version = 0

dt_table_entry[0]:
             dt_size = 380
           dt_offset = 128
                  id = 00010000
                 rev = 00010001
           custom[0] = 00000abc
           custom[1] = 00000000
           custom[2] = 00000000
           custom[3] = 00000000
           (FDT)size = 380
     (FDT)compatible = board_manufacturer,board_model
...
```

#### `help` Command

Use `help` command to get more detail options. Example:

```sh
$mkdtimg help cfg_create
```
