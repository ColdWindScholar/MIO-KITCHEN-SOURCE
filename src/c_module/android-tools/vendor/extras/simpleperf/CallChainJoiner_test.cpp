/*
 * Copyright (C) 2017 The Android Open Source Project
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

#include "CallChainJoiner.h"

#include <gtest/gtest.h>

#include <environment.h>

using namespace simpleperf;
using namespace simpleperf::call_chain_joiner_impl;

static bool JoinCallChain(LRUCache& cache, uint32_t tid, const std::vector<uint64_t>& input_ip,
                          const std::vector<uint64_t>& input_sp,
                          const std::vector<uint64_t>& expected_output_ip,
                          const std::vector<uint64_t>& expected_output_sp) {
  std::vector<uint64_t> tmp_ip = input_ip;
  std::vector<uint64_t> tmp_sp = input_sp;
  cache.AddCallChain(tid, tmp_ip, tmp_sp);
  return tmp_ip == expected_output_ip && tmp_sp == expected_output_sp;
}

// @CddTest = 6.1/C-0-2
TEST(LRUCache, different_nodes) {
  LRUCache cache(sizeof(CacheNode) * 2, 1);
  ASSERT_EQ(cache.Stat().max_node_count, 2u);
  // different tids
  std::vector<uint64_t> ip = {0x1};
  std::vector<uint64_t> sp = {0x1};
  ASSERT_TRUE(JoinCallChain(cache, 0, ip, sp, ip, sp));
  ASSERT_TRUE(JoinCallChain(cache, 1, ip, sp, ip, sp));
  ASSERT_EQ(cache.Stat().used_node_count, 2u);
  ASSERT_EQ(cache.Stat().recycled_node_count, 0u);
  ASSERT_NE(cache.FindNode(0, ip[0], sp[0]), nullptr);
  ASSERT_NE(cache.FindNode(1, ip[0], sp[0]), nullptr);

  // different ips
  std::vector<uint64_t> ip2 = {0x2};
  ASSERT_TRUE(JoinCallChain(cache, 0, ip2, sp, ip2, sp));
  ASSERT_EQ(cache.Stat().used_node_count, 2u);
  ASSERT_EQ(cache.Stat().recycled_node_count, 1u);
  ASSERT_EQ(cache.FindNode(0, ip[0], sp[0]), nullptr);
  ASSERT_NE(cache.FindNode(0, ip2[0], sp[0]), nullptr);
  ASSERT_NE(cache.FindNode(1, ip[0], sp[0]), nullptr);

  // different sps
  std::vector<uint64_t> sp2 = {0x2};
  ASSERT_TRUE(JoinCallChain(cache, 1, ip, sp2, ip, sp2));
  ASSERT_EQ(cache.Stat().used_node_count, 2u);
  ASSERT_EQ(cache.Stat().recycled_node_count, 2u);
  ASSERT_EQ(cache.FindNode(1, ip[0], sp[0]), nullptr);
  ASSERT_NE(cache.FindNode(0, ip2[0], sp[0]), nullptr);
  ASSERT_NE(cache.FindNode(1, ip[0], sp2[0]), nullptr);
}

// @CddTest = 6.1/C-0-2
TEST(LRUCache, extend_chains) {
  // matched_node_count_to_extend_callchain = 1
  // c -> b
  // b -> a  =>  c -> b -> a
  LRUCache cache1(sizeof(CacheNode) * 4, 1);
  ASSERT_TRUE(JoinCallChain(cache1, 0, {0xb, 0xc}, {0xb, 0xc}, {0xb, 0xc}, {0xb, 0xc}));
  ASSERT_TRUE(JoinCallChain(cache1, 0, {0xa, 0xb}, {0xa, 0xb}, {0xa, 0xb, 0xc}, {0xa, 0xb, 0xc}));
  ASSERT_EQ(cache1.Stat().used_node_count, 3u);

  // matched_node_count_to_extend_callchain = 2
  // c -> b
  // b -> a
  LRUCache cache2(sizeof(CacheNode) * 4, 2);
  ASSERT_TRUE(JoinCallChain(cache2, 0, {0xb, 0xc}, {0xb, 0xc}, {0xb, 0xc}, {0xb, 0xc}));
  ASSERT_TRUE(JoinCallChain(cache2, 0, {0xa, 0xb}, {0xa, 0xb}, {0xa, 0xb}, {0xa, 0xb}));
  ASSERT_EQ(cache2.Stat().used_node_count, 3u);

  // matched_node_count_to_extend_callchain = 2
  // d -> c -> b
  // c -> b -> a  =>  d -> c -> b -> a
  LRUCache cache3(sizeof(CacheNode) * 4, 2);
  ASSERT_TRUE(
      JoinCallChain(cache3, 0, {0xb, 0xc, 0xd}, {0xb, 0xc, 0xd}, {0xb, 0xc, 0xd}, {0xb, 0xc, 0xd}));
  ASSERT_TRUE(JoinCallChain(cache3, 0, {0xa, 0xb, 0xc}, {0xa, 0xb, 0xc}, {0xa, 0xb, 0xc, 0xd},
                            {0xa, 0xb, 0xc, 0xd}));
  ASSERT_EQ(cache3.Stat().used_node_count, 4u);
}

// @CddTest = 6.1/C-0-2
TEST(LRUCache, avoid_ip_sp_loop) {
  LRUCache cache(sizeof(CacheNode) * 2, 1);
  std::vector<uint64_t> ip = {0xa, 0xb};
  std::vector<uint64_t> sp = {1, 1};
  ASSERT_TRUE(JoinCallChain(cache, 0, ip, sp, ip, sp));
  ip = {0xb, 0xa};
  ASSERT_TRUE(JoinCallChain(cache, 0, ip, sp, ip, sp));
  ASSERT_EQ(cache.Stat().used_node_count, 2u);
  ASSERT_EQ(cache.Stat().recycled_node_count, 0u);
}

// @CddTest = 6.1/C-0-2
TEST(LRUCache, one_chain) {
  LRUCache cache(sizeof(CacheNode) * 4, 1);
  ASSERT_EQ(cache.Stat().max_node_count, 4u);
  std::vector<uint64_t> ip;
  std::vector<uint64_t> sp;
  for (size_t i = 1u; i <= 4u; ++i) {
    ip.push_back(i);
    sp.push_back(i);
    ASSERT_TRUE(JoinCallChain(cache, 0, ip, sp, ip, sp));
  }
  std::vector<uint64_t> origin_ip = ip;
  std::vector<uint64_t> origin_sp = sp;
  for (size_t i = ip.size(); i > 1; --i) {
    ip.pop_back();
    sp.pop_back();
    ASSERT_TRUE(JoinCallChain(cache, 0, ip, sp, origin_ip, origin_sp));
  }
  ASSERT_EQ(cache.Stat().used_node_count, 4u);
  ASSERT_EQ(cache.Stat().recycled_node_count, 0u);
}

// @CddTest = 6.1/C-0-2
TEST(LRUCache, many_chains) {
  LRUCache cache(sizeof(CacheNode) * 12, 1);
  // 4 -> 3 -> 2 -> 1
  // 8 -> 7 -> 6 -> 5
  // d -> c -> b -> a
  std::vector<uint64_t> ip = {1, 2, 3, 4};
  std::vector<uint64_t> sp = {1, 2, 3, 4};
  ASSERT_TRUE(JoinCallChain(cache, 0, ip, sp, ip, sp));
  ip = {5, 6, 7, 8};
  sp = {5, 6, 7, 8};
  ASSERT_TRUE(JoinCallChain(cache, 0, ip, sp, ip, sp));
  ip = {0xa, 0xb, 0xc, 0xd};
  sp = {0xa, 0xb, 0xc, 0xd};
  ASSERT_TRUE(JoinCallChain(cache, 0, ip, sp, ip, sp));
  ASSERT_EQ(cache.Stat().used_node_count, 12u);
  ASSERT_EQ(cache.Stat().recycled_node_count, 0u);
  ASSERT_TRUE(JoinCallChain(cache, 0, {1}, {1}, {1, 2, 3, 4}, {1, 2, 3, 4}));
  ASSERT_TRUE(JoinCallChain(cache, 0, {5, 6}, {5, 6}, {5, 6, 7, 8}, {5, 6, 7, 8}));
  ASSERT_TRUE(JoinCallChain(cache, 0, {0xa}, {0xb}, {0xa}, {0xb}));
  ASSERT_EQ(cache.Stat().used_node_count, 12u);
  ASSERT_EQ(cache.Stat().recycled_node_count, 1u);
  ASSERT_EQ(cache.FindNode(0, 0xa, 0xa), nullptr);
}

// @CddTest = 6.1/C-0-2
class CallChainJoinerTest : public ::testing::Test {
 protected:
  void SetUp() override {
#if defined(__ANDROID__)
    std::string tmpdir = "/data/local/tmp";
#else
    std::string tmpdir = "/tmp";
#endif
    scoped_temp_files_ = ScopedTempFiles::Create(tmpdir);
  }

 private:
  std::unique_ptr<ScopedTempFiles> scoped_temp_files_;
};

// @CddTest = 6.1/C-0-2
TEST_F(CallChainJoinerTest, smoke) {
  CallChainJoiner joiner(sizeof(CacheNode) * 1024, 1, true);
  for (pid_t pid = 0; pid < 10; ++pid) {
    ASSERT_TRUE(
        joiner.AddCallChain(pid, pid, CallChainJoiner::ORIGINAL_OFFLINE, {1, 2, 3}, {1, 2, 3}));
    ASSERT_TRUE(
        joiner.AddCallChain(pid, pid, CallChainJoiner::ORIGINAL_REMOTE, {3, 4, 5}, {3, 4, 5}));
    ASSERT_TRUE(joiner.AddCallChain(pid, pid, CallChainJoiner::ORIGINAL_OFFLINE, {1, 4}, {1, 4}));
  }
  ASSERT_TRUE(joiner.JoinCallChains());
  pid_t pid;
  pid_t tid;
  CallChainJoiner::ChainType type;
  std::vector<uint64_t> ips;
  std::vector<uint64_t> sps;
  for (pid_t expected_pid = 0; expected_pid < 10; ++expected_pid) {
    for (size_t i = 0; i < 2u; ++i) {
      ASSERT_TRUE(joiner.GetNextCallChain(pid, tid, type, ips, sps));
      ASSERT_EQ(pid, expected_pid);
      ASSERT_EQ(tid, expected_pid);
      if (i == 0u) {
        ASSERT_EQ(type, CallChainJoiner::ORIGINAL_OFFLINE);
        ASSERT_EQ(ips, std::vector<uint64_t>({1, 2, 3}));
        ASSERT_EQ(sps, std::vector<uint64_t>({1, 2, 3}));
      } else {
        ASSERT_EQ(type, CallChainJoiner::JOINED_OFFLINE);
        ASSERT_EQ(ips, std::vector<uint64_t>({1, 2, 3, 4, 5}));
        ASSERT_EQ(sps, std::vector<uint64_t>({1, 2, 3, 4, 5}));
      }
    }
    for (size_t i = 0; i < 2u; ++i) {
      ASSERT_TRUE(joiner.GetNextCallChain(pid, tid, type, ips, sps));
      ASSERT_EQ(pid, expected_pid);
      ASSERT_EQ(tid, expected_pid);
      ASSERT_EQ(type, i == 0u ? CallChainJoiner::ORIGINAL_REMOTE : CallChainJoiner::JOINED_REMOTE);
      ASSERT_EQ(ips, std::vector<uint64_t>({3, 4, 5}));
      ASSERT_EQ(sps, std::vector<uint64_t>({3, 4, 5}));
    }
    for (size_t i = 0; i < 2u; ++i) {
      ASSERT_TRUE(joiner.GetNextCallChain(pid, tid, type, ips, sps));
      ASSERT_EQ(pid, expected_pid);
      ASSERT_EQ(tid, expected_pid);
      if (i == 0u) {
        ASSERT_EQ(type, CallChainJoiner::ORIGINAL_OFFLINE);
        ASSERT_EQ(ips, std::vector<uint64_t>({1, 4}));
        ASSERT_EQ(sps, std::vector<uint64_t>({1, 4}));
      } else {
        ASSERT_EQ(type, CallChainJoiner::JOINED_OFFLINE);
        ASSERT_EQ(ips, std::vector<uint64_t>({1, 4, 5}));
        ASSERT_EQ(sps, std::vector<uint64_t>({1, 4, 5}));
      }
    }
  }
  ASSERT_FALSE(joiner.GetNextCallChain(pid, tid, type, ips, sps));
  joiner.DumpStat();
  ASSERT_EQ(joiner.GetCacheStat().cache_size, sizeof(CacheNode) * 1024);
  ASSERT_EQ(joiner.GetCacheStat().matched_node_count_to_extend_callchain, 1u);
  ASSERT_EQ(joiner.GetCacheStat().max_node_count, 1024u);
  ASSERT_EQ(joiner.GetCacheStat().used_node_count, 50u);
  ASSERT_EQ(joiner.GetCacheStat().recycled_node_count, 0u);
  ASSERT_EQ(joiner.GetStat().chain_count, 30u);
  ASSERT_EQ(joiner.GetStat().before_join_node_count, 80u);
  ASSERT_EQ(joiner.GetStat().after_join_node_count, 110u);
  ASSERT_EQ(joiner.GetStat().after_join_max_chain_length, 5u);
}

// @CddTest = 6.1/C-0-2
TEST_F(CallChainJoinerTest, no_original_chains) {
  CallChainJoiner joiner(sizeof(CacheNode) * 1024, 1, false);
  ASSERT_TRUE(joiner.AddCallChain(0, 0, CallChainJoiner::ORIGINAL_OFFLINE, {1}, {1}));
  ASSERT_TRUE(joiner.JoinCallChains());
  pid_t pid;
  pid_t tid;
  CallChainJoiner::ChainType type;
  std::vector<uint64_t> ips;
  std::vector<uint64_t> sps;
  ASSERT_TRUE(joiner.GetNextCallChain(pid, tid, type, ips, sps));
  ASSERT_EQ(pid, 0);
  ASSERT_EQ(tid, 0);
  ASSERT_EQ(type, CallChainJoiner::JOINED_OFFLINE);
  ASSERT_EQ(ips, std::vector<uint64_t>({1}));
  ASSERT_EQ(sps, std::vector<uint64_t>({1}));
  ASSERT_FALSE(joiner.GetNextCallChain(pid, tid, type, ips, sps));
  joiner.DumpStat();
}

// @CddTest = 6.1/C-0-2
TEST_F(CallChainJoinerTest, no_chains) {
  CallChainJoiner joiner(sizeof(CacheNode) * 1024, 1, false);
  ASSERT_TRUE(joiner.JoinCallChains());
  pid_t pid;
  pid_t tid;
  CallChainJoiner::ChainType type;
  std::vector<uint64_t> ips;
  std::vector<uint64_t> sps;
  ASSERT_FALSE(joiner.GetNextCallChain(pid, tid, type, ips, sps));
  joiner.DumpStat();
}
