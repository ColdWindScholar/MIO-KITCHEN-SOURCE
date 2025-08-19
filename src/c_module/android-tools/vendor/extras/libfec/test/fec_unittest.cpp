/*
 * Copyright (C) 2019 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <stdint.h>
#include <stdlib.h>

#include <string>
#include <vector>

#include <android-base/file.h>
#include <android-base/strings.h>
#include <gtest/gtest.h>
#include <verity/hash_tree_builder.h>

#include "../fec_private.h"
#include "fec/io.h"

class FecUnitTest : public ::testing::Test {
   protected:
    void SetUp() override {
        // Construct a 1 MiB image as file system.
        image_.reserve(1024 * 1024);
        for (unsigned i = 0; i <= 255; i++) {
            std::vector<uint8_t> tmp_vec(4096, i);
            image_.insert(image_.end(), tmp_vec.begin(), tmp_vec.end());
        }
    }
    void BuildHashtree(const std::string &hash_name) {
        // Build the hashtree.
        HashTreeBuilder builder(4096, HashTreeBuilder::HashFunction(hash_name));
        // Use a random salt.
        salt_ = std::vector<uint8_t>(64, 10);
        ASSERT_TRUE(builder.Initialize(image_.size(), salt_));
        ASSERT_TRUE(builder.Update(image_.data(), image_.size()));
        ASSERT_TRUE(builder.BuildHashTree());
        root_hash_ = builder.root_hash();

        TemporaryFile temp_file;
        ASSERT_TRUE(builder.WriteHashTreeToFd(temp_file.fd, 0));
        android::base::ReadFileToString(temp_file.path, &hashtree_content_);
    }

    // Builds the verity metadata and appends the bytes to the image.
    void BuildAndAppendsVerityMetadata() {
        BuildHashtree("sha256");
        // Append the hashtree to the end of image.
        image_.insert(image_.end(), hashtree_content_.begin(),
                      hashtree_content_.end());

        // The metadata table has the format: "1 block_device, block_device,
        // BLOCK_SIZE, BLOCK_SIZE, data_blocks, data_blocks, 'sha256',
        // root_hash, salt".
        std::vector<std::string> table = {
            "1",
            "fake_block_device",
            "fake_block_device",
            "4096",
            "4096",
            "256",
            "256",
            "sha256",
            HashTreeBuilder::BytesArrayToString(root_hash_),
            HashTreeBuilder::BytesArrayToString(salt_),
        };
        verity_table_ = android::base::Join(table, ' ');

        verity_header_ = {
            0xb001b001, 0, {}, static_cast<unsigned int>(verity_table_.size())
        };

        // Construct the verity metadata with header, table, and padding.
        constexpr auto VERITY_META_SIZE = 8 * 4096;
        image_.insert(image_.end(),
                      reinterpret_cast<uint8_t *>(&verity_header_),
                      reinterpret_cast<uint8_t *>(&verity_header_) +
                          sizeof(verity_header_));
        image_.insert(image_.end(), verity_table_.data(),
                      verity_table_.data() + verity_table_.size());
        std::vector<uint8_t> padding(
            VERITY_META_SIZE - sizeof(verity_header_) - verity_table_.size(),
            0);
        image_.insert(image_.end(), padding.begin(), padding.end());
    }

    static void BuildAndAppendsEccImage(const std::string &image_name,
                                        const std::string &fec_name) {
        std::vector<std::string> cmd = { "fec", "--encode", "--roots",
                                         "2",   image_name, fec_name };
        ASSERT_EQ(0, std::system(android::base::Join(cmd, ' ').c_str()));
    }

    void AddAvbHashtreeFooter(const std::string &image_name,
                              std::string algorithm = "sha256") {
        salt_ = std::vector<uint8_t>(64, 10);
        std::vector<std::string> cmd = {
            "avbtool",          "add_hashtree_footer",
            "--salt",           HashTreeBuilder::BytesArrayToString(salt_),
            "--hash_algorithm", algorithm,
            "--image",          image_name,
        };
        ASSERT_EQ(0, std::system(android::base::Join(cmd, ' ').c_str()));

        BuildHashtree(algorithm);
    }

    std::vector<uint8_t> image_;
    std::vector<uint8_t> salt_;
    std::vector<uint8_t> root_hash_;
    std::string hashtree_content_;
    verity_header verity_header_;
    std::string verity_table_;
};

TEST_F(FecUnitTest, LoadVerityImage_ParseVerity) {
    TemporaryFile verity_image;
    BuildAndAppendsVerityMetadata();
    ASSERT_TRUE(android::base::WriteFully(verity_image.fd, image_.data(),
                                          image_.size()));

    struct fec_handle *handle = nullptr;
    ASSERT_EQ(0, fec_open(&handle, verity_image.path, O_RDONLY, FEC_FS_EXT4, 2));
    std::unique_ptr<fec_handle> guard(handle);

    ASSERT_EQ(image_.size(), handle->size);
    ASSERT_EQ(1024 * 1024, handle->data_size);  // filesystem size

    ASSERT_EQ(1024 * 1024 + hashtree_content_.size(),
              handle->verity.metadata_start);
    ASSERT_EQ(verity_header_.length, handle->verity.header.length);
    ASSERT_EQ(verity_table_, handle->verity.table);

    // check the hashtree.
    ASSERT_EQ(salt_, handle->hashtree().salt);
    ASSERT_EQ(1024 * 1024, handle->hashtree().hash_start);
    // the fec hashtree only stores the hash of the lowest level.
    ASSERT_EQ(std::vector<uint8_t>(hashtree_content_.begin() + 4096,
                                   hashtree_content_.end()),
              handle->hashtree().hash_data);

    uint64_t hash_size =
        verity_get_size(handle->hashtree().data_blocks * FEC_BLOCKSIZE, nullptr,
                        nullptr, SHA256_DIGEST_LENGTH);
    ASSERT_EQ(hashtree_content_.size(), hash_size);
}

TEST_F(FecUnitTest, LoadVerityImage_ParseEcc) {
    TemporaryFile verity_image;
    BuildAndAppendsVerityMetadata();
    ASSERT_TRUE(android::base::WriteFully(verity_image.fd, image_.data(),
                                          image_.size()));
    TemporaryFile ecc_image;
    BuildAndAppendsEccImage(verity_image.path, ecc_image.path);
    std::string ecc_content;
    ASSERT_TRUE(android::base::ReadFileToString(ecc_image.path, &ecc_content));
    ASSERT_TRUE(android::base::WriteStringToFd(ecc_content, verity_image.fd));
    struct fec_handle *handle = nullptr;
    ASSERT_EQ(0, fec_open(&handle, verity_image.path, O_RDONLY, FEC_FS_EXT4, 2));
    std::unique_ptr<fec_handle> guard(handle);

    ASSERT_EQ(1024 * 1024, handle->data_size);  // filesystem size
    ASSERT_EQ(1024 * 1024 + hashtree_content_.size(),
              handle->verity.metadata_start);

    fec_verity_metadata verity_metadata{};
    ASSERT_EQ(0, fec_verity_get_metadata(handle, &verity_metadata));
    ASSERT_FALSE(verity_metadata.disabled);
    ASSERT_EQ(1024 * 1024, verity_metadata.data_size);
    ASSERT_EQ(verity_table_, verity_metadata.table);

    fec_ecc_metadata ecc_metadata{};
    ASSERT_EQ(0, fec_ecc_get_metadata(handle, &ecc_metadata));
    ASSERT_TRUE(ecc_metadata.valid);
    ASSERT_EQ(handle->verity.metadata_start + 8 * 4096, ecc_metadata.start);
    ASSERT_EQ(2, ecc_metadata.roots);
    // 256 (data) + 3 (hashtree) + 8 (verity meta)
    ASSERT_EQ(267, ecc_metadata.blocks);
}

TEST_F(FecUnitTest, VerityImage_FecRead) {
    TemporaryFile verity_image;
    BuildAndAppendsVerityMetadata();
    ASSERT_TRUE(android::base::WriteFully(verity_image.fd, image_.data(),
                                          image_.size()));
    TemporaryFile ecc_image;
    BuildAndAppendsEccImage(verity_image.path, ecc_image.path);
    std::string ecc_content;
    ASSERT_TRUE(android::base::ReadFileToString(ecc_image.path, &ecc_content));
    ASSERT_TRUE(android::base::WriteStringToFd(ecc_content, verity_image.fd));

    // Corrupt the last block
    uint64_t corrupt_offset = 4096 * 255;
    ASSERT_EQ(corrupt_offset, lseek64(verity_image.fd, corrupt_offset, 0));
    std::vector<uint8_t> corruption(100, 10);
    ASSERT_TRUE(android::base::WriteFully(verity_image.fd, corruption.data(),
                                          corruption.size()));

    std::vector<uint8_t> read_data(1024, 0);
    struct fec_handle *handle = nullptr;
    ASSERT_EQ(0,
              fec_open(&handle, verity_image.path, O_RDONLY, FEC_FS_EXT4, 2));
    std::unique_ptr<fec_handle> guard(handle);

    ASSERT_EQ(1024, fec_pread(handle, read_data.data(), 1024, corrupt_offset));
    ASSERT_EQ(std::vector<uint8_t>(1024, 255), read_data);

    // Unaligned read that spans two blocks
    ASSERT_EQ(678, fec_pread(handle, read_data.data(), 678, corrupt_offset - 123));
    ASSERT_EQ(std::vector<uint8_t>(123, 254),
              std::vector<uint8_t>(read_data.begin(), read_data.begin() + 123));
    ASSERT_EQ(std::vector<uint8_t>(555, 255),
              std::vector<uint8_t>(read_data.begin() + 123, read_data.begin() + 678));

    std::vector<uint8_t> large_data(53388, 0);
    ASSERT_EQ(53388, fec_pread(handle, large_data.data(), 53388, 385132));
}

TEST_F(FecUnitTest, LoadAvbImage_HashtreeFooter) {
    TemporaryFile avb_image;
    ASSERT_TRUE(
        android::base::WriteFully(avb_image.fd, image_.data(), image_.size()));
    AddAvbHashtreeFooter(avb_image.path);

    struct fec_handle *handle = nullptr;
    ASSERT_EQ(0, fec_open(&handle, avb_image.path, O_RDWR, FEC_FS_EXT4, 2));
    std::unique_ptr<fec_handle> guard(handle);

    ASSERT_EQ(1024 * 1024, handle->data_size);  // filesystem size

    ASSERT_TRUE(handle->avb.valid);

    // check the hashtree.
    ASSERT_EQ(salt_, handle->hashtree().salt);
    ASSERT_EQ(1024 * 1024, handle->hashtree().hash_start);
    // the fec hashtree only stores the hash of the lowest level.
    ASSERT_EQ(std::vector<uint8_t>(hashtree_content_.begin() + 4096,
                                   hashtree_content_.end()),
              handle->hashtree().hash_data);
    uint64_t hash_size =
        verity_get_size(handle->hashtree().data_blocks * FEC_BLOCKSIZE, nullptr,
                        nullptr, SHA256_DIGEST_LENGTH);
    ASSERT_EQ(hashtree_content_.size(), hash_size);

    fec_ecc_metadata ecc_metadata{};
    ASSERT_EQ(0, fec_ecc_get_metadata(handle, &ecc_metadata));
    ASSERT_TRUE(ecc_metadata.valid);
    ASSERT_EQ(1024 * 1024 + hash_size, ecc_metadata.start);
    ASSERT_EQ(259, ecc_metadata.blocks);
}

TEST_F(FecUnitTest, LoadAvbImage_CorrectHashtree) {
    TemporaryFile avb_image;
    ASSERT_TRUE(
        android::base::WriteFully(avb_image.fd, image_.data(), image_.size()));
    AddAvbHashtreeFooter(avb_image.path);

    uint64_t corrupt_offset = 1024 * 1024 + 2 * 4096 + 50;
    ASSERT_EQ(corrupt_offset, lseek64(avb_image.fd, corrupt_offset, 0));
    std::vector<uint8_t> corruption(20, 5);
    ASSERT_TRUE(android::base::WriteFully(avb_image.fd, corruption.data(),
                                          corruption.size()));

    struct fec_handle *handle = nullptr;
    ASSERT_EQ(0, fec_open(&handle, avb_image.path, O_RDWR, FEC_FS_EXT4, 2));
    std::unique_ptr<fec_handle> guard(handle);

    ASSERT_EQ(1024 * 1024, handle->data_size);  // filesystem size
    fec_ecc_metadata ecc_metadata{};
    ASSERT_EQ(0, fec_ecc_get_metadata(handle, &ecc_metadata));
    ASSERT_TRUE(ecc_metadata.valid);
}

TEST_F(FecUnitTest, AvbImage_FecRead) {
    TemporaryFile avb_image;
    ASSERT_TRUE(
        android::base::WriteFully(avb_image.fd, image_.data(), image_.size()));
    AddAvbHashtreeFooter(avb_image.path, "sha1");

    uint64_t corrupt_offset = 4096 * 10;
    ASSERT_EQ(corrupt_offset, lseek64(avb_image.fd, corrupt_offset, 0));
    std::vector<uint8_t> corruption(50, 99);
    ASSERT_TRUE(android::base::WriteFully(avb_image.fd, corruption.data(),
                                          corruption.size()));

    std::vector<uint8_t> read_data(1024, 0);
    struct fec_handle *handle = nullptr;
    ASSERT_EQ(0, fec_open(&handle, avb_image.path, O_RDWR, FEC_FS_EXT4, 2));
    std::unique_ptr<fec_handle> guard(handle);

    // Verify the hashtree has the expected content.
    ASSERT_EQ(std::vector<uint8_t>(hashtree_content_.begin() + 4096,
                                   hashtree_content_.end()),
              handle->hashtree().hash_data);

    // Verify the corruption gets corrected.
    ASSERT_EQ(1024, fec_pread(handle, read_data.data(), 1024, corrupt_offset));
    ASSERT_EQ(std::vector<uint8_t>(1024, 10), read_data);
}
