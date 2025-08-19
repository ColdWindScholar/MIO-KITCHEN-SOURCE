import sys
import os
from datetime import datetime

# Usage:
# replace_timestamp.py input.txt output.txt timestamp_string
#
# Description:
# Replace timestamp in the input.txt with the difference timestamp to timestamp_string.
#
# Example: replace_timestamp.py input.txt output.txt "01-28 18:12:30.339".
#
def main():
    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print("File path {} does not exist. Exiting...".format(filepath))
        sys.exit()

    output_filepath = sys.argv[2]

    timestamp_str = sys.argv[3]
    date_time_obj = datetime.strptime(timestamp_str, '%m-%d %H:%M:%S.%f')

    output_fp = open(output_filepath, 'w')
    i = 1
    with open(filepath, 'r', errors = 'ignore') as fp:
        for line in fp:
            newline = replace_timestamp_abs(line, timestamp_str, date_time_obj)
            output_fp.write(newline)
            i = i + 1
    fp.close()
    output_fp.close()


def replace_timestamp_abs(line, timestamp_str, date_time_obj0):
    if line[:5] != timestamp_str[:5]:
        return line

    index = line.find(" ", 6)
    if index <= 0:
        return line
    substr0 = line[:index]
    substr1 = line[index:]

    try:
        date_time_obj = datetime.strptime(substr0, '%m-%d %H:%M:%S.%f')
    except ValueError:
        return line

    date_time_delta = date_time_obj - date_time_obj0
    date_time_delta_str = str(date_time_delta)
    return date_time_delta_str + substr1

if __name__ == '__main__':
    main()
