"""
Cryptographic operations for NTPI file processing
Contains AES decryption and key management functions.
"""
import binascii
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import ctypes
from .structures import NTEncodeHeader


def get_aes_key_iv_for_region(region_type, keys_dict):
    """
    Get AES key and IV for a specific region type from the key dictionary.
    
    Args:
        region_type: Integer identifier for the region (1-6)
        keys_dict: Dictionary containing hex-encoded keys and IVs
    
    Returns:
        Tuple of (key_bytes, iv_bytes) as byte arrays
    """
    key_name = f"key_{region_type}"
    iv_name = f"iv_{region_type}"
    key_hex = keys_dict.get(key_name)
    iv_hex = keys_dict.get(iv_name)
    if key_hex and iv_hex:
        try:
            # Convert hex strings to byte arrays
            key_bytes = binascii.unhexlify(key_hex)
            iv_bytes = binascii.unhexlify(iv_hex)
            return key_bytes, iv_bytes
        except Exception as e:
            print(f"Error: Failed to get AES key for region {region_type}: {e}")
            exit(-1)
    else:
        print(f"Error: Key or IV not found for region {region_type}")
        exit(-1)


def aes_cbc_decrypt(encrypted_data, key=None, iv=None):
    """
    Decrypt data using AES-CBC mode.
    
    Args:
        encrypted_data: Bytes to decrypt
        key: 32-byte AES key (default: all zeros)
        iv: 16-byte initialization vector (default: all zeros)
    
    Returns:
        Decrypted data as bytes
    """
    # Use zero-filled keys if not provided
    if key is None:
        key = b'\x00' * 32
    if iv is None:
        iv = b'\x00' * 16
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_data = cipher.decrypt(encrypted_data)
        try:
            # Try to remove PKCS7 padding
            decrypted_data = unpad(decrypted_data, AES.block_size)
        except ValueError:
            # No padding or invalid padding, keep as is
            pass
        return decrypted_data
    except Exception as e:
        print(f"AES decryption failed: {e}")
        exit(-1)


def extract_key_from_keymap(keymap_data, key_index):
    """
    Extract a 32-byte AES key from the keymap at the specified index.
    
    Each file block uses a different key, calculated by:
    key = keymap[key_index * 32 : key_index * 32 + 32]
    
    Args:
        keymap_data: Complete keymap data
        key_index: Index of the key to extract
    
    Returns:
        32-byte AES key
    """
    try:
        # Calculate byte offset (32 bytes per key)
        key_offset = key_index * 32
        
        # Wrap around if index exceeds keymap size
        if key_offset >= len(keymap_data):
            key_offset = key_offset % len(keymap_data)
        
        # Extract 32-byte key
        key = keymap_data[key_offset:key_offset + 32]
        return key
    except Exception:
        raise


def decrypt_nt_encode_data(region6_data, offset, key):
    """
    Decrypt a single NTEncode block from Region6 data.
    
    Each block structure:
    - NTEncodeHeader (112 bytes): Contains magic, sizes, IV
    - Encrypted data (variable size): AES-CBC encrypted LZMA2 data
    
    Args:
        region6_data: Complete Region6 data
        offset: Byte offset where the NTEncode block starts
        key: 32-byte AES key for this block
    
    Returns:
        Tuple of (next_offset, decrypted_data)
    """

    
    # Parse the NTEncode header
    nt_header = NTEncodeHeader.from_buffer_copy(region6_data[offset:offset + ctypes.sizeof(NTEncodeHeader)])
    if nt_header.magic != b'NTENCODE':
        raise ValueError(f"Invalid NTEncode magic at offset {offset}")
    
    # Extract encrypted data
    data_offset = offset + ctypes.sizeof(NTEncodeHeader)
    encrypted_size = nt_header.original_size
    encrypted_data = region6_data[data_offset:data_offset + encrypted_size]
    
    # Decrypt using AES-CBC with IV from header
    iv = bytes(nt_header.iv[:16])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted_data = cipher.decrypt(encrypted_data)
    
    # Try to remove PKCS7 padding
    try:
        decrypted_data = unpad(decrypted_data, AES.block_size)
    except ValueError:
        # No padding or invalid padding, keep as is
        pass
    
    # Calculate offset of next block
    next_offset = data_offset + encrypted_size
    return next_offset, decrypted_data
