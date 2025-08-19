#!/system/bin/sh

#
# Copyright (C) 2019 The Android Open Source Project
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

# This script will run as an pre-checkpointing cleanup for mounting f2fs
# with checkpoint=disable, so that the first mount after the reboot will
# be faster. It is unnecessary to run if the device does not use userdata
# checkpointing on F2FS.

# TARGET_SLOT="${1}"
STATUS_FD="${2}"

SLEEP=5
TIME=0
MAX_TIME=1200

# GC_URGENT_MID, will fall back to GC_URGENT_HIGH if unsupported
GC_TYPE=3

# If we fall back, start off with less impactful GC
# To avoid long wait time, ramp up over time
GC_SLEEP_MAX=150
GC_SLEEP_MIN=50
GC_SLEEP_STEP=5

# We only need to run this if we're using f2fs
if [ ! -f /dev/sys/fs/by-name/userdata/gc_urgent ]; then
  exit 0
fi

# If we have sufficient free segments, it doesn't matter how much extra
# space is unusable, since we only need to make it to boot complete to
# get that space back
MIN_FREE_SEGMENT=500

# Ideally we want to track unusable, as it directly measures what we
# care about. If it's not present, dirty_segments is the best proxy.
if [ -f /dev/sys/fs/by-name/userdata/unusable ]; then
  UNUSABLE=1
  METRIC="unusable blocks"
  THRESHOLD=25000
  MAX_INCREASE=500
  read START < /dev/sys/fs/by-name/userdata/unusable
else
  METRIC="dirty segments"
  THRESHOLD=200
  MAX_INCREASE=5
  read START < /dev/sys/fs/by-name/userdata/dirty_segments
fi

log -pi -t checkpoint_gc Turning on GC for userdata

read OLD_SLEEP < /dev/sys/fs/by-name/userdata/gc_urgent_sleep_time || \
  { log -pw -t checkpoint_gc Cannot read gc_urgent_sleep_time; exit 1; }
GC_SLEEP=${GC_SLEEP_MAX}
echo ${GC_SLEEP} > /dev/sys/fs/by-name/userdata/gc_urgent_sleep_time || \
  { log -pw -t checkpoint_gc Cannot set gc_urgent_sleep_time; exit 1; }


echo ${GC_TYPE} > /dev/sys/fs/by-name/userdata/gc_urgent \
  || { GC_TYPE=1; log -pi -t checkpoint_gc GC_URGENT_MID not supported, using GC_URGENT_HIGH; }

if [ ${GC_TYPE} -eq 1 ]; then
  echo ${GC_TYPE} > /dev/sys/fs/by-name/userdata/gc_urgent || \
    { echo ${OLD_SLEEP} > /dev/sys/fs/by-name/userdata/gc_urgent_sleep_time; \
    log -pw -t checkpoint_gc Failed to set gc_urgent; exit 1; }
else
  # GC MID will wait for background I/O, so no need to start small
  GC_SLEEP=${GC_SLEEP_MIN}
fi


CURRENT=${START}
TODO=$((${START}-${THRESHOLD}))
CUTOFF=$((${START} + ${MAX_INCREASE}))
while [ ${CURRENT} -gt ${THRESHOLD} ]; do
  log -pi -t checkpoint_gc ${METRIC}:${CURRENT} \(threshold:${THRESHOLD}\) mode:${GC_TYPE} GC_SLEEP:${GC_SLEEP}
  PROGRESS=`echo "(${START}-${CURRENT})/${TODO}"|bc -l`
  if [[ $PROGRESS == -* ]]; then
      PROGRESS=0
  fi
  print -u${STATUS_FD} "global_progress ${PROGRESS}"
  if [ ${UNUSABLE} -eq 1 ]; then
    read CURRENT < /dev/sys/fs/by-name/userdata/unusable
  else
    read CURRENT < /dev/sys/fs/by-name/userdata/dirty_segments
  fi

  if [ ${CURRENT} -gt ${CUTOFF} ]; then
    log -pw -t checkpoint_gc Garbage Collection is making no progress. Aborting checkpoint_gc attempt \(initial ${METRIC}: ${START}, now: ${CURRENT}\)
    break
  fi

  read CURRENT_FREE_SEGMENTS < /dev/sys/fs/by-name/userdata/free_segments
  read CURRENT_OVP < /dev/sys/fs/by-name/userdata/ovp_segments
  CURRENT_FREE_SEG=$((${CURRENT_FREE_SEGMENTS}-${CURRENT_OVP}))
  if [ ${CURRENT_FREE_SEG} -gt ${MIN_FREE_SEGMENT} ]; then
    log -pi checkpoint_gc Sufficient free segments. Extra gc not needed.
    break
  fi

  sleep ${SLEEP}
  TIME=$((${TIME}+${SLEEP}))
  if [ ${TIME} -gt ${MAX_TIME} ]; then
    log -pw -t checkpoint_gc Timed out with gc threshold not met.
    break
  fi
  if [ ${GC_SLEEP} -gt ${GC_SLEEP_MIN} ]; then
    GC_SLEEP=$((${GC_SLEEP}-${GC_SLEEP_STEP}))
  fi
  # In case someone turns it off behind our back
  echo ${GC_SLEEP} > /dev/sys/fs/by-name/userdata/gc_urgent_sleep_time
  echo ${GC_TYPE} > /dev/sys/fs/by-name/userdata/gc_urgent
done

# It could be a while before the system reboots for the update...
# Leaving on low level GC can help ensure the boot for ota is faster
# If powerhints decides to turn it off, we'll just rely on normal GC
log -pi -t checkpoint_gc Leaving on GC_URGENT_LOW for userdata
echo ${OLD_SLEEP} > /dev/sys/fs/by-name/userdata/gc_urgent_sleep_time
echo 2 > /dev/sys/fs/by-name/userdata/gc_urgent
sync

print -u${STATUS_FD} "global_progress 1.0"
exit 0
