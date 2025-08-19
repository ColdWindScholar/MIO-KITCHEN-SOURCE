#!/usr/bin/env python
#
# Copyright (C) 2016 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Analyze ext4 trace with custom open trace"""
import collections
import math
import os
import re
import string
import sys

DBG = False
DBG_ISSUE = False

# hard coded maps to detect partition for given device or the other way around
# this can be different per each device. This works for marlin.
DEVICE_TO_PARTITION = { "253,0": "/system/", "253,1": "/vendor/", "259,19": "/data/" }
PARTITION_TO_DEVICE = {}
for key, value in DEVICE_TO_PARTITION.iteritems():
  PARTITION_TO_DEVICE[value] = key

# init-1     [003] ....     2.703964: do_sys_open: init: open("/sys/fs/selinux/null", 131074, 0) fd = 0, inode = 22
RE_DO_SYS_OPEN = r"""\s+\S+-([0-9]+).*\s+([0-9]+\.[0-9]+):\s+do_sys_open:\s+(\S+):\sopen..(\S+).,\s([0-9]+).\s+.+inode\s=\s([0-9]+)"""
# init-1     [003] ...1     2.703991: ext4_ext_map_blocks_enter: dev 253,0 ino 2719 lblk 154 len 30 flags
RE_EXT4_MA_BLOCKS_ENTER = r"""\s+(\S+)-([0-9]+).+\s+([0-9]+\.[0-9]+):\s+ext4_ext_map_blocks_enter:\s+dev\s+(\S+)\s+ino\s+([0-9]+)\s+lblk\s+([0-9]+)\s+len\s+([0-9]+)"""
# init-1     [002] ...1     2.687205: ext4_ext_map_blocks_exit: dev 253,0 ino 8 flags  lblk 0 pblk 196608 len 1 mflags M ret 1
RE_EXT4_MA_BLOCKS_EXIT = r"""\s+(\S+)-([0-9]+).+\s+([0-9]+\.[0-9]+):\s+ext4_ext_map_blocks_exit:\s+dev\s+(\S+)\s+ino\s+([0-9]+)\sflags.*\slblk\s+([0-9]+)\spblk\s([0-9]+)\slen\s+([0-9]+).*mflags\s(\S*)\sret\s([0-9]+)"""
#  init-1     [002] ...1     2.887119: block_bio_remap: 8,0 R 10010384 + 8 <- (259,18) 3998944
RE_BLOCK_BIO_REMAP = r""".+block_bio_remap:\s\d+,\d+\s\S+\s(\d+)\s\+\s\d+\s<-\s\([^\)]+\)\s(\d+)"""
# kworker/u9:1-83    [003] d..2     2.682991: block_rq_issue: 8,0 RA 0 () 10140208 + 32 [kworker/u9:1]
RE_BLOCK_RQ_ISSUE = r"""\s+\S+-([0-9]+).*\s+([0-9]+\.[0-9]+):\s+block_rq_issue:\s+([0-9]+)\,([0-9]+)\s+([RW]\S*)\s[0-9]+\s\([^\)]*\)\s([0-9]+)\s+\+\s+([0-9]+)\s+\[([^\]]+)\]"""

EXT4_SIZE_TO_BLOCK_SIZE = 8 # ext4: 4KB, block device block size: 512B

class FileAccess:
  def __init__(self, file):
    self.file = file
    self.accesses = []
    self.total_access = 0
    self.ext4_access_size_histogram = {} #key: read size, value: occurrence
    self.block_access_size_histogram = {}
    self.ext4_single_block_accesses = {} # process name, occurrence
    self.block_single_block_accesses = {} # process name, occurrence
    self.blocks_histogram = {} # K: offset, V: read counter

  def add_if_single_block(self, container, size, offset, process_name):
    if size != 1:
      return
    offsets = container.get(process_name)
    if not offsets:
      offsets = []
      container[process_name] = offsets
    offsets.append(offset)

  def add_access(self, time, offset, size, process_name, read_sizes):
    self.accesses.append((time, offset, size, process_name))
    self.total_access += size
    self.ext4_access_size_histogram[size] = self.ext4_access_size_histogram.get(size, 0) + 1
    read_offset = offset
    for s in read_sizes:
      self.block_access_size_histogram[s] = self.block_access_size_histogram.get(s, 0) + 1
      self.add_if_single_block(self.block_single_block_accesses, s, read_offset, process_name)
      read_offset += s
    for i in range(size):
      self.blocks_histogram[offset + i] = self.blocks_histogram.get(offset + i, 0) + 1
    self.add_if_single_block(self.ext4_single_block_accesses, size, offset, process_name)

  def add_merged_access(self, time, offsets, lens, process_names):
    total_read_offsets = set() # each read can overwrap. So count only once for block level counting
    for i in range(len(offsets)):
      self.accesses.append((time, offsets[i], lens[i], process_names[i]))
      self.ext4_access_size_histogram[lens[i]] = self.ext4_access_size_histogram.get(lens[i], 0) + 1
      self.add_if_single_block(self.ext4_single_block_accesses, lens[i], offsets[i], process_names[i])
      for j in range(len(lens)):
        total_read_offsets.add(offsets[i] + j)
    total_lens = len(total_read_offsets)
    start_offset = min(total_read_offsets)
    self.total_access += total_lens
    self.block_access_size_histogram[total_lens] = self.block_access_size_histogram.get(total_lens, 0) \
                                                   + 1
    self.add_if_single_block(self.block_single_block_accesses, total_lens, start_offset, \
                             process_names[0])
    for s in range(total_lens):
      self.blocks_histogram[start_offset + s] = self.blocks_histogram.get(start_offset + s, 0) + 1


  def dump(self):
    if len(self.ext4_access_size_histogram) > 1:
      print "   Ext4 access size histograms:", collections.OrderedDict( \
        sorted(self.ext4_access_size_histogram.items(), key = lambda item: item[0]))
    if len(self.ext4_single_block_accesses) > 0 and self.total_access > 1:
      print "   Ext4 single block accesses:", collections.OrderedDict( \
        sorted(self.ext4_single_block_accesses.items(), key = lambda item: item[1], reverse = True))
    if len(self.block_access_size_histogram) > 1:
      print "   Block access size histograms:", collections.OrderedDict( \
        sorted(self.block_access_size_histogram.items(), key = lambda item: item[0]))
    if len(self.block_single_block_accesses) > 0 and self.total_access > 1:
      print "   Block single block accesses:", collections.OrderedDict( \
        sorted(self.block_single_block_accesses.items(), key = lambda item: item[1], reverse = True))
    if self.total_access > 1:
      sorted_blocks_histogram = sorted(self.blocks_histogram.items(), key = lambda item: item[1], \
                                       reverse = True)
      prints = []
      repeating_reads_counter = 0
      for entry in sorted_blocks_histogram:
        offset = entry[0]
        counter = entry[1]
        if counter == 1:
          break
        prints.append(str(offset) + ":" + str(counter))
        repeating_reads_counter += (counter - 1)
      if len(prints) > 0:
        print "   repeating accesses", repeating_reads_counter, " offset:count ->", ','.join(prints)

class FileEvent:
  def __init__(self, open_time, file_name, process_name, inode, flags):
    self.file_name = file_name
    self.inode = inode
    self.total_open = 1
    self.processes = []
    self.processes.append((open_time, process_name, flags))
    self.read = FileAccess(self)
    self.write = FileAccess(self)


  def add_open(self, open_time, process_name, flags):
    self.processes.append((open_time, process_name, flags))
    self.total_open += 1

  def add_access(self, is_read, time, offset, size, process_name, read_sizes):
    if is_read:
      self.read.add_access(time, offset, size, process_name, read_sizes)
    else:
      self.write.add_access(time, offset, size, process_name, read_sizes)

  def add_merged_access(self, is_read, time, offsets, lens, process_names):
    if is_read:
      self.read.add_merged_access(time, offsets, lens, process_names)
    else:
      self.write.add_merged_access(time, offsets, lens, process_names)

  def dump(self, name_to_pid_map):
    print " ***filename %s, total reads %d, total writes %d, total open %d inode %s" \
          % (self.file_name, self.read.total_access, self.write.total_access, self.total_open,\
             self.inode)
    process_names = []
    for opener in self.processes:
      process_names.append(opener[1] + "-" + name_to_pid_map.get(opener[1], '?') + " t:" + \
                           str(opener[0]) + " flags:" + opener[2])
    print "  Processes opened this file:", ','.join(process_names)
    if self.read.total_access > 0:
      print "  ****Reads:"
      self.read.dump()
    if self.write.total_access > 0:
      print "  ****Writes:"
      self.write.dump()

  def dump_short(self):
    print "    filename %s, total reads %d, total writes %d" % (self.file_name,
      self.read.total_access, self.write.total_access)

class PendingAccess:
  def __init__(self, process_name, pid, time, dev, inode, lblk, pblk, len, fevent):
    self.process_name = process_name
    self.pid = pid
    self.time = time
    self.dev = dev
    self.inode = inode
    self.lblk = lblk
    self.pblk = pblk
    self.blk_len = len * EXT4_SIZE_TO_BLOCK_SIZE
    self.len = len
    self.fevent = fevent
    self.pending_accesses = set()
    for i in range(len):
      self.pending_accesses.add(i)
    self.access_sizes = [] # valid read for this file in block dev level.
    self.block_access_counter = 0

  def get_valid_access(self, block_offset, block_len):
    ext4_offset = block_offset / EXT4_SIZE_TO_BLOCK_SIZE
    if ext4_offset > self.len:
      return 0, 0
    ext4_len = block_len / EXT4_SIZE_TO_BLOCK_SIZE
    if (ext4_offset + ext4_len) > self.len:
      ext4_len = self.len - ext4_offset
    return ext4_offset, ext4_len

  def queue_block_access(self, ext4_offset, ext4_len):
    if ext4_len <= 0:
      return
    self.block_access_counter += 1
    ext4_blocks_accessed = 0
    for i in range(ext4_len):
      ext4_block_i = i + ext4_offset
      if ext4_block_i in self.pending_accesses:
        ext4_blocks_accessed += 1
        self.pending_accesses.remove(ext4_block_i)
    if ext4_blocks_accessed > 0:
      self.access_sizes.append(ext4_blocks_accessed)

  def handle_req_complete(self, time, is_read):
    self.fevent.add_access(is_read, self.time, self.lblk, self.len, self.process_name,\
                           self.access_sizes)

  def handle_merged_req(self, time, offsets, lens, names, is_read):
    self.fevent.add_merged_access(is_read, time, offsets, lens, names)

  def is_req_complete(self):
    return len(self.pending_accesses) == 0

  def is_req_started(self):
    return self.len is not len(self.pending_accesses)

class Trace:
  def __init__(self):
    self.files_per_device = {} # key: device, value: { key: inode, value; FileEvent }
    self.re_open = re.compile(RE_DO_SYS_OPEN)
    self.re_ext4_access = re.compile(RE_EXT4_MA_BLOCKS_EXIT)
    self.re_bio_remap = re.compile(RE_BLOCK_BIO_REMAP)
    self.re_block_issue = re.compile(RE_BLOCK_RQ_ISSUE)
    # req from ext4 that has not gone down to block level yet, K:block address,
    #  V: list of PendingRead
    self.pending_accesses = {}
    self.remap = {}
    self.process_names = {} # K: PID, V : name

  def handle_line(self, line):
    match = self.re_open.match(line)
    if match:
      self.handle_open(match)
      return
    match = self.re_ext4_access.match(line)
    if match:
      self.handle_ext4_block_exit(match)
      return
    match = self.re_bio_remap.match(line)
    if match:
      self.handle_bio_remap(match)
      return
    match = self.re_block_issue.match(line)
    if match:
      self.handle_block_issue(match)
      return

  def handle_open(self, match):
    pid = int(match.group(1))
    time = match.group(2)
    process_name = match.group(3)
    file_name = match.group(4)
    flag = match.group(5)
    inode = int(match.group(6))
    dev_name = None
    self.process_names[pid] = process_name
    #print "open", pid, process_name, file_name, inode
    for p in PARTITION_TO_DEVICE:
      if file_name.startswith(p):
        dev_name = PARTITION_TO_DEVICE[p]
    if not dev_name:
      if DBG:
        print "Ignore open for file", file_name
      return
    files = self.files_per_device[dev_name]
    fevent = files.get(inode)
    if not fevent:
      fevent = FileEvent(time, file_name, process_name, inode, flag)
      files[inode] = fevent
    else:
      fevent.add_open(time, process_name, flag)

  def handle_ext4_block_exit(self, match):
    process_name = match.group(1)
    pid = int(match.group(2))
    time = float(match.group(3))
    dev = match.group(4)
    inode = int(match.group(5))
    lblk = int(match.group(6))
    pblk = int(match.group(7)) * EXT4_SIZE_TO_BLOCK_SIZE # address in ext4 blocks, ...
    l = int(match.group(8))
    mflags = match.group(9)
    ret = int(match.group(10))
    if ret <= 0: # no block access
      return
    process_name = self.process_names.get(pid, process_name)
    if process_name == '<...>':
      process_name = "pid-" + str(pid)
    if DBG_ISSUE:
      print "ext4", pblk, l, inode, process_name
    files = self.files_per_device.get(dev)
    if not files:
      if DEVICE_TO_PARTITION.get(dev):
        files = {}
        self.files_per_device[dev] = files
      else:
        if DBG:
          print "access ignored for device", dev
        return
    fevent = files.get(inode)
    if not fevent:
      if DBG:
        print 'no open for device %s with inode %s' % (dev, inode)
      fevent = FileEvent(time, "unknown", process_name, inode, "-")
      files[inode] = fevent
    pending_access = PendingAccess(process_name, pid, time, dev, inode, lblk, pblk, l,\
                                   fevent)
    access_list = self.pending_accesses.get(pblk, [])
    access_list.append(pending_access)
    self.pending_accesses[pblk] = access_list

  def handle_bio_remap(self, match):
    new_addr = int(match.group(1))
    old_addr = int(match.group(2))
    self.remap[new_addr] = old_addr
    if DBG_ISSUE:
      print "remap", new_addr, old_addr

  def handle_block_issue(self, match):
    pid = int(match.group(1))
    time = float(match.group(2))
    dev_major = match.group(3)
    dev_minor = match.group(4)
    access = match.group(5)
    new_address = int(match.group(6))
    l = int(match.group(7))
    name = match.group(8)
    name = self.process_names.get(pid, name)
    if name == '<...>':
      name = "pid-" + str(pid)
    is_read = not 'W' in access
    accesses_per_inodes = {} # K:inodes, V: list of two entries, 1st: offsets, 2nd: length
    addrs_to_remove = []
    completed_reqs = []
    address = self.remap.get(new_address, new_address)
    if DBG_ISSUE:
      print "issue", address, l, is_read, access
    for access_addr, access_list in self.pending_accesses.iteritems():
      if (address >= access_addr) and (address + l) > access_addr:
        reqs_to_remove = []
        for pending in access_list:
          offset, valid_access_size = pending.get_valid_access(address - access_addr, l)
          if valid_access_size > 0:
            if pending.is_req_started(): # spread across multiple reads. complete alone
              pending.queue_block_access(offset, valid_access_size)
              if pending.is_req_complete():
                pending.handle_req_complete(time, is_read)
                reqs_to_remove.append(pending)
            else: # possible multiple reads completed in this read. complete them together
              pending.queue_block_access(offset, valid_access_size)
              if pending.is_req_complete():
                reads = accesses_per_inodes.get(pending.inode, [[], [], []])
                reads[0].append(offset + pending.lblk)
                reads[1].append(valid_access_size)
                reads[2].append(pending.process_name)
                accesses_per_inodes[pending.inode] = reads
                completed_reqs.append(pending)
                reqs_to_remove.append(pending)
        for to_remove in reqs_to_remove:
          access_list.remove(to_remove)
        if len(access_list) == 0:
          addrs_to_remove.append(access_addr)
    for addr in addrs_to_remove:
      del self.pending_accesses[addr]
    for pending in completed_reqs: # these will be reported as batch
      accesses = accesses_per_inodes.get(pending.inode)
      if not accesses: # merged one already dispatched
        continue
      if len(accesses[0]) == 1:
        pending.handle_req_complete(time, is_read)
      else: #merged
        pending.handle_merged_req(time, accesses[0], accesses[1], accesses[2], is_read)
        del accesses_per_inodes[pending.inode]

  def dump_partition(self, partition_name, files):
    name_to_pid_map = {}
    for pid, name in self.process_names.iteritems():
      name_to_pid_map[name] = str(pid)
    print "**Dump partition:", partition_name, "total number of files:", len(files)
    total_reads = 0
    total_writes = 0
    files_sorted_by_read = files.values()
    files_sorted_by_read.sort(key=lambda f : f.read.total_access, reverse = True)
    files_sorted_by_write = files.values()
    files_sorted_by_write.sort(key=lambda f : f.write.total_access, reverse = True)
    print " Top 10 readers:"
    for i in range(min(10, len(files_sorted_by_read))):
      files_sorted_by_read[i].dump_short()
    print " Top 10 writers:"
    for i in range(min(10, len(files_sorted_by_write))):
      files_sorted_by_write[i].dump_short()
    for f in files_sorted_by_read:
      f.dump(name_to_pid_map)
      total_reads += f.read.total_access
      total_writes += f.write.total_access
    print " Total reads:", total_reads, " total writes:", total_writes
    return total_reads, total_writes, len(files)


  def dump(self):
    print "*Dump R/W per each partition"
    total_reads = 0
    total_writes = 0
    summaries = []
    for d in self.files_per_device:
      reads, writes, num_files = self.dump_partition(DEVICE_TO_PARTITION[d], \
        self.files_per_device[d])
      total_reads += reads
      total_writes += writes
      summaries.append((DEVICE_TO_PARTITION[d], reads, writes, num_files))
    print "*Summary*"
    print "Total blocks read", total_reads
    print "Total blocks wrote", total_writes
    print "Partition total_reads total_writes num_files"
    for s in summaries:
      print s[0], s[1], s[2], s[3]

def main(argv):
  if (len(argv) < 2):
    print "check_file_read.py filename"
    return
  filename = argv[1]
  trace = Trace()
  with open(filename) as f:
    for l in f:
      trace.handle_line(l)
  trace.dump()

if __name__ == '__main__':
  main(sys.argv)
