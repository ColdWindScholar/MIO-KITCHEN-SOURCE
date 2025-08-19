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

//! User callback APIs.
//!
//! This module is responsible for bridging the user-implemented callbacks so that they can be
//! written in safe Rust but libavb can call them from C.

extern crate alloc;

use crate::{error::result_to_io_enum, CertOps, IoError, IoResult, SHA256_DIGEST_SIZE};
use avb_bindgen::{AvbCertOps, AvbCertPermanentAttributes, AvbIOResult, AvbOps};
use core::{
    cmp::min,
    ffi::{c_char, c_void, CStr},
    marker::PhantomPinned,
    pin::Pin,
    ptr, slice,
};
#[cfg(feature = "uuid")]
use uuid::Uuid;

/// Base implementation-provided callbacks for verification.
///
/// See libavb `AvbOps` for more complete documentation.
///
/// # Lifetimes
/// The trait lifetime `'a` indicates the lifetime of any preloaded partition data.
///
/// Preloading partitions is an optional feature which allows libavb to use data already loaded to
/// RAM rather than allocating memory itself and loading data from disk. Preloading changes the
/// data ownership model so that the verification result borrows this existing data rather than
/// allocating and owning the data itself. Because of this borrow, we need the lifetime here to
/// ensure that the underlying data outlives the verification result object.
///
/// If `get_preloaded_partition()` is left unimplemented, all data is loaded and owned by the
/// verification result rather than borrowed, and this trait lifetime can be `'static`.
pub trait Ops<'a> {
    /// Reads data from the requested partition on disk.
    ///
    /// # Arguments
    /// * `partition`: partition name to read from.
    /// * `offset`: offset in bytes within the partition to read from; a positive value indicates an
    ///             offset from the partition start, a negative value indicates a backwards offset
    ///             from the partition end.
    /// * `buffer`: buffer to read data into.
    ///
    /// # Returns
    /// The number of bytes actually read into `buffer` or an `IoError`. Reading less than
    /// `buffer.len()` bytes is only allowed if the end of the partition was reached.
    fn read_from_partition(
        &mut self,
        partition: &CStr,
        offset: i64,
        buffer: &mut [u8],
    ) -> IoResult<usize>;

    /// Returns a reference to preloaded partition contents.
    ///
    /// This is an optional optimization if a partition has already been loaded to provide libavb
    /// with a reference to the data rather than copying it as `read_from_partition()` would.
    ///
    /// May be left unimplemented if preloaded partitions are not used.
    ///
    /// # Arguments
    /// * `partition`: partition name to read from.
    ///
    /// # Returns
    /// * A reference to the entire partition contents if the partition has been preloaded.
    /// * `Err<IoError::NotImplemented>` if the requested partition has not been preloaded;
    ///   verification will next attempt to load the partition via `read_from_partition()`.
    /// * Any other `Err<IoError>` if an error occurred; verification will exit immediately.
    fn get_preloaded_partition(&mut self, _partition: &CStr) -> IoResult<&'a [u8]> {
        Err(IoError::NotImplemented)
    }

    /// Checks if the given public key is valid for vbmeta image signing.
    ///
    /// If using libavb_cert, this should forward to `cert_validate_vbmeta_public_key()`.
    ///
    /// # Arguments
    /// * `public_key`: the public key.
    /// * `public_key_metadata`: public key metadata set by the `--public_key_metadata` arg in
    ///                          `avbtool`, or None if no metadata was provided.
    ///
    /// # Returns
    /// True if the given key is valid, false if it is not, `IoError` on error.
    fn validate_vbmeta_public_key(
        &mut self,
        public_key: &[u8],
        public_key_metadata: Option<&[u8]>,
    ) -> IoResult<bool>;

    /// Reads the rollback index at the given location.
    ///
    /// # Arguments
    /// * `rollback_index_location`: the rollback location.
    ///
    /// # Returns
    /// The rollback index at this location or `IoError` on error.
    fn read_rollback_index(&mut self, rollback_index_location: usize) -> IoResult<u64>;

    /// Writes the rollback index at the given location.
    ///
    /// This API is never actually used by libavb; the purpose of having it here is to group it
    /// with `read_rollback_index()` and indicate to the implementation that it is responsible
    /// for providing this functionality. However, it's up to the implementation to call this
    /// function at the proper time after verification, which is a device-specific decision that
    /// depends on things like the A/B strategy. See the libavb documentation for more information.
    ///
    /// # Arguments
    /// * `rollback_index_location`: the rollback location.
    /// * `index`: the rollback index to write.
    ///
    /// # Returns
    /// Unit on success or `IoError` on error.
    fn write_rollback_index(&mut self, rollback_index_location: usize, index: u64) -> IoResult<()>;

    /// Returns the device unlock state.
    ///
    /// # Returns
    /// True if the device is unlocked, false if locked, `IoError` on error.
    fn read_is_device_unlocked(&mut self) -> IoResult<bool>;

    /// Returns the GUID of the requested partition.
    ///
    /// This is only necessary if the kernel commandline requires GUID substitution, and is omitted
    /// from the library by default to avoid unnecessary dependencies. To implement:
    /// 1. Enable the `uuid` feature during compilation
    /// 2. Provide the [`uuid` crate](https://docs.rs/uuid/latest/uuid/) dependency
    ///
    /// # Arguments
    /// * `partition`: partition name.
    ///
    /// # Returns
    /// The partition GUID or `IoError` on error.
    #[cfg(feature = "uuid")]
    fn get_unique_guid_for_partition(&mut self, partition: &CStr) -> IoResult<Uuid>;

    /// Returns the size of the requested partition.
    ///
    /// # Arguments
    /// * `partition`: partition name.
    ///
    /// # Returns
    /// The partition size in bytes or `IoError` on error.
    fn get_size_of_partition(&mut self, partition: &CStr) -> IoResult<u64>;

    /// Reads the requested persistent value.
    ///
    /// This is only necessary if using persistent digests or the "managed restart and EIO"
    /// hashtree verification mode; if verification is not using these features, this function will
    /// never be called.
    ///
    /// # Arguments
    /// * `name`: persistent value name.
    /// * `value`: buffer to read persistent value into; if too small to hold the persistent value,
    ///            `IoError::InsufficientSpace` should be returned and this function will be called
    ///            again with an appropriately-sized buffer. This may be an empty slice if the
    ///            caller only wants to query the persistent value size.
    ///
    /// # Returns
    /// * The number of bytes written into `value` on success.
    /// * `IoError::NoSuchValue` if `name` is not a known persistent value.
    /// * `IoError::InsufficientSpace` with the required size if the `value` buffer is too small.
    /// * Any other `IoError` on failure.
    fn read_persistent_value(&mut self, name: &CStr, value: &mut [u8]) -> IoResult<usize>;

    /// Writes the requested persistent value.
    ///
    /// This is only necessary if using persistent digests or the "managed restart and EIO"
    /// hashtree verification mode; if verification is not using these features, this function will
    /// never be called.
    ///
    /// # Arguments
    /// * `name`: persistent value name.
    /// * `value`: bytes to write as the new value.
    ///
    /// # Returns
    /// * Unit on success.
    /// * `IoError::NoSuchValue` if `name` is not a supported persistent value.
    /// * `IoError::InvalidValueSize` if `value` is too large to save as a persistent value.
    /// * Any other `IoError` on failure.
    fn write_persistent_value(&mut self, name: &CStr, value: &[u8]) -> IoResult<()>;

    /// Erases the requested persistent value.
    ///
    /// This is only necessary if using persistent digests or the "managed restart and EIO"
    /// hashtree verification mode; if verification is not using these features, this function will
    /// never be called.
    ///
    /// If the requested persistent value is already erased, this function is a no-op and should
    /// return `Ok(())`.
    ///
    /// # Arguments
    /// * `name`: persistent value name.
    ///
    /// # Returns
    /// * Unit on success.
    /// * `IoError::NoSuchValue` if `name` is not a supported persistent value.
    /// * Any other `IoError` on failure.
    fn erase_persistent_value(&mut self, name: &CStr) -> IoResult<()>;

    /// Checks if the given public key is valid for the given partition.
    ///
    /// This is only used if the "no vbmeta" verification flag is passed, meaning the partitions
    /// to verify have an embedded vbmeta image rather than locating it in a separate vbmeta
    /// partition. If this flag is not used, the `validate_vbmeta_public_key()` callback is used
    /// instead, and this function will never be called.
    ///
    /// If using libavb_cert for `partition`, this should forward to
    /// `cert_validate_vbmeta_public_key()`.
    ///
    /// # Arguments
    /// * `partition`: partition name.
    /// * `public_key`: the public key.
    /// * `public_key_metadata`: public key metadata set by the `--public_key_metadata` arg in
    ///                          `avbtool`, or None if no metadata was provided.
    ///
    /// # Returns
    /// On success, returns a `PublicKeyForPartitionInfo` object indicating whether the given
    /// key is trusted and its rollback index location.
    ///
    /// On failure, returns an error.
    fn validate_public_key_for_partition(
        &mut self,
        partition: &CStr,
        public_key: &[u8],
        public_key_metadata: Option<&[u8]>,
    ) -> IoResult<PublicKeyForPartitionInfo>;

    /// Returns the libavb_cert certificate ops if supported.
    ///
    /// The libavb_cert extension provides some additional key management and authentication support
    /// APIs, see the cert module documentation for more info.
    ///
    /// The default implementation returns `None` to disable cert APIs.
    ///
    /// Commonly when using certs the same struct will implement both `Ops` and `CertOps`, in which
    /// case this can just return `Some(self)`.
    ///
    /// Note: changing this return value in the middle of a libavb operation (e.g. from another
    /// callback) is not recommended; it may cause runtime errors or a panic later on in the
    /// operation. It's fine to change this return value outside of libavb operations.
    ///
    /// # Returns
    /// The `CertOps` object, or `None` if not supported.
    fn cert_ops(&mut self) -> Option<&mut dyn CertOps> {
        None
    }
}

/// Info returned from `validate_public_key_for_partition()`.
#[derive(Clone, Copy, Debug)]
pub struct PublicKeyForPartitionInfo {
    /// Whether the key is trusted for the given partition..
    pub trusted: bool,
    /// The rollback index to use for the given partition.
    pub rollback_index_location: u32,
}

/// Provides the logic to bridge between the libavb C ops and our Rust ops.
///
/// This struct internally owns the C ops structs, and borrows ownership of the Rust `Ops`. This
/// allows us to translate in both directions, from Rust -> C to call into libavb and then back
/// from C -> Rust when servicing the callbacks.
///
/// The general control flow look like this:
///
/// ```ignore
/// user calls a Rust API with their `Ops` {
///     we create `OpsBridge` wrapping `Ops` and the C structs
///     we call into C libavb API {
///         libavb makes C ops callback {
///             we retrieve `OpsBridge` from the callback `user_data` param
///             we make the corresponding Rust `Ops` callback
///         }
///         ... libavb makes more callbacks as needed ...
///     }
/// }
/// ```
///
/// # Lifetimes
/// * `'o`: lifetime of the `Ops` object
/// * `'p`: lifetime of any preloaded data provided by `Ops`
pub(crate) struct OpsBridge<'o, 'p> {
    /// C `AvbOps` holds a raw pointer to the `OpsBridge` so we can retrieve it during callbacks.
    avb_ops: AvbOps,
    /// When using libavb_cert, C `AvbOps`/`AvbCertOps` hold circular pointers to each other.
    cert_ops: AvbCertOps,
    /// Rust `Ops` implementation, which may also provide Rust `CertOps`.
    rust_ops: &'o mut dyn Ops<'p>,
    /// Remove the `Unpin` trait to indicate this type has address-sensitive state.
    _pin: PhantomPinned,
}

impl<'o, 'p> OpsBridge<'o, 'p> {
    pub(crate) fn new(ops: &'o mut dyn Ops<'p>) -> Self {
        Self {
            avb_ops: AvbOps {
                user_data: ptr::null_mut(), // Set at the time of use.
                ab_ops: ptr::null_mut(),    // Deprecated, no need to support.
                cert_ops: ptr::null_mut(),  // Set at the time of use.
                read_from_partition: Some(read_from_partition),
                get_preloaded_partition: Some(get_preloaded_partition),
                write_to_partition: None, // Not needed, only used for deprecated A/B.
                validate_vbmeta_public_key: Some(validate_vbmeta_public_key),
                read_rollback_index: Some(read_rollback_index),
                write_rollback_index: Some(write_rollback_index),
                read_is_device_unlocked: Some(read_is_device_unlocked),
                get_unique_guid_for_partition: Some(get_unique_guid_for_partition),
                get_size_of_partition: Some(get_size_of_partition),
                read_persistent_value: Some(read_persistent_value),
                write_persistent_value: Some(write_persistent_value),
                validate_public_key_for_partition: Some(validate_public_key_for_partition),
            },
            cert_ops: AvbCertOps {
                ops: ptr::null_mut(), // Set at the time of use.
                read_permanent_attributes: Some(read_permanent_attributes),
                read_permanent_attributes_hash: Some(read_permanent_attributes_hash),
                set_key_version: Some(set_key_version),
                get_random: Some(get_random),
            },
            rust_ops: ops,
            _pin: PhantomPinned,
        }
    }

    /// Initializes and returns the C `AvbOps` structure from an `OpsBridge`.
    ///
    /// If the contained `Ops` supports `CertOps`, the returned `AvbOps` will also be configured
    /// properly for libavb_cert.
    ///
    /// Pinning is necessary here because the returned `AvbOps` contains pointers into `self`, so
    /// we cannot allow `self` to subsequently move or else the pointers would become invalid.
    ///
    /// # Returns
    /// The C `AvbOps` struct to make libavb calls with.
    pub(crate) fn init_and_get_c_ops<'a>(self: Pin<&'a mut Self>) -> &'a mut AvbOps {
        // SAFETY: we do not move out of `self_mut`, but only set pointers to pinned addresses.
        let self_mut = unsafe { self.get_unchecked_mut() };

        // Set the C `user_data` to point back to us so we can retrieve ourself in callbacks.
        self_mut.avb_ops.user_data = self_mut as *mut _ as *mut _;

        // If the `Ops` supports certs, set up the necessary additional pointer tracking.
        if self_mut.rust_ops.cert_ops().is_some() {
            self_mut.avb_ops.cert_ops = &mut self_mut.cert_ops;
            self_mut.cert_ops.ops = &mut self_mut.avb_ops;
        }

        &mut self_mut.avb_ops
    }
}

/// Extracts the user-provided `Ops` from a raw `AvbOps`.
///
/// This function is used in libavb callbacks to bridge libavb's raw C `AvbOps` struct to our Rust
/// implementation.
///
/// # Arguments
/// * `avb_ops`: The raw `AvbOps` pointer used by libavb.
///
/// # Returns
/// The Rust `Ops` extracted from `avb_ops.user_data`.
///
/// # Safety
/// * only call this function on an `AvbOps` created via `OpsBridge`
/// * drop all references to the returned `Ops` and preloaded data before returning control to
///   libavb or calling this function again
///
/// In practice, these conditions are met since we call this at most once in each callback
/// to extract the `Ops`, and drop the references at callback completion.
///
/// # Lifetimes
/// * `'o`: lifetime of the `Ops` object
/// * `'p`: lifetime of any preloaded data provided by `Ops`
///
/// It's difficult to accurately provide the lifetimes when calling this function, since we are in
/// a C callback which provides no lifetime information in the args. We solve this in the safety
/// requirements by requiring the caller to drop both references before returning, which is always
/// a subset of the actual object lifetimes as the objects must remain valid while libavb is
/// actively using them:
///
/// ```ignore
/// ops/preloaded lifetime {  // Actual 'o/'p start
///   call into libavb {
///     libavb callbacks {
///       as_ops()            // as_ops() 'o/'p start
///     }                     // as_ops() 'o/'p end
///   }
/// }                         // Actual 'o/'p end
/// ```
unsafe fn as_ops<'o, 'p>(avb_ops: *mut AvbOps) -> IoResult<&'o mut dyn Ops<'p>> {
    // SAFETY: we created this AvbOps object and passed it to libavb so we know it meets all
    // the criteria for `as_mut()`.
    let avb_ops = unsafe { avb_ops.as_mut() }.ok_or(IoError::Io)?;
    // Cast the void* `user_data` back to a OpsBridge*.
    let bridge = avb_ops.user_data as *mut OpsBridge;
    // SAFETY: we created this OpsBridge object and passed it to libavb so we know it meets all
    // the criteria for `as_mut()`.
    Ok(unsafe { bridge.as_mut() }.ok_or(IoError::Io)?.rust_ops)
}

/// Similar to `as_ops()`, but for `CertOps`.
///
/// # Safety
/// Same as `as_ops()`.
unsafe fn as_cert_ops<'o>(cert_ops: *mut AvbCertOps) -> IoResult<&'o mut dyn CertOps> {
    // SAFETY: we created this `CertOps` object and passed it to libavb so we know it meets all
    // the criteria for `as_mut()`.
    let cert_ops = unsafe { cert_ops.as_mut() }.ok_or(IoError::Io)?;

    // SAFETY: caller must adhere to `as_ops()` safety requirements.
    let ops = unsafe { as_ops(cert_ops.ops) }?;

    // Return the `CertOps` implementation. If it doesn't exist here, it indicates an internal error
    // in this library; somewhere we accepted a non-cert `Ops` into a function that requires cert.
    ops.cert_ops().ok_or(IoError::NotImplemented)
}

/// Converts a non-NULL `ptr` to `()`, NULL to `Err(IoError::Io)`.
fn check_nonnull<T>(ptr: *const T) -> IoResult<()> {
    match ptr.is_null() {
        true => Err(IoError::Io),
        false => Ok(()),
    }
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn read_from_partition(
    ops: *mut AvbOps,
    partition: *const c_char,
    offset: i64,
    num_bytes: usize,
    buffer: *mut c_void,
    out_num_read: *mut usize,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe {
        result_to_io_enum(try_read_from_partition(
            ops,
            partition,
            offset,
            num_bytes,
            buffer,
            out_num_read,
        ))
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `partition` must adhere to the requirements of `CStr::from_ptr()`.
/// * `buffer` must adhere to the requirements of `slice::from_raw_parts_mut()`.
/// * `out_num_read` must adhere to the requirements of `ptr::write()`.
unsafe fn try_read_from_partition(
    ops: *mut AvbOps,
    partition: *const c_char,
    offset: i64,
    num_bytes: usize,
    buffer: *mut c_void,
    out_num_read: *mut usize,
) -> IoResult<()> {
    check_nonnull(partition)?;
    check_nonnull(buffer)?;
    check_nonnull(out_num_read)?;

    // Initialize the output variables first in case something fails.
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_num_read`.
    unsafe { ptr::write(out_num_read, 0) };

    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated and nul-terminated `partition`.
    // * the string contents are not modified while the returned `&CStr` exists.
    // * the returned `&CStr` is not held past the scope of this callback.
    let partition = unsafe { CStr::from_ptr(partition) };
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `buffer` with size `num_bytes`.
    // * we only access the contents via the returned slice.
    // * the returned slice is not held past the scope of this callback.
    let buffer = unsafe { slice::from_raw_parts_mut(buffer as *mut u8, num_bytes) };

    let bytes_read = ops.read_from_partition(partition, offset, buffer)?;
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_num_read`.
    unsafe { ptr::write(out_num_read, bytes_read) };
    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn get_preloaded_partition(
    ops: *mut AvbOps,
    partition: *const c_char,
    num_bytes: usize,
    out_pointer: *mut *mut u8,
    out_num_bytes_preloaded: *mut usize,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe {
        result_to_io_enum(try_get_preloaded_partition(
            ops,
            partition,
            num_bytes,
            out_pointer,
            out_num_bytes_preloaded,
        ))
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `partition` must adhere to the requirements of `CStr::from_ptr()`.
/// * `out_pointer` and `out_num_bytes_preloaded` must adhere to the requirements of `ptr::write()`.
/// * `out_pointer` will become an alias to the `ops` preloaded partition data, so the preloaded
///   data must remain valid and unmodified while `out_pointer` exists.
unsafe fn try_get_preloaded_partition(
    ops: *mut AvbOps,
    partition: *const c_char,
    num_bytes: usize,
    out_pointer: *mut *mut u8,
    out_num_bytes_preloaded: *mut usize,
) -> IoResult<()> {
    check_nonnull(partition)?;
    check_nonnull(out_pointer)?;
    check_nonnull(out_num_bytes_preloaded)?;

    // Initialize the output variables first in case something fails.
    // SAFETY:
    // * we've checked that the pointers are non-NULL.
    // * libavb gives us properly-aligned and sized `out` vars.
    unsafe {
        ptr::write(out_pointer, ptr::null_mut());
        ptr::write(out_num_bytes_preloaded, 0);
    }

    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated and nul-terminated `partition`.
    // * the string contents are not modified while the returned `&CStr` exists.
    // * the returned `&CStr` is not held past the scope of this callback.
    let partition = unsafe { CStr::from_ptr(partition) };

    match ops.get_preloaded_partition(partition) {
        // SAFETY:
        // * we've checked that the pointers are non-NULL.
        // * libavb gives us properly-aligned and sized `out` vars.
        Ok(contents) => unsafe {
            ptr::write(
                out_pointer,
                // Warning: we are casting an immutable &[u8] to a mutable *u8. If libavb actually
                // modified these contents this could cause undefined behavior, but it just reads.
                // TODO: can we change the libavb API to take a const*?
                contents.as_ptr() as *mut u8,
            );
            ptr::write(
                out_num_bytes_preloaded,
                // Truncate here if necessary, we may have more preloaded data than libavb needs.
                min(contents.len(), num_bytes),
            );
        },
        // No-op if this partition is not preloaded, we've already reset the out variables to
        // indicate preloaded data is not available.
        Err(IoError::NotImplemented) => (),
        Err(e) => return Err(e),
    };
    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn validate_vbmeta_public_key(
    ops: *mut AvbOps,
    public_key_data: *const u8,
    public_key_length: usize,
    public_key_metadata: *const u8,
    public_key_metadata_length: usize,
    out_is_trusted: *mut bool,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe {
        result_to_io_enum(try_validate_vbmeta_public_key(
            ops,
            public_key_data,
            public_key_length,
            public_key_metadata,
            public_key_metadata_length,
            out_is_trusted,
        ))
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `public_key_*` args must adhere to the requirements of `slice::from_raw_parts()`.
/// * `out_is_trusted` must adhere to the requirements of `ptr::write()`.
unsafe fn try_validate_vbmeta_public_key(
    ops: *mut AvbOps,
    public_key_data: *const u8,
    public_key_length: usize,
    public_key_metadata: *const u8,
    public_key_metadata_length: usize,
    out_is_trusted: *mut bool,
) -> IoResult<()> {
    check_nonnull(public_key_data)?;
    check_nonnull(out_is_trusted)?;

    // Initialize the output variables first in case something fails.
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_is_trusted`.
    unsafe { ptr::write(out_is_trusted, false) };

    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `public_key_data` with size `public_key_length`.
    // * we only access the contents via the returned slice.
    // * the returned slice is not held past the scope of this callback.
    let public_key = unsafe { slice::from_raw_parts(public_key_data, public_key_length) };
    let metadata = check_nonnull(public_key_metadata).ok().map(
        // SAFETY:
        // * we've checked that the pointer is non-NULL.
        // * libavb gives us a properly-allocated `public_key_metadata` with size
        //   `public_key_metadata_length`.
        // * we only access the contents via the returned slice.
        // * the returned slice is not held past the scope of this callback.
        |_| unsafe { slice::from_raw_parts(public_key_metadata, public_key_metadata_length) },
    );

    let trusted = ops.validate_vbmeta_public_key(public_key, metadata)?;

    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_is_trusted`.
    unsafe { ptr::write(out_is_trusted, trusted) };
    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn read_rollback_index(
    ops: *mut AvbOps,
    rollback_index_location: usize,
    out_rollback_index: *mut u64,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe {
        result_to_io_enum(try_read_rollback_index(
            ops,
            rollback_index_location,
            out_rollback_index,
        ))
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `out_rollback_index` must adhere to the requirements of `ptr::write()`.
unsafe fn try_read_rollback_index(
    ops: *mut AvbOps,
    rollback_index_location: usize,
    out_rollback_index: *mut u64,
) -> IoResult<()> {
    check_nonnull(out_rollback_index)?;

    // Initialize the output variables first in case something fails.
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_rollback_index`.
    unsafe { ptr::write(out_rollback_index, 0) };

    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    let index = ops.read_rollback_index(rollback_index_location)?;

    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_rollback_index`.
    unsafe { ptr::write(out_rollback_index, index) };
    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn write_rollback_index(
    ops: *mut AvbOps,
    rollback_index_location: usize,
    rollback_index: u64,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe {
        result_to_io_enum(try_write_rollback_index(
            ops,
            rollback_index_location,
            rollback_index,
        ))
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
unsafe fn try_write_rollback_index(
    ops: *mut AvbOps,
    rollback_index_location: usize,
    rollback_index: u64,
) -> IoResult<()> {
    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    ops.write_rollback_index(rollback_index_location, rollback_index)
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn read_is_device_unlocked(
    ops: *mut AvbOps,
    out_is_unlocked: *mut bool,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe { result_to_io_enum(try_read_is_device_unlocked(ops, out_is_unlocked)) }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `out_is_unlocked` must adhere to the requirements of `ptr::write()`.
unsafe fn try_read_is_device_unlocked(
    ops: *mut AvbOps,
    out_is_unlocked: *mut bool,
) -> IoResult<()> {
    check_nonnull(out_is_unlocked)?;

    // Initialize the output variables first in case something fails.
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_is_unlocked`.
    unsafe { ptr::write(out_is_unlocked, false) };

    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    let unlocked = ops.read_is_device_unlocked()?;

    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_is_unlocked`.
    unsafe { ptr::write(out_is_unlocked, unlocked) };
    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn get_unique_guid_for_partition(
    ops: *mut AvbOps,
    partition: *const c_char,
    guid_buf: *mut c_char,
    guid_buf_size: usize,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe {
        result_to_io_enum(try_get_unique_guid_for_partition(
            ops,
            partition,
            guid_buf,
            guid_buf_size,
        ))
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// When the `uuid` feature is not enabled, this doesn't call into the user ops at all and instead
/// gives the empty string for all partitions.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `partition` must adhere to the requirements of `CStr::from_ptr()`.
/// * `guid_buf` must adhere to the requirements of `slice::from_raw_parts_mut()`.
unsafe fn try_get_unique_guid_for_partition(
    #[allow(unused_variables)] ops: *mut AvbOps,
    #[allow(unused_variables)] partition: *const c_char,
    guid_buf: *mut c_char,
    guid_buf_size: usize,
) -> IoResult<()> {
    check_nonnull(guid_buf)?;

    // On some architectures `c_char` is `u8`, and on others `i8`. We make sure it's `u8` here
    // since that's what `CStr::to_bytes_with_nul()` always provides.
    #[allow(clippy::unnecessary_cast)]
    let guid_buf = guid_buf as *mut u8;

    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `guid_buf` with size `guid_buf_size`.
    // * we only access the contents via the returned slice.
    // * the returned slice is not held past the scope of this callback.
    let buffer = unsafe { slice::from_raw_parts_mut(guid_buf, guid_buf_size) };

    // Initialize the output buffer to the empty string.
    //
    // When the `uuid` feature is not selected, the user doesn't need commandline GUIDs but libavb
    // may still attempt to inject the `vmbeta` or `boot` partition GUIDs into the commandline,
    // depending on the verification settings. In order to satisfy libavb's requirements we must:
    // * write a nul-terminated string to avoid undefined behavior (empty string is sufficient)
    // * return `Ok(())` or verification will fail
    if buffer.is_empty() {
        return Err(IoError::Oom);
    }
    buffer[0] = b'\0';

    #[cfg(feature = "uuid")]
    {
        check_nonnull(partition)?;

        // SAFETY:
        // * we've checked that the pointer is non-NULL.
        // * libavb gives us a properly-allocated and nul-terminated `partition`.
        // * the string contents are not modified while the returned `&CStr` exists.
        // * the returned `&CStr` is not held past the scope of this callback.
        let partition = unsafe { CStr::from_ptr(partition) };

        // SAFETY:
        // * we only use `ops` objects created via `OpsBridge` as required.
        // * `ops` is only extracted once and is dropped at the end of the callback.
        let ops = unsafe { as_ops(ops) }?;
        let guid = ops.get_unique_guid_for_partition(partition)?;

        // Write the UUID string to a uuid buffer which is guaranteed to be large enough, then use
        // `CString` to apply nul-termination.
        // This does allocate memory, but it's short-lived and discarded as soon as we copy the
        // properly-terminated string back to the buffer.
        let mut encode_buffer = Uuid::encode_buffer();
        let guid_str = guid.as_hyphenated().encode_lower(&mut encode_buffer);
        let guid_cstring = alloc::ffi::CString::new(guid_str.as_bytes()).or(Err(IoError::Io))?;
        let guid_bytes = guid_cstring.to_bytes_with_nul();

        if buffer.len() < guid_bytes.len() {
            // This would indicate some internal error - the uuid library needs more
            // space to print the UUID string than libavb provided.
            return Err(IoError::Oom);
        }
        buffer[..guid_bytes.len()].copy_from_slice(guid_bytes);
    }

    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn get_size_of_partition(
    ops: *mut AvbOps,
    partition: *const c_char,
    out_size_num_bytes: *mut u64,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe {
        result_to_io_enum(try_get_size_of_partition(
            ops,
            partition,
            out_size_num_bytes,
        ))
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `partition` must adhere to the requirements of `CStr::from_ptr()`.
/// * `out_size_num_bytes` must adhere to the requirements of `ptr::write()`.
unsafe fn try_get_size_of_partition(
    ops: *mut AvbOps,
    partition: *const c_char,
    out_size_num_bytes: *mut u64,
) -> IoResult<()> {
    check_nonnull(partition)?;
    check_nonnull(out_size_num_bytes)?;

    // Initialize the output variables first in case something fails.
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_size_num_bytes`.
    unsafe { ptr::write(out_size_num_bytes, 0) };

    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated and nul-terminated `partition`.
    // * the string contents are not modified while the returned `&CStr` exists.
    // * the returned `&CStr` is not held past the scope of this callback.
    let partition = unsafe { CStr::from_ptr(partition) };
    let size = ops.get_size_of_partition(partition)?;

    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_size_num_bytes`.
    unsafe { ptr::write(out_size_num_bytes, size) };
    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn read_persistent_value(
    ops: *mut AvbOps,
    name: *const c_char,
    buffer_size: usize,
    out_buffer: *mut u8,
    out_num_bytes_read: *mut usize,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe {
        result_to_io_enum(try_read_persistent_value(
            ops,
            name,
            buffer_size,
            out_buffer,
            out_num_bytes_read,
        ))
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `name` must adhere to the requirements of `CStr::from_ptr()`.
/// * `out_buffer` must adhere to the requirements of `slice::from_raw_parts_mut()`.
/// * `out_num_bytes_read` must adhere to the requirements of `ptr::write()`.
unsafe fn try_read_persistent_value(
    ops: *mut AvbOps,
    name: *const c_char,
    buffer_size: usize,
    out_buffer: *mut u8,
    out_num_bytes_read: *mut usize,
) -> IoResult<()> {
    check_nonnull(name)?;
    check_nonnull(out_num_bytes_read)?;

    // Initialize the output variables first in case something fails.
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `out_num_bytes_read`.
    unsafe { ptr::write(out_num_bytes_read, 0) };

    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated and nul-terminated `name`.
    // * the string contents are not modified while the returned `&CStr` exists.
    // * the returned `&CStr` is not held past the scope of this callback.
    let name = unsafe { CStr::from_ptr(name) };
    let mut empty: [u8; 0] = [];
    let value = match out_buffer.is_null() {
        // NULL buffer => empty slice, used to just query the value size.
        true => &mut empty,
        false => {
            // SAFETY:
            // * we've checked that the pointer is non-NULL.
            // * libavb gives us a properly-allocated `out_buffer` with size `buffer_size`.
            // * we only access the contents via the returned slice.
            // * the returned slice is not held past the scope of this callback.
            unsafe { slice::from_raw_parts_mut(out_buffer, buffer_size) }
        }
    };

    let result = ops.read_persistent_value(name, value);
    // On success or insufficient space we need to write the property size back.
    if let Ok(size) | Err(IoError::InsufficientSpace(size)) = result {
        // SAFETY:
        // * we've checked that the pointer is non-NULL.
        // * libavb gives us a properly-allocated `out_num_bytes_read`.
        unsafe { ptr::write(out_num_bytes_read, size) };
    };
    // We've written the size back and can drop it now.
    result.map(|_| ())
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn write_persistent_value(
    ops: *mut AvbOps,
    name: *const c_char,
    value_size: usize,
    value: *const u8,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe { result_to_io_enum(try_write_persistent_value(ops, name, value_size, value)) }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `name` must adhere to the requirements of `CStr::from_ptr()`.
/// * `out_buffer` must adhere to the requirements of `slice::from_raw_parts()`.
unsafe fn try_write_persistent_value(
    ops: *mut AvbOps,
    name: *const c_char,
    value_size: usize,
    value: *const u8,
) -> IoResult<()> {
    check_nonnull(name)?;

    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated and nul-terminated `name`.
    // * the string contents are not modified while the returned `&CStr` exists.
    // * the returned `&CStr` is not held past the scope of this callback.
    let name = unsafe { CStr::from_ptr(name) };

    if value_size == 0 {
        ops.erase_persistent_value(name)
    } else {
        check_nonnull(value)?;
        // SAFETY:
        // * we've checked that the pointer is non-NULL.
        // * libavb gives us a properly-allocated `value` with size `value_size`.
        // * we only access the contents via the returned slice.
        // * the returned slice is not held past the scope of this callback.
        let value = unsafe { slice::from_raw_parts(value, value_size) };
        ops.write_persistent_value(name, value)
    }
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn validate_public_key_for_partition(
    ops: *mut AvbOps,
    partition: *const c_char,
    public_key_data: *const u8,
    public_key_length: usize,
    public_key_metadata: *const u8,
    public_key_metadata_length: usize,
    out_is_trusted: *mut bool,
    out_rollback_index_location: *mut u32,
) -> AvbIOResult {
    // SAFETY: see corresponding `try_*` function safety documentation.
    unsafe {
        result_to_io_enum(try_validate_public_key_for_partition(
            ops,
            partition,
            public_key_data,
            public_key_length,
            public_key_metadata,
            public_key_metadata_length,
            out_is_trusted,
            out_rollback_index_location,
        ))
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `ops` must have been created via `OpsBridge`.
/// * `partition` must adhere to the requirements of `CStr::from_ptr()`.
/// * `public_key_*` args must adhere to the requirements of `slice::from_raw_parts()`.
/// * `out_*` must adhere to the requirements of `ptr::write()`.
#[allow(clippy::too_many_arguments)] // Mirroring libavb C API.
unsafe fn try_validate_public_key_for_partition(
    ops: *mut AvbOps,
    partition: *const c_char,
    public_key_data: *const u8,
    public_key_length: usize,
    public_key_metadata: *const u8,
    public_key_metadata_length: usize,
    out_is_trusted: *mut bool,
    out_rollback_index_location: *mut u32,
) -> IoResult<()> {
    check_nonnull(partition)?;
    check_nonnull(public_key_data)?;
    check_nonnull(out_is_trusted)?;
    check_nonnull(out_rollback_index_location)?;

    // Initialize the output variables first in case something fails.
    // SAFETY:
    // * we've checked that the pointers are non-NULL.
    // * libavb gives us a properly-allocated `out_*`.
    unsafe {
        ptr::write(out_is_trusted, false);
        ptr::write(out_rollback_index_location, 0);
    }

    // SAFETY:
    // * we only use `ops` objects created via `OpsBridge` as required.
    // * `ops` is only extracted once and is dropped at the end of the callback.
    let ops = unsafe { as_ops(ops) }?;
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated and nul-terminated `partition`.
    // * the string contents are not modified while the returned `&CStr` exists.
    // * the returned `&CStr` is not held past the scope of this callback.
    let partition = unsafe { CStr::from_ptr(partition) };
    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `public_key_data` with size `public_key_length`.
    // * we only access the contents via the returned slice.
    // * the returned slice is not held past the scope of this callback.
    let public_key = unsafe { slice::from_raw_parts(public_key_data, public_key_length) };
    let metadata = check_nonnull(public_key_metadata).ok().map(
        // SAFETY:
        // * we've checked that the pointer is non-NULL.
        // * libavb gives us a properly-allocated `public_key_metadata` with size
        //   `public_key_metadata_length`.
        // * we only access the contents via the returned slice.
        // * the returned slice is not held past the scope of this callback.
        |_| unsafe { slice::from_raw_parts(public_key_metadata, public_key_metadata_length) },
    );

    let key_info = ops.validate_public_key_for_partition(partition, public_key, metadata)?;

    // SAFETY:
    // * we've checked that the pointers are non-NULL.
    // * libavb gives us a properly-allocated `out_*`.
    unsafe {
        ptr::write(out_is_trusted, key_info.trusted);
        ptr::write(
            out_rollback_index_location,
            key_info.rollback_index_location,
        );
    }
    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn read_permanent_attributes(
    cert_ops: *mut AvbCertOps,
    attributes: *mut AvbCertPermanentAttributes,
) -> AvbIOResult {
    result_to_io_enum(
        // SAFETY: see corresponding `try_*` function safety documentation.
        unsafe { try_read_permanent_attributes(cert_ops, attributes) },
    )
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `cert_ops` must have been created via `ScopedAvbOps`.
/// * `attributes` must be a valid `AvbCertPermanentAttributes` that we have exclusive access to.
unsafe fn try_read_permanent_attributes(
    cert_ops: *mut AvbCertOps,
    attributes: *mut AvbCertPermanentAttributes,
) -> IoResult<()> {
    // SAFETY: `attributes` is a valid object provided by libavb that we have exclusive access to.
    let attributes = unsafe { attributes.as_mut() }.ok_or(IoError::Io)?;

    // SAFETY:
    // * we only use `cert_ops` objects created via `ScopedAvbOps` as required.
    // * `cert_ops` is only extracted once and is dropped at the end of the callback.
    let cert_ops = unsafe { as_cert_ops(cert_ops) }?;
    cert_ops.read_permanent_attributes(attributes)
}

/// Wraps a callback to convert the given `IoResult<>` to raw `AvbIOResult` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn read_permanent_attributes_hash(
    cert_ops: *mut AvbCertOps,
    hash: *mut u8,
) -> AvbIOResult {
    result_to_io_enum(
        // SAFETY: see corresponding `try_*` function safety documentation.
        unsafe { try_read_permanent_attributes_hash(cert_ops, hash) },
    )
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `cert_ops` must have been created via `ScopedAvbOps`.
/// * `hash` must point to a valid buffer of size `SHA256_DIGEST_SIZE` that we have exclusive
///   access to.
unsafe fn try_read_permanent_attributes_hash(
    cert_ops: *mut AvbCertOps,
    hash: *mut u8,
) -> IoResult<()> {
    check_nonnull(hash)?;

    // SAFETY:
    // * we only use `cert_ops` objects created via `ScopedAvbOps` as required.
    // * `cert_ops` is only extracted once and is dropped at the end of the callback.
    let cert_ops = unsafe { as_cert_ops(cert_ops) }?;
    let provided_hash = cert_ops.read_permanent_attributes_hash()?;

    // SAFETY:
    // * `provided_hash` is a valid `[u8]` with size `SHA256_DIGEST_SIZE`.
    // * libavb gives us a properly-allocated `hash` with size `SHA256_DIGEST_SIZE`.
    // * the arrays are independent objects and cannot overlap.
    unsafe { ptr::copy_nonoverlapping(provided_hash.as_ptr(), hash, SHA256_DIGEST_SIZE) };

    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to `None` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn set_key_version(
    cert_ops: *mut AvbCertOps,
    rollback_index_location: usize,
    key_version: u64,
) {
    // SAFETY: see corresponding `try_*` function safety documentation.
    let result = unsafe { try_set_key_version(cert_ops, rollback_index_location, key_version) };

    // `set_key_version()` is unique in that it has no return value, and therefore cannot fail.
    // However, our internal C -> Rust logic does have some potential failure points when we unwrap
    // the C pointers to extract our Rust objects.
    //
    // Ignoring the error could be a security risk, as it would silently prevent the device from
    // updating key rollback versions, so instead we panic here.
    if let Err(e) = result {
        panic!("Fatal error in set_key_version(): {:?}", e);
    }
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// `cert_ops` must have been created via `ScopedAvbOps`.
unsafe fn try_set_key_version(
    cert_ops: *mut AvbCertOps,
    rollback_index_location: usize,
    key_version: u64,
) -> IoResult<()> {
    // SAFETY:
    // * we only use `cert_ops` objects created via `ScopedAvbOps` as required.
    // * `cert_ops` is only extracted once and is dropped at the end of the callback.
    let cert_ops = unsafe { as_cert_ops(cert_ops) }?;
    cert_ops.set_key_version(rollback_index_location, key_version);
    Ok(())
}

/// Wraps a callback to convert the given `IoResult<>` to `None` for libavb.
///
/// See corresponding `try_*` function docs.
unsafe extern "C" fn get_random(
    cert_ops: *mut AvbCertOps,
    num_bytes: usize,
    output: *mut u8,
) -> AvbIOResult {
    result_to_io_enum(
        // SAFETY: see corresponding `try_*` function safety documentation.
        unsafe { try_get_random(cert_ops, num_bytes, output) },
    )
}

/// Bounces the C callback into the user-provided Rust implementation.
///
/// # Safety
/// * `cert_ops` must have been created via `ScopedAvbOps`.
/// * `output` must point to a valid buffer of size `num_bytes` that we have exclusive access to.
unsafe fn try_get_random(
    cert_ops: *mut AvbCertOps,
    num_bytes: usize,
    output: *mut u8,
) -> IoResult<()> {
    check_nonnull(output)?;
    if num_bytes == 0 {
        return Ok(());
    }

    // SAFETY:
    // * we've checked that the pointer is non-NULL.
    // * libavb gives us a properly-allocated `output` with size `num_bytes`.
    // * we only access the contents via the returned slice.
    // * the returned slice is not held past the scope of this callback.
    let output = unsafe { slice::from_raw_parts_mut(output, num_bytes) };

    // SAFETY:
    // * we only use `cert_ops` objects created via `ScopedAvbOps` as required.
    // * `cert_ops` is only extracted once and is dropped at the end of the callback.
    let cert_ops = unsafe { as_cert_ops(cert_ops) }?;
    cert_ops.get_random(output)
}
