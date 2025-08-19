#!/usr/bin/env python
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
"""Simpleperf runtest runner: run simpleperf runtests on host or on device.

For a simpleperf runtest like one_function test, it contains following steps:
1. Run simpleperf record command to record simpleperf_runtest_one_function's
   running samples, which is generated in perf.data.
2. Run simpleperf report command to parse perf.data, generate perf.report.
4. Parse perf.report and see if it matches expectation.

The information of all runtests is stored in runtest.conf.
"""

import os
import os.path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


class CallTreeNode(object):

  def __init__(self, name):
    self.name = name
    self.children = []

  def add_child(self, child):
    self.children.append(child)

  def __str__(self):
    return 'CallTreeNode:\n' + '\n'.join(self._dump(1))

  def _dump(self, indent):
    indent_str = '  ' * indent
    strs = [indent_str + self.name]
    for child in self.children:
      strs.extend(child._dump(indent + 1))
    return strs


class Symbol(object):

  def __init__(self, name, comm, overhead, children_overhead):
    self.name = name
    self.comm = comm
    self.overhead = overhead
    # children_overhead is the overhead sum of this symbol and functions
    # called by this symbol.
    self.children_overhead = children_overhead
    self.call_tree = None

  def set_call_tree(self, call_tree):
    self.call_tree = call_tree

  def __str__(self):
    strs = []
    strs.append('Symbol name=%s comm=%s overhead=%f children_overhead=%f' % (
        self.name, self.comm, self.overhead, self.children_overhead))
    if self.call_tree:
      strs.append('\t%s' % self.call_tree)
    return '\n'.join(strs)


class SymbolOverheadRequirement(object):

  def __init__(self, symbol_name=None, comm=None, min_overhead=None,
               max_overhead=None):
    self.symbol_name = symbol_name
    self.comm = comm
    self.min_overhead = min_overhead
    self.max_overhead = max_overhead

  def __str__(self):
    strs = []
    strs.append('SymbolOverheadRequirement')
    if self.symbol_name is not None:
      strs.append('symbol_name=%s' % self.symbol_name)
    if self.comm is not None:
      strs.append('comm=%s' % self.comm)
    if self.min_overhead is not None:
      strs.append('min_overhead=%f' % self.min_overhead)
    if self.max_overhead is not None:
      strs.append('max_overhead=%f' % self.max_overhead)
    return ' '.join(strs)

  def is_match(self, symbol):
    if self.symbol_name is not None:
      if self.symbol_name != symbol.name:
        return False
    if self.comm is not None:
      if self.comm != symbol.comm:
        return False
    return True

  def check_overhead(self, overhead):
    if self.min_overhead is not None:
      if self.min_overhead > overhead:
        return False
    if self.max_overhead is not None:
      if self.max_overhead < overhead:
        return False
    return True


class SymbolRelationRequirement(object):

  def __init__(self, symbol_name, comm=None):
    self.symbol_name = symbol_name
    self.comm = comm
    self.children = []

  def add_child(self, child):
    self.children.append(child)

  def __str__(self):
    return 'SymbolRelationRequirement:\n' + '\n'.join(self._dump(1))

  def _dump(self, indent):
    indent_str = '  ' * indent
    strs = [indent_str + self.symbol_name +
            (' ' + self.comm if self.comm else '')]
    for child in self.children:
      strs.extend(child._dump(indent + 1))
    return strs

  def is_match(self, symbol):
    if symbol.name != self.symbol_name:
      return False
    if self.comm is not None:
      if symbol.comm != self.comm:
        return False
    return True

  def check_relation(self, call_tree):
    if not call_tree:
      return False
    if self.symbol_name != call_tree.name:
      return False
    for child in self.children:
      child_matched = False
      for node in call_tree.children:
        if child.check_relation(node):
          child_matched = True
          break
      if not child_matched:
        return False
    return True


class Test(object):

  def __init__(
          self,
          test_name,
          executable_name,
          disable_host,
          record_options,
          report_options,
          symbol_overhead_requirements,
          symbol_children_overhead_requirements,
          symbol_relation_requirements):
    self.test_name = test_name
    self.executable_name = executable_name
    self.disable_host = disable_host
    self.record_options = record_options
    self.report_options = report_options
    self.symbol_overhead_requirements = symbol_overhead_requirements
    self.symbol_children_overhead_requirements = (
        symbol_children_overhead_requirements)
    self.symbol_relation_requirements = symbol_relation_requirements

  def __str__(self):
    strs = []
    strs.append('Test test_name=%s' % self.test_name)
    strs.append('\texecutable_name=%s' % self.executable_name)
    strs.append('\tdisable_host=%s' % self.disable_host)
    strs.append('\trecord_options=%s' % (' '.join(self.record_options)))
    strs.append('\treport_options=%s' % (' '.join(self.report_options)))
    strs.append('\tsymbol_overhead_requirements:')
    for req in self.symbol_overhead_requirements:
      strs.append('\t\t%s' % req)
    strs.append('\tsymbol_children_overhead_requirements:')
    for req in self.symbol_children_overhead_requirements:
      strs.append('\t\t%s' % req)
    strs.append('\tsymbol_relation_requirements:')
    for req in self.symbol_relation_requirements:
      strs.append('\t\t%s' % req)
    return '\n'.join(strs)


def load_config_file(config_file):
  tests = []
  tree = ET.parse(config_file)
  root = tree.getroot()
  assert root.tag == 'runtests'
  for test in root:
    assert test.tag == 'test'
    test_name = test.attrib['name']
    executable_name = None
    disable_host = False
    record_options = []
    report_options = []
    symbol_overhead_requirements = []
    symbol_children_overhead_requirements = []
    symbol_relation_requirements = []
    for test_item in test:
      if test_item.tag == 'executable':
        executable_name = test_item.attrib['name']
      elif test_item.tag == 'disable_host':
        disable_host = True
      elif test_item.tag == 'record':
        record_options = test_item.attrib['option'].split()
      elif test_item.tag == 'report':
        report_options = test_item.attrib['option'].split()
      elif (test_item.tag == 'symbol_overhead' or
              test_item.tag == 'symbol_children_overhead'):
        for symbol_item in test_item:
          assert symbol_item.tag == 'symbol'
          symbol_name = None
          if 'name' in symbol_item.attrib:
            symbol_name = symbol_item.attrib['name']
          comm = None
          if 'comm' in symbol_item.attrib:
            comm = symbol_item.attrib['comm']
          overhead_min = None
          if 'min' in symbol_item.attrib:
            overhead_min = float(symbol_item.attrib['min'])
          overhead_max = None
          if 'max' in symbol_item.attrib:
            overhead_max = float(symbol_item.attrib['max'])

          if test_item.tag == 'symbol_overhead':
            symbol_overhead_requirements.append(
                SymbolOverheadRequirement(
                    symbol_name,
                    comm,
                    overhead_min,
                    overhead_max)
            )
          else:
            symbol_children_overhead_requirements.append(
                SymbolOverheadRequirement(
                    symbol_name,
                    comm,
                    overhead_min,
                    overhead_max))
      elif test_item.tag == 'symbol_callgraph_relation':
        for symbol_item in test_item:
          req = load_symbol_relation_requirement(symbol_item)
          symbol_relation_requirements.append(req)

    tests.append(
        Test(
            test_name,
            executable_name,
            disable_host,
            record_options,
            report_options,
            symbol_overhead_requirements,
            symbol_children_overhead_requirements,
            symbol_relation_requirements))
  return tests


def load_symbol_relation_requirement(symbol_item):
  symbol_name = symbol_item.attrib['name']
  comm = None
  if 'comm' in symbol_item.attrib:
    comm = symbol_item.attrib['comm']
  req = SymbolRelationRequirement(symbol_name, comm)
  for item in symbol_item:
    child_req = load_symbol_relation_requirement(item)
    req.add_child(child_req)
  return req


class Runner(object):

  def __init__(self, target, perf_path):
    self.target = target
    self.is32 = target.endswith('32')
    self.perf_path = perf_path
    self.use_callgraph = False
    self.sampler = 'cpu-cycles'

  def record(self, test_executable_name, record_file, additional_options=[]):
    call_args = [self.perf_path, 'record']
    call_args += ['--duration', '2']
    call_args += ['-e', '%s:u' % self.sampler]
    if self.use_callgraph:
      call_args += ['-f', '1000', '-g']
    call_args += ['-o', record_file]
    call_args += additional_options
    test_executable_name += '32' if self.is32 else '64'
    call_args += [test_executable_name]
    self._call(call_args)

  def report(self, record_file, report_file, additional_options=[]):
    call_args = [self.perf_path, 'report']
    call_args += ['-i', record_file]
    if self.use_callgraph:
      call_args += ['-g', 'callee']
    call_args += additional_options
    self._call(call_args, report_file)

  def _call(self, args, output_file=None):
    pass


class HostRunner(Runner):

  """Run perf test on host."""

  def __init__(self, target):
    perf_path = 'simpleperf32' if target.endswith('32') else 'simpleperf'
    super(HostRunner, self).__init__(target, perf_path)

  def _call(self, args, output_file=None):
    output_fh = None
    if output_file is not None:
      output_fh = open(output_file, 'w')
    subprocess.check_call(args, stdout=output_fh)
    if output_fh is not None:
      output_fh.close()


class DeviceRunner(Runner):

  """Run perf test on device."""

  def __init__(self, target):
    self.tmpdir = '/data/local/tmp/'
    perf_path = 'simpleperf32' if target.endswith('32') else 'simpleperf'
    super(DeviceRunner, self).__init__(target, self.tmpdir + perf_path)
    self._download(os.environ['OUT'] + '/system/xbin/' + perf_path, self.tmpdir)

  def _call(self, args, output_file=None):
    output_fh = None
    if output_file is not None:
      output_fh = open(output_file, 'w')
    args_with_adb = ['adb', 'shell']
    args_with_adb.append('export LD_LIBRARY_PATH=' + self.tmpdir + ' && ' + ' '.join(args))
    subprocess.check_call(args_with_adb, stdout=output_fh)
    if output_fh is not None:
      output_fh.close()

  def _download(self, file, to_dir):
    args = ['adb', 'push', file, to_dir]
    subprocess.check_call(args)

  def record(self, test_executable_name, record_file, additional_options=[]):
    self._download(os.environ['OUT'] + '/system/bin/' + test_executable_name +
                   ('32' if self.is32 else '64'), self.tmpdir)
    super(DeviceRunner, self).record(self.tmpdir + test_executable_name,
                                     self.tmpdir + record_file,
                                     additional_options)

  def report(self, record_file, report_file, additional_options=[]):
    super(DeviceRunner, self).report(self.tmpdir + record_file,
                                     report_file,
                                     additional_options)

class ReportAnalyzer(object):

  """Check if perf.report matches expectation in Configuration."""

  def _read_report_file(self, report_file, has_callgraph):
    fh = open(report_file, 'r')
    lines = fh.readlines()
    fh.close()

    lines = [x.rstrip() for x in lines]
    blank_line_index = -1
    for i in range(len(lines)):
      if not lines[i]:
        blank_line_index = i
    assert blank_line_index != -1
    assert blank_line_index + 1 < len(lines)
    title_line = lines[blank_line_index + 1]
    report_item_lines = lines[blank_line_index + 2:]

    if has_callgraph:
      assert re.search(r'^Children\s+Self\s+Command.+Symbol$', title_line)
    else:
      assert re.search(r'^Overhead\s+Command.+Symbol$', title_line)

    return self._parse_report_items(report_item_lines, has_callgraph)

  def _parse_report_items(self, lines, has_callgraph):
    symbols = []
    cur_symbol = None
    call_tree_stack = {}
    vertical_columns = []
    last_node = None
    last_depth = -1

    for line in lines:
      if not line:
        continue
      if not line[0].isspace():
        if has_callgraph:
          items = line.split(None, 6)
          assert len(items) == 7
          children_overhead = float(items[0][:-1])
          overhead = float(items[1][:-1])
          comm = items[2]
          symbol_name = items[6]
          cur_symbol = Symbol(symbol_name, comm, overhead, children_overhead)
          symbols.append(cur_symbol)
        else:
          items = line.split(None, 5)
          assert len(items) == 6
          overhead = float(items[0][:-1])
          comm = items[1]
          symbol_name = items[5]
          cur_symbol = Symbol(symbol_name, comm, overhead, 0)
          symbols.append(cur_symbol)
        # Each report item can have different column depths.
        vertical_columns = []
      else:
        for i in range(len(line)):
          if line[i] == '|':
            if not vertical_columns or vertical_columns[-1] < i:
              vertical_columns.append(i)

        if not line.strip('| \t'):
          continue
        if line.find('-') == -1:
          function_name = line.strip('| \t')
          node = CallTreeNode(function_name)
          last_node.add_child(node)
          last_node = node
          call_tree_stack[last_depth] = node
        else:
          pos = line.find('-')
          depth = -1
          for i in range(len(vertical_columns)):
            if pos >= vertical_columns[i]:
              depth = i
          assert depth != -1

          line = line.strip('|- \t')
          m = re.search(r'^[\d\.]+%[-\s]+(.+)$', line)
          if m:
            function_name = m.group(1)
          else:
            function_name = line

          node = CallTreeNode(function_name)
          if depth == 0:
            cur_symbol.set_call_tree(node)

          else:
            call_tree_stack[depth - 1].add_child(node)
          call_tree_stack[depth] = node
          last_node = node
          last_depth = depth

    return symbols

  def check_report_file(self, test, report_file, has_callgraph):
    symbols = self._read_report_file(report_file, has_callgraph)
    if not self._check_symbol_overhead_requirements(test, symbols):
      return False
    if has_callgraph:
      if not self._check_symbol_children_overhead_requirements(test, symbols):
        return False
      if not self._check_symbol_relation_requirements(test, symbols):
        return False
    return True

  def _check_symbol_overhead_requirements(self, test, symbols):
    result = True
    matched = [False] * len(test.symbol_overhead_requirements)
    matched_overhead = [0] * len(test.symbol_overhead_requirements)
    for symbol in symbols:
      for i in range(len(test.symbol_overhead_requirements)):
        req = test.symbol_overhead_requirements[i]
        if req.is_match(symbol):
          matched[i] = True
          matched_overhead[i] += symbol.overhead
    for i in range(len(matched)):
      if not matched[i]:
        print 'requirement (%s) has no matched symbol in test %s' % (
            test.symbol_overhead_requirements[i], test)
        result = False
      else:
        fulfilled = req.check_overhead(matched_overhead[i])
        if not fulfilled:
          print "Symbol (%s) doesn't match requirement (%s) in test %s" % (
              symbol, req, test)
          result = False
    return result

  def _check_symbol_children_overhead_requirements(self, test, symbols):
    result = True
    matched = [False] * len(test.symbol_children_overhead_requirements)
    for symbol in symbols:
      for i in range(len(test.symbol_children_overhead_requirements)):
        req = test.symbol_children_overhead_requirements[i]
        if req.is_match(symbol):
          matched[i] = True
          fulfilled = req.check_overhead(symbol.children_overhead)
          if not fulfilled:
            print "Symbol (%s) doesn't match requirement (%s) in test %s" % (
                symbol, req, test)
            result = False
    for i in range(len(matched)):
      if not matched[i]:
        print 'requirement (%s) has no matched symbol in test %s' % (
            test.symbol_children_overhead_requirements[i], test)
        result = False
    return result

  def _check_symbol_relation_requirements(self, test, symbols):
    result = True
    matched = [False] * len(test.symbol_relation_requirements)
    for symbol in symbols:
      for i in range(len(test.symbol_relation_requirements)):
        req = test.symbol_relation_requirements[i]
        if req.is_match(symbol):
          matched[i] = True
          fulfilled = req.check_relation(symbol.call_tree)
          if not fulfilled:
            print "Symbol (%s) doesn't match requirement (%s) in test %s" % (
                symbol, req, test)
            result = False
    for i in range(len(matched)):
      if not matched[i]:
        print 'requirement (%s) has no matched symbol in test %s' % (
            test.symbol_relation_requirements[i], test)
        result = False
    return result


def build_runner(target, use_callgraph, sampler):
  if target == 'host32' and use_callgraph:
    print "Current 64bit linux host doesn't support `simpleperf32 record -g`"
    return None
  if target.startswith('host'):
    runner = HostRunner(target)
  else:
    runner = DeviceRunner(target)
  runner.use_callgraph = use_callgraph
  runner.sampler = sampler
  return runner


def test_with_runner(runner, tests):
  report_analyzer = ReportAnalyzer()
  for test in tests:
    if test.disable_host and runner.target.startswith('host'):
      print('Skip test %s on %s' % (test.test_name, runner.target))
      continue
    runner.record(test.executable_name, 'perf.data', additional_options = test.record_options)
    runner.report('perf.data', 'perf.report', additional_options = test.report_options)
    result = report_analyzer.check_report_file(test, 'perf.report', runner.use_callgraph)
    str = 'test %s on %s ' % (test.test_name, runner.target)
    if runner.use_callgraph:
      str += 'with call graph '
    str += 'using %s ' % runner.sampler
    str += ' Succeeded' if result else 'Failed'
    print str
    if not result:
      exit(1)


def runtest(target_options, use_callgraph_options, sampler_options, selected_tests):
  tests = load_config_file(os.path.dirname(os.path.realpath(__file__)) + \
                           '/runtest.conf')
  if selected_tests is not None:
    new_tests = []
    for test in tests:
      if test.test_name in selected_tests:
        new_tests.append(test)
    tests = new_tests
  for target in target_options:
    for use_callgraph in use_callgraph_options:
      for sampler in sampler_options:
        runner = build_runner(target, use_callgraph, sampler)
        if runner is not None:
          test_with_runner(runner, tests)


def main():
  target_options = ['host64', 'host32', 'device64', 'device32']
  use_callgraph_options = [False, True]
  sampler_options = ['cpu-cycles']
  selected_tests = None
  i = 1
  while i < len(sys.argv):
    if sys.argv[i] == '--host':
      target_options = ['host64', 'host32']
    elif sys.argv[i] == '--device':
      target_options = ['device64', 'device32']
    elif sys.argv[i] == '--normal':
      use_callgraph_options = [False]
    elif sys.argv[i] == '--callgraph':
      use_callgraph_options = [True]
    elif sys.argv[i] == '--test':
      if i < len(sys.argv):
        i += 1
        for test in sys.argv[i].split(','):
          if selected_tests is None:
            selected_tests = {}
          selected_tests[test] = True
    i += 1
  runtest(target_options, use_callgraph_options, sampler_options, selected_tests)

if __name__ == '__main__':
  main()
