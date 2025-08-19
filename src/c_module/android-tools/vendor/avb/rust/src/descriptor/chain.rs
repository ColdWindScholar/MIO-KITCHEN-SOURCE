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

//! Chain partition descriptors.

use super::{
    util::{parse_descriptor, split_slice, ValidateAndByteswap, ValidationFunc},
    DescriptorResult,
};
use avb_bindgen::{
    avb_chain_partition_descriptor_validate_and_byteswap, AvbChainPartitionDescriptor,
};
use core::str::from_utf8;

/// `AvbChainPartitionDescriptorFlags`; see libavb docs for details.
pub use avb_bindgen::AvbChainPartitionDescriptorFlags as ChainPartitionDescriptorFlags;

/// Wraps a chain partition descriptor stored in a vbmeta image.
#[derive(Debug, PartialEq, Eq)]
pub struct ChainPartitionDescriptor<'a> {
    /// Chained partition rollback index location.
    pub rollback_index_location: u32,

    /// Chained partition name.
    ///
    /// Most partition names in this library are passed as `&CStr`, but inside
    /// descriptors the partition names are not nul-terminated making them
    /// ineligible for use directly as `&CStr`. If `&CStr` is required, one
    /// option is to allocate a nul-terminated copy of this string via
    /// `CString::new()` which can then be converted to `&CStr`.
    pub partition_name: &'a str,

    /// Chained partition public key.
    pub public_key: &'a [u8],

    /// Flags.
    pub flags: ChainPartitionDescriptorFlags,
}

// SAFETY: `VALIDATE_AND_BYTESWAP_FUNC` is the correct libavb validator for this descriptor type.
unsafe impl ValidateAndByteswap for AvbChainPartitionDescriptor {
    const VALIDATE_AND_BYTESWAP_FUNC: ValidationFunc<Self> =
        avb_chain_partition_descriptor_validate_and_byteswap;
}

impl<'a> ChainPartitionDescriptor<'a> {
    /// Extract a `ChainPartitionDescriptor` from the given descriptor contents.
    ///
    /// # Arguments
    /// * `contents`: descriptor contents, including the header, in raw big-endian format.
    ///
    /// # Returns
    /// The new descriptor, or `DescriptorError` if the given `contents` aren't a valid
    /// `AvbChainPartitionDescriptor`.
    pub(super) fn new(contents: &'a [u8]) -> DescriptorResult<Self> {
        // Descriptor contains: header + partition name + public key.
        let descriptor = parse_descriptor::<AvbChainPartitionDescriptor>(contents)?;
        let (partition_name, remainder) =
            split_slice(descriptor.body, descriptor.header.partition_name_len)?;
        let (public_key, _) = split_slice(remainder, descriptor.header.public_key_len)?;

        Ok(Self {
            flags: ChainPartitionDescriptorFlags(descriptor.header.flags),
            partition_name: from_utf8(partition_name)?,
            rollback_index_location: descriptor.header.rollback_index_location,
            public_key,
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
        fs::read("testdata/chain_partition_descriptor.bin").unwrap()
    }

    #[test]
    fn new_chain_partition_descriptor_success() {
        assert!(ChainPartitionDescriptor::new(&test_contents()).is_ok());
    }

    #[test]
    fn new_chain_partition_descriptor_too_short_header_fails() {
        let bad_header_size = size_of::<AvbChainPartitionDescriptor>() - 1;
        assert_eq!(
            ChainPartitionDescriptor::new(&test_contents()[..bad_header_size]).unwrap_err(),
            DescriptorError::InvalidHeader
        );
    }

    #[test]
    fn new_chain_partition_descriptor_too_short_contents_fails() {
        // The last byte is padding, so we need to drop 2 bytes to trigger an error.
        let bad_contents_size = test_contents().len() - 2;
        assert_eq!(
            ChainPartitionDescriptor::new(&test_contents()[..bad_contents_size]).unwrap_err(),
            DescriptorError::InvalidSize
        );
    }
}
