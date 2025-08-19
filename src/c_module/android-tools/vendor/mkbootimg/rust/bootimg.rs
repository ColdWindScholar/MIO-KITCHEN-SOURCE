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

//! The public interface for bootimg structs
use zerocopy::{ByteSlice, LayoutVerified};

use bootimg_private::{
    boot_img_hdr_v0, boot_img_hdr_v1, boot_img_hdr_v2, boot_img_hdr_v3, boot_img_hdr_v4,
    vendor_boot_img_hdr_v3, vendor_boot_img_hdr_v4, BOOT_MAGIC, BOOT_MAGIC_SIZE, VENDOR_BOOT_MAGIC,
    VENDOR_BOOT_MAGIC_SIZE,
};

/// Generalized boot image from a backing store of bytes.
#[derive(PartialEq, Debug)]
pub enum BootImage<B: ByteSlice + PartialEq> {
    /// Version 0 header
    V0(LayoutVerified<B, boot_img_hdr_v0>),
    /// Version 1 header
    V1(LayoutVerified<B, boot_img_hdr_v1>),
    /// Version 2 header
    V2(LayoutVerified<B, boot_img_hdr_v2>),
    /// Version 3 header
    V3(LayoutVerified<B, boot_img_hdr_v3>),
    /// Version 4 header
    V4(LayoutVerified<B, boot_img_hdr_v4>),
}

/// Generalized vendor boot header from a backing store of bytes.
#[derive(PartialEq, Debug)]
pub enum VendorImageHeader<B: ByteSlice + PartialEq> {
    /// Version 3 header
    V3(LayoutVerified<B, vendor_boot_img_hdr_v3>),
    /// Version 4 header
    V4(LayoutVerified<B, vendor_boot_img_hdr_v4>),
}

/// Boot related errors.
#[derive(PartialEq, Debug)]
pub enum ImageError {
    /// The provided buffer was too small to hold a header.
    BufferTooSmall,
    /// The magic string was incorrect.
    BadMagic,
    /// The header version present is not supported.
    UnexpectedVersion,
    /// Catch-all for remaining errors.
    Unknown,
}

impl core::fmt::Display for ImageError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        let str = match self {
            Self::BufferTooSmall => "The provided buffer is too small",
            Self::BadMagic => "The magic string is incorrect",
            Self::UnexpectedVersion => "Header version is not supported",
            Self::Unknown => "Unknown error",
        };
        write!(f, "{str}")
    }
}

/// Common result type for use with boot headers
pub type BootResult<T> = Result<T, ImageError>;

fn parse_header<B: ByteSlice + PartialEq, T>(buffer: B) -> BootResult<LayoutVerified<B, T>> {
    Ok(LayoutVerified::<B, T>::new_from_prefix(buffer).ok_or(ImageError::BufferTooSmall)?.0)
}

impl<B: ByteSlice + PartialEq> BootImage<B> {
    /// Given a byte buffer, attempt to parse the contents and return a zero-copy reference
    /// to the associated boot image header.
    ///
    /// # Arguments
    /// * `buffer` - buffer to parse
    ///
    /// # Returns
    ///
    /// * `Ok(BootImage)` - if parsing was successful.
    /// * `Err(ImageError)` - if `buffer` does not contain a valid boot image header.
    ///
    /// # Example
    ///
    /// ```
    /// use bootimg::BootImage;
    ///
    /// let mut buffer = [0; 4096];
    /// // Not shown: read first 4096 bytes of boot image into buffer
    /// let header = BootImage::parse(&buffer[..]).unwrap();
    /// ```
    pub fn parse(buffer: B) -> BootResult<Self> {
        let magic_size = BOOT_MAGIC_SIZE as usize;
        // Note: even though the v3 header is not a prefix for the v0, v1, or v2 header,
        // the version and the magic string exist at the same offset and have the same types.
        // Make a v3 temporary because it is the smallest.
        let (hdr, _) =
            LayoutVerified::<&[u8], boot_img_hdr_v3>::new_from_prefix(buffer.get(..).unwrap())
                .ok_or(ImageError::BufferTooSmall)?;

        if hdr.magic.ne(&BOOT_MAGIC[..magic_size]) {
            return Err(ImageError::BadMagic);
        }

        match hdr.header_version {
            0 => Ok(Self::V0(parse_header::<B, boot_img_hdr_v0>(buffer)?)),
            1 => Ok(Self::V1(parse_header::<B, boot_img_hdr_v1>(buffer)?)),
            2 => Ok(Self::V2(parse_header::<B, boot_img_hdr_v2>(buffer)?)),
            3 => Ok(Self::V3(parse_header::<B, boot_img_hdr_v3>(buffer)?)),
            4 => Ok(Self::V4(parse_header::<B, boot_img_hdr_v4>(buffer)?)),
            _ => Err(ImageError::UnexpectedVersion),
        }
    }
}

impl<B: ByteSlice + PartialEq> VendorImageHeader<B> {
    /// Given a byte buffer, attempt to parse the contents and return a zero-copy reference
    /// to the associated vendor boot image header.
    ///
    /// # Arguments
    /// * `buffer` - buffer to parse
    ///
    /// # Returns
    ///
    /// * `Ok(VendorImageHeader)` - if parsing was successful.
    /// * `Err(ImageError)` - If `buffer` does not contain a valid boot image header.
    ///
    /// # Example
    ///
    /// ```
    /// use bootimg::VendorImageHeader;
    ///
    /// let mut buffer = [0; 4096];
    /// // Not shown: read first 4096 bytes of vendor image into buffer
    /// let header = VendorImageHeader::parse(&buffer[..]).unwrap();
    /// ```
    pub fn parse(buffer: B) -> BootResult<Self> {
        let magic_size = VENDOR_BOOT_MAGIC_SIZE as usize;
        let (hdr, _) = LayoutVerified::<&[u8], vendor_boot_img_hdr_v3>::new_from_prefix(
            buffer.get(..).unwrap(),
        )
        .ok_or(ImageError::BufferTooSmall)?;

        if hdr.magic.ne(&VENDOR_BOOT_MAGIC[..magic_size]) {
            return Err(ImageError::BadMagic);
        }

        match hdr.header_version {
            3 => Ok(Self::V3(parse_header::<B, vendor_boot_img_hdr_v3>(buffer)?)),
            4 => Ok(Self::V4(parse_header::<B, vendor_boot_img_hdr_v4>(buffer)?)),
            _ => Err(ImageError::UnexpectedVersion),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use zerocopy::AsBytes;

    const MAGIC_SIZE: usize = BOOT_MAGIC_SIZE as usize;
    const VENDOR_MAGIC_SIZE: usize = VENDOR_BOOT_MAGIC_SIZE as usize;

    pub fn add<T: AsBytes>(buffer: &mut [u8], t: T) {
        t.write_to_prefix(buffer).unwrap();
    }

    #[test]
    fn buffer_too_small_for_version() {
        let buffer = [0; 40];
        assert_eq!(BootImage::parse(&buffer[..]), Err(ImageError::BufferTooSmall));
    }

    #[test]
    fn buffer_too_small_valid_version() {
        // Note: because the v1 header fully encapsulates the v0 header,
        // we can trigger a buffer-too-small error by providing
        // a perfectly valid v0 header and changing the version to 1.
        let mut buffer = [0; core::mem::size_of::<boot_img_hdr_v0>()];
        add::<boot_img_hdr_v0>(
            &mut buffer,
            boot_img_hdr_v0 {
                magic: BOOT_MAGIC[0..MAGIC_SIZE].try_into().unwrap(),
                header_version: 1,
                ..Default::default()
            },
        );
        assert_eq!(BootImage::parse(&buffer[..]), Err(ImageError::BufferTooSmall));
    }

    #[test]
    fn bad_magic() {
        let mut buffer = [0; core::mem::size_of::<boot_img_hdr_v0>()];
        add::<boot_img_hdr_v0>(
            &mut buffer,
            boot_img_hdr_v0 { magic: *b"ANDROGEN", ..Default::default() },
        );
        assert_eq!(BootImage::parse(&buffer[..]), Err(ImageError::BadMagic));
    }

    #[test]
    fn bad_version() {
        let mut buffer = [0; core::mem::size_of::<boot_img_hdr_v0>()];
        add::<boot_img_hdr_v0>(
            &mut buffer,
            boot_img_hdr_v0 {
                magic: BOOT_MAGIC[0..MAGIC_SIZE].try_into().unwrap(),
                header_version: 2112,
                ..Default::default()
            },
        );
        assert_eq!(BootImage::parse(&buffer[..]), Err(ImageError::UnexpectedVersion));
    }

    #[test]
    fn parse_v0() {
        let mut buffer = [0; core::mem::size_of::<boot_img_hdr_v0>()];
        add::<boot_img_hdr_v0>(
            &mut buffer,
            boot_img_hdr_v0 {
                magic: BOOT_MAGIC[0..MAGIC_SIZE].try_into().unwrap(),
                header_version: 0,
                ..Default::default()
            },
        );
        let expected =
            Ok(BootImage::V0(LayoutVerified::<&[u8], boot_img_hdr_v0>::new(&buffer).unwrap()));
        assert_eq!(BootImage::parse(&buffer[..]), expected);
    }

    #[test]
    fn parse_v1() {
        let mut buffer = [0; core::mem::size_of::<boot_img_hdr_v1>()];
        add::<boot_img_hdr_v1>(
            &mut buffer,
            boot_img_hdr_v1 {
                _base: boot_img_hdr_v0 {
                    magic: BOOT_MAGIC[0..MAGIC_SIZE].try_into().unwrap(),
                    header_version: 1,
                    ..Default::default()
                },
                ..Default::default()
            },
        );
        let expected =
            Ok(BootImage::V1(LayoutVerified::<&[u8], boot_img_hdr_v1>::new(&buffer).unwrap()));
        assert_eq!(BootImage::parse(&buffer[..]), expected);
    }

    #[test]
    fn parse_v2() {
        let mut buffer = [0; core::mem::size_of::<boot_img_hdr_v2>()];
        add::<boot_img_hdr_v2>(
            &mut buffer,
            boot_img_hdr_v2 {
                _base: boot_img_hdr_v1 {
                    _base: boot_img_hdr_v0 {
                        magic: BOOT_MAGIC[0..MAGIC_SIZE].try_into().unwrap(),
                        header_version: 2,
                        ..Default::default()
                    },
                    ..Default::default()
                },
                ..Default::default()
            },
        );
        let expected =
            Ok(BootImage::V2(LayoutVerified::<&[u8], boot_img_hdr_v2>::new(&buffer).unwrap()));
        assert_eq!(BootImage::parse(&buffer[..]), expected);
    }

    #[test]
    fn parse_v3() {
        let mut buffer = [0; core::mem::size_of::<boot_img_hdr_v3>()];
        add::<boot_img_hdr_v3>(
            &mut buffer,
            boot_img_hdr_v3 {
                magic: BOOT_MAGIC[0..MAGIC_SIZE].try_into().unwrap(),
                header_version: 3,
                ..Default::default()
            },
        );
        let expected =
            Ok(BootImage::V3(LayoutVerified::<&[u8], boot_img_hdr_v3>::new(&buffer).unwrap()));
        assert_eq!(BootImage::parse(&buffer[..]), expected);
    }

    #[test]
    fn parse_v4() {
        let mut buffer = [0; core::mem::size_of::<boot_img_hdr_v4>()];
        add::<boot_img_hdr_v4>(
            &mut buffer,
            boot_img_hdr_v4 {
                _base: boot_img_hdr_v3 {
                    magic: BOOT_MAGIC[0..MAGIC_SIZE].try_into().unwrap(),
                    header_version: 4,
                    ..Default::default()
                },
                ..Default::default()
            },
        );
        let expected =
            Ok(BootImage::V4(LayoutVerified::<&[u8], boot_img_hdr_v4>::new(&buffer).unwrap()));
        assert_eq!(BootImage::parse(&buffer[..]), expected);
    }

    #[test]
    fn vendor_buffer_too_small_for_version() {
        let buffer = [0; VENDOR_MAGIC_SIZE + 3];
        assert_eq!(VendorImageHeader::parse(&buffer[..]), Err(ImageError::BufferTooSmall));
    }

    #[test]
    fn vendor_bad_magic() {
        let mut buffer = [0; core::mem::size_of::<vendor_boot_img_hdr_v3>()];
        add::<vendor_boot_img_hdr_v3>(
            &mut buffer,
            vendor_boot_img_hdr_v3 { magic: *b"VNDRBOOK", header_version: 3, ..Default::default() },
        );
        assert_eq!(VendorImageHeader::parse(&buffer[..]), Err(ImageError::BadMagic));
    }

    #[test]
    fn vendor_bad_version() {
        let mut buffer = [0; core::mem::size_of::<vendor_boot_img_hdr_v3>()];
        add::<vendor_boot_img_hdr_v3>(
            &mut buffer,
            vendor_boot_img_hdr_v3 {
                magic: VENDOR_BOOT_MAGIC[0..VENDOR_MAGIC_SIZE].try_into().unwrap(),
                header_version: 2112,
                ..Default::default()
            },
        );
        assert_eq!(VendorImageHeader::parse(&buffer[..]), Err(ImageError::UnexpectedVersion));
    }

    #[test]
    fn vendor_buffer_too_small_valid_version() {
        let mut buffer = [0; core::mem::size_of::<vendor_boot_img_hdr_v3>()];
        add::<vendor_boot_img_hdr_v3>(
            &mut buffer,
            vendor_boot_img_hdr_v3 {
                magic: VENDOR_BOOT_MAGIC[0..VENDOR_MAGIC_SIZE].try_into().unwrap(),
                // Note: because the v4 header fully encapsulates the v3 header,
                // we can trigger a buffer-too-small error by providing
                // a perfectly valid v3 header and changing the version to 4.
                header_version: 4,
                ..Default::default()
            },
        );
        assert_eq!(VendorImageHeader::parse(&buffer[..]), Err(ImageError::BufferTooSmall));
    }

    #[test]
    fn vendor_parse_v3() {
        let mut buffer = [0; core::mem::size_of::<vendor_boot_img_hdr_v3>()];
        add::<vendor_boot_img_hdr_v3>(
            &mut buffer,
            vendor_boot_img_hdr_v3 {
                magic: VENDOR_BOOT_MAGIC[0..VENDOR_MAGIC_SIZE].try_into().unwrap(),
                header_version: 3,
                ..Default::default()
            },
        );
        let expected = Ok(VendorImageHeader::V3(
            LayoutVerified::<&[u8], vendor_boot_img_hdr_v3>::new(&buffer).unwrap(),
        ));
        assert_eq!(VendorImageHeader::parse(&buffer[..]), expected);
    }

    #[test]
    fn vendor_parse_v4() {
        let mut buffer = [0; core::mem::size_of::<vendor_boot_img_hdr_v4>()];
        add::<vendor_boot_img_hdr_v4>(
            &mut buffer,
            vendor_boot_img_hdr_v4 {
                _base: vendor_boot_img_hdr_v3 {
                    magic: VENDOR_BOOT_MAGIC[0..VENDOR_MAGIC_SIZE].try_into().unwrap(),
                    header_version: 4,
                    ..Default::default()
                },
                ..Default::default()
            },
        );
        let expected = Ok(VendorImageHeader::V4(
            LayoutVerified::<&[u8], vendor_boot_img_hdr_v4>::new(&buffer).unwrap(),
        ));
        assert_eq!(VendorImageHeader::parse(&buffer[..]), expected);
    }
}
