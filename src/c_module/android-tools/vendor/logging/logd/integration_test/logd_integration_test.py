#!/usr/bin/env python3
#
# Copyright (C) 2023 The Android Open Source Project
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

import re
import subprocess
import unittest

KNOWN_NON_LOGGING_SERVICES = [
    "vendor.ir-default",

    "SELF_TEST_SERVICE_DOES_NOT_EXIST",
]

KNOWN_LOGGING_SERVICES = [
    "zygote",

    # b/210919187 - main log is too busy, gets dropped off
    # "statsd",
    # "vendor.audio-hal-aidl",

    "SELF_TEST_SERVICE_DOES_NOT_EXIST",
]

def device_log(log):
    ret = subprocess.check_output(["adb", "shell", "log", "-t", "logd_integration_test", log]).decode()
    assert len(ret) == 0, f"Expected no output, but found '{ret}'"

def get_service_pid(svc):
    return int(subprocess.check_output(["adb", "shell", "getprop", "init.svc_debug_pid." + svc]))

def get_pid_logs(pid):
    return subprocess.check_output(["adb", "logcat", "--pid", str(pid), "-d"]).decode()

def get_product_name():
    return subprocess.check_output(["adb", "shell", "getprop", "ro.product.name"]).decode()

def iter_service_pids(test_case, services):
    a_service_worked = False
    for service in services:
        try:
            yield service, get_service_pid(service)
            a_service_worked = True
        except subprocess.CalledProcessError:
            continue
        except ValueError:
            continue
    test_case.assertTrue(a_service_worked)

def get_dropped_logs(test_case, buffer):
        output = subprocess.check_output(["adb", "logcat", "-b", buffer, "--statistics"]).decode()
        lines = iter(output.split("\n"))

        res = []

        # Search for these lines, in order. Consider output:
        # :) adb logcat -b system -S | grep -E "Total|Now"
        # size/num system             Total
        # Total    883973/6792        883973/6792
        # Now      883973/6792        883973/6792
        for indication in ["Total", "Now"]:
            reLineCount = re.compile(f"^{indication}.*\s+[0-9]+/([0-9]+)")
            while True:
                line = next(lines)
                match = reLineCount.match(line)
                if match:
                    res.append(int(match.group(1)))
                    break

        total, now = res
        return total, now, output

class LogdIntegrationTest(unittest.TestCase):
    def subTest(self, subtest_name):
        """install logger for all subtests"""

        class SubTestLogger:
            def __init__(self, testcase, subtest_name):
                self.subtest_name = subtest_name
                self.subtest = testcase.subTest(subtest_name)
            def __enter__(self):
                device_log(f"Starting subtest {subtest_name}")
                return self.subtest.__enter__()
            def __exit__(self, *args):
                device_log(f"Ending subtest {subtest_name}")
                return self.subtest.__exit__(*args)

        return SubTestLogger(super(), subtest_name)

    def test_no_logs(self):
        for service, pid in iter_service_pids(self, KNOWN_NON_LOGGING_SERVICES):
            with self.subTest(service + "_no_logs"):
                lines = get_pid_logs(pid)
                self.assertFalse("\n" in lines, f"{service} ({pid}) shouldn't have logs, but found: {lines}")

    def test_has_logs(self):
        for service, pid in iter_service_pids(self, KNOWN_LOGGING_SERVICES):
            with self.subTest(service + "_has_logs"):
                lines = get_pid_logs(pid)
                self.assertTrue("\n" in lines, f"{service} ({pid}) should have logs, but found: {lines}")

    def test_no_dropped_logs(self):
        dropped_buffer_allowed = {
            "crash": 0,
            "kernel": 0,
            "main": 4000,
            "system": 0 if get_product_name().startswith("aosp") else 10000,
        }

        for buffer, allowed in dropped_buffer_allowed.items():
            with self.subTest(buffer + "_buffer_not_dropped"):
                total, now, output = get_dropped_logs(self, buffer)
                dropped = total - now

                self.assertLessEqual(dropped, allowed,
                    f"Buffer {buffer} has {dropped} dropped logs (now {now} out of {total} total logs), but expecting <= {allowed}. {output}")

def main():
    unittest.main(verbosity=3)

if __name__ == "__main__":
    main()
