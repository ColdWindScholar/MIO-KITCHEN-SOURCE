"""
NTPI File Structure Definitions
Contains all ctypes structure definitions for parsing NTPI files.
"""
import ctypes


class RegionHeader(ctypes.Structure):
    """Header for each region in the NTPI file"""
    _fields_ = [
        ("region_type", ctypes.c_uint64),
        ("region_size", ctypes.c_uint64),
    ]


class NTPIHeader(ctypes.Structure):
    """Main NTPI file header"""
    _fields_ = [
        ("magic", ctypes.c_char * 4),
        ("padding", ctypes.c_uint32),
        ("version_major", ctypes.c_uint64),
        ("version_minor", ctypes.c_uint64),
        ("version_patch", ctypes.c_uint64),
        ("first_region_header", RegionHeader),
    ]

    def is_valid(self):
        """Check if this is a valid NTPI file"""
        return self.magic == b'NTPI'


class RegionBlockHeader(ctypes.Structure):
    """Header for region data blocks"""
    _fields_ = [
        ("this_header", RegionHeader),
        ("next_header", RegionHeader),
        ("real_size", ctypes.c_uint64),
    ]


class NTEncodeHeader(ctypes.Structure):
    """Header for encrypted/encoded blocks"""
    _fields_ = [
        ("magic", ctypes.c_char * 8),
        ("primary_type", ctypes.c_uint32),
        ("compress_subtype", ctypes.c_uint32),
        ("encrypt_subtype", ctypes.c_uint32),
        ("padding", ctypes.c_uint32),
        ("processed_size", ctypes.c_uint64),
        ("original_size", ctypes.c_uint64),
        ("key", ctypes.c_ubyte * 32),
        ("iv", ctypes.c_ubyte * 32),
        ("key_size", ctypes.c_uint32),
        ("iv_size", ctypes.c_uint32),
    ]


class NTDecompressHeader(ctypes.Structure):
    """Header for compressed data blocks"""
    _fields_ = [
        ("magic", ctypes.c_char * 8),
        ("primary_type", ctypes.c_uint32),
        ("decompress_subtype", ctypes.c_uint32),
        ("padding", ctypes.c_uint64),
        ("processed_size", ctypes.c_uint64),
        ("original_size", ctypes.c_uint64),
        ("padding2", ctypes.c_ubyte * 72),
    ]


# AES key dictionaries for different firmware versions
# Each version has its own set of region keys (key_1 to key_5) and IVs (iv_1 to iv_5)

# Version 1.3.0 keys
AESDICT_V1_3_0 = {
    'key_1': '08ed9260dec3807aac3ec00e765186cf4b9c677601ba844f8ec3e8c2fe1e11cb',
    'iv_1': '0797205f6b02c0232cd2798795ba588d',
    'key_2': '7cec0ee7e63a703197afa8e09ce40f9b10a5fded6e5f04cb4ba7a435ed600288',
    'iv_2': '01c5aaae7c4001592ea6a2310364a9a1',
    'key_3': '76fa1a8d6663aae8b964470c384508f7f974d21af2535cd3549c7c51ed68b0e6',
    'iv_3': 'de930fcc2c37009400e21dfa9f7d1363',
    'key_4': '1c37c2a0b579512481e8529532909c7c1be72f9bb5e1a4610328a5e2b67c10f4',
    'iv_4': 'ab15d90ce88a83680a4074d5bb96d94c',
    'key_5': '4ae22e3ae6ff0b65d06fa18df4f99ae59e6a90cb92ca03de65b64fc0fac958ce',
    'iv_5': 'eaaa17604ad7dae5773639c217978da5',
}

# Example: Add more versions as needed
# AESDICT_V1_4_0 = {
#     'key_1': 'new_key_hex_string_here...',
#     'iv_1': 'new_iv_hex_string_here...',
#     ...
# }

# Version mapping: map version tuples to key dictionaries
VERSION_KEY_MAP = {
    (1, 3, 0): AESDICT_V1_3_0,
    # (1, 4, 0): AESDICT_V1_4_0,  # Add future versions here
}

# Default key dictionary (used when version is not recognized)
DEFAULT_AESDICT = AESDICT_V1_3_0

# Backward compatibility: keep AESDICT as default
AESDICT = DEFAULT_AESDICT


def get_aesdict_for_version(version_major, version_minor, version_patch):
    """
    Get the appropriate AES key dictionary for a specific firmware version.
    
    Args:
        version_major: Major version number (e.g., 1)
        version_minor: Minor version number (e.g., 3)
        version_patch: Patch version number (e.g., 0)
    
    Returns:
        Dictionary containing AES keys and IVs for the specified version.
        Returns None if version is not supported.
    
    Example:
        >>> keys = get_aesdict_for_version(1, 3, 0)
        >>> if keys:
        >>>     print(keys['key_1'])
    """
    version_tuple = (version_major, version_minor, version_patch)
    
    # Try to find exact version match
    if version_tuple in VERSION_KEY_MAP:
        return VERSION_KEY_MAP[version_tuple]
    
    # Try to find partial match (major.minor)
    partial_version = (version_major, version_minor)
    for key, value in VERSION_KEY_MAP.items():
        if key[:2] == partial_version:
            return value
    
    # Return None if no match found (unsupported version)
    return None
