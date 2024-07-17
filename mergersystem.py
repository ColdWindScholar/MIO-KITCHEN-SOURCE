"""
Copyright (C) 2013  Cybojenix <anthonydking@slimroms.net>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# concept taken from thecubed's guide on xda
# http://forum.xda-developers.com/showpost.php?p=46486167&postcount=8

from __future__ import print_function
import os
import subprocess

print(
    "System Image Merger Copyright (C) 2013  Cybojenix <anthonydking@slimroms.net>\n"
    "This program comes with ABSOLUTELY NO WARRANTY\n"
    "This is free software, and you are welcome to redistribute it\n"
    "under certain conditions"
)

if not os.name == "posix":
    raise Exception("This script is designed for Linux, it will not work on Windows")


def dd_main(dd_if, dd_of="system.img", args=None):
    """
        dd_if: the input file. ex- "system_2342.bin"
        dd_of: the output file ex- "system.img"
        args: for any other argument that dd uses. must be in the form:
                  ["seek=20391", "conv=notrunc"]
        returns: nothing
    """
    cmd_line = [
        "dd",
        "=".join(["if", dd_if]),
        "=".join(["of", dd_of]),
    ]
    if not args is None:
        cmd_line.extend(args)

    # we shall allow the output information to be seen by the user
    temp = subprocess.Popen(cmd_line)
    temp.wait()
    if not temp.poll() == 0:
        raise Exception("There was an issue with dd. please report")
    del temp


# this command is used repeatedly, give it a function
def dd_seek(dd_if, seek, dd_of="system.img", args=None):
    """
        dd_if: the input file. ex- "system_2342.bin"
        dd_of: the output file ex- "system.img"
        seek: the position of which to start writing from
              ex- int("34324")
        args: for any other argument that dd uses. must be in the form:
                  ["seek=20391", "conv=notrunc"]
        returns: nothing
    """
    extension = ["=".join(["seek", seek])]
    if not args is None:
        extension.extend(args)
    dd_main(dd_if, dd_of, extension)


def find_files():
    """
        returns: a list of files found that match the form "system_.*.bin"
    """
    listing = os.listdir(".")
    found = []
    for bin_file in listing:
        if bin_file.startswith("system_") and bin_file.endswith(".bin"):
            found.append(bin_file)
    return found


def order_files(system_bins):
    """
        system_bins: a list of the system bins found
                     ex- ["system_455.bin", "system_342.bin"]
        returns: an ordered list with turples based on the numerical data in the file name
                 ex- [("system_342.bin", 342), (system_455.bin", 455)]
    """
    ordered_list = []
    for system_bin in system_bins:
        try:
            x = system_bin.strip("system_").strip(".bin")
        except ValueError:
            raise Exception("the file formatting has changed. Please contact me")
        ordered_list.append(x)
    ordered_list.sort(key=int)

    final_list = []
    for x in ordered_list:
        temp_turple = (int(x), "".join(["system_", x, ".bin"]))
        final_list.append(temp_turple)
    return final_list


def start_image(file_list, offset):
    """
        file_list: a list with turples of the files and numerical data they hold
        offset: the amount of bytes that the system.img is offset by
        returns: nothing
    """
    last = file_list[-1:][0][0]
    size = last  # - offset # fudge factor to extend the system image more. allows for mounting
    print("writing zero's to the base of the image. this can take a while")
    dd_main("/dev/zero", args=["bs=512", "=".join(["count", str(size)])])


def bin_to_image(file_list, offset):
    """
        file_list: a list with turples of the files and numerical data they hold
        returns: nothing
    """
    #dd_main(file_list[0][1], args=["conv=notrunc", "bs=512"])
    for system_bin in file_list:  #[1:]:
        seek = str(system_bin[0] - offset)
        print("writing %s to system.img" % system_bin[1])
        dd_seek(system_bin[1], seek, args=["bs=512", "conv=notrunc"])


def print_after():
    print(
        "the system image has been made. to mount it, run\n"
        "Lazy Script mod by @Innfinite4evr\n"
        "...\n"
        "sudo mkdir -p /mnt/lgimg && mount system.img /mnt/lgimg\n"
    )


def main():
    if os.path.isfile("system.img"):
        os.remove("system.img")
    system_files = find_files()
    ordered = order_files(system_files)
    offset = ordered[0][0]
    start_image(ordered, offset)
    bin_to_image(ordered, offset)
    print_after()


if __name__ == '__main__':
    main()

"""
system_binss = find_files()
ordered = order_files(system_binss)
offset = ordered[0][0]
print(ordered)
start_image(ordered, offset)
bin_to_image(ordered, offset)
for turple_file in ordered:
    print(", ".join([turple_file[1], str(turple_file[0])]))
"""
