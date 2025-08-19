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

#include <android-base/logging.h>

#include "environment.h"
#include "utils.h"

namespace simpleperf {
namespace call_chain_joiner_impl {

LRUCache::LRUCache(size_t cache_size, size_t matched_node_count_to_extend_callchain)
    : node_set_(1024 * 16, CacheNodeHash, CacheNodeEqual) {
  cache_stat_.cache_size = cache_size;
  cache_stat_.max_node_count = cache_size / sizeof(CacheNode);
  CHECK_GE(cache_stat_.max_node_count, 2u);
  CHECK_GE(matched_node_count_to_extend_callchain, 1u);
  cache_stat_.matched_node_count_to_extend_callchain = matched_node_count_to_extend_callchain;
  nodes_ = new CacheNode[cache_stat_.max_node_count + 1];  // with 1 sentinel node
  // nodes_[0] is the sentinel node of the LRU linked list.
  nodes_[0].is_leaf = 1;
  nodes_[0].parent_index = 0;
  nodes_[0].leaf_link_prev = nodes_[0].leaf_link_next = 0;
}

LRUCache::~LRUCache() {
  delete[] nodes_;
}

void LRUCache::AddCallChain(pid_t tid, std::vector<uint64_t>& ips, std::vector<uint64_t>& sps) {
  // 1. Build current call chain.
  std::vector<CacheNode*> chain;
  for (size_t i = 0; i < ips.size(); ++i) {
    CacheNode* node = GetNode(tid, ips[i], sps[i]);
    chain.push_back(node);
  }

  // 2. Check if the (tid, ip, sp) tuples of the top [matched_node_count_to_extend_callchain]
  // nodes of current call chain exist in the cache and have the same relation as in current
  // call chain. If true, we can extend current call chain.
  bool can_extend = true;
  if (chain.size() < cache_stat_.matched_node_count_to_extend_callchain) {
    can_extend = false;
  } else {
    size_t chain_pos = chain.size() - 2;
    for (size_t i = 1; i < cache_stat_.matched_node_count_to_extend_callchain; ++i) {
      if (GetParent(chain[chain_pos]) != chain[chain_pos + 1]) {
        can_extend = false;
        break;
      }
    }
  }
  std::vector<uint64_t> origin_ip = ips;

  // 3. Add current call chain to the cache.
  for (size_t i = 0; i + 1 < chain.size(); ++i) {
    LinkParent(chain[i], chain[i + 1]);
  }
  // 4. Optionally extend current call chain.
  if (can_extend) {
    CacheNode* top = chain.back();
    while ((top = GetParent(top)) != nullptr) {
      if (top->sp == chain.back()->sp) {
        // This is to prevent a loop case as below, which is unlikely to happen.
        // The cache has node A.parent = B, while current call chain has node B.parent = A.
        // This makes a loop of A -> B -> A -> B...
        bool has_loop = false;
        for (auto it = chain.rbegin(); it != chain.rend() && (*it)->sp == top->sp; ++it) {
          if ((*it)->ip == top->ip) {
            has_loop = true;
            break;
          }
        }
        if (has_loop) {
          UnlinkParent(chain.back());
          ips.resize(chain.size());
          sps.resize(chain.size());
          break;
        }
      }
      ips.push_back(top->ip);
      sps.push_back(top->sp);
    }
  } else {
    UnlinkParent(chain.back());
  }
}

bool LRUCache::CacheNodeEqual(const CacheNode* n1, const CacheNode* n2) {
  return n1->tid == n2->tid && n1->ip == n2->ip && n1->sp == n2->sp;
}

size_t LRUCache::CacheNodeHash(const CacheNode* n) {
  return static_cast<size_t>(n->tid ^ n->ip ^ n->sp);
}

CacheNode* LRUCache::GetNode(uint32_t tid, uint64_t ip, uint64_t sp) {
  CacheNode* node = FindNode(tid, ip, sp);
  if (node != nullptr) {
    if (node->is_leaf) {
      // Update the node's position in the LRU linked list.
      RemoveNodeFromLRUList(node);
      AppendNodeToLRUList(node);
    }
    return node;
  }
  node = AllocNode();
  node->tid = tid;
  node->ip = ip;
  node->sp = sp;
  node->is_leaf = 1;
  node->parent_index = 0;
  node->leaf_link_prev = node->leaf_link_next = GetNodeIndex(node);
  node_set_.insert(node);
  AppendNodeToLRUList(node);
  return node;
}

CacheNode* LRUCache::AllocNode() {
  if (cache_stat_.used_node_count < cache_stat_.max_node_count) {
    return &nodes_[++cache_stat_.used_node_count];
  }
  // Recycle the node at the front of the LRU linked list.
  CacheNode* node = &nodes_[nodes_->leaf_link_next];
  RemoveNodeFromLRUList(node);
  node_set_.erase(node);
  CacheNode* parent = GetParent(node);
  if (parent != nullptr) {
    DecreaseChildCountOfNode(parent);
  }
  cache_stat_.recycled_node_count++;
  return node;
}

void LRUCache::LinkParent(CacheNode* child, CacheNode* new_parent) {
  CacheNode* old_parent = GetParent(child);
  if (old_parent != nullptr) {
    DecreaseChildCountOfNode(old_parent);
  }
  child->parent_index = GetNodeIndex(new_parent);
  if (new_parent->is_leaf) {
    RemoveNodeFromLRUList(new_parent);
    new_parent->is_leaf = 0;
    new_parent->children_count = 1;
  } else {
    new_parent->children_count++;
  }
}

void LRUCache::UnlinkParent(CacheNode* child) {
  CacheNode* old_parent = GetParent(child);
  if (old_parent != nullptr) {
    DecreaseChildCountOfNode(old_parent);
  }
  child->parent_index = 0;
}

}  // namespace call_chain_joiner_impl

using namespace call_chain_joiner_impl;

static bool WriteCallChain(FILE* fp, pid_t pid, pid_t tid, CallChainJoiner::ChainType type,
                           const std::vector<uint64_t>& ips, const std::vector<uint64_t>& sps,
                           size_t ip_count) {
  // Below is the content of a call chain stored in file.
  //   uint32_t pid;
  //   uint32_t tid;
  //   uint32_t chain_type;
  //   uint32_t ip_count;
  //   uint64_t ips[];
  //   uint64_t sps[];
  //   uint32_t size;
  uint32_t size = 4 * sizeof(uint32_t) + sizeof(uint64_t) * ip_count * 2 + sizeof(uint32_t);
  std::vector<char> data(size);
  char* p = data.data();
  MoveToBinaryFormat(pid, p);
  MoveToBinaryFormat(tid, p);
  MoveToBinaryFormat(type, p);
  MoveToBinaryFormat(static_cast<uint32_t>(ip_count), p);
  MoveToBinaryFormat(ips.data(), ip_count, p);
  MoveToBinaryFormat(sps.data(), ip_count, p);
  MoveToBinaryFormat(size, p);
  if (fwrite(data.data(), size, 1, fp) != 1) {
    PLOG(ERROR) << "fwrite";
    return false;
  }
  return true;
}

static bool ReadCallChain(FILE* fp, pid_t& pid, pid_t& tid, CallChainJoiner::ChainType& type,
                          std::vector<uint64_t>& ips, std::vector<uint64_t>& sps) {
  std::vector<char> data(4 * sizeof(uint32_t));
  if (fread(data.data(), data.size(), 1, fp) != 1) {
    PLOG(ERROR) << "fread";
    return false;
  }
  const char* p = data.data();
  MoveFromBinaryFormat(pid, p);
  MoveFromBinaryFormat(tid, p);
  MoveFromBinaryFormat(type, p);
  uint32_t ip_count;
  MoveFromBinaryFormat(ip_count, p);
  data.resize(sizeof(uint64_t) * ip_count * 2 + sizeof(uint32_t));
  if (fread(data.data(), data.size(), 1, fp) != 1) {
    PLOG(ERROR) << "fread";
    return false;
  }
  p = data.data();
  ips.resize(ip_count);
  MoveFromBinaryFormat(ips.data(), ip_count, p);
  sps.resize(ip_count);
  MoveFromBinaryFormat(sps.data(), ip_count, p);
  return true;
}

static bool ReadCallChainInReverseOrder(FILE* fp, pid_t& pid, pid_t& tid,
                                        CallChainJoiner::ChainType& type,
                                        std::vector<uint64_t>& ips, std::vector<uint64_t>& sps) {
  uint32_t size;
  if (fseek(fp, -4, SEEK_CUR) != 0 || fread(&size, sizeof(size), 1, fp) != 1) {
    PLOG(ERROR) << "fread";
    return false;
  }
  std::vector<char> data(size - 4);
  if (fseek(fp, -static_cast<int>(size), SEEK_CUR) != 0 ||
      fread(data.data(), data.size(), 1, fp) != 1 ||
      fseek(fp, -static_cast<int>(data.size()), SEEK_CUR) != 0) {
    PLOG(ERROR) << "fread";
    return false;
  }
  const char* p = data.data();
  MoveFromBinaryFormat(pid, p);
  MoveFromBinaryFormat(tid, p);
  MoveFromBinaryFormat(type, p);
  uint32_t ip_count;
  MoveFromBinaryFormat(ip_count, p);
  ips.resize(ip_count);
  MoveFromBinaryFormat(ips.data(), ip_count, p);
  sps.resize(ip_count);
  MoveFromBinaryFormat(sps.data(), ip_count, p);
  return true;
}

static FILE* CreateTempFp() {
  std::unique_ptr<TemporaryFile> tmpfile = ScopedTempFiles::CreateTempFile();
  FILE* fp = fdopen(tmpfile->release(), "web+");
  if (fp == nullptr) {
    PLOG(ERROR) << "fdopen";
    return nullptr;
  }
  return fp;
}

CallChainJoiner::CallChainJoiner(size_t cache_size, size_t matched_node_count_to_extend_callchain,
                                 bool keep_original_callchains)
    : keep_original_callchains_(keep_original_callchains),
      original_chains_fp_(nullptr),
      joined_chains_fp_(nullptr),
      next_chain_index_(0u) {
  cache_stat_.cache_size = cache_size;
  cache_stat_.matched_node_count_to_extend_callchain = matched_node_count_to_extend_callchain;
}

CallChainJoiner::~CallChainJoiner() {
  if (original_chains_fp_ != nullptr) {
    fclose(original_chains_fp_);
  }
  if (joined_chains_fp_ != nullptr) {
    fclose(joined_chains_fp_);
  }
}

bool CallChainJoiner::AddCallChain(pid_t pid, pid_t tid, ChainType type,
                                   const std::vector<uint64_t>& ips,
                                   const std::vector<uint64_t>& sps) {
  CHECK_EQ(ips.size(), sps.size());
  CHECK_GT(ips.size(), 0u);
  CHECK(type == ORIGINAL_OFFLINE || type == ORIGINAL_REMOTE);
  // Make sure sps are in non-decreasing order, and there is no duplicated items.
  size_t ip_count = ips.size();
  for (size_t i = 1; i < ips.size(); ++i) {
    if (sps[i] < sps[i - 1]) {
      ip_count = i;
      break;
    } else if (sps[i] == sps[i - 1]) {
      bool has_duplicated_items = false;
      for (size_t j = i; j > 0 && sps[j - 1] == sps[i]; --j) {
        if (ips[j - 1] == ips[i]) {
          has_duplicated_items = true;
          break;
        }
      }
      if (has_duplicated_items) {
        ip_count = i;
        break;
      }
    }
  }

  if (original_chains_fp_ == nullptr) {
    original_chains_fp_ = CreateTempFp();
    if (original_chains_fp_ == nullptr) {
      return false;
    }
  }
  stat_.chain_count++;
  return WriteCallChain(original_chains_fp_, pid, tid, type, ips, sps, ip_count);
}

bool CallChainJoiner::JoinCallChains() {
  if (stat_.chain_count == 0u) {
    return true;
  }
  LRUCache cache(cache_stat_.cache_size, cache_stat_.matched_node_count_to_extend_callchain);
  std::unique_ptr<FILE, decltype(&fclose)> tmp_fp(CreateTempFp(), fclose);
  if (!tmp_fp) {
    return false;
  }
  joined_chains_fp_ = CreateTempFp();
  if (joined_chains_fp_ == nullptr) {
    return false;
  }
  pid_t pid;
  pid_t tid;
  ChainType type;
  std::vector<uint64_t> ips;
  std::vector<uint64_t> sps;
  if (fseek(original_chains_fp_, 0, SEEK_END) != 0) {
    PLOG(ERROR) << "fseek";
    return false;
  }
  std::vector<std::pair<FILE*, FILE*>> file_pairs = {
      std::make_pair(original_chains_fp_, tmp_fp.get()),
      std::make_pair(tmp_fp.get(), joined_chains_fp_)};
  for (size_t pass = 0; pass < 2u; ++pass) {
    auto& pair = file_pairs[pass];
    for (size_t i = 0; i < stat_.chain_count; ++i) {
      if (!ReadCallChainInReverseOrder(pair.first, pid, tid, type, ips, sps)) {
        return false;
      }
      if (pass == 0u) {
        if (type == ORIGINAL_OFFLINE) {
          type = JOINED_OFFLINE;
        } else if (type == ORIGINAL_REMOTE) {
          type = JOINED_REMOTE;
        }
        stat_.before_join_node_count += ips.size();
      }

      cache.AddCallChain(tid, ips, sps);

      if (pass == 1u) {
        stat_.after_join_node_count += ips.size();
        stat_.after_join_max_chain_length = std::max(stat_.after_join_max_chain_length, ips.size());
      }

      if (!WriteCallChain(pair.second, pid, tid, type, ips, sps, ips.size())) {
        return false;
      }
    }
  }
  cache_stat_ = cache.Stat();
  return true;
}

bool CallChainJoiner::GetNextCallChain(pid_t& pid, pid_t& tid, ChainType& type,
                                       std::vector<uint64_t>& ips, std::vector<uint64_t>& sps) {
  if (next_chain_index_ == stat_.chain_count * 2) {
    // No more chains.
    return false;
  }
  if (next_chain_index_ == 0u) {
    if (fseek(original_chains_fp_, 0, SEEK_SET) != 0 ||
        fseek(joined_chains_fp_, 0, SEEK_SET) != 0) {
      PLOG(ERROR) << "fseek";
      return false;
    }
  }
  FILE* fp;
  if (keep_original_callchains_) {
    fp = (next_chain_index_ & 1) ? joined_chains_fp_ : original_chains_fp_;
    next_chain_index_++;
  } else {
    fp = joined_chains_fp_;
    next_chain_index_ += 2;
  }
  return ReadCallChain(fp, pid, tid, type, ips, sps);
}

void CallChainJoiner::DumpStat() {
  LOG(DEBUG) << "call chain joiner stat:";
  LOG(DEBUG) << "  cache_size: " << cache_stat_.cache_size;
  LOG(DEBUG) << "  matched_node_count_to_extend_callchain: "
             << cache_stat_.matched_node_count_to_extend_callchain;
  LOG(DEBUG) << "  max_node_count in cache: " << cache_stat_.max_node_count;
  LOG(DEBUG) << "  used_node_count in cache: " << cache_stat_.used_node_count;
  LOG(DEBUG) << "  recycled_node_count in cache: " << cache_stat_.recycled_node_count;
  LOG(DEBUG) << "  call_chain_count: " << stat_.chain_count;
  LOG(DEBUG) << "  before_join_node_count: " << stat_.before_join_node_count;
  if (stat_.chain_count > 0u) {
    LOG(DEBUG) << "  before_join_average_chain_length: "
               << (stat_.before_join_node_count * 1.0 / stat_.chain_count);
  }
  LOG(DEBUG) << "  after_join_node_count: " << stat_.after_join_node_count;
  if (stat_.chain_count > 0u) {
    LOG(DEBUG) << "  after_join_average_chain_length: "
               << (stat_.after_join_node_count * 1.0 / stat_.chain_count);
  }
  LOG(DEBUG) << "  after_join_max_chain_length: " << stat_.after_join_max_chain_length;
}

}  // namespace simpleperf
