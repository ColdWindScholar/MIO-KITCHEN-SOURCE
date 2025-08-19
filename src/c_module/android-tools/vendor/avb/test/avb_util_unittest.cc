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

#include <endian.h>
#include <string.h>

#include <gtest/gtest.h>

#include <libavb/libavb.h>

#include "avb_unittest_util.h"

namespace avb {

// Subclass BaseAvbToolTest to check for memory leaks.
class UtilTest : public BaseAvbToolTest {
 public:
  UtilTest() {}
};

TEST_F(UtilTest, RSAPublicKeyHeaderByteswap) {
  AvbRSAPublicKeyHeader h;
  AvbRSAPublicKeyHeader s;
  uint32_t n32;
  uint64_t n64;

  n32 = 0x11223344;
  n64 = 0x1122334455667788;

  h.key_num_bits = htobe32(n32);
  n32++;
  h.n0inv = htobe32(n32);
  n32++;

  EXPECT_NE(0, avb_rsa_public_key_header_validate_and_byteswap(&h, &s));

  n32 = 0x11223344;
  n64 = 0x1122334455667788;

  EXPECT_EQ(n32, s.key_num_bits);
  n32++;
  EXPECT_EQ(n32, s.n0inv);
  n32++;
}

TEST_F(UtilTest, FooterByteswap) {
  AvbFooter h;
  AvbFooter s;
  AvbFooter other;
  AvbFooter bad;
  uint64_t n64;

  n64 = 0x1122334455667788;

  memcpy(h.magic, AVB_FOOTER_MAGIC, AVB_FOOTER_MAGIC_LEN);
  h.version_major = htobe32(AVB_FOOTER_VERSION_MAJOR);
  h.version_minor = htobe32(AVB_FOOTER_VERSION_MINOR);
  h.original_image_size = htobe64(n64);
  n64++;
  h.vbmeta_offset = htobe64(n64);
  n64++;
  h.vbmeta_size = htobe64(n64);
  n64++;

  EXPECT_NE(0, avb_footer_validate_and_byteswap(&h, &s));

  n64 = 0x1122334455667788;

  EXPECT_EQ((uint32_t)AVB_FOOTER_VERSION_MAJOR, s.version_major);
  EXPECT_EQ((uint32_t)AVB_FOOTER_VERSION_MINOR, s.version_minor);
  EXPECT_EQ(n64, s.original_image_size);
  n64++;
  EXPECT_EQ(n64, s.vbmeta_offset);
  n64++;
  EXPECT_EQ(n64, s.vbmeta_size);
  n64++;

  // Check that the struct still validates if minor is bigger than
  // what we expect.
  other = h;
  h.version_minor = htobe32(AVB_FOOTER_VERSION_MINOR + 1);
  EXPECT_NE(0, avb_footer_validate_and_byteswap(&other, &s));

  // Check for bad magic.
  bad = h;
  bad.magic[0] = 'x';
  EXPECT_EQ(0, avb_footer_validate_and_byteswap(&bad, &s));

  // Check for bad major version.
  bad = h;
  bad.version_major = htobe32(AVB_FOOTER_VERSION_MAJOR + 1);
  EXPECT_EQ(0, avb_footer_validate_and_byteswap(&bad, &s));
}

TEST_F(UtilTest, KernelCmdlineDescriptorByteswap) {
  AvbKernelCmdlineDescriptor h;
  AvbKernelCmdlineDescriptor s;
  AvbKernelCmdlineDescriptor bad;
  uint64_t nbf;
  uint32_t n32;

  // Specify 40 bytes of data past the end of the descriptor struct.
  nbf = 40 + sizeof(AvbKernelCmdlineDescriptor) - sizeof(AvbDescriptor);
  h.parent_descriptor.num_bytes_following = htobe64(nbf);
  h.parent_descriptor.tag = htobe64(AVB_DESCRIPTOR_TAG_KERNEL_CMDLINE);
  h.kernel_cmdline_length = htobe32(40);

  n32 = 0x11223344;
  h.flags = htobe32(n32);
  n32++;

  EXPECT_NE(0, avb_kernel_cmdline_descriptor_validate_and_byteswap(&h, &s));

  n32 = 0x11223344;
  EXPECT_EQ(n32, s.flags);
  n32++;

  EXPECT_EQ(AVB_DESCRIPTOR_TAG_KERNEL_CMDLINE, s.parent_descriptor.tag);
  EXPECT_EQ(nbf, s.parent_descriptor.num_bytes_following);
  EXPECT_EQ(40UL, s.kernel_cmdline_length);

  // Check for bad tag.
  bad = h;
  bad.parent_descriptor.tag = htobe64(0xf00dd00d);
  EXPECT_EQ(0, avb_kernel_cmdline_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 41 bytes.
  bad = h;
  bad.kernel_cmdline_length = htobe32(41);
  EXPECT_EQ(0, avb_kernel_cmdline_descriptor_validate_and_byteswap(&bad, &s));
}

TEST_F(UtilTest, HashtreeDescriptorByteswap) {
  AvbHashtreeDescriptor h;
  AvbHashtreeDescriptor s;
  AvbHashtreeDescriptor bad;
  uint64_t nbf;
  uint32_t n32;
  uint64_t n64;

  // Specify 44 bytes of data past the end of the descriptor struct.
  nbf = 44 + sizeof(AvbHashtreeDescriptor) - sizeof(AvbDescriptor);
  h.parent_descriptor.num_bytes_following = htobe64(nbf);
  h.parent_descriptor.tag = htobe64(AVB_DESCRIPTOR_TAG_HASHTREE);
  h.partition_name_len = htobe32(10);
  h.salt_len = htobe32(10);
  h.root_digest_len = htobe32(10);

  n32 = 0x11223344;
  n64 = 0x1122334455667788;

  h.dm_verity_version = htobe32(n32);
  n32++;
  h.image_size = htobe64(n64);
  n64++;
  h.tree_offset = htobe64(n64);
  n64++;
  h.tree_size = htobe64(n64);
  n64++;
  h.data_block_size = htobe32(n32);
  n32++;
  h.hash_block_size = htobe32(n32);
  n32++;
  h.fec_num_roots = htobe32(n32);
  n32++;
  h.fec_offset = htobe64(n64);
  n64++;
  h.fec_size = htobe64(n64);
  n64++;

  EXPECT_TRUE(avb_hashtree_descriptor_validate_and_byteswap(&h, &s));

  n32 = 0x11223344;
  n64 = 0x1122334455667788;

  EXPECT_EQ(n32, s.dm_verity_version);
  n32++;
  EXPECT_EQ(n64, s.image_size);
  n64++;
  EXPECT_EQ(n64, s.tree_offset);
  n64++;
  EXPECT_EQ(n64, s.tree_size);
  n64++;
  EXPECT_EQ(n32, s.data_block_size);
  n32++;
  EXPECT_EQ(n32, s.hash_block_size);
  n32++;
  EXPECT_EQ(n32, s.fec_num_roots);
  n32++;
  EXPECT_EQ(n64, s.fec_offset);
  n64++;
  EXPECT_EQ(n64, s.fec_size);
  n64++;

  EXPECT_EQ(AVB_DESCRIPTOR_TAG_HASHTREE, s.parent_descriptor.tag);
  EXPECT_EQ(nbf, s.parent_descriptor.num_bytes_following);
  EXPECT_EQ(10UL, s.partition_name_len);
  EXPECT_EQ(10UL, s.salt_len);
  EXPECT_EQ(10UL, s.root_digest_len);

  // Check for bad tag.
  bad = h;
  bad.parent_descriptor.tag = htobe64(0xf00dd00d);
  EXPECT_FALSE(avb_hashtree_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 44 bytes (30 + 10 + 10 = 50).
  bad = h;
  bad.partition_name_len = htobe32(30);
  EXPECT_FALSE(avb_hashtree_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 44 bytes (10 + 30 + 10 = 50).
  bad = h;
  bad.salt_len = htobe32(30);
  EXPECT_FALSE(avb_hashtree_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 44 bytes (10 + 10 + 30 = 50).
  bad = h;
  bad.root_digest_len = htobe32(30);
  EXPECT_FALSE(avb_hashtree_descriptor_validate_and_byteswap(&bad, &s));
}

TEST_F(UtilTest, HashDescriptorByteswap) {
  AvbHashDescriptor h;
  AvbHashDescriptor s;
  AvbHashDescriptor bad;
  uint64_t nbf;

  // Specify 44 bytes of data past the end of the descriptor struct.
  nbf = 44 + sizeof(AvbHashDescriptor) - sizeof(AvbDescriptor);
  h.parent_descriptor.num_bytes_following = htobe64(nbf);
  h.parent_descriptor.tag = htobe64(AVB_DESCRIPTOR_TAG_HASH);
  h.partition_name_len = htobe32(10);
  h.salt_len = htobe32(10);
  h.digest_len = htobe32(10);

  EXPECT_NE(0, avb_hash_descriptor_validate_and_byteswap(&h, &s));

  EXPECT_EQ(AVB_DESCRIPTOR_TAG_HASH, s.parent_descriptor.tag);
  EXPECT_EQ(nbf, s.parent_descriptor.num_bytes_following);
  EXPECT_EQ(10UL, s.partition_name_len);
  EXPECT_EQ(10UL, s.salt_len);
  EXPECT_EQ(10UL, s.digest_len);

  // Check for bad tag.
  bad = h;
  bad.parent_descriptor.tag = htobe64(0xf00dd00d);
  EXPECT_EQ(0, avb_hash_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 44 bytes (30 + 10 + 10 = 50).
  bad = h;
  bad.partition_name_len = htobe32(30);
  EXPECT_EQ(0, avb_hash_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 44 bytes (10 + 30 + 10 = 50).
  bad = h;
  bad.salt_len = htobe32(30);
  EXPECT_EQ(0, avb_hash_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 44 bytes (10 + 10 + 30 = 50).
  bad = h;
  bad.digest_len = htobe32(30);
  EXPECT_EQ(0, avb_hash_descriptor_validate_and_byteswap(&bad, &s));
}

TEST_F(UtilTest, ChainPartitionDescriptorByteswap) {
  AvbChainPartitionDescriptor h;
  AvbChainPartitionDescriptor s;
  AvbChainPartitionDescriptor bad;
  uint64_t nbf;

  // Specify 36 bytes of data past the end of the descriptor struct.
  nbf = 36 + sizeof(AvbChainPartitionDescriptor) - sizeof(AvbDescriptor);
  h.parent_descriptor.num_bytes_following = htobe64(nbf);
  h.parent_descriptor.tag = htobe64(AVB_DESCRIPTOR_TAG_CHAIN_PARTITION);
  h.rollback_index_location = htobe32(42);
  h.partition_name_len = htobe32(16);
  h.public_key_len = htobe32(17);

  EXPECT_NE(0, avb_chain_partition_descriptor_validate_and_byteswap(&h, &s));

  EXPECT_EQ(AVB_DESCRIPTOR_TAG_CHAIN_PARTITION, s.parent_descriptor.tag);
  EXPECT_EQ(nbf, s.parent_descriptor.num_bytes_following);
  EXPECT_EQ(42UL, s.rollback_index_location);
  EXPECT_EQ(16UL, s.partition_name_len);
  EXPECT_EQ(17UL, s.public_key_len);

  // Check for bad tag.
  bad = h;
  bad.parent_descriptor.tag = htobe64(0xf00dd00d);
  EXPECT_EQ(0, avb_chain_partition_descriptor_validate_and_byteswap(&bad, &s));

  // Check for bad rollback index slot (must be at least 1).
  bad = h;
  bad.rollback_index_location = htobe32(0);
  EXPECT_EQ(0, avb_chain_partition_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 40 bytes (24 + 17 = 41).
  bad = h;
  bad.partition_name_len = htobe32(24);
  EXPECT_EQ(0, avb_chain_partition_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 40 bytes (16 + 25 = 41).
  bad = h;
  bad.public_key_len = htobe32(25);
  EXPECT_EQ(0, avb_chain_partition_descriptor_validate_and_byteswap(&bad, &s));
}

TEST_F(UtilTest, PropertyDescriptorByteswap) {
  AvbPropertyDescriptor h;
  AvbPropertyDescriptor s;
  AvbPropertyDescriptor bad;
  uint64_t nbf;

  // Specify 40 bytes of data past the end of the descriptor struct.
  nbf = 40 + sizeof(AvbPropertyDescriptor) - sizeof(AvbDescriptor);
  h.parent_descriptor.num_bytes_following = htobe64(nbf);
  h.parent_descriptor.tag = htobe64(AVB_DESCRIPTOR_TAG_PROPERTY);
  h.key_num_bytes = htobe64(16);
  h.value_num_bytes = htobe64(17);

  EXPECT_NE(0, avb_property_descriptor_validate_and_byteswap(&h, &s));

  EXPECT_EQ(AVB_DESCRIPTOR_TAG_PROPERTY, s.parent_descriptor.tag);
  EXPECT_EQ(nbf, s.parent_descriptor.num_bytes_following);
  EXPECT_EQ(16UL, s.key_num_bytes);
  EXPECT_EQ(17UL, s.value_num_bytes);

  // Check for bad tag.
  bad = h;
  bad.parent_descriptor.tag = htobe64(0xf00dd00d);
  EXPECT_EQ(0, avb_property_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 40 bytes (22 + 17 + 2 = 41).
  bad = h;
  bad.key_num_bytes = htobe64(22);
  EXPECT_EQ(0, avb_property_descriptor_validate_and_byteswap(&bad, &s));

  // Doesn't fit in 40 bytes (16 + 23 + 2 = 41).
  bad = h;
  bad.value_num_bytes = htobe64(23);
  EXPECT_EQ(0, avb_property_descriptor_validate_and_byteswap(&bad, &s));
}

TEST_F(UtilTest, DescriptorByteswap) {
  AvbDescriptor h;
  AvbDescriptor s;
  uint64_t n64;

  n64 = 0x1122334455667788;

  h.num_bytes_following = htobe64(n64);
  n64++;
  h.tag = htobe64(n64);
  n64++;

  EXPECT_NE(0, avb_descriptor_validate_and_byteswap(&h, &s));

  n64 = 0x1122334455667788;

  EXPECT_EQ(n64, s.num_bytes_following);
  n64++;
  EXPECT_EQ(n64, s.tag);
  n64++;

  // Check that we catch if |num_bytes_following| isn't divisble by 8.
  h.num_bytes_following = htobe64(7);
  EXPECT_EQ(0, avb_descriptor_validate_and_byteswap(&h, &s));
}

TEST_F(UtilTest, SafeAddition) {
  uint64_t value;
  uint64_t pow2_60 = 1ULL << 60;

  value = 2;
  EXPECT_NE(0, avb_safe_add_to(&value, 5));
  EXPECT_EQ(7UL, value);

  /* These should not overflow */
  value = 1 * pow2_60;
  EXPECT_NE(0, avb_safe_add_to(&value, 2 * pow2_60));
  EXPECT_EQ(3 * pow2_60, value);
  value = 7 * pow2_60;
  EXPECT_NE(0, avb_safe_add_to(&value, 8 * pow2_60));
  EXPECT_EQ(15 * pow2_60, value);
  value = 9 * pow2_60;
  EXPECT_NE(0, avb_safe_add_to(&value, 3 * pow2_60));
  EXPECT_EQ(12 * pow2_60, value);
  value = 0xfffffffffffffffcUL;
  EXPECT_NE(0, avb_safe_add_to(&value, 2));
  EXPECT_EQ(0xfffffffffffffffeUL, value);

  /* These should overflow. */
  value = 8 * pow2_60;
  EXPECT_EQ(0, avb_safe_add_to(&value, 8 * pow2_60));
  value = 0xfffffffffffffffcUL;
  EXPECT_EQ(0, avb_safe_add_to(&value, 4));
}

static int avb_validate_utf8z(const char* data) {
  return avb_validate_utf8(reinterpret_cast<const uint8_t*>(data),
                           strlen(data));
}

TEST_F(UtilTest, UTF8Validation) {
  // These should succeed.
  EXPECT_NE(0, avb_validate_utf8z("foo bar"));
  // Encoding of U+00E6 LATIN SMALL LETTER AE: æ
  EXPECT_NE(0, avb_validate_utf8z("foo \xC3\xA6 bar"));
  // Encoding of U+20AC EURO SIGN: €
  EXPECT_NE(0, avb_validate_utf8z("foo \xE2\x82\xAC bar"));
  // Encoding of U+1F466 BOY: 👦
  EXPECT_NE(0, avb_validate_utf8z("foo \xF0\x9F\x91\xA6 bar"));
  // All three runes following each other.
  EXPECT_NE(0, avb_validate_utf8z("\xC3\xA6\xE2\x82\xAC\xF0\x9F\x91\xA6"));

  // These should fail.
  EXPECT_EQ(0, avb_validate_utf8z("foo \xF8 bar"));
  EXPECT_EQ(0, avb_validate_utf8z("\xF8"));
  // Stops in the middle of Unicode rune.
  EXPECT_EQ(0, avb_validate_utf8z("foo \xC3"));
}

TEST_F(UtilTest, StrConcat) {
  char buf[8];

  // These should succeed.
  EXPECT_NE(0, avb_str_concat(buf, sizeof buf, "foo", 3, "bar1", 4));

  // This should fail: Insufficient space.
  EXPECT_EQ(0, avb_str_concat(buf, sizeof buf, "foo0", 4, "bar1", 4));
}

TEST_F(UtilTest, StrStr) {
  const char* haystack = "abc def abcabc";

  EXPECT_EQ(nullptr, avb_strstr(haystack, "needle"));
  EXPECT_EQ(haystack, avb_strstr(haystack, "abc"));
  EXPECT_EQ(haystack + 4, avb_strstr(haystack, "def"));
  EXPECT_EQ(haystack, avb_strstr(haystack, haystack));
}

TEST_F(UtilTest, StrvFindStr) {
  const char* strings[] = {"abcabc", "abc", "def", nullptr};

  EXPECT_EQ(nullptr, avb_strv_find_str(strings, "not there", 9));
  EXPECT_EQ(strings[1], avb_strv_find_str(strings, "abc", 3));
  EXPECT_EQ(strings[2], avb_strv_find_str(strings, "def", 3));
  EXPECT_EQ(strings[0], avb_strv_find_str(strings, "abcabc", 6));
}

TEST_F(UtilTest, StrReplace) {
  char* str;

  str = avb_replace("$(FOO) blah bah $(FOO $(FOO) blah", "$(FOO)", "OK");
  EXPECT_EQ("OK blah bah $(FOO OK blah", std::string(str));
  avb_free(str);

  str = avb_replace("$(FOO)", "$(FOO)", "OK");
  EXPECT_EQ("OK", std::string(str));
  avb_free(str);

  str = avb_replace(" $(FOO)", "$(FOO)", "OK");
  EXPECT_EQ(" OK", std::string(str));
  avb_free(str);

  str = avb_replace("$(FOO) ", "$(FOO)", "OK");
  EXPECT_EQ("OK ", std::string(str));
  avb_free(str);

  str = avb_replace("$(FOO)$(FOO)", "$(FOO)", "LONGSTRING");
  EXPECT_EQ("LONGSTRINGLONGSTRING", std::string(str));
  avb_free(str);
}

TEST_F(UtilTest, StrDupV) {
  char* str;

  str = avb_strdupv("x", "y", "z", NULL);
  EXPECT_EQ("xyz", std::string(str));
  avb_free(str);

  str = avb_strdupv("Hello", "World", " XYZ", NULL);
  EXPECT_EQ("HelloWorld XYZ", std::string(str));
  avb_free(str);
}

TEST_F(UtilTest, Crc32) {
  /* Compare with output of crc32(1):
   *
   *  $ (echo -n foobar > /tmp/crc32_input); crc32 /tmp/crc32_input
   *  9ef61f95
   */
  EXPECT_EQ(uint32_t(0x9ef61f95), avb_crc32((const uint8_t*)"foobar", 6));
}

TEST_F(UtilTest, htobe32) {
  EXPECT_EQ(avb_htobe32(0x12345678), htobe32(0x12345678));
}

TEST_F(UtilTest, be32toh) {
  EXPECT_EQ(avb_be32toh(0x12345678), be32toh(0x12345678));
}

TEST_F(UtilTest, htobe64) {
  EXPECT_EQ(avb_htobe64(0x123456789abcdef0), htobe64(0x123456789abcdef0));
}

TEST_F(UtilTest, be64toh) {
  EXPECT_EQ(avb_be64toh(0x123456789abcdef0), be64toh(0x123456789abcdef0));
}

TEST_F(UtilTest, Basename) {
  EXPECT_EQ("foobar.c", std::string(avb_basename("foobar.c")));
  EXPECT_EQ("foobar.c", std::string(avb_basename("/path/to/foobar.c")));
  EXPECT_EQ("foobar.c", std::string(avb_basename("a/foobar.c")));
  EXPECT_EQ("baz.c", std::string(avb_basename("/baz.c")));
  EXPECT_EQ("some_dir/", std::string(avb_basename("some_dir/")));
  EXPECT_EQ("some_dir/", std::string(avb_basename("/path/to/some_dir/")));
  EXPECT_EQ("some_dir/", std::string(avb_basename("a/some_dir/")));
  EXPECT_EQ("some_dir/", std::string(avb_basename("/some_dir/")));
  EXPECT_EQ("/", std::string(avb_basename("/")));
}

}  // namespace avb
