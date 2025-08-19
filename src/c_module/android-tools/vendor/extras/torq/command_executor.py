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

class CommandExecutor:
  def __init__(self):
    raise NotImplementedError

  def execute(self, command):
    error = command.validate()
    if error is not None:
      return error
    print("executing", command.get_type(), "command")
    return None


class ProfilerCommandExecutor(CommandExecutor):
  def __init__(self):
    pass

  def execute(self, profiler_command):
    super().execute(profiler_command)


class HWCommandExecutor(CommandExecutor):
  def __init__(self):
    pass

  def execute(self, hw_command):
    super().execute(hw_command)


class ConfigCommandExecutor(CommandExecutor):
  def __init__(self):
    pass

  def execute(self, config_command):
    super().execute(config_command)