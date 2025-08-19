// Copyright 2023, The Android Open Source Project
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

//! Hash descriptors.

use super::{
    util::{parse_descriptor, split_slice, ValidateAndByteswap, ValidationFunc},
    DescriptorResult,
};
use avb_bindgen::{avb_hash_descriptor_validate_and_byteswap, AvbHashDescriptor};
use core::{ffi::CStr, str::from_utf8};

/// `AvbHashDescriptorFlags`; see libavb docs for details.
pub use avb_bindgen::AvbHashDescriptorFlags as HashDescriptorFlags;

/// Wraps a Hash descriptor stored in a vbmeta image.
#[derive(Debug, PartialEq, Eq)]
pub struct HashDescriptor<'a> {
    /// The size of the hashed image.
    pub image_size: u64,

    /// Hash algorithm name.
    pub hash_algorithm: &'a str,

    /// Flags.
    pub flags: HashDescriptorFlags,

    /// Partition name.
    ///
    /// Most partition names in this library are passed as `&CStr`, but inside
    /// descriptors the partition names are not nul-terminated making them
    /// ineligible for use directly as `&CStr`. If `&CStr` is required, one
    /// option is to allocate a nul-terminated copy of this string via
    /// `CString::new()` which can then be converted to `&CStr`.
    pub partition_name: &'a str,

    /// Salt used to hash the image.
    pub salt: &'a [u8],

    /// Image hash digest.
    pub digest: &'a [u8],
}

// SAFETY: `VALIDATE_AND_BYTESWAP_FUNC` is the correct libavb validator for this descriptor type.
unsafe impl ValidateAndByteswap for AvbHashDescriptor {
    const VALIDATE_AND_BYTESWAP_FUNC: ValidationFunc<Self> =
        avb_hash_descriptor_validate_and_byteswap;
}

impl<'a> HashDescriptor<'a> {
    /// Extract a `HashDescriptor` from the given descriptor contents.
    ///
    /// # Arguments
    /// * `contents`: descriptor contents, including the header, in raw big-endian format.
    ///
    /// # Returns
    /// The new descriptor, or `DescriptorError` if the given `contents` aren't a valid
    /// `AvbHashDescriptor`.
    pub(super) fn new(contents: &'a [u8]) -> DescriptorResult<Self> {
        // Descriptor contains: header + name + salt + digest.
        let descriptor = parse_descriptor::<AvbHashDescriptor>(contents)?;
        let (partition_name, remainder) =
            split_slice(descriptor.body, descriptor.header.partition_name_len)?;
        let (salt, remainder) = split_slice(remainder, descriptor.header.salt_len)?;
        let (digest, _) = split_slice(remainder, descriptor.header.digest_len)?;

        // Extract the hash algorithm from the original raw header since the temporary
        // byte-swapped header doesn't live past this function.
        // The hash algorithm is a nul-terminated UTF-8 string which is identical in the raw
        // and byteswapped headers.
        let hash_algorithm =
            CStr::from_bytes_until_nul(&descriptor.raw_header.hash_algorithm)?.to_str()?;

        Ok(Self {
            image_size: descriptor.header.image_size,
            hash_algorithm,
            flags: HashDescriptorFlags(descriptor.header.flags),
            partition_name: from_utf8(partition_name)?,
            salt,
            digest,
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
        fs::read("testdata/hash_descriptor.bin").unwrap()
    }

    #[test]
    fn new_hash_descriptor_success() {
        assert!(HashDescriptor::new(&test_contents()).is_ok());
    }

    #[test]
    fn new_hash_descriptor_too_short_header_fails() {
        let bad_header_size = size_of::<AvbHashDescriptor>() - 1;
        assert_eq!(
            HashDescriptor::new(&test_contents()[..bad_header_size]).unwrap_err(),
            DescriptorError::InvalidHeader
        );
    }

    #[test]
    fn new_hash_descriptor_too_short_contents_fails() {
        // The last byte is padding, so we need to drop 2 bytes to trigger an error.
        let bad_contents_size = test_contents().len() - 2;
        assert_eq!(
            HashDescriptor::new(&test_contents()[..bad_contents_size]).unwrap_err(),
            DescriptorError::InvalidSize
        );
    }
}
