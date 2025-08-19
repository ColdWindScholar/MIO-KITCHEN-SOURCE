/*
 * Copyright (C) 2015 The Android Open Source Project
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

#ifndef SIMPLE_PERF_CALLCHAIN_H_
#define SIMPLE_PERF_CALLCHAIN_H_

#include <string.h>

#include <algorithm>
#include <functional>
#include <memory>
#include <queue>
#include <vector>

#include <android-base/logging.h>

namespace simpleperf {

template <typename EntryT>
struct CallChainNode {
  uint64_t period;
  uint64_t children_period;
  std::vector<EntryT*> chain;
  std::vector<std::unique_ptr<CallChainNode>> children;
};

template <typename EntryT>
struct CallChainRoot {
  typedef CallChainNode<EntryT> NodeT;
  // If duplicated = true, this call tree is part of another call tree.
  // And we don't need to show it in brief callgraph report mode.
  bool duplicated;
  uint64_t children_period;
  std::vector<std::unique_ptr<NodeT>> children;

  CallChainRoot() : duplicated(false), children_period(0) {}

  void AddCallChain(const std::vector<EntryT*>& callchain, uint64_t period,
                    std::function<bool(const EntryT*, const EntryT*)> is_same_sample) {
    children_period += period;
    NodeT* p = FindMatchingNode(children, callchain[0], is_same_sample);
    if (p == nullptr) {
      std::unique_ptr<NodeT> new_node = AllocateNode(callchain, 0, period, 0);
      children.push_back(std::move(new_node));
      return;
    }
    size_t callchain_pos = 0;
    while (true) {
      size_t match_length = GetMatchingLengthInNode(p, callchain, callchain_pos, is_same_sample);
      CHECK_GT(match_length, 0u);
      callchain_pos += match_length;
      bool find_child = true;
      if (match_length < p->chain.size()) {
        SplitNode(p, match_length);
        find_child = false;  // No need to find matching node in p->children.
      }
      if (callchain_pos == callchain.size()) {
        p->period += period;
        return;
      }
      p->children_period += period;
      if (find_child) {
        NodeT* np = FindMatchingNode(p->children, callchain[callchain_pos], is_same_sample);
        if (np != nullptr) {
          p = np;
          continue;
        }
      }
      std::unique_ptr<NodeT> new_node = AllocateNode(callchain, callchain_pos, period, 0);
      p->children.push_back(std::move(new_node));
      break;
    }
  }

  void SortByPeriod() {
    std::queue<std::vector<std::unique_ptr<NodeT>>*> queue;
    queue.push(&children);
    while (!queue.empty()) {
      std::vector<std::unique_ptr<NodeT>>* v = queue.front();
      queue.pop();
      std::sort(v->begin(), v->end(), CallChainRoot::CompareNodeByPeriod);
      for (auto& node : *v) {
        if (!node->children.empty()) {
          queue.push(&node->children);
        }
      }
    }
  }

 private:
  NodeT* FindMatchingNode(const std::vector<std::unique_ptr<NodeT>>& nodes, const EntryT* sample,
                          std::function<bool(const EntryT*, const EntryT*)> is_same_sample) {
    for (auto& node : nodes) {
      if (is_same_sample(node->chain.front(), sample)) {
        return node.get();
      }
    }
    return nullptr;
  }

  size_t GetMatchingLengthInNode(NodeT* node, const std::vector<EntryT*>& chain, size_t chain_start,
                                 std::function<bool(const EntryT*, const EntryT*)> is_same_sample) {
    size_t i, j;
    for (i = 0, j = chain_start; i < node->chain.size() && j < chain.size(); ++i, ++j) {
      if (!is_same_sample(node->chain[i], chain[j])) {
        break;
      }
    }
    return i;
  }

  void SplitNode(NodeT* parent, size_t parent_length) {
    std::unique_ptr<NodeT> child =
        AllocateNode(parent->chain, parent_length, parent->period, parent->children_period);
    child->children = std::move(parent->children);
    parent->period = 0;
    parent->children_period = child->period + child->children_period;
    parent->chain.resize(parent_length);
    parent->children.clear();
    parent->children.push_back(std::move(child));
  }

  std::unique_ptr<NodeT> AllocateNode(const std::vector<EntryT*>& chain, size_t chain_start,
                                      uint64_t period, uint64_t children_period) {
    std::unique_ptr<NodeT> node(new NodeT);
    for (size_t i = chain_start; i < chain.size(); ++i) {
      node->chain.push_back(chain[i]);
    }
    node->period = period;
    node->children_period = children_period;
    return node;
  }

  static bool CompareNodeByPeriod(const std::unique_ptr<NodeT>& n1,
                                  const std::unique_ptr<NodeT>& n2) {
    uint64_t period1 = n1->period + n1->children_period;
    uint64_t period2 = n2->period + n2->children_period;
    return period1 > period2;
  }
};

}  // namespace simpleperf

#endif  // SIMPLE_PERF_CALLCHAIN_H_
