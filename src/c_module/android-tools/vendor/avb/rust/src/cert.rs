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

//! libavb_cert support.
//!
//! libavb_cert is an optional extension on top of the standard libavb API. It provides two
//! additional features:
//!
//! 1. Key management
//! 2. Authenticated unlock
//!
//! # Key management
//! The standard avb `Ops` must provide callbacks to manually validate vbmeta signing keys. This can
//! become complicated when using best-practices such as key heirarchies and rotations, which often
//! results in implementations omitting these features and just using a single fixed key.
//!
//! libavb_cert enables these features more easily by internally managing a set of related keys:
//!
//! * Product root key (PRK): un-rotateable root key
//! * Product intermediate key (PIK): rotateable key signed by the PRK
//! * Product signing key (PSK): rotateable key signed by the PIK, used as the vbmeta key
//!
//! PIK and PSK rotations are supported by storing their versions as rollback indices, so that
//! once the keys have been rotated the rollback value updates and the older keys will no longer
//! be accepted.
//!
//! The device validates keys using a fixed blob of data called "permanent attributes", which can
//! authenticate via the PRK and never needs to change even when PIK/PSK are rotated.
//!
//! To use this functionality, implement the `CertOps` trait and forward
//! `validate_vbmeta_public_key()` and/or `validate_public_key_for_partition()` to the provided
//! `cert_validate_vbmeta_public_key()` implementation.
//!
//! # Authenticated unlock
//! Typically devices support fastboot commands such as `fastboot flashing unlock` to unlock the
//! bootloader. Authenticated unlock is an optional feature that additionally adds an authentication
//! requirement in order to unlock the bootloader.
//!
//! Authenticated unlock introduces one additional key, the product unlock key (PUK), which is
//! signed by the PIK. The PUK is in the same key heirarchy but a distinct key, so that access to
//! the PUK does not give the ability to sign images. When authenticated unlock is requested,
//! libavb_cert produces a randomized "challenge token" which the user must then properly sign with
//! the PUK in order to unlock.
//!
//! It's up to individual device policy how to use authenticated unlock. For example a device may
//! want to support standard un-authenticated unlock for most operations, but then additionally
//! use authenticated unlock to enable higher-privileged operations.
//!
//! An example unlock flow using fastboot might look like this:
//!
//! ```ignore
//! # 1. Generate an unlock challenge (the exact fastboot command is device-specific).
//! $ fastboot oem get-auth-unlock-challenge
//!
//! # Internally, the device calls `cert_generate_unlock_challenge()` to generate the token.
//!
//! # 2. Download the challenge token from the device.
//! $ fastboot get_staged /tmp/challenge.bin
//!
//! # 3. Sign the challenge with the PUK.
//! $ avbtool make_cert_unlock_credential \
//!     --challenge /tmp/challenge.bin \
//!     --output /tmp/signed.bin \
//!     ...  # see --help for full args
//!
//! # 4. Upload the signed credential back to the device.
//! $ fastboot stage /tmp/signed.bin
//!
//! # 5. Unlock the device (the exact fastboot command is device-specific).
//! $ fastboot oem auth-unlock
//!
//! # Internally, the device calls `cert_validate_unlock_credential()` to verify the credential.
//! ```

use crate::{error::io_enum_to_result, ops, IoError, IoResult, Ops, PublicKeyForPartitionInfo};
use avb_bindgen::{
    avb_cert_generate_unlock_challenge, avb_cert_validate_unlock_credential,
    avb_cert_validate_vbmeta_public_key,
};
use core::{ffi::CStr, pin::pin};
#[cfg(feature = "uuid")]
use uuid::Uuid;

/// libavb_cert permanent attributes.
pub use avb_bindgen::AvbCertPermanentAttributes as CertPermanentAttributes;

/// Authenticated unlock challenge.
pub use avb_bindgen::AvbCertUnlockChallenge as CertUnlockChallenge;

/// Signed authenticated unlock credential.
pub use avb_bindgen::AvbCertUnlockCredential as CertUnlockCredential;

/// Size in bytes of a SHA256 digest.
pub const SHA256_DIGEST_SIZE: usize = avb_bindgen::AVB_SHA256_DIGEST_SIZE as usize;

/// Product intermediate key (PIK) rollback index location.
///
/// If using libavb_cert, make sure no vbmetas use this location, it must be reserved for the PIK.
pub const CERT_PIK_VERSION_LOCATION: usize = avb_bindgen::AVB_CERT_PIK_VERSION_LOCATION as usize;

/// Product signing key (PSK) rollback index location.
///
/// If using libavb_cert, make sure no vbmetas use this location, it must be reserved for the PSK.
pub const CERT_PSK_VERSION_LOCATION: usize = avb_bindgen::AVB_CERT_PSK_VERSION_LOCATION as usize;

/// libavb_cert extension callbacks.
pub trait CertOps {
    /// Reads the device's permanent attributes.
    ///
    /// The full permanent attributes are not required to be securely stored; corruption of this
    /// data will result in failing to verify the images (denial-of-service), but will not change
    /// the signing keys or allow improperly-signed images to verify.
    ///
    /// # Arguments
    /// * `attributes`: permanent attributes to update; passed as an output parameter rather than a
    ///                 return value due to the size (>1KiB).
    ///
    /// # Returns
    /// Unit on success, error on failure.
    fn read_permanent_attributes(
        &mut self,
        attributes: &mut CertPermanentAttributes,
    ) -> IoResult<()>;

    /// Reads the SHA256 hash of the device's permanent attributes.
    ///
    /// This hash must be sourced from secure storage whenever the device is locked; corruption
    /// of this data could result in changing the signing keys and allowing improperly-signed images
    /// to pass verification.
    ///
    /// This may be calculated at runtime from `read_permanent_attributes()` only if the entire
    /// permanent attributes are sourced from secure storage, but secure storage space is often
    /// limited so it can be useful to only store the hash securely.
    ///
    /// # Returns
    /// The 32-byte SHA256 digest on success, error on failure.
    fn read_permanent_attributes_hash(&mut self) -> IoResult<[u8; SHA256_DIGEST_SIZE]>;

    /// Provides the key version for the rotateable keys.
    ///
    /// libavb_cert stores signing key versions as rollback indices; when this function is called it
    /// indicates that the key at the given index location is using the given version.
    ///
    /// The exact steps to take when receiving this callback depend on device policy, but generally
    /// these values should only be cached in this callback, and written to the rollback storage
    /// only after the images are known to be successful.
    ///
    /// For example, a device using A/B boot slots should not update the key version rollbacks
    /// until it knows for sure the new image works, otherwise an OTA could break the A/B fallback
    /// behavior by updating the key version too soon and preventing falling back to the previous
    /// slot.
    ///
    /// # Arguments
    /// * `rollback_index_location`: rollback location to store this key version
    /// * `key_version`: value to store in the rollback location
    ///
    /// # Returns
    /// `None`; since the rollback should be cached rather than written immediately, this function
    /// cannot fail.
    fn set_key_version(&mut self, rollback_index_location: usize, key_version: u64);

    /// Generates random bytes.
    ///
    /// This is only used for authenticated unlock. If authenticated unlock is not needed, this can
    /// just return `IoError::NotImplemented`.
    ///
    /// # Arguments
    /// * `bytes`: buffer to completely fill with random bytes.
    ///
    /// # Returns
    /// Unit on success, error on failure.
    fn get_random(&mut self, bytes: &mut [u8]) -> IoResult<()>;
}

/// Certificate-based vbmeta key validation.
///
/// This can be called from `validate_vbmeta_public_key()` or `validate_public_key_for_partition()`
/// to provide the correct behavior using the libavb_cert keys, such as:
///
/// ```
/// impl avb::Ops for MyOps {
///   fn validate_vbmeta_public_key(
///     &mut self,
///     public_key: &[u8],
///     public_key_metadata: Option<&[u8]>,
///   ) -> IoResult<bool> {
///     cert_validate_vbmeta_public_key(self, public_key, public_key_metadata)
///   }
/// }
/// ```
///
/// We don't automatically call this from the validation functions because it's up to the device
/// when to use certificate authentication e.g. a device may want to use libavb_cert only for
/// specific partitions.
///
/// # Arguments
/// * `ops`: the `Ops` callback implementations, which must provide a `cert_ops()` implementation.
/// * `public_key`: the public key.
/// * `public_key_metadata`: public key metadata.
///
/// # Returns
/// * `Ok(true)` if the given key is valid according to the permanent attributes.
/// * `Ok(false)` if the given key is invalid.
/// * `Err(IoError::NotImplemented)` if `ops` does not provide the required `cert_ops()`.
/// * `Err(IoError)` on `ops` callback error.
pub fn cert_validate_vbmeta_public_key(
    ops: &mut dyn Ops,
    public_key: &[u8],
    public_key_metadata: Option<&[u8]>,
) -> IoResult<bool> {
    // This API requires both AVB and cert ops.
    if ops.cert_ops().is_none() {
        return Err(IoError::NotImplemented);
    }

    let ops_bridge = pin!(ops::OpsBridge::new(ops));
    let public_key_metadata = public_key_metadata.unwrap_or(&[]);
    let mut trusted = false;
    io_enum_to_result(
        // SAFETY:
        // * `ops_bridge.init_and_get_c_ops()` gives us a valid `AvbOps` with cert.
        // * `public_key` args are C-compatible pointer + size byte buffers.
        // * `trusted` is a C-compatible bool.
        // * this function does not retain references to any of these arguments.
        unsafe {
            avb_cert_validate_vbmeta_public_key(
                ops_bridge.init_and_get_c_ops(),
                public_key.as_ptr(),
                public_key.len(),
                public_key_metadata.as_ptr(),
                public_key_metadata.len(),
                &mut trusted,
            )
        },
    )?;
    Ok(trusted)
}

/// Generates a challenge for authenticated unlock.
///
/// Used to create a challenge token to be signed with the PUK.
///
/// The user can sign the resulting token via `avbtool make_cert_unlock_credential`.
///
/// # Arguments
/// * `cert_ops`: the `CertOps` callback implementations; base `Ops` are not required here.
///
/// # Returns
/// The challenge to sign with the PUK, or `IoError` on `cert_ops` failure.
pub fn cert_generate_unlock_challenge(cert_ops: &mut dyn CertOps) -> IoResult<CertUnlockChallenge> {
    // `OpsBridge` requires a full `Ops` object, so we wrap `cert_ops` in a do-nothing `Ops`
    // implementation. This is simpler than teaching `OpsBridge` to handle the cert-only case.
    let mut ops = CertOnlyOps { cert_ops };
    let ops_bridge = pin!(ops::OpsBridge::new(&mut ops));
    let mut challenge = CertUnlockChallenge::default();
    io_enum_to_result(
        // SAFETY:
        // * `ops_bridge.init_and_get_c_ops()` gives us a valid `AvbOps` with cert.
        // * `challenge` is a valid C-compatible `CertUnlockChallenge`.
        // * this function does not retain references to any of these arguments.
        unsafe {
            avb_cert_generate_unlock_challenge(
                ops_bridge.init_and_get_c_ops().cert_ops,
                &mut challenge,
            )
        },
    )?;
    Ok(challenge)
}

/// Validates a signed credential for authenticated unlock.
///
/// Used to check that an unlock credential was properly signed with the PUK according to the
/// device's permanent attributes.
///
/// # Arguments
/// * `ops`: the `Ops` callback implementations, which must provide a `cert_ops()` implementation.
/// * `credential`: the signed unlock credential to verify.
///
/// # Returns
/// * `Ok(true)` if the credential validated
/// * `Ok(false)` if it failed validation
/// * `Err(IoError::NotImplemented)` if `ops` does not provide the required `cert_ops()`.
/// * `Err(IoError)` on `ops` failure
pub fn cert_validate_unlock_credential(
    // Note: in the libavb C API this function takes an `AvbCertOps` rather than `AvbOps`, but
    // the implementation requires both, so we need an `Ops` here. This is also more consistent
    // with `validate_vbmeta_public_key()` which similarly requires both but takes `AvbOps`.
    ops: &mut dyn Ops,
    credential: &CertUnlockCredential,
) -> IoResult<bool> {
    // This API requires both AVB and cert ops.
    if ops.cert_ops().is_none() {
        return Err(IoError::NotImplemented);
    }

    let ops_bridge = pin!(ops::OpsBridge::new(ops));
    let mut trusted = false;
    io_enum_to_result(
        // SAFETY:
        // * `ops_bridge.init_and_get_c_ops()` gives us a valid `AvbOps` with cert.
        // * `credential` is a valid C-compatible `CertUnlockCredential`.
        // * `trusted` is a C-compatible bool.
        // * this function does not retain references to any of these arguments.
        unsafe {
            avb_cert_validate_unlock_credential(
                ops_bridge.init_and_get_c_ops().cert_ops,
                credential,
                &mut trusted,
            )
        },
    )?;
    Ok(trusted)
}

/// An `Ops` implementation that only provides the `cert_ops()` callback.
struct CertOnlyOps<'a> {
    cert_ops: &'a mut dyn CertOps,
}

impl<'a> Ops<'static> for CertOnlyOps<'a> {
    fn read_from_partition(
        &mut self,
        _partition: &CStr,
        _offset: i64,
        _buffer: &mut [u8],
    ) -> IoResult<usize> {
        Err(IoError::NotImplemented)
    }

    fn validate_vbmeta_public_key(
        &mut self,
        _public_key: &[u8],
        _public_key_metadata: Option<&[u8]>,
    ) -> IoResult<bool> {
        Err(IoError::NotImplemented)
    }

    fn read_rollback_index(&mut self, _rollback_index_location: usize) -> IoResult<u64> {
        Err(IoError::NotImplemented)
    }

    fn write_rollback_index(
        &mut self,
        _rollback_index_location: usize,
        _index: u64,
    ) -> IoResult<()> {
        Err(IoError::NotImplemented)
    }

    fn read_is_device_unlocked(&mut self) -> IoResult<bool> {
        Err(IoError::NotImplemented)
    }

    #[cfg(feature = "uuid")]
    fn get_unique_guid_for_partition(&mut self, _partition: &CStr) -> IoResult<Uuid> {
        Err(IoError::NotImplemented)
    }

    fn get_size_of_partition(&mut self, _partition: &CStr) -> IoResult<u64> {
        Err(IoError::NotImplemented)
    }

    fn read_persistent_value(&mut self, _name: &CStr, _value: &mut [u8]) -> IoResult<usize> {
        Err(IoError::NotImplemented)
    }

    fn write_persistent_value(&mut self, _name: &CStr, _value: &[u8]) -> IoResult<()> {
        Err(IoError::NotImplemented)
    }

    fn erase_persistent_value(&mut self, _name: &CStr) -> IoResult<()> {
        Err(IoError::NotImplemented)
    }

    fn validate_public_key_for_partition(
        &mut self,
        _partition: &CStr,
        _public_key: &[u8],
        _public_key_metadata: Option<&[u8]>,
    ) -> IoResult<PublicKeyForPartitionInfo> {
        Err(IoError::NotImplemented)
    }

    fn cert_ops(&mut self) -> Option<&mut dyn CertOps> {
        Some(self.cert_ops)
    }
}
