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

#ifndef SIMPLE_PERF_CALLCHAIN_JOINER_H_
#define SIMPLE_PERF_CALLCHAIN_JOINER_H_

#include <inttypes.h>
#include <stdio.h>
#include <unistd.h>

#include <unordered_set>
#include <vector>

namespace simpleperf {

namespace call_chain_joiner_impl {

// Each node represents a function in a call chain, having a tuple info (tid, ip, sp).
// A node remembers its parent in the call chain.
struct CacheNode {
  uint64_t ip;
  uint64_t sp;
  uint32_t tid;
  // Whether the node is at the bottom of a call chain.
  uint32_t is_leaf : 1;
  // The index of the parent node in a call chain.
  uint32_t parent_index : 31;
  // When is_leaf = false, children_count remembers how many nodes have current node as parent.
  // When is_leaf = true, leaf_link_prev and leaf_link_next keeps current node in a LRU linked list.
  union {
    uint32_t children_count;
    struct {
      uint32_t leaf_link_prev;
      uint32_t leaf_link_next;
    };
  };
};

static_assert(sizeof(CacheNode) == 32, "");

struct LRUCacheStat {
  size_t cache_size = 0u;
  size_t matched_node_count_to_extend_callchain = 0u;
  size_t max_node_count = 0u;
  size_t used_node_count = 0u;
  size_t recycled_node_count = 0u;
};

// LRUCache caches call chains in memory, and supports extending a call chain if the (tid, ip, sp)
// tuples of its top [matched_node_count_to_extend_callchain] appear in the cache.
class LRUCache {
 public:
  // cache_size is the bytes of memory we want to use in this cache.
  // matched_node_count_to_extend_callchain decides how many nodes we need to match to extend a
  // call chain. Higher value means more strict.
  LRUCache(size_t cache_size = 8 * 1024 * 1024, size_t matched_node_count_to_extend_callchain = 1);
  ~LRUCache();

  // Add a call chain in the cache, and extend it if possible.
  void AddCallChain(pid_t tid, std::vector<uint64_t>& ips, std::vector<uint64_t>& sps);

  const LRUCacheStat& Stat() { return cache_stat_; }

  CacheNode* FindNode(uint32_t tid, uint64_t ip, uint64_t sp) {
    CacheNode key;
    key.tid = tid;
    key.ip = ip;
    key.sp = sp;
    auto it = node_set_.find(&key);
    return it != node_set_.end() ? *it : nullptr;
  }

 private:
  static bool CacheNodeEqual(const CacheNode* n1, const CacheNode* n2);
  static size_t CacheNodeHash(const CacheNode* n);

  typedef std::unordered_set<CacheNode*, decltype(&CacheNodeHash), decltype(&CacheNodeEqual)>
      set_type;

  CacheNode* GetParent(CacheNode* node) {
    return node->parent_index == 0u ? nullptr : nodes_ + node->parent_index;
  }

  int GetNodeIndex(CacheNode* node) { return node - nodes_; }

  void RemoveNodeFromLRUList(CacheNode* node) {
    CacheNode* prev = &nodes_[node->leaf_link_prev];
    CacheNode* next = &nodes_[node->leaf_link_next];
    prev->leaf_link_next = node->leaf_link_next;
    next->leaf_link_prev = node->leaf_link_prev;
  }

  void AppendNodeToLRUList(CacheNode* node) {
    CacheNode* next = &nodes_[0];
    CacheNode* prev = &nodes_[next->leaf_link_prev];
    node->leaf_link_next = 0;
    node->leaf_link_prev = next->leaf_link_prev;
    next->leaf_link_prev = prev->leaf_link_next = GetNodeIndex(node);
  }

  void DecreaseChildCountOfNode(CacheNode* node) {
    if (--node->children_count == 0u) {
      node->is_leaf = true;
      AppendNodeToLRUList(node);
    }
  }

  CacheNode* GetNode(uint32_t tid, uint64_t ip, uint64_t sp);
  CacheNode* AllocNode();
  void LinkParent(CacheNode* child, CacheNode* new_parent);
  void UnlinkParent(CacheNode* child);

  CacheNode* nodes_;
  set_type node_set_;
  LRUCacheStat cache_stat_;
};

}  // namespace call_chain_joiner_impl

// CallChainJoiner is used to join callchains of samples in the same thread, in order to get
// complete call graph. For example, if we have two samples for a thread:
//   sample 1: (ip A, sp A) -> (ip B, sp B) -> (ip C, sp C) -> ...
//   sample 2:                 (ip B, sp B) -> (ip C, sp C) -> ...
// Because we know (ip A, sp A) calls (ip B, sp B) in sample 1, then we can guess the (ip B, sp B)
// in sample 2 is also called from (ip A, sp A). So we can add (ip A, sp A) in sample 2 as below.
//   sample 2: (ip A, sp A) -> (ip B, sp B) -> (ip C, sp C) -> ...
class CallChainJoiner {
 public:
  // The parameters are used in LRUCache.
  CallChainJoiner(size_t cache_size, size_t matched_node_count_to_extend_callchain,
                  bool keep_original_callchains);
  ~CallChainJoiner();

  enum ChainType {
    ORIGINAL_OFFLINE,
    ORIGINAL_REMOTE,
    JOINED_OFFLINE,
    JOINED_REMOTE,
  };

  bool AddCallChain(pid_t pid, pid_t tid, ChainType type, const std::vector<uint64_t>& ips,
                    const std::vector<uint64_t>& sps);
  bool JoinCallChains();
  bool GetNextCallChain(pid_t& pid, pid_t& tid, ChainType& type, std::vector<uint64_t>& ips,
                        std::vector<uint64_t>& sps);

  struct Stat {
    size_t chain_count = 0u;
    size_t before_join_node_count = 0u;
    size_t after_join_node_count = 0u;
    size_t after_join_max_chain_length = 0u;
  };
  void DumpStat();
  const Stat& GetStat() { return stat_; }
  const call_chain_joiner_impl::LRUCacheStat& GetCacheStat() { return cache_stat_; }

 private:
  bool keep_original_callchains_;
  FILE* original_chains_fp_;
  FILE* joined_chains_fp_;
  size_t next_chain_index_;
  call_chain_joiner_impl::LRUCacheStat cache_stat_;
  Stat stat_;
};

}  // namespace simpleperf

#endif  // SIMPLE_PERF_CALLCHAIN_JOINER_H_
