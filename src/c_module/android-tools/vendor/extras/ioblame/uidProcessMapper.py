#!/usr/bin/env python
#
# Copyright (C) 2022 The Android Open Source Project
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
"""Package <-> UID <-> Process mapper."""

import re

# ex) Name:   init
PROC_STATUS_NAME_LINE = r"Name:\s+(\S+)"

# ex) Pid:    1
PROC_STATUS_PID_LINE = r"Pid:\s+([0-9]+)"

# ex) Uid:    0       0       0       0
PROC_STATUS_UID_LINE = r"Uid:\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)"

# ex) package:com.google.android.car.uxr.sample uid:1000
PACKAGE_UID_LINE = r"package:(\S+)\suid:([0-9]+)"

USER_ID_OFFSET = 100000
AID_APP_START = 10000
UNKNOWN_UID = -1


class UidInfo:

  def __init__(self, uid, packageName=None):
    self.uid = uid
    self.packageName = packageName

  def to_string(self):
    appId = int(self.uid % USER_ID_OFFSET)
    if self.uid == UNKNOWN_UID:
      return "UID: UNKNOWN"
    elif self.packageName is None and appId < AID_APP_START:
      return "User ID: {}, Native service AID: {}".format(
          int(self.uid / USER_ID_OFFSET), appId)
    elif self.packageName is None:
      return "User ID: {}, App ID: {}".format(
          int(self.uid / USER_ID_OFFSET), appId)
    else:
      return "User ID: {}, Package name: {}".format(
          int(self.uid / USER_ID_OFFSET), self.packageName)


class UidProcessMapper:

  def __init__(self):
    self.nameReMatcher = re.compile(PROC_STATUS_NAME_LINE)
    self.pidReMatcher = re.compile(PROC_STATUS_PID_LINE)
    self.uidReMatcher = re.compile(PROC_STATUS_UID_LINE)
    self.packageUidMatcher = re.compile(PACKAGE_UID_LINE)
    self.uidByProcessDict = {}  # Key: Process Name, Value: {PID: UID}
    self.packageNameByAppId = {}  # Key: App ID, Value: Package name

  def parse_proc_status_dump(self, dump):
    name, pid, uid = "", "", ""

    for line in dump.split("\n"):
      if line.startswith("Name:"):
        name = self.match_re(self.nameReMatcher, line)
        pid, uid = "", ""
      elif line.startswith("Pid:"):
        pid = self.match_re(self.pidReMatcher, line)
        uid = ""
      elif line.startswith("Uid:"):
        uid = self.match_re(self.uidReMatcher, line)
        if name != "" and pid != "" and uid != "":
          self.add_mapping(name, int(pid), int(uid))
        name, pid, uid = "", "", ""

  def parse_uid_package_dump(self, dump):
    for line in dump.split("\n"):
      if line == "":
        continue

      match = self.packageUidMatcher.match(line)
      if (match):
        packageName = match.group(1)
        appId = int(match.group(2))
        if appId in self.packageNameByAppId:
          self.packageNameByAppId[appId].add(packageName)
        else:
          self.packageNameByAppId[appId] = {packageName}
      else:
        print("'{}' line doesn't match '{}' regex".format(
            line, self.packageUidMatcher))

  def match_re(self, reMatcher, line):
    match = reMatcher.match(line)
    if not match:
      return ""
    return match.group(1)

  def add_mapping(self, name, pid, uid):
    if name in self.uidByProcessDict:
      self.uidByProcessDict[name][pid] = uid
    else:
      self.uidByProcessDict[name] = {pid: uid}

  def get_uid(self, name, pid):
    if name in self.uidByProcessDict:
      if pid in self.uidByProcessDict[name]:
        return self.uidByProcessDict[name][pid]
    return UNKNOWN_UID

  def get_uid_info(self, uid):
    appId = uid % USER_ID_OFFSET
    if appId in self.packageNameByAppId:
      return UidInfo(uid, " | ".join(self.packageNameByAppId[appId]))
    else:
      return UidInfo(uid)
