// Copyright (C) 2015 The Android Open Source Project
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <linux/taskstats.h>
#include <netlink/genl/ctrl.h>
#include <netlink/genl/genl.h>
#include <netlink/socket.h>

#include <algorithm>
#include <memory>

#include <android-base/logging.h>

#include "taskstats.h"

TaskstatsSocket::TaskstatsSocket() : nl_(nullptr, nl_socket_free), family_id_(0) {}

bool TaskstatsSocket::Open() {
  std::unique_ptr<nl_sock, decltype(&nl_socket_free)> nl(nl_socket_alloc(), nl_socket_free);
  if (!nl.get()) {
    LOG(ERROR) << "Failed to allocate netlink socket";
    return false;
  }

  int ret = genl_connect(nl.get());
  if (ret < 0) {
    LOG(ERROR) << nl_geterror(ret) << std::endl << "Unable to open netlink socket (are you root?)";
    return false;
  }

  int family_id = genl_ctrl_resolve(nl.get(), TASKSTATS_GENL_NAME);
  if (family_id < 0) {
    LOG(ERROR) << nl_geterror(family_id) << std::endl
               << "Unable to determine taskstats family id (does your kernel support taskstats?)";
    return false;
  }

  nl_ = std::move(nl);
  family_id_ = family_id;

  return true;
}

void TaskstatsSocket::Close() {
  nl_.reset();
}

struct TaskStatsRequest {
  pid_t requested_pid;
  taskstats stats;
};

static pid_t ParseAggregateTaskStats(nlattr* attr, int attr_size, taskstats* stats) {
  pid_t received_pid = -1;
  nla_for_each_attr(attr, attr, attr_size, attr_size) {
    switch (nla_type(attr)) {
      case TASKSTATS_TYPE_PID:
      case TASKSTATS_TYPE_TGID:
        received_pid = nla_get_u32(attr);
        break;
      case TASKSTATS_TYPE_STATS: {
        int len = static_cast<int>(sizeof(*stats));
        len = std::min(len, nla_len(attr));
        nla_memcpy(stats, attr, len);
        return received_pid;
      }
      default:
        LOG(ERROR) << "unexpected attribute inside AGGR";
        return -1;
    }
  }

  return -1;
}

static int ParseTaskStats(nl_msg* msg, void* arg) {
  TaskStatsRequest* taskstats_request = static_cast<TaskStatsRequest*>(arg);
  genlmsghdr* gnlh = static_cast<genlmsghdr*>(nlmsg_data(nlmsg_hdr(msg)));
  nlattr* attr = genlmsg_attrdata(gnlh, 0);
  int remaining = genlmsg_attrlen(gnlh, 0);

  nla_for_each_attr(attr, attr, remaining, remaining) {
    switch (nla_type(attr)) {
      case TASKSTATS_TYPE_AGGR_PID:
      case TASKSTATS_TYPE_AGGR_TGID: {
        nlattr* nested_attr = static_cast<nlattr*>(nla_data(attr));
        taskstats stats;
        pid_t ret;

        ret = ParseAggregateTaskStats(nested_attr, nla_len(attr), &stats);
        if (ret < 0) {
          LOG(ERROR) << "Bad AGGR_PID contents";
        } else if (ret == taskstats_request->requested_pid) {
          taskstats_request->stats = stats;
        } else {
          LOG(WARNING) << "got taskstats for unexpected pid " << ret << " (expected "
                       << taskstats_request->requested_pid << ", continuing...";
        }
        break;
      }
      case TASKSTATS_TYPE_NULL:
        break;
      default:
        LOG(ERROR) << "unexpected attribute in taskstats";
    }
  }
  return NL_OK;
}

bool TaskstatsSocket::GetStats(int pid, int type, TaskStatistics& stats) {
  TaskStatsRequest taskstats_request = TaskStatsRequest();
  taskstats_request.requested_pid = pid;

  std::unique_ptr<nl_msg, decltype(&nlmsg_free)> message(nlmsg_alloc(), nlmsg_free);

  genlmsg_put(message.get(), NL_AUTO_PID, NL_AUTO_SEQ, family_id_, 0, 0, TASKSTATS_CMD_GET,
              TASKSTATS_VERSION);
  nla_put_u32(message.get(), type, pid);

  int result = nl_send_auto_complete(nl_.get(), message.get());
  if (result < 0) {
    return false;
  }

  std::unique_ptr<nl_cb, decltype(&nl_cb_put)> callbacks(nl_cb_alloc(NL_CB_DEFAULT), nl_cb_put);
  nl_cb_set(callbacks.get(), NL_CB_VALID, NL_CB_CUSTOM, &ParseTaskStats,
            static_cast<void*>(&taskstats_request));

  result = nl_recvmsgs(nl_.get(), callbacks.get());
  if (result < 0) {
    return false;
  }
  nl_wait_for_ack(nl_.get());

  stats = TaskStatistics(taskstats_request.stats);

  return true;
}

bool TaskstatsSocket::GetPidStats(int pid, TaskStatistics& stats) {
  return GetStats(pid, TASKSTATS_CMD_ATTR_PID, stats);
}

bool TaskstatsSocket::GetTgidStats(int tgid, TaskStatistics& stats) {
  bool ret = GetStats(tgid, TASKSTATS_CMD_ATTR_TGID, stats);
  if (ret) {
    stats.set_pid(tgid);
  }
  return ret;
}

TaskStatistics::TaskStatistics(const taskstats& taskstats_stats) {
  comm_ = std::string(taskstats_stats.ac_comm);
  pid_ = taskstats_stats.ac_pid;

  uid_ = taskstats_stats.ac_uid;
  gid_ = taskstats_stats.ac_gid;
  pid_ = taskstats_stats.ac_pid;
  ppid_ = taskstats_stats.ac_ppid;

  cpu_delay_count_ = taskstats_stats.cpu_count;
  cpu_delay_ns_ = taskstats_stats.cpu_delay_total;

  block_io_delay_count_ = taskstats_stats.blkio_count;
  block_io_delay_ns_ = taskstats_stats.blkio_delay_total;

  swap_in_delay_count_ = taskstats_stats.swapin_count;
  swap_in_delay_ns_ = taskstats_stats.swapin_delay_total;

  reclaim_delay_count_ = taskstats_stats.freepages_count;
  reclaim_delay_ns_ = taskstats_stats.freepages_delay_total;

  total_delay_ns_ = cpu_delay_ns_ + block_io_delay_ns_ + swap_in_delay_ns_ + reclaim_delay_ns_;

  cpu_time_real_ = taskstats_stats.cpu_run_real_total;
  cpu_time_virtual_ = taskstats_stats.cpu_run_virtual_total;

  majflt_ = taskstats_stats.ac_majflt;
  minflt_ = taskstats_stats.ac_minflt;

  read_bytes_ = taskstats_stats.read_bytes;
  write_bytes_ = taskstats_stats.write_bytes;
  read_write_bytes_ = read_bytes_ + write_bytes_;
  cancelled_write_bytes_ = taskstats_stats.cancelled_write_bytes;
  threads_ = 1;
}

void TaskStatistics::AddPidToTgid(const TaskStatistics& pid_statistics) {
  // tgid statistics already contain delay values totalled across all pids
  // only add IO statistics
  read_bytes_ += pid_statistics.read_bytes_;
  write_bytes_ += pid_statistics.write_bytes_;
  read_write_bytes_ += pid_statistics.read_write_bytes_;
  cancelled_write_bytes_ += pid_statistics.cancelled_write_bytes_;
  if (pid_ == pid_statistics.pid_) {
    comm_ = pid_statistics.comm_;
    uid_ = pid_statistics.uid_;
    gid_ = pid_statistics.pid_;
    ppid_ = pid_statistics.ppid_;
  } else {
    threads_++;
  }
}

// Store new statistics and return the delta from the old statistics
TaskStatistics TaskStatistics::Update(const TaskStatistics& new_statistics) {
  TaskStatistics delta = new_statistics;
  delta.minflt_ -= minflt_;
  delta.majflt_ -= majflt_;
  delta.cpu_delay_count_ -= cpu_delay_count_;
  delta.cpu_delay_ns_ -= cpu_delay_ns_;
  delta.block_io_delay_count_ -= block_io_delay_count_;
  delta.block_io_delay_ns_ -= block_io_delay_ns_;
  delta.swap_in_delay_count_ -= swap_in_delay_count_;
  delta.swap_in_delay_ns_ -= swap_in_delay_ns_;
  delta.reclaim_delay_count_ -= reclaim_delay_count_;
  delta.reclaim_delay_ns_ -= reclaim_delay_ns_;
  delta.total_delay_ns_ -= total_delay_ns_;
  delta.cpu_time_real_ -= cpu_time_real_;
  delta.cpu_time_virtual_ -= cpu_time_virtual_;
  delta.read_bytes_ -= read_bytes_;
  delta.write_bytes_ -= write_bytes_;
  delta.read_write_bytes_ -= read_write_bytes_;
  delta.cancelled_write_bytes_ -= cancelled_write_bytes_;
  *this = new_statistics;
  return delta;
}
