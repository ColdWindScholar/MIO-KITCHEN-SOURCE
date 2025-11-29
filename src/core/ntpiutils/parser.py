"""
NTPI File Parser
Handles parsing of NTPI file structure and region extraction.
"""
import ctypes
import time
import xml.etree.ElementTree as ET

from .structures import (
    NTPIHeader, RegionBlockHeader, get_aesdict_for_version
)
from .crypto import get_aes_key_iv_for_region, aes_cbc_decrypt


def extract_region_data(file_data, region_header, offset, output_dir, keys_dict=None):
    """
    Extract and decrypt a region from the NTPI file.
    
    Args:
        file_data: Complete NTPI file data in memory
        region_header: RegionHeader structure for this region
        offset: Byte offset where region data starts
        output_dir: Directory to save extracted files
        keys_dict: Dictionary of AES keys for decryption
    
    Returns:
        Tuple of (next_offset, next_region_header) or (-1, None) if no more regions
    """
    # Map region type IDs to human-readable names
    region_names = {
        1: "Metadata",
        2: "Patch",
        3: "RawProgram",
        4: "KeyMap",
        5: "FileIndex",
        6: "Region6"
    }
    region_name = region_names.get(region_header.region_type, f"Unknown{region_header.region_type}")
    
    # Validate region boundaries
    if offset + region_header.region_size > len(file_data):
        print(f"Error: Region data out of bounds for {region_name}")
        exit(-1)
    
    # Extract region data
    region_data = file_data[offset:offset + region_header.region_size]
    
    # Region6 contains encrypted file blocks, save as-is for later processing
    if region_header.region_type == 6:
        output_file = output_dir / "region6block.bin"
        with open(output_file, 'wb') as f:
            f.write(region_data)
        return -1, None
    
    # Get decryption keys for this region
    key, iv = None, None
    if keys_dict:
        key, iv = get_aes_key_iv_for_region(region_header.region_type, keys_dict)
    
    # Decrypt the region data
    decrypted_data = aes_cbc_decrypt(region_data, key, iv)
    # Parse the block header from decrypted data
    if len(decrypted_data) < ctypes.sizeof(RegionBlockHeader):
        print(f"Error: Decrypted data for {region_name} is too small for a RegionBlockHeader")
        exit(-1)
    
    block_header = RegionBlockHeader.from_buffer_copy(decrypted_data[:ctypes.sizeof(RegionBlockHeader)])
    data_offset = ctypes.sizeof(RegionBlockHeader)
    
    # Extract actual data content
    if data_offset + block_header.real_size > len(decrypted_data):
        print(f"Error: Real data size for {region_name} exceeds decrypted data buffer")
        exit(-1)
    
    actual_data = decrypted_data[data_offset:data_offset + block_header.real_size]
    
    # Save to file (KeyMap is binary, others are XML)
    if region_header.region_type == 4:
        output_file = output_dir / f"{region_name}.bin"
    else:
        output_file = output_dir / f"{region_name}.xml"
    with open(output_file, 'wb') as f:
        f.write(actual_data)
    
    # Check if there's a next region to process
    if block_header.next_header.region_size > 0:
        next_offset = offset + region_header.region_size
        return next_offset, block_header.next_header
    else:
        return -1, None


def parse_ntpi_file(file_path, output_dir):
    """
    Parse NTPI file header and extract all regions (Stage 1).
    
    This function reads the NTPI file, validates its header, and extracts
    all regions (Metadata, Patch, RawProgram, KeyMap, FileIndex, Region6).
    
    Args:
        file_path: Path to the .ntpi file
        output_dir: Directory to save extracted region files
    
    Returns:
        True if successful, False otherwise
    """
    print(f"=== Stage 1: Parsing NTPI File... ===")
    stage1_start = time.time()
    
    # Validate file existence
    if not file_path.exists():
        print(f"Error: Input file not found: {file_path}")
        return False

    # Read entire file into memory
    with open(file_path, 'rb') as f:
        file_data = f.read()
    
    # Validate file size
    if len(file_data) < ctypes.sizeof(NTPIHeader):
        print(f"Error: File is too small to be a valid NTPI file.")
        return False
    
    # Parse NTPI header
    ntpi_header = NTPIHeader.from_buffer_copy(file_data[:ctypes.sizeof(NTPIHeader)])
    if not ntpi_header.is_valid():
        print(f"Error: Invalid NTPI file magic.")
        return False
    
    print(f"NTPI header parsed successfully. Version: {ntpi_header.version_major}.{ntpi_header.version_minor}.{ntpi_header.version_patch}")
    
    # Get AES keys for this specific version
    keys_dict = get_aesdict_for_version(
        ntpi_header.version_major,
        ntpi_header.version_minor,
        ntpi_header.version_patch
    )
    
    # Check if version is supported
    if keys_dict is None:
        print(f"Error: Unsupported firmware version {ntpi_header.version_major}.{ntpi_header.version_minor}.{ntpi_header.version_patch}")
        print(f"This version is not currently supported. Please add AES keys to utils/structures.py")
        print(f"Supported versions:")
        from .structures import VERSION_KEY_MAP
        for ver in VERSION_KEY_MAP.keys():
            print(f"  - Version {ver[0]}.{ver[1]}.{ver[2]}")
        return False
    
    print(f"Using AES keys for version {ntpi_header.version_major}.{ntpi_header.version_minor}.{ntpi_header.version_patch}")

    # Process all regions in sequence
    current_offset = ctypes.sizeof(NTPIHeader)
    current_region = ntpi_header.first_region_header
    region_count = 0
    
    while current_region and current_region.region_size > 0:
        region_count += 1
        result = extract_region_data(file_data, current_region, current_offset, output_dir, keys_dict)
        if isinstance(result, tuple):
            next_offset, next_region = result
            if next_offset == -1:
                break
            current_offset = next_offset
            current_region = next_region
        else:
            break
    
    stage1_elapsed = time.time() - stage1_start
    print(f"Stage 1 completed. Parsed {region_count} regions.")
    print(f"Stage 1 Time: {stage1_elapsed:.2f}s")
    return True


def parse_fileindex_xml(xml_path):
    """
    Parse FileIndex.xml to get information about all files in the archive.
    
    Args:
        xml_path: Path to FileIndex.xml
    
    Returns:
        List of dictionaries containing file metadata (name, size, hash, etc.)
    """
    if not xml_path.exists():
        print(f"Error: FileIndex.xml not found at {xml_path}")
        return []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        files_info = []
        
        # Extract metadata for each file
        for file_elem in root.iter('file'):
            file_info = {
                'name': file_elem.get('Name', ''),
                'size': int(file_elem.get('OriginalLength', '0')),  # Decompressed size
                'length': int(file_elem.get('Length', '0')),  # Compressed size in Region6
                'hash': file_elem.get('FileSha256Hash', ''),  # SHA256 for verification
                'keyindex': int(file_elem.get('KeyIndex', '0')),  # Starting key index
                'offset': int(file_elem.get('Offset', '0'))  # Offset in Region6
            }
            files_info.append(file_info)
        
        print(f"Parsed {len(files_info)} file entries from FileIndex.xml.")
        return files_info
    except Exception as e:
        print(f"Error parsing FileIndex.xml: {e}")
        exit(-1)
