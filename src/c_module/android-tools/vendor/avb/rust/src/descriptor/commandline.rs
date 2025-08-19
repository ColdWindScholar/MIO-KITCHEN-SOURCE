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

//! Kernel commandline descriptors.

use super::{
    util::{parse_descriptor, split_slice, ValidateAndByteswap, ValidationFunc},
    DescriptorResult,
};
use avb_bindgen::{
    avb_kernel_cmdline_descriptor_validate_and_byteswap, AvbKernelCmdlineDescriptor,
};
use core::str::from_utf8;

/// `AvbKernelCmdlineFlags`; see libavb docs for details.
pub use avb_bindgen::AvbKernelCmdlineFlags as KernelCommandlineDescriptorFlags;

/// Wraps an `AvbKernelCmdlineDescriptor` stored in a vbmeta image.
#[derive(Debug, PartialEq, Eq)]
pub struct KernelCommandlineDescriptor<'a> {
    /// Flags.
    pub flags: KernelCommandlineDescriptorFlags,

    /// Kernel commandline.
    pub commandline: &'a str,
}

// SAFETY: `VALIDATE_AND_BYTESWAP_FUNC` is the correct libavb validator for this descriptor type.
unsafe impl ValidateAndByteswap for AvbKernelCmdlineDescriptor {
    const VALIDATE_AND_BYTESWAP_FUNC: ValidationFunc<Self> =
        avb_kernel_cmdline_descriptor_validate_and_byteswap;
}

impl<'a> KernelCommandlineDescriptor<'a> {
    /// Extracts a `KernelCommandlineDescriptor` from the given descriptor contents.
    ///
    /// # Arguments
    /// * `contents`: descriptor contents, including the header, in raw big-endian format.
    ///
    /// # Returns
    /// The new descriptor, or `DescriptorError` if the given `contents` aren't a valid
    /// `AvbKernelCmdlineDescriptor`.
    pub(super) fn new(contents: &'a [u8]) -> DescriptorResult<Self> {
        // Descriptor contains: header + commandline.
        let descriptor = parse_descriptor::<AvbKernelCmdlineDescriptor>(contents)?;
        let (commandline, _) =
            split_slice(descriptor.body, descriptor.header.kernel_cmdline_length)?;

        Ok(Self {
            flags: KernelCommandlineDescriptorFlags(descriptor.header.flags),
            commandline: from_utf8(commandline)?,
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
        fs::read("testdata/kernel_commandline_descriptor.bin").unwrap()
    }

    #[test]
    fn new_commandline_descriptor_success() {
        assert!(KernelCommandlineDescriptor::new(&test_contents()).is_ok());
    }

    #[test]
    fn new_commandline_descriptor_too_short_header_fails() {
        let bad_header_size = size_of::<KernelCommandlineDescriptor>() - 1;
        assert_eq!(
            KernelCommandlineDescriptor::new(&test_contents()[..bad_header_size]).unwrap_err(),
            DescriptorError::InvalidHeader
        );
    }

    #[test]
    fn new_commandline_descriptor_too_short_contents_fails() {
        // The last 5 bytes are padding, so we need to drop 6 bytes to trigger an error.
        let bad_contents_size = test_contents().len() - 6;
        assert_eq!(
            KernelCommandlineDescriptor::new(&test_contents()[..bad_contents_size]).unwrap_err(),
            DescriptorError::InvalidSize
        );
    }
}
