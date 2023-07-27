#!/usr/bin/env python3
# (c) B. Kerler 2017-2020, licensed under MIT license
"""
Usage:
    ozipdecrypt.py --help
    ozipdecrypt.py <filename>

Options:
    Mode 1 for regular ozip, Mode 2 for CPH1803/CPH1909 [default: 1]
"""

import binascii
import os
import shutil
import stat
import zipfile

from Crypto.Cipher import AES


def main(file_arg):
    keys = [
        "D6EECF0AE5ACD4E0E9FE522DE7CE381E",  # mnkey
        "D6ECCF0AE5ACD4E0E92E522DE7C1381E",  # mkey
        "D6DCCF0AD5ACD4E0292E522DB7C1381E",
        # realkey, R9s CPH1607 MSM8953, Plus, R11, RMX1921 Realme XT, RMX1851EX Realme Android 10, RMX1992EX_11_OTA_1050
        "D7DCCE1AD4AFDCE2393E5161CBDC4321",  # testkey
        "D7DBCE2AD4ADDCE1393E5521CBDC4321",  # utilkey
        "D7DBCE1AD4AFDCE1393E5121CBDC4321",  # R11s CPH1719 MSM8976, Plus
        "D4D2CD61D4AFDCE13B5E01221BD14D20",  # FindX CPH1871 SDM845
        "261CC7131D7C1481294E532DB752381E",  # FindX
        "1CA21E12271335AE33AB81B2A7B14622",  # Realme 2 pro SDM660/MSM8976
        "D4D2CE11D4AFDCE13B3E0121CBD14D20",  # K1 SDM660/MSM8976
        "1C4C1EA3A12531AE491B21BB31613C11",  # Realme 3 Pro SDM710, X, 5 Pro, Q, RMX1921 Realme XT
        "1C4C1EA3A12531AE4A1B21BB31C13C21",  # Reno 10x zoom PCCM00 SDM855, CPH1921EX Reno 5G
        "1C4A11A3A12513AE441B23BB31513121",  # Reno 2 PCKM00 SDM730G
        "1C4A11A3A12589AE441A23BB31517733",  # Realme X2 SDM730G
        "1C4A11A3A22513AE541B53BB31513121",  # Realme 5 SDM665
        "2442CE821A4F352E33AE81B22BC1462E",  # R17 Pro SDM710
        "14C2CD6214CFDC2733AE81B22BC1462C",  # CPH1803 OppoA3s SDM450/MSM8953
        "1E38C1B72D522E29E0D4ACD50ACFDCD6",
        "12341EAAC4C123CE193556A1BBCC232D",
        "2143DCCB21513E39E1DCAFD41ACEDBD7",
        "2D23CCBBA1563519CE23C1C4AA1E3412",  # A77 CPH1715 MT6750T
        "172B3E14E46F3CE13E2B5121CBDC4321",  # Realme 1 MTK P60
        "ACAA1E12A71431CE4A1B21BBA1C1C6A2",  # Realme U1 RMX1831 MTK P70
        "ACAC1E13A72531AE4A1B22BB31C1CC22",  # Realme 3 RMX1825EX P70
        "1C4411A3A12533AE441B21BB31613C11",  # A1k CPH1923 MTK P22
        "1C4416A8A42717AE441523B336513121",  # Reno 3 PCRM00 MTK 1000L, CPH2059 OPPO A92, CPH2067 OPPO A72
        "55EEAA33112133AE441B23BB31513121",  # RenoAce SDM855Plus
        "ACAC1E13A12531AE4A1B21BB31C13C21",  # Reno, K3
        "ACAC1E13A72431AE4A1B22BBA1C1C6A2",  # A9
        "12CAC11211AAC3AEA2658690122C1E81",  # A1,A83t
        "1CA21E12271435AE331B81BBA7C14612",  # CPH1909 OppoA5s MT6765
        "D1DACF24351CE428A9CE32ED87323216",  # Realme1(reserved)
        "A1CC75115CAECB890E4A563CA1AC67C8",  # A73(reserved)
        "2132321EA2CA86621A11241ABA512722",  # Realme3(reserved)
        "22A21E821743E5EE33AE81B227B1462E"
        # F3 Plus CPH1613 - MSM8976
    ]

    def keytest(data):
        for key in keys:
            ctx = AES.new(binascii.unhexlify(key), AES.MODE_ECB)
            dat = ctx.decrypt(data)
            if dat[0:4] == b'\x50\x4B\x03\x04':
                print("Found correct AES key: " + key)
                return binascii.unhexlify(key)
            elif dat[0:4] == b'\x41\x56\x42\x30':
                print("Found correct AES key: " + key)
                return binascii.unhexlify(key)
            elif dat[0:4] == b'\x41\x4E\x44\x52':
                print("Found correct AES key: " + key)
                return binascii.unhexlify(key)
        return -1

    def del_rw(action, name, exc):
        os.chmod(name, stat.S_IWRITE)
        os.remove(name)

    def rmrf(path):
        if os.path.exists(path):
            if os.path.isfile(path):
                del_rw("", path, "")
            else:
                shutil.rmtree(path, onerror=del_rw)

    def decryptfile(key, rfilename):
        with open(rfilename, 'rb') as rr:
            with open(rfilename + ".tmp", 'wb') as wf:
                rr.seek(0x10)
                dsize = int(rr.read(0x10).replace(b"\x00", b"").decode('utf-8'), 10)
                rr.seek(0x1050)
                flen = os.stat(rfilename).st_size - 0x1050

                ctx = AES.new(key, AES.MODE_ECB)
                while dsize > 0:
                    if flen > 0x4000:
                        size = 0x4000
                    else:
                        size = flen
                    data = rr.read(size)
                    if dsize < size:
                        size = dsize
                    if len(data) == 0:
                        break
                    dr = ctx.decrypt(data)
                    wf.write(dr[:size])
                    flen -= size
                    dsize -= size
        os.remove(rfilename)
        os.rename(rfilename + ".tmp", rfilename)

    def decryptfile2(key, rfilename, wfilename):
        with open(rfilename, 'rb') as rr:
            with open(wfilename, 'wb') as wf:
                ctx = AES.new(key, AES.MODE_ECB)
                bstart = 0
                goon = True
                while goon:
                    rr.seek(bstart)
                    header = rr.read(12)
                    if len(header) == 0:
                        break
                    if header != b"OPPOENCRYPT!":
                        return 1
                    rr.seek(0x10 + bstart)
                    bdsize = int(rr.read(0x10).replace(b"\x00", b"").decode('utf-8'), 10)
                    if bdsize < 0x40000:
                        goon = False
                    rr.seek(0x50 + bstart)
                    while bdsize > 0:
                        data = rr.read(0x10)
                        if len(data) == 0:
                            break
                        size = 0x10
                        if bdsize < 0x10:
                            size = bdsize
                        dr = ctx.decrypt(data)
                        wf.write(dr[:size])
                        bdsize -= 0x10
                        data = rr.read(0x3FF0)
                        if len(data) == 0:
                            break
                        bdsize -= 0x3FF0
                        wf.write(data)
                    bstart = bstart + 0x40000 + 0x50
        return 0

    def mode2(filename):
        temp = os.path.join(os.path.abspath(os.path.dirname(filename)), "temp")
        out = os.path.join(os.path.abspath(os.path.dirname(filename)), "out")
        with open(filename, 'rb') as fr:
            magic = fr.read(12)
            if magic[:2] == b"PK":
                with zipfile.ZipFile(file_arg, 'r') as zipObj:
                    if os.path.exists(temp):
                        rmrf(temp)
                    os.mkdir(temp)
                    if os.path.exists(out):
                        rmrf(out)
                    os.mkdir(out)
                    print("Finding key...  " + file_arg)
                    for zi in zipObj.infolist():
                        orgfilename = zi.filename
                        if "boot.img" in orgfilename:
                            zi.filename = "out"
                            zipObj.extract(zi, temp)
                            zi.filename = orgfilename
                            with open(os.path.join(temp, "out"), 'rb') as rr:
                                if rr.read(12) == b"OPPOENCRYPT!":
                                    rr.seek(0x50)
                                    data = rr.read(16)
                                    key = keytest(data)
                                    if key == -1:
                                        print("Unknown AES key, reverse key from recovery first!")
                                        return 1
                                    else:
                                        break
                                else:
                                    print("Unknown mode2, boot.img wasn't encrypted")
                                    break

                    print("Extracting...  " + file_arg)
                    outzip = filename[:-4] + 'zip'
                    if os.path.exists(outzip):
                        os.remove(outzip)
                    with zipfile.ZipFile(outzip, 'w', zipfile.ZIP_DEFLATED) as WzipObj:
                        for zi in zipObj.infolist():
                            orgfilename = zi.filename
                            zi.filename = "out"
                            zipObj.extract(zi, temp)
                            zi.filename = orgfilename
                            with open(os.path.join(temp, "out"), 'rb') as rr:
                                if rr.read(12) == b"OPPOENCRYPT!":
                                    print("Decrypting " + orgfilename)
                                    if decryptfile2(key, os.path.join(temp, "out"),
                                                    os.path.join(temp, "out") + ".dec") == 1:
                                        return 1
                                    WzipObj.write(os.path.join(temp, "out") + ".dec", orgfilename)
                                    os.remove(os.path.join(temp, "out"))
                                    os.remove(os.path.join(temp, "out") + ".dec")
                                else:
                                    WzipObj.write(os.path.join(temp, "out"), orgfilename)
                                    os.remove(os.path.join(temp, "out"))
                    rmrf(temp)
                    print("DONE... file decrypted to: " + outzip)
                    return 0

    print("ozipdecrypt 1.32 (c) B.Kerler 2017-2022")
    filename = file_arg
    with open(filename, 'rb') as fr:
        magic = fr.read(12)
        if magic == b"OPPOENCRYPT!":
            pk = False
        elif magic[:2] == b"PK":
            pk = True
        else:
            print("ozip has unknown magic, OPPOENCRYPT! expected!")
            return 1

        if not pk:
            fr.seek(0x1050)
            data = fr.read(16)
            key = keytest(data)
            if key == -1:
                print("Unknown AES key, reverse key from recovery first!")
                return 1
            ctx = AES.new(key, AES.MODE_ECB)
            filename = file_arg[:-4] + "zip"
            with open(filename, 'wb') as wf:
                fr.seek(0x1050)
                print("Decrypting...")
                while True:
                    data = fr.read(16)
                    if len(data) == 0:
                        break
                    wf.write(ctx.decrypt(data))
                    data = fr.read(0x4000)
                    if len(data) == 0:
                        break
                    wf.write(data)
            print("DONE!!")
        else:
            testkey = True
            filename = os.path.abspath(file_arg)
            path = os.path.abspath(os.path.dirname(filename))
            outpath = os.path.join(path, "tmp")
            if os.path.exists(outpath):
                shutil.rmtree(outpath)
            os.mkdir(outpath)
            with zipfile.ZipFile(filename, 'r') as zo:
                clist = []
                try:
                    if zo.extract('oppo_metadata', outpath):
                        with open(os.path.join(outpath, 'oppo_metadata')) as rt:
                            for line in rt:
                                clist.append(line[:-1])
                except Exception as e:
                    print(str(e))
                    print("Detected mode 2....")
                    return mode2(filename)
                if testkey:
                    fname = ''
                    if "firmware-update/vbmeta.img" in clist:
                        fname = "firmware-update/vbmeta.img"
                    elif "vbmeta.img" in clist:
                        fname = 'vbmeta.img'
                    if fname != '':
                        if zo.extract(fname, outpath):
                            with open(os.path.join(outpath, fname.replace("/", os.sep)), "rb") as rt:
                                rt.seek(0x1050)
                                data = rt.read(16)
                                key = keytest(data)
                                if key == -1:
                                    print("Unknown AES key, reverse key from recovery first!")
                                    return 1
                            testkey = False
                    if testkey:
                        print("Unknown image, please report an issue with image name!")
                        return 1

                outzip = filename[:-4] + 'zip'
                with zipfile.ZipFile(outzip, 'w', zipfile.ZIP_DEFLATED) as WzipObj:
                    for info in zo.infolist():
                        print("Extracting " + info.filename)
                        orgfilename = info.filename
                        info.filename = "out"
                        zo.extract(info, outpath)
                        info.filename = orgfilename
                        if len(clist) > 0:
                            if info.filename in clist:
                                print("Decrypting " + info.filename)
                                decryptfile(key, os.path.join(outpath, "out"))
                        else:
                            with open(os.path.join(outpath, "out"), 'rb') as rr:
                                magic = rr.read(12)
                                if magic == b"OPPOENCRYPT!":
                                    decryptfile(key, os.path.join(outpath, "out"))
                        WzipObj.write(os.path.join(outpath, "out"), orgfilename)
                rmrf(os.path.join(outpath, "out"))
                print("DONE... files decrypted to: " + outzip)
                return 0


if __name__ == '__main__':
    import sys, argparse

    parser = argparse.ArgumentParser(description="ozipdecrypt 1.3 (c) B.Kerler 2017-2021", add_help=False)
    required = parser.add_argument_group('Required')
    required.add_argument("filename", help="Path to ozip file")
    optional = parser.add_argument_group('Optional')
    optional.add_argument("-h", "--help", action="help", help="Show this help message and exit")
    args = parser.parse_args()

    sys.exit(main(args.filename))
