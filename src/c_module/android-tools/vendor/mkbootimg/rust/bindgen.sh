#! /usr/bin/env bash
# Copyright 2023, The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

# Run this script to regenerate bootimg_priv.rs if
# include/bootimg/bootimg.h ever changes.
# The rust_bindgen rule is not cooperative, causing custom derive types
# to not percolate to the generated structures.
# It's just easier to do all the munging in a script.

SCRATCH_DIR=$(mktemp -d)

cleanup (){
    rm -rf ${SCRATCH_DIR}
}

trap cleanup EXIT
pushd ~/aosp > /dev/null

BOOTIMG_DIR=$(realpath system/tools/mkbootimg/)
# The stdint include generates a lot of unnecessary types that the
# generated rust bindings really don't need.
BLOCKED_TYPES_RE="__.+|.?int.+"
# The stdint include generates a lot of unnecessary constants that the
# generated rust bindings really don't need.
BLOCKED_ITEMS_RE="_.+|.?INT.+|PTR.+|ATOMIC.+|.+SOURCE|.+_H|SIG_.+|SIZE_.+|.?CHAR.+"
CUSTOM_STRUCT_RE="(vendor_)?(boot_img_hdr|ramdisk_table_entry)_v\d+"
CUSTOM_STRUCT_DERIVES="AsBytes,FromBytes,FromZeroes,PartialEq,Copy,Clone,Debug"
BINDGEN_FLAGS="--use-core --with-derive-default"
BOOTIMG_PRIV=${BOOTIMG_DIR}/rust/bootimg_priv.rs

# We need C++ isms, and the only obvious way to convince bindgen
# that the source is C++ is with a C++ extension.
cp ${BOOTIMG_DIR}/include/bootimg/bootimg.h ${SCRATCH_DIR}/bootimg.hpp

./out/host/linux-x86/bin/bindgen \
    --blocklist-type="${BLOCKED_TYPES_RE}" \
    --blocklist-item="${BLOCKED_ITEMS_RE}" \
    --with-derive-custom-struct="${CUSTOM_STRUCT_RE}=${CUSTOM_STRUCT_DERIVES}" \
    ${BINDGEN_FLAGS} \
    ${SCRATCH_DIR}/bootimg.hpp \
    -o ${SCRATCH_DIR}/bootimg_gen.rs

cat << EOF | cat - ${SCRATCH_DIR}/bootimg_gen.rs > ${BOOTIMG_PRIV}
// Copyright $(date +%Y), The Android Open Source Project
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

use zerocopy::{AsBytes, FromBytes, FromZeroes};

EOF

rustfmt ${BOOTIMG_PRIV} --config-path system/tools/aidl/rustfmt.toml
