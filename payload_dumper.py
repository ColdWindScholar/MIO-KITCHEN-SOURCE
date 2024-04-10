#!/usr/bin/env python3
from struct import unpack

import update_metadata_pb2 as um


def u64(x):
    return unpack('>Q', x)[0]


class ota_payload_dumper:
    def __init__(self, payloadfile_):
        self.payloadfile = payloadfile_
        if self.payloadfile.read(4) != b'CrAU':
            print(f"Magic Check Fail\n")
            self.payloadfile.close()
            return
        file_format_version = u64(self.payloadfile.read(8))
        assert file_format_version == 2
        manifest_size = u64(self.payloadfile.read(8))
        metadata_signature_size = unpack('>I', self.payloadfile.read(4))[0] if file_format_version > 1 else 0
        manifest = self.payloadfile.read(manifest_size)
        self.payloadfile.read(metadata_signature_size)
        self.data_offset = self.payloadfile.tell()
        self.dam = um.DeltaArchiveManifest()
        self.dam.ParseFromString(manifest)
