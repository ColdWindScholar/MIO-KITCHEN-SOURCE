#!/usr/bin/env python3

import curses
import operator
import optparse
import os
import re
import subprocess
import sys
import threading
import queue

STATS_UPDATE_INTERVAL = 0.2
PAGE_SIZE = 4096

class PagecacheStats:
  """Holds pagecache stats by accounting for pages added and removed.

  """
  def __init__(self, inode_to_filename):
    self._inode_to_filename = inode_to_filename
    self._file_size = {}
    self._file_pages = {}
    self._total_pages_added = 0
    self._total_pages_removed = 0

  def add_page(self, device_number, inode, offset):
    # See if we can find the page in our lookup table
    if (device_number, inode) in self._inode_to_filename:
      filename, filesize = self._inode_to_filename[(device_number, inode)]
      if filename not in self._file_pages:
        self._file_pages[filename] = [1, 0]
      else:
        self._file_pages[filename][0] += 1

      self._total_pages_added += 1

      if filename not in self._file_size:
        self._file_size[filename] = filesize

  def remove_page(self, device_number, inode, offset):
    if (device_number, inode) in self._inode_to_filename:
      filename, filesize = self._inode_to_filename[(device_number, inode)]
      if filename not in self._file_pages:
        self._file_pages[filename] = [0, 1]
      else:
        self._file_pages[filename][1] += 1

      self._total_pages_removed += 1

      if filename not in self._file_size:
        self._file_size[filename] = filesize

  def pages_to_mb(self, num_pages):
    return "%.2f" % round(num_pages * PAGE_SIZE / 1024.0 / 1024.0, 2)

  def bytes_to_mb(self, num_bytes):
    return "%.2f" % round(int(num_bytes) / 1024.0 / 1024.0, 2)

  def print_pages_and_mb(self, num_pages):
    pages_string = str(num_pages) + ' (' + str(self.pages_to_mb(num_pages)) + ' MB)'
    return pages_string

  def reset_stats(self):
    self._file_pages.clear()
    self._total_pages_added = 0
    self._total_pages_removed = 0

  def print_stats(self):
    # Create new merged dict
    sorted_added = sorted(list(self._file_pages.items()), key=operator.itemgetter(1), reverse=True)
    row_format = "{:<70}{:<12}{:<14}{:<9}"
    print(row_format.format('NAME', 'ADDED (MB)', 'REMOVED (MB)', 'SIZE (MB)'))
    for filename, added in sorted_added:
      filesize = self._file_size[filename]
      added = self._file_pages[filename][0]
      removed = self._file_pages[filename][1]
      if len(filename) > 64:
        filename = filename[-64:]
      print(row_format.format(filename, self.pages_to_mb(added), self.pages_to_mb(removed), self.bytes_to_mb(filesize)))

    print(row_format.format('TOTAL', self.pages_to_mb(self._total_pages_added), self.pages_to_mb(self._total_pages_removed), ''))

  def print_stats_curses(self, pad):
    sorted_added = sorted(list(self._file_pages.items()), key=operator.itemgetter(1), reverse=True)
    height, width = pad.getmaxyx()
    pad.clear()
    pad.addstr(0, 2, 'NAME'.ljust(68), curses.A_REVERSE)
    pad.addstr(0, 70, 'ADDED (MB)'.ljust(12), curses.A_REVERSE)
    pad.addstr(0, 82, 'REMOVED (MB)'.ljust(14), curses.A_REVERSE)
    pad.addstr(0, 96, 'SIZE (MB)'.ljust(9), curses.A_REVERSE)
    y = 1
    for filename, added_removed in sorted_added:
      filesize = self._file_size[filename]
      added  = self._file_pages[filename][0]
      removed = self._file_pages[filename][1]
      if len(filename) > 64:
        filename = filename[-64:]
      pad.addstr(y, 2, filename)
      pad.addstr(y, 70, self.pages_to_mb(added).rjust(10))
      pad.addstr(y, 80, self.pages_to_mb(removed).rjust(14))
      pad.addstr(y, 96, self.bytes_to_mb(filesize).rjust(9))
      y += 1
      if y == height - 2:
        pad.addstr(y, 4, "<more...>")
        break
    y += 1
    pad.addstr(y, 2, 'TOTAL'.ljust(74), curses.A_REVERSE)
    pad.addstr(y, 70, str(self.pages_to_mb(self._total_pages_added)).rjust(10), curses.A_REVERSE)
    pad.addstr(y, 80, str(self.pages_to_mb(self._total_pages_removed)).rjust(14), curses.A_REVERSE)
    pad.refresh(0,0, 0,0, height,width)

class FileReaderThread(threading.Thread):
  """Reads data from a file/pipe on a worker thread.

  Use the standard threading. Thread object API to start and interact with the
  thread (start(), join(), etc.).
  """

  def __init__(self, file_object, output_queue, text_file, chunk_size=-1):
    """Initializes a FileReaderThread.

    Args:
      file_object: The file or pipe to read from.
      output_queue: A queue.Queue object that will receive the data
      text_file: If True, the file will be read one line at a time, and
          chunk_size will be ignored.  If False, line breaks are ignored and
          chunk_size must be set to a positive integer.
      chunk_size: When processing a non-text file (text_file = False),
          chunk_size is the amount of data to copy into the queue with each
          read operation.  For text files, this parameter is ignored.
    """
    threading.Thread.__init__(self)
    self._file_object = file_object
    self._output_queue = output_queue
    self._text_file = text_file
    self._chunk_size = chunk_size
    assert text_file or chunk_size > 0

  def run(self):
    """Overrides Thread's run() function.

    Returns when an EOF is encountered.
    """
    if self._text_file:
      # Read a text file one line at a time.
      for line in self._file_object:
        self._output_queue.put(line)
    else:
      # Read binary or text data until we get to EOF.
      while True:
        chunk = self._file_object.read(self._chunk_size)
        if not chunk:
          break
        self._output_queue.put(chunk)

  def set_chunk_size(self, chunk_size):
    """Change the read chunk size.

    This function can only be called if the FileReaderThread object was
    created with an initial chunk_size > 0.
    Args:
      chunk_size: the new chunk size for this file.  Must be > 0.
    """
    # The chunk size can be changed asynchronously while a file is being read
    # in a worker thread.  However, type of file can not be changed after the
    # the FileReaderThread has been created.  These asserts verify that we are
    # only changing the chunk size, and not the type of file.
    assert not self._text_file
    assert chunk_size > 0
    self._chunk_size = chunk_size

class AdbUtils:
  @staticmethod
  def add_adb_serial(adb_command, device_serial):
    if device_serial is not None:
      adb_command.insert(1, device_serial)
      adb_command.insert(1, '-s')

  @staticmethod
  def construct_adb_shell_command(shell_args, device_serial):
    adb_command = ['adb', 'shell', ' '.join(shell_args)]
    AdbUtils.add_adb_serial(adb_command, device_serial)
    return adb_command

  @staticmethod
  def run_adb_shell(shell_args, device_serial):
    """Runs "adb shell" with the given arguments.

    Args:
      shell_args: array of arguments to pass to adb shell.
      device_serial: if not empty, will add the appropriate command-line
          parameters so that adb targets the given device.
    Returns:
      A tuple containing the adb output (stdout & stderr) and the return code
      from adb.  Will exit if adb fails to start.
    """
    adb_command = AdbUtils.construct_adb_shell_command(shell_args, device_serial)

    adb_output = []
    adb_return_code = 0
    try:
      adb_output = subprocess.check_output(adb_command, stderr=subprocess.STDOUT,
                                           shell=False, universal_newlines=True)
    except OSError as error:
      # This usually means that the adb executable was not found in the path.
      print('\nThe command "%s" failed with the following error:'
                            % ' '.join(adb_command), file=sys.stderr)
      print('    %s' % str(error), file=sys.stderr)
      print('Is adb in your path?', file=sys.stderr)
      adb_return_code = error.errno
      adb_output = error
    except subprocess.CalledProcessError as error:
      # The process exited with an error.
      adb_return_code = error.returncode
      adb_output = error.output

    return adb_output, adb_return_code

  @staticmethod
  def do_preprocess_adb_cmd(command, serial):
    args = [command]
    dump, ret_code = AdbUtils.run_adb_shell(args, serial)
    if ret_code != 0:
      return None

    dump = ''.join(dump)
    return dump

def parse_atrace_line(line, pagecache_stats, app_name):
  # Find a mm_filemap_add_to_page_cache entry
  m = re.match('.* (mm_filemap_add_to_page_cache|mm_filemap_delete_from_page_cache): dev (\d+):(\d+) ino ([0-9a-z]+) page=([0-9a-z]+) pfn=([0-9a-z]+) ofs=(\d+).*', line)
  if m is not None:
    # Get filename
    device_number = int(m.group(2)) << 8 | int(m.group(3))
    if device_number == 0:
      return
    inode = int(m.group(4), 16)
    if app_name is not None and not (app_name in m.group(0)):
      return
    if m.group(1) == 'mm_filemap_add_to_page_cache':
      pagecache_stats.add_page(device_number, inode, m.group(4))
    elif m.group(1) == 'mm_filemap_delete_from_page_cache':
      pagecache_stats.remove_page(device_number, inode, m.group(4))

def build_inode_lookup_table(inode_dump):
  inode2filename = {}
  text = inode_dump.splitlines()
  for line in text:
    result = re.match('([0-9]+)d? ([0-9]+) ([0-9]+) (.*)', line)
    if result:
      inode2filename[(int(result.group(1)), int(result.group(2)))] = (result.group(4), result.group(3))

  return inode2filename

def get_inode_data(datafile, dumpfile, adb_serial):
  if datafile is not None and os.path.isfile(datafile):
    print('Using cached inode data from ' + datafile)
    f = open(datafile, 'r')
    stat_dump = f.read()
  else:
    # Build inode maps if we were tracing page cache
    print('Downloading inode data from device')
    stat_dump = AdbUtils.do_preprocess_adb_cmd(
        'find /apex /system /system_ext /product /data /vendor ' +
        '-exec stat -c "%d %i %s %n" {} \;', adb_serial)
    if stat_dump is None:
      print('Could not retrieve inode data from device.')
      sys.exit(1)

    if dumpfile is not None:
      print('Storing inode data in ' + dumpfile)
      f = open(dumpfile, 'w')
      f.write(stat_dump)
      f.close()

    sys.stdout.write('Done.\n')

  return stat_dump

def read_and_parse_trace_file(trace_file, pagecache_stats, app_name):
  for line in trace_file:
    parse_atrace_line(line, pagecache_stats, app_name)
  pagecache_stats.print_stats()

def read_and_parse_trace_data_live(stdout, stderr, pagecache_stats, app_name):
  # Start reading trace data
  stdout_queue = queue.Queue(maxsize=128)
  stderr_queue = queue.Queue()

  stdout_thread = FileReaderThread(stdout, stdout_queue,
                                   text_file=True, chunk_size=64)
  stderr_thread = FileReaderThread(stderr, stderr_queue,
                                   text_file=True)
  stdout_thread.start()
  stderr_thread.start()

  stdscr = curses.initscr()

  try:
    height, width = stdscr.getmaxyx()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(True)
    stdscr.refresh()
    # We need at least a 30x100 window
    used_width = max(width, 100)
    used_height = max(height, 30)

    # Create a pad for pagecache stats
    pagecache_pad = curses.newpad(used_height - 2, used_width)

    stdscr.addstr(used_height - 1, 0, 'KEY SHORTCUTS: (r)eset stats, CTRL-c to quit')
    while (stdout_thread.isAlive() or stderr_thread.isAlive() or
           not stdout_queue.empty() or not stderr_queue.empty()):
      while not stderr_queue.empty():
        # Pass along errors from adb.
        line = stderr_queue.get().decode("utf-8")
        sys.stderr.write(line)
      while True:
        try:
          line = stdout_queue.get(True, STATS_UPDATE_INTERVAL).decode("utf-8")
          parse_atrace_line(line, pagecache_stats, app_name)
        except (queue.Empty, KeyboardInterrupt):
          break

      key = ''
      try:
        key = stdscr.getkey()
      except:
        pass

      if key == 'r':
        pagecache_stats.reset_stats()

      pagecache_stats.print_stats_curses(pagecache_pad)
  except Exception as e:
    curses.endwin()
    print(e)
  finally:
    curses.endwin()
    # The threads should already have stopped, so this is just for cleanup.
    stdout_thread.join()
    stderr_thread.join()

    stdout.close()
    stderr.close()

def parse_options(argv):
  usage = 'Usage: %prog [options]'
  desc = 'Example: %prog'
  parser = optparse.OptionParser(usage=usage, description=desc)
  parser.add_option('-d', dest='inode_dump_file', metavar='FILE',
                    help='Dump the inode data read from a device to a file.'
                    ' This file can then be reused with the -i option to speed'
                    ' up future invocations of this script.')
  parser.add_option('-i', dest='inode_data_file', metavar='FILE',
                    help='Read cached inode data from a file saved arlier with the'
                    ' -d option.')
  parser.add_option('-s', '--serial', dest='device_serial', type='string',
                    help='adb device serial number')
  parser.add_option('-f', dest='trace_file', metavar='FILE',
                    help='Show stats from a trace file, instead of running live.')
  parser.add_option('-a', dest='app_name', type='string',
                    help='filter a particular app')

  options, categories = parser.parse_args(argv[1:])
  if options.inode_dump_file and options.inode_data_file:
    parser.error('options -d and -i can\'t be used at the same time')
  return options, categories

def main():
  options, categories = parse_options(sys.argv)

  # Load inode data for this device
  inode_data = get_inode_data(options.inode_data_file, options.inode_dump_file,
      options.device_serial)
  # Build (dev, inode) -> filename hash
  inode_lookup_table = build_inode_lookup_table(inode_data)
  # Init pagecache stats
  pagecache_stats = PagecacheStats(inode_lookup_table)

  if options.trace_file is not None:
    if not os.path.isfile(options.trace_file):
      print('Couldn\'t load trace file.', file=sys.stderr)
      sys.exit(1)
    trace_file = open(options.trace_file, 'r')
    read_and_parse_trace_file(trace_file, pagecache_stats, options.app_name)
  else:
    # Construct and execute trace command
    trace_cmd = AdbUtils.construct_adb_shell_command(['atrace', '--stream', 'pagecache'],
        options.device_serial)

    try:
      atrace = subprocess.Popen(trace_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
          stderr=subprocess.PIPE)
    except OSError as error:
      print('The command failed', file=sys.stderr)
      sys.exit(1)

    read_and_parse_trace_data_live(atrace.stdout, atrace.stderr, pagecache_stats, options.app_name)

if __name__ == "__main__":
  main()
