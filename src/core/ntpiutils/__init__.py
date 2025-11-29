"""
NTPI Dumper Utilities Package
"""
from .structures import (
    RegionHeader,
    NTPIHeader,
    RegionBlockHeader,
    NTEncodeHeader,
    NTDecompressHeader,
    AESDICT,
    AESDICT_V1_3_0,
    VERSION_KEY_MAP,
    DEFAULT_AESDICT,
    get_aesdict_for_version
)

from .crypto import (
    get_aes_key_iv_for_region,
    aes_cbc_decrypt,
    extract_key_from_keymap,
    decrypt_nt_encode_data
)

from .parser import (
    extract_region_data,
    parse_ntpi_file,
    parse_fileindex_xml
)

from .extractor import (
    init_worker,
    decompress_lzma2_data,
    split_file_into_segments,
    process_segment,
    calculate_optimal_segments,
    process_large_file_parallel,
    process_file_task,
    stage2_extract_files
)

__all__ = [
    # Structures
    'RegionHeader',
    'NTPIHeader',
    'RegionBlockHeader',
    'NTEncodeHeader',
    'NTDecompressHeader',
    'AESDICT',
    'AESDICT_V1_3_0',
    'VERSION_KEY_MAP',
    'DEFAULT_AESDICT',
    'get_aesdict_for_version',
    
    # Crypto
    'get_aes_key_iv_for_region',
    'aes_cbc_decrypt',
    'extract_key_from_keymap',
    'decrypt_nt_encode_data',
    
    # Parser
    'extract_region_data',
    'parse_ntpi_file',
    'parse_fileindex_xml',
    
    # Extractor
    'init_worker',
    'decompress_lzma2_data',
    'split_file_into_segments',
    'process_segment',
    'calculate_optimal_segments',
    'process_large_file_parallel',
    'process_file_task',
    'stage2_extract_files',
]
