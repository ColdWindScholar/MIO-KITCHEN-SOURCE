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

//! Descriptor extraction and handling.
//!
//! Descriptors are information encoded into vbmeta images which can be
//! extracted from the resulting data after performing verification.

extern crate alloc;

mod chain;
mod commandline;
mod hash;
mod hashtree;
mod property;
mod util;

use crate::VbmetaData;
use alloc::vec::Vec;
use avb_bindgen::{
    avb_descriptor_foreach, avb_descriptor_validate_and_byteswap, AvbDescriptor, AvbDescriptorTag,
};
use core::{
    ffi::{c_void, FromBytesUntilNulError},
    mem::size_of,
    slice,
    str::Utf8Error,
};

pub use chain::{ChainPartitionDescriptor, ChainPartitionDescriptorFlags};
pub use commandline::{KernelCommandlineDescriptor, KernelCommandlineDescriptorFlags};
pub use hash::{HashDescriptor, HashDescriptorFlags};
pub use hashtree::{HashtreeDescriptor, HashtreeDescriptorFlags};
pub use property::PropertyDescriptor;

/// A single descriptor.
#[derive(Debug, PartialEq, Eq)]
pub enum Descriptor<'a> {
    /// Wraps `AvbPropertyDescriptor`.
    Property(PropertyDescriptor<'a>),
    /// Wraps `AvbHashtreeDescriptor`.
    Hashtree(HashtreeDescriptor<'a>),
    /// Wraps `AvbHashDescriptor`.
    Hash(HashDescriptor<'a>),
    /// Wraps `AvbKernelCmdlineDescriptor`.
    KernelCommandline(KernelCommandlineDescriptor<'a>),
    /// Wraps `AvbChainPartitionDescriptor`.
    ChainPartition(ChainPartitionDescriptor<'a>),
    /// Unknown descriptor type.
    Unknown(&'a [u8]),
}

/// Possible errors when extracting descriptors.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum DescriptorError {
    /// libavb rejected the descriptor header.
    InvalidHeader,
    /// A value in the descriptor was invalid.
    InvalidValue,
    /// The descriptor claimed to be larger than the available data.
    InvalidSize,
    /// A field that was supposed to be valid UTF-8 was not.
    InvalidUtf8,
    /// Descriptor contents don't match what we expect.
    InvalidContents,
}

impl From<Utf8Error> for DescriptorError {
    fn from(_: Utf8Error) -> Self {
        Self::InvalidUtf8
    }
}

impl From<FromBytesUntilNulError> for DescriptorError {
    fn from(_: FromBytesUntilNulError) -> Self {
        Self::InvalidContents
    }
}

/// `Result` type for `DescriptorError` errors.
pub type DescriptorResult<T> = Result<T, DescriptorError>;

impl<'a> Descriptor<'a> {
    /// Extracts the fully-typed descriptor from the generic `AvbDescriptor` header.
    ///
    /// # Arguments
    /// * `raw_descriptor`: the raw `AvbDescriptor` pointing into the vbmeta image.
    ///
    /// # Returns
    /// The fully-typed `Descriptor`, or `DescriptorError` if parsing the descriptor failed.
    ///
    /// # Safety
    /// `raw_descriptor` must point to a valid `AvbDescriptor`, including the `num_bytes_following`
    /// data contents, that lives at least as long as `'a`.
    unsafe fn new(raw_descriptor: *const AvbDescriptor) -> DescriptorResult<Self> {
        // Transform header to host-endian.
        let mut descriptor = AvbDescriptor {
            tag: 0,
            num_bytes_following: 0,
        };
        // SAFETY: both args point to valid `AvbDescriptor` objects.
        if !unsafe { avb_descriptor_validate_and_byteswap(raw_descriptor, &mut descriptor) } {
            return Err(DescriptorError::InvalidHeader);
        }

        // Extract the descriptor header and contents bytes. The descriptor sub-type headers
        // include the top-level header as the first member, so we need to grab the entire
        // descriptor including the top-level header.
        let num_bytes_following = descriptor
            .num_bytes_following
            .try_into()
            .map_err(|_| DescriptorError::InvalidValue)?;
        let total_size = size_of::<AvbDescriptor>()
            .checked_add(num_bytes_following)
            .ok_or(DescriptorError::InvalidValue)?;

        // SAFETY: `raw_descriptor` points to the header plus `num_bytes_following` bytes.
        let contents = unsafe { slice::from_raw_parts(raw_descriptor as *const u8, total_size) };

        match descriptor.tag.try_into() {
            Ok(AvbDescriptorTag::AVB_DESCRIPTOR_TAG_PROPERTY) => {
                Ok(Descriptor::Property(PropertyDescriptor::new(contents)?))
            }
            Ok(AvbDescriptorTag::AVB_DESCRIPTOR_TAG_HASHTREE) => {
                Ok(Descriptor::Hashtree(HashtreeDescriptor::new(contents)?))
            }
            Ok(AvbDescriptorTag::AVB_DESCRIPTOR_TAG_HASH) => {
                Ok(Descriptor::Hash(HashDescriptor::new(contents)?))
            }
            Ok(AvbDescriptorTag::AVB_DESCRIPTOR_TAG_KERNEL_CMDLINE) => Ok(
                Descriptor::KernelCommandline(KernelCommandlineDescriptor::new(contents)?),
            ),
            Ok(AvbDescriptorTag::AVB_DESCRIPTOR_TAG_CHAIN_PARTITION) => Ok(
                Descriptor::ChainPartition(ChainPartitionDescriptor::new(contents)?),
            ),
            _ => Ok(Descriptor::Unknown(contents)),
        }
    }
}

/// Returns a vector of descriptors extracted from the given vbmeta image.
///
/// # Arguments
/// * `vbmeta`: the `VbmetaData` object to extract descriptors from.
///
/// # Returns
/// The descriptors, or `DescriptorError` if any error occurred.
///
/// # Safety
/// `vbmeta` must have been validated by `slot_verify()`.
pub(crate) unsafe fn get_descriptors(vbmeta: &VbmetaData) -> DescriptorResult<Vec<Descriptor>> {
    let mut result = Ok(Vec::new());

    // Use `avb_descriptor_foreach()` to grab all the descriptor pointers in `vmbeta.data()`.
    // This implementation processes all the descriptors immediately, so that any error is
    // detected here and working with descriptors can be error-free.
    //
    // SAFETY:
    // * the caller ensures that `vbmeta` has been validated by `slot_verify()`, which satisfies
    //   the libavb `avb_vbmeta_image_verify()` requirement.
    // * `avb_descriptor_foreach()` ensures the validity of each descriptor pointer passed to
    //   the `fill_descriptors_vec()` callback.
    // * our lifetimes guarantee that the raw descriptor data in `vbmeta` will remain unchanged for
    //   the lifetime of the returned `Descriptor` objects.
    // * the `user_data` param is a valid `DescriptorResult<Vec<Descriptor>>` with no other
    //   concurrent access.
    unsafe {
        // We can ignore the return value of this function since we use the passed-in `result`
        // to convey success/failure as well as more detailed error info.
        avb_descriptor_foreach(
            vbmeta.data().as_ptr(),
            vbmeta.data().len(),
            Some(fill_descriptors_vec),
            &mut result as *mut _ as *mut c_void,
        );
    }

    result
}

/// Adds the given descriptor to the `Vec` pointed to by `user_data`.
///
/// Serves as a C callback for use with `avb_descriptor_foreach()`.
///
/// # Returns
/// True on success, false on failure (which will stop iteration early).
///
/// # Safety
/// * `descriptor` must point to a valid `AvbDescriptor`, including the `num_bytes_following`
///   data contents, which remains valid and unmodified for the lifetime of the `Descriptor` objects
///   in `user_data`.
/// * `user_data` must point to a valid `DescriptorResult<Vec<Descriptor>>` with no other concurrent
///   access.
unsafe extern "C" fn fill_descriptors_vec(
    descriptor: *const AvbDescriptor,
    user_data: *mut c_void,
) -> bool {
    // SAFETY: `user_data` gives exclusive access to a valid `DescriptorResult<Vec<Descriptor>>`.
    let result = unsafe { (user_data as *mut DescriptorResult<Vec<Descriptor>>).as_mut() };
    // We can always unwrap here because we never pass a NULL pointer as `user_data`.
    let result = result.unwrap();

    // SAFETY: caller ensures that `descriptor` points to a valid `AvbDescriptor` with header and
    // body contents, which remains unmodified at least as long as the new `Descriptor`.
    match unsafe { Descriptor::new(descriptor) } {
        Ok(d) => {
            // We can always unwrap here because this function will never be called with an error
            // in `result`, since we stop iteration as soon as we encounter an error.
            result.as_mut().unwrap().push(d);
            true
        }
        Err(e) => {
            // Set the error and stop iteration early.
            *result = Err(e);
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_unknown_descriptor() {
        // A fake descriptor which is valid but with an unknown tag.
        let data: &[u8] = &[
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x42, // tag = 0x42u64 (BE)
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x08, // num_bytes_following = 8u64 (BE)
            0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, // fake contents
        ];

        // SAFETY: we've crafted a valid descriptor in `data`.
        let descriptor = unsafe { Descriptor::new(data.as_ptr() as *const _) }.unwrap();

        let contents = match descriptor {
            Descriptor::Unknown(c) => c,
            d => panic!("Expected Unknown descriptor, got {d:?}"),
        };
        assert_eq!(data, contents);
    }

    #[test]
    fn new_invalid_descriptor_length_fails() {
        // `avb_descriptor_validate_and_byteswap()` should detect and reject descriptors whose
        // `num_bytes_following` is not 8-byte aligned.
        let data: &[u8] = &[
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x42, // tag = 0x42u64 (BE)
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, // num_bytes_following = 7u64 (BE)
            0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, // fake contents
        ];

        assert_eq!(
            // SAFETY: we've created an invalid descriptor in a way that should be detected and
            // fail safely without triggering any undefined behavior.
            unsafe { Descriptor::new(data.as_ptr() as *const _) }.unwrap_err(),
            DescriptorError::InvalidHeader
        );
    }
}
