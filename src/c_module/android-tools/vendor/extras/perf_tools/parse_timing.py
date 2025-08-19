import sys
import os
from datetime import datetime

# Usage:
# python3 parse_timing.py logcat.txt "08-23 23:10:32.555" 10 200
#
# Description: extract events and timing in the log that start from timestamp "08-23 23:10:32.555"
# till 10 seconds
#
# Usage:
# python3 parse_timing.py logcat1.txt logcat2.txt 10 ts1 ts1 200
#
# Description: report the timing that the differences are bigger than 200
#
# Example:
# python3 log_processing/parse_timing.py 8976224/logcat.txt 8879724/logcat.txt
# "08-23 23:10:32.555" "07-29 06:39:06.254" 200
def main():
   if len(sys.argv) == 5:
      process_one_log()
   elif len(sys.argv) == 6:
      compair_two_log()
   else:
      print("wrong number of arguments")

def compair_two_log():
   filepath1 = sys.argv[1]
   print(filepath1)
   if not os.path.isfile(filepath1):
       print("File path {} does not exist. Exiting...".format(filepath1))
       sys.exit()

   filepath2 = sys.argv[2]
   print(filepath2)
   if not os.path.isfile(filepath2):
       print("File path {} does not exist. Exiting...".format(filepath2))
       sys.exit()

   ts1 = datetime.strptime(sys.argv[3], '%m-%d %H:%M:%S.%f')
   ts2 = datetime.strptime(sys.argv[4], '%m-%d %H:%M:%S.%f')
   duration = float(sys.argv[5])*1000

   # 1: took to complete 1000ms
   # 2: took 33ms
   # 3: took 33 ms or took 0.3 seconds
   file1_events = [{}, {}, {}]
   file2_events = [{}, {}, {}]

   extract_events(filepath1, file1_events, ts1, duration)
   extract_events(filepath2, file2_events, ts2, duration)


   sum_events_timing(file1_events)
   sum_events_timing(file2_events)

   sum_all_events_timing_diff(file1_events, file2_events)

   sys.exit()


def process_one_log():
   filepath = sys.argv[1]
   print(filepath)
   if not os.path.isfile(filepath):
       print("File path {} does not exist. Exiting...".format(filepath))
       sys.exit()

   # 1: took to complete 1000ms
   # 2: took 33ms
   # 3: took 33 ms or took 0.3 seconds
   events = [{}, {}, {}]
   ts = datetime.strptime(sys.argv[2], '%m-%d %H:%M:%S.%f')
   duration = float(sys.argv[3])*1000
   extract_events(filepath, events, ts, duration)

   timing = float(sys.argv[3])
   print_sorted_all_events(events, timing)

   sys.exit()

def print_sorted_all_events(file_events, timing):
   for i in range(len(file_events)):
      print_sorted_events(file_events[i], timing)

def print_sorted_events(events, timing):
   for word in sorted(events, key=events.get, reverse=True):
      if (events[word]) > timing:
         print("event:{} \ttiming:{} ".format(word, events[word]))

def sum_events_timing(events):
   total_sum = 0;
   for i in range(len(events)):
      sum = 0
      print("start summary for type {}".format(i))
      for event in events[i]:
         sum += events[i][event]
         #print("event {} timing {} ".format(event, events[i][event]))
      print("sum events type {} {} : timing {}".format(i, len(events), sum))
      total_sum += sum
   print("sum all type events timing {}\n".format(total_sum))

def sum_events_timing_diff(type, file1_events, file2_events):
   sum_diff = 0
   max_diff = 0
   regression_events = {}
   print("start summary for type {}".format(type))
   for event in file1_events:
      val = file2_events.get(event)
      if val != None:
         diff = file1_events[event] - val
         if diff > 100 and val > 100:
            # print("regression event {} \t{}: {} \t{}: {} \tdiff: {}"
            #      .format(event, "case1", file1_events[event], "case2", val, diff))
            regression_events[event] = diff
            sum_diff += diff
            max_diff = max(max_diff, diff)
   print("\nsummary for timing type {} sum_diff {} max_diff {}".format(type, sum_diff, max_diff))
   print_events(regression_events, file1_events, file2_events)

def sum_all_events_timing_diff(file1_events, file2_events):
   for i in range(len(file1_events)):
      sum_events_timing_diff(i, file1_events[i], file2_events[i])

def print_events(events, file1_events, file2_events):
   for word in sorted(events, key=events.get, reverse=True):
      if (events[word]) > 10:
          print("{} \tdiff {} \t{} \t{}".format(word, events[word],file1_events[word], file2_events[word]))

def find_took(words):
   for i in range(len(words)):
      if words[i] == 'took' or words[i] == "took:":
         return i

def extract_time(line, events):
   if not "took" in line:
      return

   # 1: took to complete 1000ms
   # 2: took 33ms
   # 3: took 33 ms or took 0.3 seconds
   words = line.strip().split(' ')
   i = find_took(words)
   index = 0;
   str1 = " "
   key = str1.join(words[8:i])

   if words[i+1] == 'to' and words[i+2] == 'complete:':
      index = 0;
      val = float(words[i+3][:-2]);
   elif words[i+1][-2:] == 'ms':
      index = 1
      val = float(words[i+1][:-2]);
   elif len(words) > i+2:
      index = 2
      if words[i+2] == 'seconds':
         val = float(words[i+1])*1000;
      elif words[i+2] == 'ms':
         val = float(words[i+1])
      else:
         return True

   # print("index: {}  key: {} val: {}".format(index, key, val));

   if events[index].get(key) == None:
      events[index][key] = val
      return True
   else:
      # print("duplicate key: " + key + " line: " + line)
      return True

def check_time_range(line, ts, duration):
   index = line.find(" ", 6)
   if index <= 0:
      return False

   try:
      current_time = datetime.strptime(line[:index], '%m-%d %H:%M:%S.%f')
   except ValueError:
      return False

   deltatime = current_time - ts
   if deltatime.total_seconds()*1000 < 0 or deltatime.total_seconds() > duration:
      return False
   return True

def extract_events(filepath, events, ts, duration):
   with open(filepath, errors='ignore') as fp:
      for line in fp:
         if check_time_range(line, ts, duration) == False:
            continue
         if extract_time(line, events) == False:
            return


if __name__ == '__main__':
    main()
