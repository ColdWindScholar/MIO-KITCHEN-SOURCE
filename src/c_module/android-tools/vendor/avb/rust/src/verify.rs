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

//! Verification APIs.
//!
//! This module is responsible for all the conversions required to pass information between
//! libavb and Rust for verifying images.

extern crate alloc;

use crate::{
    descriptor::{get_descriptors, Descriptor, DescriptorResult},
    error::{
        slot_verify_enum_to_result, vbmeta_verify_enum_to_result, SlotVerifyError,
        SlotVerifyNoDataResult, SlotVerifyResult, VbmetaVerifyResult,
    },
    ops, Ops,
};
use alloc::vec::Vec;
use avb_bindgen::{
    avb_slot_verify, avb_slot_verify_data_free, AvbPartitionData, AvbSlotVerifyData, AvbVBMetaData,
};
use core::{
    ffi::{c_char, CStr},
    fmt,
    marker::PhantomData,
    pin::pin,
    ptr::{self, null, null_mut, NonNull},
    slice,
};

/// `AvbHashtreeErrorMode`; see libavb docs for descriptions of each mode.
pub use avb_bindgen::AvbHashtreeErrorMode as HashtreeErrorMode;
/// `AvbSlotVerifyFlags`; see libavb docs for descriptions of each flag.
pub use avb_bindgen::AvbSlotVerifyFlags as SlotVerifyFlags;

/// Returns `Err(SlotVerifyError::Internal)` if the given pointer is `NULL`.
fn check_nonnull<T>(ptr: *const T) -> SlotVerifyNoDataResult<()> {
    match ptr.is_null() {
        true => Err(SlotVerifyError::Internal),
        false => Ok(()),
    }
}

/// Wraps a raw C `AvbVBMetaData` struct.
///
/// This provides a Rust safe view over the raw data; no copies are made.
//
// `repr(transparent)` guarantees that size and alignment match the underlying type exactly, so that
// we can cast the array of `AvbVBMetaData` structs directly into a slice of `VbmetaData` wrappers
// without allocating any additional memory.
#[repr(transparent)]
pub struct VbmetaData(AvbVBMetaData);

impl VbmetaData {
    /// Validates the internal data so the accessors can be fail-free. This should be called on all
    /// `VbmetaData` objects before they are handed to the user.
    ///
    /// Normally this would be done in a `new()` function but we never instantiate `VbmetaData`
    /// objects ourselves, we just cast them from the C structs provided by libavb.
    ///
    /// Returns `Err(SlotVerifyError::Internal)` on failure.
    fn validate(&self) -> SlotVerifyNoDataResult<()> {
        check_nonnull(self.0.partition_name)?;
        check_nonnull(self.0.vbmeta_data)?;
        Ok(())
    }

    /// Returns the name of the partition this vbmeta image was loaded from.
    pub fn partition_name(&self) -> &CStr {
        // SAFETY:
        // * libavb gives us a properly-allocated and nul-terminated string.
        // * the returned contents remain valid and unmodified while we exist.
        unsafe { CStr::from_ptr(self.0.partition_name) }
    }

    /// Returns the vbmeta image contents.
    pub fn data(&self) -> &[u8] {
        // SAFETY:
        // * libavb gives us a properly-allocated byte array.
        // * the returned contents remain valid and unmodified while we exist.
        unsafe { slice::from_raw_parts(self.0.vbmeta_data, self.0.vbmeta_size) }
    }

    /// Returns the vbmeta verification result.
    pub fn verify_result(&self) -> VbmetaVerifyResult<()> {
        vbmeta_verify_enum_to_result(self.0.verify_result)
    }

    /// Extracts the descriptors from the vbmeta image.
    ///
    /// Note that this function allocates memory to hold the `Descriptor` objects.
    ///
    /// # Returns
    /// A vector of descriptors, or `DescriptorError` on failure.
    pub fn descriptors(&self) -> DescriptorResult<Vec<Descriptor>> {
        // SAFETY: the only way to get a `VbmetaData` object is via the return value of
        // `slot_verify()`, so we know we have been properly validated.
        unsafe { get_descriptors(self) }
    }

    /// Gets a property from the vbmeta image for the given key
    ///
    /// This function re-implements the libavb avb_property_lookup logic.
    ///
    /// # Returns
    /// Byte array with property data or None in case property not found or failure.
    pub fn get_property_value(&self, key: &str) -> Option<&[u8]> {
        self.descriptors().ok()?.iter().find_map(|d| match d {
            Descriptor::Property(p) if p.key == key => Some(p.value),
            _ => None,
        })
    }
}

impl fmt::Display for VbmetaData {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}: {:?}", self.partition_name(), self.verify_result())
    }
}

/// Forwards to `Display` formatting; the default `Debug` formatting implementation isn't very
/// useful as it's mostly raw pointer addresses.
impl fmt::Debug for VbmetaData {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(self, f)
    }
}

/// Wraps a raw C `AvbPartitionData` struct.
///
/// This provides a Rust safe view over the raw data; no copies are made.
#[repr(transparent)]
pub struct PartitionData(AvbPartitionData);

impl PartitionData {
    /// Validates the internal data so the accessors can be fail-free. This should be called on all
    /// `PartitionData` objects before they are handed to the user.
    ///
    /// Normally this would be done in a `new()` function but we never instantiate `PartitionData`
    /// objects ourselves, we just cast them from the C structs provided by libavb.
    ///
    /// Returns `Err(SlotVerifyError::Internal)` on failure.
    fn validate(&self) -> SlotVerifyNoDataResult<()> {
        check_nonnull(self.0.partition_name)?;
        check_nonnull(self.0.data)?;
        Ok(())
    }

    /// Returns the name of the partition this image was loaded from.
    pub fn partition_name(&self) -> &CStr {
        // SAFETY:
        // * libavb gives us a properly-allocated and nul-terminated string.
        // * the returned contents remain valid and unmodified while we exist.
        unsafe { CStr::from_ptr(self.0.partition_name) }
    }

    /// Returns the image contents.
    pub fn data(&self) -> &[u8] {
        // SAFETY:
        // * libavb gives us a properly-allocated byte array.
        // * the returned contents remain valid and unmodified while we exist.
        unsafe { slice::from_raw_parts(self.0.data, self.0.data_size) }
    }

    /// Returns whether this partition was preloaded via `get_preloaded_partition()`.
    pub fn preloaded(&self) -> bool {
        self.0.preloaded
    }

    /// Returns the verification result for this partition.
    ///
    /// Only top-level `Verification` errors will contain valid `SlotVerifyData` objects, if this
    /// individual partition returns a `Verification` error the error will always contain `None`.
    pub fn verify_result(&self) -> SlotVerifyNoDataResult<()> {
        slot_verify_enum_to_result(self.0.verify_result)
    }
}

/// A "(p)" after the partition name indicates a preloaded partition.
impl fmt::Display for PartitionData {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{:?}{}: {:?}",
            self.partition_name(),
            match self.preloaded() {
                true => "(p)",
                false => "",
            },
            self.verify_result()
        )
    }
}

/// Forwards to `Display` formatting; the default `Debug` formatting implementation isn't very
/// useful as it's mostly raw pointer addresses.
impl fmt::Debug for PartitionData {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(self, f)
    }
}

/// Wraps a raw C `AvbSlotVerifyData` struct.
///
/// This provides a Rust safe view over the raw data; no copies are made.
///
/// # Lifetimes
/// * `'a`: the lifetime of any preloaded partition data borrowed from an `Ops<'a>` object.
///
/// If the `Ops` doesn't provide any preloaded data, `SlotVerifyData` doesn't borrow anything
/// and instead allocates and owns all data internally, freeing it accordingly on `Drop`. In this
/// case, `'a` can be `'static` which imposes no lifetime restrictions on `SlotVerifyData`.
pub struct SlotVerifyData<'a> {
    /// Internally owns the underlying data and deletes it on drop.
    raw_data: NonNull<AvbSlotVerifyData>,

    /// This provides the necessary lifetimes so the compiler can make sure that the preloaded
    /// partition data stays alive at least as long as we do, since the underlying
    /// `AvbSlotVerifyData` may wrap this data rather than making a copy.
    //
    // We do not want to actually borrow an `Ops` here, since in some cases `Ops` is just a
    // temporary object and may go out of scope before us. The only shared data is the preloaded
    // partition contents, not the entire `Ops` object.
    _preloaded: PhantomData<&'a [u8]>,
}

// Useful so that `SlotVerifyError`, which may hold a `SlotVerifyData`, can derive `PartialEq`.
impl<'a> PartialEq for SlotVerifyData<'a> {
    fn eq(&self, other: &Self) -> bool {
        // A `SlotVerifyData` uniquely owns the underlying data so is only equal to itself.
        ptr::eq(self, other)
    }
}

impl<'a> Eq for SlotVerifyData<'a> {}

impl<'a> SlotVerifyData<'a> {
    /// Creates a `SlotVerifyData` wrapping the given raw `AvbSlotVerifyData`.
    ///
    /// The returned `SlotVerifyData` will take ownership of the given `AvbSlotVerifyData` and
    /// properly release the allocated memory when it drops.
    ///
    /// If `ops` provided any preloaded data, the returned `SlotVerifyData` also borrows the data to
    /// account for the underlying `AvbSlotVerifyData` holding a pointer to it. If there was no
    /// preloaded data, then `SlotVerifyData` owns all its data.
    ///
    /// # Arguments
    /// * `data`: a `AvbSlotVerifyData` object created by libavb using `ops`.
    /// * `ops`: the user-provided `Ops` object that was used for verification; only used here to
    ///          grab the preloaded data lifetime.
    ///
    /// # Returns
    /// The new object, or `Err(SlotVerifyError::Internal)` if the data looks invalid.
    ///
    /// # Safety
    /// * `data` must be a valid `AvbSlotVerifyData` object created by libavb using `ops`.
    /// * after calling this function, do not access `data` except through the returned object
    unsafe fn new(
        data: *mut AvbSlotVerifyData,
        _ops: &dyn Ops<'a>,
    ) -> SlotVerifyNoDataResult<Self> {
        let ret = Self {
            raw_data: NonNull::new(data).ok_or(SlotVerifyError::Internal)?,
            _preloaded: PhantomData,
        };

        // Validate all the contained data here so accessors will never fail.
        // SAFETY: `raw_data` points to a valid `AvbSlotVerifyData` object owned by us.
        let data = unsafe { ret.raw_data.as_ref() };
        check_nonnull(data.ab_suffix)?;
        check_nonnull(data.vbmeta_images)?;
        check_nonnull(data.loaded_partitions)?;
        check_nonnull(data.cmdline)?;
        ret.vbmeta_data().iter().try_for_each(|v| v.validate())?;
        ret.partition_data().iter().try_for_each(|i| i.validate())?;

        Ok(ret)
    }

    /// Returns the slot suffix string.
    pub fn ab_suffix(&self) -> &CStr {
        // SAFETY:
        // * `raw_data` points to a valid `AvbSlotVerifyData` object owned by us.
        // * libavb gives us a properly-allocated and nul-terminated string.
        // * the returned contents remain valid and unmodified while we exist.
        unsafe { CStr::from_ptr(self.raw_data.as_ref().ab_suffix) }
    }

    /// Returns the `VbmetaData` structs.
    pub fn vbmeta_data(&self) -> &[VbmetaData] {
        // SAFETY:
        // * `raw_data` points to a valid `AvbSlotVerifyData` object owned by us.
        // * libavb gives us a properly-allocated array of structs.
        // * the returned contents remain valid and unmodified while we exist.
        unsafe {
            slice::from_raw_parts(
                // `repr(transparent)` means we can cast between these types.
                self.raw_data.as_ref().vbmeta_images as *const VbmetaData,
                self.raw_data.as_ref().num_vbmeta_images,
            )
        }
    }

    /// Returns the `PartitionData` structs.
    pub fn partition_data(&self) -> &[PartitionData] {
        // SAFETY:
        // * `raw_data` points to a valid `AvbSlotVerifyData` object owned by us.
        // * libavb gives us a properly-allocated array of structs.
        // * the returned contents remain valid and unmodified while we exist.
        unsafe {
            slice::from_raw_parts(
                // `repr(transparent)` means we can cast between these types.
                self.raw_data.as_ref().loaded_partitions as *const PartitionData,
                self.raw_data.as_ref().num_loaded_partitions,
            )
        }
    }

    /// Returns the kernel commandline.
    pub fn cmdline(&self) -> &CStr {
        // SAFETY:
        // * `raw_data` points to a valid `AvbSlotVerifyData` object owned by us.
        // * libavb gives us a properly-allocated and nul-terminated string.
        // * the returned contents remain valid and unmodified while we exist.
        unsafe { CStr::from_ptr(self.raw_data.as_ref().cmdline) }
    }

    /// Returns the rollback indices.
    pub fn rollback_indexes(&self) -> &[u64] {
        // SAFETY: `raw_data` points to a valid `AvbSlotVerifyData` object owned by us.
        &unsafe { self.raw_data.as_ref() }.rollback_indexes[..]
    }

    /// Returns the resolved hashtree error mode.
    pub fn resolved_hashtree_error_mode(&self) -> HashtreeErrorMode {
        // SAFETY: `raw_data` points to a valid `AvbSlotVerifyData` object owned by us.
        unsafe { self.raw_data.as_ref() }.resolved_hashtree_error_mode
    }
}

/// Frees any internally-allocated and owned data.
impl<'a> Drop for SlotVerifyData<'a> {
    fn drop(&mut self) {
        // SAFETY:
        // * `raw_data` points to a valid `AvbSlotVerifyData` object owned by us.
        // * libavb created the object and requires us to free it by calling this function.
        unsafe { avb_slot_verify_data_free(self.raw_data.as_ptr()) };
    }
}

/// Implements `Display` to make it easy to print some basic information.
///
/// This implementation will print the slot, partition name, and verification status for all
/// vbmetadata and images.
impl<'a> fmt::Display for SlotVerifyData<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "slot: {:?}, vbmeta: {:?}, images: {:?}",
            self.ab_suffix(),
            self.vbmeta_data(),
            self.partition_data()
        )
    }
}

/// Forwards to `Display` formatting; the default `Debug` formatting implementation isn't very
/// useful as it's mostly raw pointer addresses.
impl<'a> fmt::Debug for SlotVerifyData<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(self, f)
    }
}

/// Performs verification of the requested images.
///
/// This wraps `avb_slot_verify()` for Rust, see the original docs for more details.
///
/// # Arguments
/// * `ops`: implementation of the required verification callbacks.
/// * `requested_partition`: the set of partition names to verify.
/// * `ab_suffix`: the slot suffix to append to the partition names, or None.
/// * `flags`: flags to configure verification.
/// * `hashtree_error_mode`: desired error handling behavior.
///
/// # Returns
/// `Ok` if verification completed successfully, the verification error otherwise. `SlotVerifyData`
/// will be returned in two cases:
///
/// 1. always returned on verification success
/// 2. if `AllowVerificationError` is given in `flags`, it will also be returned on verification
///    failure
///
/// A returned `SlotVerifyData` will also borrow any preloaded data provided by `ops`. The `ops`
/// object itself can go out of scope, but any preloaded data it could provide must outlive the
/// returned object.
pub fn slot_verify<'a>(
    ops: &mut dyn Ops<'a>,
    requested_partitions: &[&CStr],
    ab_suffix: Option<&CStr>,
    flags: SlotVerifyFlags,
    hashtree_error_mode: HashtreeErrorMode,
) -> SlotVerifyResult<'a, SlotVerifyData<'a>> {
    // libavb detects the size of the `requested_partitions` array by NULL termination. Expecting
    // the Rust caller to do this would make the API much more awkward, so we populate a
    // NULL-terminated array of c-string pointers ourselves. For now we use a fixed-sized array
    // rather than dynamically allocating, 8 should be more than enough.
    const MAX_PARTITION_ARRAY_SIZE: usize = 8 + 1; // Max 8 partition names + 1 for NULL terminator.
    if requested_partitions.len() >= MAX_PARTITION_ARRAY_SIZE {
        return Err(SlotVerifyError::Internal);
    }
    let mut partitions_array = [null() as *const c_char; MAX_PARTITION_ARRAY_SIZE];
    for (source, dest) in requested_partitions.iter().zip(partitions_array.iter_mut()) {
        *dest = source.as_ptr();
    }

    // To be more Rust idiomatic we allow `ab_suffix` to be `None`, but libavb requires a valid
    // pointer to an empty string in this case, not NULL.
    let ab_suffix = ab_suffix.unwrap_or(CStr::from_bytes_with_nul(b"\0").unwrap());

    let ops_bridge = pin!(ops::OpsBridge::new(ops));
    let mut out_data: *mut AvbSlotVerifyData = null_mut();

    // Call the libavb verification function.
    //
    // Note: do not use the `?` operator to return-early here; in some cases `out_data` will be
    // allocated and returned even on verification failure, and we need to take ownership of it
    // or else the memory will leak.
    //
    // SAFETY:
    // * `ops_bridge.init_and_get_c_ops()` gives us a valid `AvbOps`.
    // * we've properly initialized all objects passed into libavb.
    // * if `out_data` is non-null on return, we take ownership via `SlotVerifyData`.
    let result = slot_verify_enum_to_result(unsafe {
        avb_slot_verify(
            ops_bridge.init_and_get_c_ops(),
            partitions_array.as_ptr(),
            ab_suffix.as_ptr(),
            flags,
            hashtree_error_mode,
            &mut out_data,
        )
    });

    // If `out_data` is non-null, take ownership so memory gets released on drop.
    let data = match out_data.is_null() {
        true => None,
        // SAFETY: `out_data` was properly allocated by libavb and ownership has passed to us.
        false => Some(unsafe { SlotVerifyData::new(out_data, ops)? }),
    };

    // Fold the verify data into the result.
    match result {
        // libavb will always provide verification data on success.
        Ok(()) => Ok(data.unwrap()),
        // Data may also be provided on verification failure, fold it into the error.
        Err(SlotVerifyError::Verification(None)) => Err(SlotVerifyError::Verification(data)),
        // No other error provides verification data.
        Err(e) => Err(e),
    }
}
