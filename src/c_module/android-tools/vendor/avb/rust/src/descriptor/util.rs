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

//! Descriptor utilities.

use super::{DescriptorError, DescriptorResult};
use zerocopy::{FromBytes, FromZeroes, Ref};

/// Splits `size` bytes off the front of `data`.
///
/// This is a thin wrapper around `slice::split_at()` but it:
/// 1. Returns a `DescriptorError` rather than panicking if `data` is too small.
/// 2. Accepts a variety of `size` types since descriptors commonly use `u32` or `u64`.
///
/// # Arguments
/// * `data`: descriptor data.
/// * `size`: the number of bytes to pull off the front.
///
/// # Returns
/// A tuple containing (extracted_bytes, data_remainder) on success, or
/// `DescriptorError` if we couldn't get `size` bytes out of `data`.
pub(super) fn split_slice<T>(data: &[u8], size: T) -> DescriptorResult<(&[u8], &[u8])>
where
    T: TryInto<usize>,
{
    let size = size.try_into().map_err(|_| DescriptorError::InvalidValue)?;
    if size > data.len() {
        Err(DescriptorError::InvalidSize)
    } else {
        Ok(data.split_at(size))
    }
}

/// Function type for the `avb_*descriptor_validate_and_byteswap()` C functions.
pub(super) type ValidationFunc<T> = unsafe extern "C" fn(*const T, *mut T) -> bool;

/// Trait to represent an `Avb*Descriptor` type which has an associated `ValidationFunc`.
///
/// This allows the generic `parse_descriptor()` function to extract a descriptor header for any
/// descriptor type.
///
/// To use, implement `ValidateAndByteSwap` on the `Avb*Descriptor` struct.
///
/// # Safety
/// The function assigned to `VALIDATE_AND_BYTESWAP_FUNC` must be the libavb
/// `avb_*descriptor_validate_and_byteswap()` function corresponding to the descriptor implementing
/// this trait (e.g. `AvbHashDescriptor` -> `avb_hash_descriptor_validate_and_byteswap`).
pub(super) unsafe trait ValidateAndByteswap {
    /// The specific libavb validation function for this descriptor type.
    const VALIDATE_AND_BYTESWAP_FUNC: ValidationFunc<Self>;
}

/// A descriptor that has been extracted, validated, and byteswapped.
#[derive(Debug)]
pub(super) struct ParsedDescriptor<'a, T> {
    /// The original raw (big-endian) header.
    pub raw_header: &'a T,
    /// A copy of the header in host-endian format.
    pub header: T,
    /// The descriptor body contents.
    pub body: &'a [u8],
}

/// Extracts the descriptor header from the given buffer.
///
/// # Arguments
/// `data`: the descriptor contents in raw (big-endian) format.
///
/// # Returns
/// A `ParsedDescriptor` on success, `DescriptorError` if `data` was too small or the header looks
/// invalid.
pub(super) fn parse_descriptor<T>(data: &[u8]) -> DescriptorResult<ParsedDescriptor<T>>
where
    T: Default + FromZeroes + FromBytes + ValidateAndByteswap,
{
    let (raw_header, body) =
        Ref::<_, T>::new_from_prefix(data).ok_or(DescriptorError::InvalidHeader)?;
    let raw_header = raw_header.into_ref();

    let mut header = T::default();
    // SAFETY:
    // * all `VALIDATE_AND_BYTESWAP_FUNC` functions check the validity of the fields.
    // * even if the data is corrupted somehow and is not detected by the validation logic, these
    //   functions never try to access memory outside of the header.
    if !unsafe { T::VALIDATE_AND_BYTESWAP_FUNC(raw_header, &mut header) } {
        return Err(DescriptorError::InvalidHeader);
    }

    Ok(ParsedDescriptor {
        raw_header,
        header,
        body,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use avb_bindgen::{avb_descriptor_validate_and_byteswap, AvbDescriptor, AvbHashDescriptor};
    use std::mem::size_of;

    #[test]
    fn split_slice_with_various_size_types_succeeds() {
        let data = &[1, 2, 3, 4];
        let expected = Ok((&data[..2], &data[2..]));
        assert_eq!(split_slice(data, 2u32), expected);
        assert_eq!(split_slice(data, 2u64), expected);
        assert_eq!(split_slice(data, 2usize), expected);
    }

    #[test]
    fn split_slice_with_negative_size_fails() {
        let data = &[1, 2, 3, 4];
        assert_eq!(split_slice(data, -1i32), Err(DescriptorError::InvalidValue));
    }

    #[test]
    fn split_slice_with_size_overflow_fails() {
        let data = &[1, 2, 3, 4];
        assert_eq!(split_slice(data, 5u32), Err(DescriptorError::InvalidSize));
    }

    // Enable `parse_descriptor()` on a generic `AvbDescriptor` of any sub-type.
    // SAFETY: `VALIDATE_AND_BYTESWAP_FUNC` is the correct libavb validator for this descriptor.
    unsafe impl ValidateAndByteswap for AvbDescriptor {
        const VALIDATE_AND_BYTESWAP_FUNC: ValidationFunc<Self> =
            avb_descriptor_validate_and_byteswap;
    }

    // Hardcoded test descriptor of custom sub-type (tag = 42).
    const TEST_DESCRIPTOR: &[u8] = &[
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x42, // tag = 0x42u64 (BE)
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x08, // num_bytes_following = 8u64 (BE)
        0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, // fake contents
    ];

    #[test]
    fn parse_descriptor_success() {
        let descriptor = parse_descriptor::<AvbDescriptor>(TEST_DESCRIPTOR).unwrap();

        // `assert_eq!()` cannot be used on `repr(packed)` struct fields.
        assert!(descriptor.raw_header.tag == 0x42u64.to_be());
        assert!(descriptor.raw_header.num_bytes_following == 8u64.to_be());
        assert!(descriptor.header.tag == 0x42);
        assert!(descriptor.header.num_bytes_following == 8);
        assert_eq!(descriptor.body, &[1, 2, 3, 4, 5, 6, 7, 8]);
    }

    #[test]
    fn parse_descriptor_buffer_too_short_failure() {
        let bad_length = size_of::<AvbDescriptor>() - 1;
        assert_eq!(
            parse_descriptor::<AvbDescriptor>(&TEST_DESCRIPTOR[..bad_length]).unwrap_err(),
            DescriptorError::InvalidHeader
        );
    }

    #[test]
    fn parse_descriptor_wrong_type_failure() {
        assert_eq!(
            // `TEST_DESCRIPTOR` is not a valid `AvbHashDescriptor`, this should fail without
            // triggering any undefined behavior.
            parse_descriptor::<AvbHashDescriptor>(TEST_DESCRIPTOR).unwrap_err(),
            DescriptorError::InvalidHeader
        );
    }
}
