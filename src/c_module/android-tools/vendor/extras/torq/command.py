#
# Copyright (C) 2024 The Android Open Source Project
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

from command_executor import ProfilerCommandExecutor, HWCommandExecutor,\
  ConfigCommandExecutor


class Command:
  def __init__(self, type):
    self.type = type

  def get_type(self):
    return self.type

  def execute(self):
    raise NotImplementedError

  def validate(self):
    raise NotImplementedError


class ProfilerCommand(Command):
  def __init__(self, type, event, profiler, out_dir, dur_ms, app, runs,
      simpleperf_event, perfetto_config, between_dur_ms, ui,
      exclude_ftrace_event, include_ftrace_event, from_user, to_user):
    super().__init__(type)
    self.event = event
    self.profiler = profiler
    self.out_dir = out_dir
    self.dur_ms = dur_ms
    self.app = app
    self.runs = runs
    self.simpleperf_event = simpleperf_event
    self.perfetto_config = perfetto_config
    self.between_dur_ms = between_dur_ms
    self.ui = ui
    self.exclude_ftrace_event = exclude_ftrace_event
    self.include_ftrace_event = include_ftrace_event
    self.from_user = from_user
    self.to_user = to_user

  def execute(self):
    command_executor = ProfilerCommandExecutor()
    command_executor.execute(self)

  def validate(self):
    print("Further validating arguments of ProfilerCommand.")
    return None


class HWCommand(Command):
  def __init__(self, type, config, num_cpus, memory):
    super().__init__(type)
    self.config = config
    self.num_cpus = num_cpus
    self.memory = memory

  def execute(self):
    command_executor = HWCommandExecutor()
    command_executor.execute(self)

  def validate(self):
    print("Further validating arguments of HWCommand.")
    return None


class ConfigCommand(Command):
  def __init__(self, type, config_name, file_path):
    super().__init__(type)
    self.config_name = config_name
    self.file_path = file_path

  def execute(self):
    conmand_executor = ConfigCommandExecutor()
    conmand_executor.execute(self)

  def validate(self):
    print("Further validating arguments of ConfigCommand.")
    return None
