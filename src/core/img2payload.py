# src/core/img2payload.py
"""
Creates an Android update payload (payload.bin) from a directory of partition images.

This module handles the entire payload generation process, including:
- Compressing individual partition images.
- Building the DeltaArchiveManifest protobuf.
- Optionally signing the generated payload with a private key.
"""

import os
import struct
import bz2
import lzma
import zstandard as zstd
import hashlib
import base64
import json
from typing import Optional, Dict

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from .update_metadata_pb2 import DeltaArchiveManifest, InstallOperation, PartitionUpdate, Signatures


class _Localization:
    """A simple, self-contained class for loading localization strings."""

    def __init__(self, lang_code: str = 'English', lang_dir: Optional[str] = None) -> None:
        """
        Initializes the localization loader.

        It first loads the default English language as a fallback, then overlays
        the target language if it's specified and found.

        Args:
            lang_code: The language code for the desired translation (e.g., 'English').
            lang_dir: The directory where language JSON files are stored.
                      Defaults to a path relative to this script.
        """
        if lang_dir is None:
            script_path = os.path.dirname(os.path.abspath(__file__))
            lang_dir = os.path.join(script_path, '..', '..', 'bin', 'languages')

        self.data: Dict[str, str] = {}
        # Load English as a fallback first.
        default_lang_file = os.path.join(lang_dir, 'English.json')
        if os.path.exists(default_lang_file):
            try:
                with open(default_lang_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # Ignore errors in the default language file.

        # If a different language is requested, load it and update the defaults.
        if lang_code and lang_code.lower() != 'english':
            target_lang_file = os.path.join(lang_dir, f"{lang_code}.json")
            if os.path.exists(target_lang_file):
                try:
                    with open(target_lang_file, 'r', encoding='utf-8') as f:
                        lang_data = json.load(f)
                        self.data.update(lang_data)
                except (json.JSONDecodeError, IOError):
                    pass # Ignore errors in the target language file.

    def __getattr__(self, name: str) -> str:
        """
        Allows accessing localization strings as attributes (e.g., lang.my_key).

        Returns a placeholder string if the key is not found.
        """
        return self.data.get(name, f"<{name.upper()}_NOT_FOUND>")


def create_payload_image_compressed(img_dir: str, output_path: str, compression_type: str = "xz",
                                    private_key_path: Optional[str] = None, lang_code: str = 'English') -> bool:
    """
    Creates a payload.bin file from a directory of partition images.

    This function orchestrates the entire payload creation process. It reads all
    `.img` files from a source directory, compresses them, builds a manifest,
    and assembles the final `payload.bin`.

    If a `private_key_path` is provided, it will attempt to sign the payload.
    The process adheres to a "fail-fast" principle: if signing is requested but
    fails for any reason (e.g., missing key, invalid key format, missing crypto
    library), the function will abort immediately and will not create the
    output file.

    Args:
        img_dir: Path to the directory containing partition images (`.img` files).
        output_path: The full path where the final `payload.bin` will be saved.
        compression_type: The compression algorithm to use.
                          Supported: 'xz', 'bz2', 'zstd', 'none'.
        private_key_path: Optional path to the PEM/PKCS8 private key for signing.
                          If None, the payload will not be signed.
        lang_code: Language code for user-facing console messages.

    Returns:
        True on successful creation, False on any critical error.
    """
    lang = _Localization(lang_code=lang_code)
    manifest = DeltaArchiveManifest()
    data_offset = 0
    # A single binary blob containing all compressed partition data, concatenated.
    all_data_blob = b""
    is_signed = False

    print(lang.pack_step_compressing)
    print(lang.info_compression_used.format(compression_type=compression_type.upper()))

    # Sort files to ensure a deterministic order of partitions in the manifest.
    image_files = sorted([f for f in os.listdir(img_dir) if f.endswith(".img")])

    for img_file in image_files:
        img_path = os.path.join(img_dir, img_file)
        original_size = os.path.getsize(img_path)

        print(lang.info_processing_file.format(
            file_name=img_file,
            size_mb=f"{original_size / (1024*1024):.1f}"
        ))

        with open(img_path, "rb") as f:
            chunk = f.read()

        image_hash = hashlib.sha256(chunk).digest()

        part_update = manifest.partitions.add()
        part_update.partition_name = os.path.splitext(img_file)[0]
        part_update.new_partition_info.size = original_size
        part_update.new_partition_info.hash = image_hash

        if compression_type == "xz":
            compressed_data = lzma.compress(chunk, preset=6)
            op_type = InstallOperation.REPLACE_XZ
        elif compression_type == "bz2":
            compressed_data = bz2.compress(chunk, compresslevel=9)
            op_type = InstallOperation.REPLACE_BZ
        elif compression_type == "zstd":
            try:
                compressor = zstd.ZstdCompressor(level=15)
                compressed_data = compressor.compress(chunk)
                # Defensively get the ZSTD operation type, as its name might vary.
                op_type = getattr(InstallOperation, 'REPLACE_ZSTD', getattr(InstallOperation, 'ZSTD', InstallOperation.REPLACE_XZ))
            except Exception:
                print(f"   {lang.warning_zstd_unavailable}")
                compressed_data = lzma.compress(chunk, preset=6)
                op_type = InstallOperation.REPLACE_XZ
        else:  # "none"
            compressed_data = chunk
            op_type = InstallOperation.REPLACE

        compression_ratio = len(compressed_data) / original_size * 100 if original_size > 0 else 0
        saved_mb = (original_size - len(compressed_data)) / (1024*1024)
        print(lang.info_compression_result.format(
            compressed_size_mb=f"{len(compressed_data) / (1024*1024):.1f}",
            ratio=f"{compression_ratio:.1f}",
            saved_mb=f"{saved_mb:.1f}"
        ))

        op = part_update.operations.add()
        op.type = op_type
        op.data_offset = data_offset
        op.data_length = len(compressed_data)

        extent = op.dst_extents.add()
        extent.start_block = 0
        # Calculate the number of blocks required for the uncompressed data, rounding up.
        extent.num_blocks = (original_size + 4095) // 4096

        all_data_blob += compressed_data
        data_offset += len(compressed_data)

    manifest.block_size = 4096
    manifest.minor_version = 0
    signature_blob = b""

    # --- Signing Process ---
    # If a private key is specified, any failure in this block is critical and
    # will abort the entire process.
    if private_key_path:
        print(lang.pack_step_signing)
        if not CRYPTO_AVAILABLE:
            print(lang.error_crypto_lib_missing_for_signing)
            return False
        if not os.path.exists(private_key_path):
            print(lang.error_priv_key_not_found.format(key_path=private_key_path))
            return False

        try:
            with open(private_key_path, "rb") as key_file:
                key_data = key_file.read()
            private_key = serialization.load_pem_private_key(key_data, password=None)
        except Exception as e:
            print(lang.error_priv_key_read_failed.format(error=e))
            return False

        try:
            # The signature is calculated over the header, manifest, and all data blobs.
            # To do this, we must first determine the size of the signature blob itself,
            # as it's included in the manifest.
            manifest.signatures_offset = data_offset
            # Pre-calculate the signature's size by creating a dummy signature of the correct length.
            temp_sig_proto = Signatures()
            temp_sig = temp_sig_proto.signatures.add()
            temp_sig.data = b'\x00' * (private_key.key_size // 8)
            manifest.signatures_size = len(temp_sig_proto.SerializeToString())

            manifest_bytes_for_signing = manifest.SerializeToString()

            header_for_signing = (b"CrAU" + struct.pack(">Q", 2) + struct.pack(">Q", len(manifest_bytes_for_signing)) + struct.pack(">I", 0))
            data_to_sign = header_for_signing + manifest_bytes_for_signing + all_data_blob

            payload_hash = hashlib.sha256(data_to_sign).digest()
            signature_data = private_key.sign(payload_hash, padding.PKCS1v15(), hashes.SHA256())

            final_sig_proto = Signatures()
            sig = final_sig_proto.signatures.add()
            sig.data = signature_data
            signature_blob = final_sig_proto.SerializeToString()
            # Sanity check to ensure the final signature blob has the expected size.
            assert len(signature_blob) == manifest.signatures_size, "Signature size mismatch!"
            is_signed = True
        except Exception as e:
            print(lang.error_signing_process_failed.format(error=e))
            return False

    # --- Final Assembly and Write ---
    # This part is reached only if all previous steps, including signing, were successful.
    print(lang.pack_step_saving)
    manifest_bytes = manifest.SerializeToString()
    header = (b"CrAU" + struct.pack(">Q", 2) + struct.pack(">Q", len(manifest_bytes)) + struct.pack(">I", 0))
    full_payload_data = header + manifest_bytes + all_data_blob + signature_blob

    with open(output_path, "wb") as out:
        out.write(full_payload_data)

    total_size = os.path.getsize(output_path)
    signed_status_str = lang.status_signed if is_signed else lang.status_not_signed
    print(lang.success_payload_created.format(size_mb=f"{total_size / (1024*1024):.1f}", status=signed_status_str))

    # Create the accompanying properties file.
    file_hash = hashlib.sha256(full_payload_data).digest()
    file_hash_b64 = base64.b64encode(file_hash).decode('utf-8')
    metadata_hash = hashlib.sha256(manifest_bytes).digest()
    metadata_hash_b64 = base64.b64encode(metadata_hash).decode('utf-8')
    properties_content = (f"FILE_HASH={file_hash_b64}\nMETADATA_HASH={metadata_hash_b64}\nMETADATA_SIZE={len(manifest_bytes)}\n")
    properties_path = os.path.join(os.path.dirname(output_path), "payload_properties.txt")
    try:
        with open(properties_path, "w", encoding="utf-8") as f:
            f.write(properties_content)
        print(lang.success_properties_created.format(status=signed_status_str))
    except IOError as e:
        print(lang.error_creating_properties.format(error=e))

    return True