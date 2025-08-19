// Copyright 2024, The Android Open Source Project
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

//! Hashtree descriptors.

use super::{
    util::{parse_descriptor, split_slice, ValidateAndByteswap, ValidationFunc},
    DescriptorResult,
};
use avb_bindgen::{avb_hashtree_descriptor_validate_and_byteswap, AvbHashtreeDescriptor};
use core::{ffi::CStr, str::from_utf8};

/// `AvbHashtreeDescriptorFlags`; see libavb docs for details.
pub use avb_bindgen::AvbHashtreeDescriptorFlags as HashtreeDescriptorFlags;

/// Wraps a Hashtree descriptor stored in a vbmeta image.
#[derive(Debug, PartialEq, Eq)]
pub struct HashtreeDescriptor<'a> {
    /// DM-Verity version.
    pub dm_verity_version: u32,

    /// Hashed image size.
    pub image_size: u64,

    /// Offset to the root block of the hash tree.
    pub tree_offset: u64,

    /// Hash tree size.
    pub tree_size: u64,

    /// Data block size in bytes.
    pub data_block_size: u32,

    /// Hash block size in bytes.
    pub hash_block_size: u32,

    /// Number of forward error correction roots.
    pub fec_num_roots: u32,

    /// Offset to the forward error correction data.
    pub fec_offset: u64,

    /// Forward error correction data size.
    pub fec_size: u64,

    /// Hash algorithm name.
    pub hash_algorithm: &'a str,

    /// Flags.
    pub flags: HashtreeDescriptorFlags,

    /// Partition name.
    pub partition_name: &'a str,

    /// Salt used to hash the image.
    pub salt: &'a [u8],

    /// Image root hash digest.
    pub root_digest: &'a [u8],
}

// SAFETY: `VALIDATE_AND_BYTESWAP_FUNC` is the correct libavb validator for this descriptor type.
unsafe impl ValidateAndByteswap for AvbHashtreeDescriptor {
    const VALIDATE_AND_BYTESWAP_FUNC: ValidationFunc<Self> =
        avb_hashtree_descriptor_validate_and_byteswap;
}

impl<'a> HashtreeDescriptor<'a> {
    /// Extract a `HashtreeDescriptor` from the given descriptor contents.
    ///
    /// # Arguments
    /// * `contents`: descriptor contents, including the header, in raw big-endian format.
    ///
    /// # Returns
    /// The new descriptor, or `DescriptorError` if the given `contents` aren't a valid
    /// `AvbHashtreeDescriptor`.
    pub(super) fn new(contents: &'a [u8]) -> DescriptorResult<Self> {
        // Descriptor contains: header + name + salt + digest.
        let descriptor = parse_descriptor::<AvbHashtreeDescriptor>(contents)?;
        let (partition_name, remainder) =
            split_slice(descriptor.body, descriptor.header.partition_name_len)?;
        let (salt, remainder) = split_slice(remainder, descriptor.header.salt_len)?;
        let (root_digest, _) = split_slice(remainder, descriptor.header.root_digest_len)?;

        // Extract the hash algorithm from the original raw header since the temporary
        // byte-swapped header doesn't live past this function.
        // The hash algorithm is a nul-terminated UTF-8 string which is identical in the raw
        // and byteswapped headers.
        let hash_algorithm =
            CStr::from_bytes_until_nul(&descriptor.raw_header.hash_algorithm)?.to_str()?;

        Ok(Self {
            dm_verity_version: descriptor.header.dm_verity_version,
            image_size: descriptor.header.image_size,
            tree_offset: descriptor.header.tree_offset,
            tree_size: descriptor.header.tree_size,
            data_block_size: descriptor.header.data_block_size,
            hash_block_size: descriptor.header.hash_block_size,
            fec_num_roots: descriptor.header.fec_num_roots,
            fec_offset: descriptor.header.fec_offset,
            fec_size: descriptor.header.fec_size,
            hash_algorithm,
            partition_name: from_utf8(partition_name)?,
            salt,
            root_digest,
            flags: HashtreeDescriptorFlags(descriptor.header.flags),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    use crate::DescriptorError;
    use std::{fs, mem::size_of};

    /// A valid descriptor that we've pre-generated as test data.
    fn test_contents() -> Vec<u8> {
        fs::read("testdata/hashtree_descriptor.bin").unwrap()
    }

    #[test]
    fn new_hashtree_descriptor_success() {
        assert!(HashtreeDescriptor::new(&test_contents()).is_ok());
    }

    #[test]
    fn new_hashtree_descriptor_too_short_header_fails() {
        let bad_header_size = size_of::<AvbHashtreeDescriptor>() - 1;
        assert_eq!(
            HashtreeDescriptor::new(&test_contents()[..bad_header_size]).unwrap_err(),
            DescriptorError::InvalidHeader
        );
    }

    #[test]
    fn new_hashtree_descriptor_too_short_contents_fails() {
        // The last 2 bytes are padding, so we need to drop 3 bytes to trigger an error.
        let bad_contents_size = test_contents().len() - 3;
        assert_eq!(
            HashtreeDescriptor::new(&test_contents()[..bad_contents_size]).unwrap_err(),
            DescriptorError::InvalidSize
        );
    }
}
