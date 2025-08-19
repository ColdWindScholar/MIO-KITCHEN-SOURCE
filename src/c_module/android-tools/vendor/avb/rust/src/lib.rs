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

//! Rust libavb.
//!
//! This library wraps the libavb C code with safe Rust APIs. This does not materially affect the
//! safety of the library itself, since the internal implementation is still C. The goal here is
//! instead to provide a simple way to use libavb from Rust, in order to make Rust a more
//! appealing option for code that may want to use libavb such as bootloaders.
//!
//! This library is [no_std] for portability.

// ANDROID: Use std to allow building as a dylib.
// This condition lets us make the hack to add a dependency on std for the
// panic_handler and eh_personality conditional on actually building a dylib.
#![cfg_attr(not(any(test, android_dylib)), no_std)]

mod cert;
mod descriptor;
mod error;
mod ops;
mod verify;

pub use cert::{
    cert_generate_unlock_challenge, cert_validate_unlock_credential,
    cert_validate_vbmeta_public_key, CertOps, CertPermanentAttributes, CertUnlockChallenge,
    CertUnlockCredential, CERT_PIK_VERSION_LOCATION, CERT_PSK_VERSION_LOCATION, SHA256_DIGEST_SIZE,
};
pub use descriptor::{
    ChainPartitionDescriptor, ChainPartitionDescriptorFlags, Descriptor, DescriptorError,
    DescriptorResult, HashDescriptor, HashDescriptorFlags, HashtreeDescriptor,
    HashtreeDescriptorFlags, KernelCommandlineDescriptor, KernelCommandlineDescriptorFlags,
    PropertyDescriptor,
};
pub use error::{
    IoError, IoResult, SlotVerifyError, SlotVerifyNoDataResult, SlotVerifyResult,
    VbmetaVerifyError, VbmetaVerifyResult,
};
pub use ops::{Ops, PublicKeyForPartitionInfo};
pub use verify::{
    slot_verify, HashtreeErrorMode, PartitionData, SlotVerifyData, SlotVerifyFlags, VbmetaData,
};
