/*
 * Copyright (C) 2016 The Android Open Source Project
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy,
 * modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#ifndef AVB_UNITTEST_UTIL_H_
#define AVB_UNITTEST_UTIL_H_

#include <inttypes.h>

#include <gtest/gtest.h>

#include <base/files/file_util.h>
#include <base/strings/stringprintf.h>

// Encodes |len| bytes of |data| as a lower-case hex-string.
std::string mem_to_hexstring(const uint8_t* data, size_t len);

// Trims whitespace from start and end of |str|.
std::string string_trim(const std::string& str);

/* Utility macro to run the command expressed by the printf()-style string
 * |command_format| using the system(3) utility function. Will assert unless
 * the command exits normally with exit status |expected_exit_status|.
 */
#define EXPECT_COMMAND(expected_exit_status, command_format, ...)          \
  do {                                                                     \
    int rc =                                                               \
        system(base::StringPrintf(command_format, ##__VA_ARGS__).c_str()); \
    EXPECT_TRUE(WIFEXITED(rc));                                            \
    EXPECT_EQ(WEXITSTATUS(rc), expected_exit_status);                      \
  } while (0);

namespace avb {

// These two functions are in avb_sysdeps_posix_testing.cc and is
// used for finding memory leaks.
void testing_memory_reset();
size_t testing_memory_all_freed();

/* Base-class used for unit test. */
class BaseAvbToolTest : public ::testing::Test {
 public:
  BaseAvbToolTest() {}

 protected:
  virtual ~BaseAvbToolTest() {}

  /* Calculates the vbmeta digest using 'avbtool calc_vbmeta_digest' command. */
  std::string CalcVBMetaDigest(const std::string& vbmeta_image,
                               const std::string& digest_alg);

  /* Generates a vbmeta image, using avbtoool, with file name
   * |image_name|. The generated vbmeta image will written to disk,
   * see the |vbmeta_image_path_| variable for its path and
   * |vbmeta_image_| for the content.
   */
  void GenerateVBMetaImage(const std::string& image_name,
                           const std::string& algorithm,
                           uint64_t rollback_index,
                           const base::FilePath& key_path,
                           const std::string& additional_options = "");

  /* Generate a file with name |file_name| of size |image_size| with
   * known content (0x00 0x01 0x02 .. 0xff 0x00 0x01 ..).
   */
  base::FilePath GenerateImage(const std::string file_name,
                               size_t image_size,
                               uint8_t start_byte = 0);

  /* Returns the output of 'avbtool info_image' for a given image. */
  std::string InfoImage(const base::FilePath& image_path);

  /* Returns public key in AVB format for a .pem key */
  std::string PublicKeyAVB(const base::FilePath& key_path);

  void SetUp() override;
  void TearDown() override;

  /* Temporary directory created in SetUp(). */
  base::FilePath testdir_;

  /* Path to vbmeta image generated with GenerateVBMetaImage(). */
  base::FilePath vbmeta_image_path_;

  /* Contents of the image generated with GenerateVBMetaImage(). */
  std::vector<uint8_t> vbmeta_image_;
};

}  // namespace avb

#endif /* AVB_UNITTEST_UTIL_H_ */
