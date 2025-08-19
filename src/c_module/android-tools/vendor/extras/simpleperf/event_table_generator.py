#!/usr/bin/env python3
#
# Copyright (C) 2015 The Android Open Source Project
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

import dataclasses
from dataclasses import dataclass
import json
import sys


def gen_event_type_entry_str(event_type_name, event_type, event_config, description='',
                             limited_arch=''):
    return '{"%s", %s, %s, "%s", "%s"},\n' % (
        event_type_name, event_type, event_config, description, limited_arch)


def gen_hardware_events():
    hardware_configs = ["cpu-cycles",
                        "instructions",
                        "cache-references",
                        "cache-misses",
                        "branch-instructions",
                        "branch-misses",
                        "bus-cycles",
                        "stalled-cycles-frontend",
                        "stalled-cycles-backend",
                        ]
    generated_str = ""
    for config in hardware_configs:
        event_type_name = config
        event_config = "PERF_COUNT_HW_" + config.replace('-', '_').upper()

        generated_str += gen_event_type_entry_str(
            event_type_name, "PERF_TYPE_HARDWARE", event_config)

    return generated_str


def gen_software_events():
    software_configs = ["cpu-clock",
                        "task-clock",
                        "page-faults",
                        "context-switches",
                        "cpu-migrations",
                        ["minor-faults", "PERF_COUNT_SW_PAGE_FAULTS_MIN"],
                        ["major-faults", "PERF_COUNT_SW_PAGE_FAULTS_MAJ"],
                        "alignment-faults",
                        "emulation-faults",
                        ]
    generated_str = ""
    for config in software_configs:
        if isinstance(config, list):
            event_type_name = config[0]
            event_config = config[1]
        else:
            event_type_name = config
            event_config = "PERF_COUNT_SW_" + config.replace('-', '_').upper()

        generated_str += gen_event_type_entry_str(
            event_type_name, "PERF_TYPE_SOFTWARE", event_config)

    return generated_str


def gen_hw_cache_events():
    hw_cache_types = [["L1-dcache", "PERF_COUNT_HW_CACHE_L1D"],
                      ["L1-icache", "PERF_COUNT_HW_CACHE_L1I"],
                      ["LLC", "PERF_COUNT_HW_CACHE_LL"],
                      ["dTLB", "PERF_COUNT_HW_CACHE_DTLB"],
                      ["iTLB", "PERF_COUNT_HW_CACHE_ITLB"],
                      ["branch", "PERF_COUNT_HW_CACHE_BPU"],
                      ["node", "PERF_COUNT_HW_CACHE_NODE"],
                      ]
    hw_cache_ops = [["loads", "load", "PERF_COUNT_HW_CACHE_OP_READ"],
                    ["stores", "store", "PERF_COUNT_HW_CACHE_OP_WRITE"],
                    ["prefetches", "prefetch",
                     "PERF_COUNT_HW_CACHE_OP_PREFETCH"],
                    ]
    hw_cache_op_results = [["accesses", "PERF_COUNT_HW_CACHE_RESULT_ACCESS"],
                           ["misses", "PERF_COUNT_HW_CACHE_RESULT_MISS"],
                           ]
    generated_str = ""
    for (type_name, type_config) in hw_cache_types:
        for (op_name_access, op_name_miss, op_config) in hw_cache_ops:
            for (result_name, result_config) in hw_cache_op_results:
                if result_name == "accesses":
                    event_type_name = type_name + '-' + op_name_access
                else:
                    event_type_name = type_name + '-' + \
                        op_name_miss + '-' + result_name
                event_config = "((%s) | (%s << 8) | (%s << 16))" % (
                    type_config, op_config, result_config)
                generated_str += gen_event_type_entry_str(
                    event_type_name, "PERF_TYPE_HW_CACHE", event_config)

    return generated_str


@dataclass
class RawEvent:
    number: int
    name: str
    desc: str
    limited_arch: str


@dataclass
class CpuModel:
    name: str
    implementer: int
    partnum: int
    supported_raw_events: list[int] = dataclasses.field(default_factory=list)


class ArchData:
    def __init__(self, arch: str):
        self.arch = arch
        self.events: List[RawEvent] = []
        self.cpus: List[CpuModel] = []

    def load_from_json_data(self, data) -> None:
        # Load common events
        for event in data['events']:
            number = int(event[0], 16)
            name = 'raw-' + event[1].lower().replace('_', '-')
            desc = event[2]
            self.events.append(RawEvent(number, name, desc, self.arch))
        for cpu in data['cpus']:
            cpu_name = cpu['name'].lower().replace('_', '-')
            cpu_model = CpuModel(cpu['name'], int(cpu['implementer'], 16),
                                 int(cpu['partnum'], 16), [])
            cpu_index = len(self.cpus)
            self.cpus.append(cpu_model)
            # Load common events supported in this cpu model.
            for number in cpu['common_events']:
                number = int(number, 16)
                event = self.get_event(number)
                cpu_model.supported_raw_events.append(number)

            # Load cpu specific events supported in this cpu model.
            if 'implementation_defined_events' in cpu:
                for event in cpu['implementation_defined_events']:
                    number = int(event[0], 16)
                    name = ('raw-' + cpu_name + '-' + event[1]).lower().replace('_', '-')
                    desc = event[2]
                    limited_arch = self.arch + ':' + cpu['name']
                    self.events.append(RawEvent(number, name, desc, limited_arch))
                    cpu_model.supported_raw_events.append(number)

    def get_event(self, event_number: int) -> RawEvent:
        for event in self.events:
            if event.number == event_number:
                return event
        raise Exception(f'no event for event number {event_number}')


class RawEventGenerator:
    def __init__(self, event_table_file: str):
        with open(event_table_file, 'r') as fh:
            event_table = json.load(fh)
            self.arm64_data = ArchData('arm64')
            self.arm64_data.load_from_json_data(event_table['arm64'])

    def generate_raw_events(self) -> str:
        lines = []
        for event in self.arm64_data.events:
            lines.append(gen_event_type_entry_str(event.name, 'PERF_TYPE_RAW', '0x%x' %
                         event.number, event.desc, event.limited_arch))
        return self.add_arm_guard(''.join(lines))

    def generate_cpu_support_events(self) -> str:
        text = """
        // Map from cpu model to raw events supported on that cpu.',
        std::unordered_map<std::string, std::unordered_set<int>> cpu_supported_raw_events = {
        """

        lines = []
        for cpu in self.arm64_data.cpus:
            event_list = ', '.join('0x%x' % number for number in cpu.supported_raw_events)
            lines.append('{"%s", {%s}},' % (cpu.name, event_list))
        text += self.add_arm_guard('\n'.join(lines))
        text += '};\n'
        return text

    def generate_cpu_models(self) -> str:
        text = """
        std::unordered_map<uint64_t, std::string> arm64_cpuid_to_name = {
        """
        lines = []
        for cpu in self.arm64_data.cpus:
            cpu_id = (cpu.implementer << 32) | cpu.partnum
            lines.append('{0x%xull, "%s"},' % (cpu_id, cpu.name))
        text += '\n'.join(lines)
        text += '};\n'
        return self.add_arm_guard(text)

    def add_arm_guard(self, data: str) -> str:
        return f'#if defined(__aarch64__) || defined(__arm__)\n{data}\n#endif\n'


def gen_events(event_table_file: str):
    generated_str = """
        #include <unordered_map>
        #include <unordered_set>

        #include "event_type.h"

        namespace simpleperf {

        std::set<EventType> builtin_event_types = {
    """
    generated_str += gen_hardware_events() + '\n'
    generated_str += gen_software_events() + '\n'
    generated_str += gen_hw_cache_events() + '\n'
    raw_event_generator = RawEventGenerator(event_table_file)
    generated_str += raw_event_generator.generate_raw_events() + '\n'
    generated_str += """
        };


    """
    generated_str += raw_event_generator.generate_cpu_support_events()
    generated_str += raw_event_generator.generate_cpu_models()

    generated_str += """
        }  // namespace simpleperf
    """
    return generated_str


def main():
    event_table_file = sys.argv[1]
    output_file = sys.argv[2]
    generated_str = gen_events(event_table_file)
    with open(output_file, 'w') as fh:
        fh.write(generated_str)


if __name__ == '__main__':
    main()
