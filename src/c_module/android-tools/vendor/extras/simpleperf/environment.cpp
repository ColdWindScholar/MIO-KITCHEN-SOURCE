/*
 * Copyright (C) 2015 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "environment.h"

#include <inttypes.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/sysinfo.h>
#include <sys/utsname.h>
#include <unistd.h>

#include <limits>
#include <optional>
#include <set>
#include <unordered_map>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/parseint.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <procinfo/process.h>
#include <procinfo/process_map.h>

#if defined(__ANDROID__)
#include <android-base/properties.h>
#include <cutils/android_filesystem_config.h>
#endif

#include "IOEventLoop.h"
#include "command.h"
#include "event_type.h"
#include "kallsyms.h"
#include "read_elf.h"
#include "thread_tree.h"
#include "utils.h"
#include "workload.h"

namespace simpleperf {

std::vector<int> GetOnlineCpus() {
  std::vector<int> result;
  LineReader reader("/sys/devices/system/cpu/online");
  if (!reader.Ok()) {
    PLOG(ERROR) << "can't open online cpu information";
    return result;
  }

  std::string* line;
  if ((line = reader.ReadLine()) != nullptr) {
    if (auto cpus = GetCpusFromString(*line); cpus) {
      result.assign(cpus->begin(), cpus->end());
    }
  }
  CHECK(!result.empty()) << "can't get online cpu information";
  return result;
}

static void GetAllModuleFiles(const std::string& path,
                              std::unordered_map<std::string, std::string>* module_file_map) {
  if (!IsDir(path)) {
    return;
  }
  for (const auto& name : GetEntriesInDir(path)) {
    std::string entry_path = path + "/" + name;
    if (IsRegularFile(entry_path) && android::base::EndsWith(name, ".ko")) {
      std::string module_name = name.substr(0, name.size() - 3);
      std::replace(module_name.begin(), module_name.end(), '-', '_');
      module_file_map->insert(std::make_pair(module_name, entry_path));
    } else if (IsDir(entry_path)) {
      GetAllModuleFiles(entry_path, module_file_map);
    }
  }
}

static std::vector<KernelMmap> GetModulesInUse() {
  std::vector<KernelMmap> module_mmaps = GetLoadedModules();
  if (module_mmaps.empty()) {
    return std::vector<KernelMmap>();
  }
  std::unordered_map<std::string, std::string> module_file_map;
#if defined(__ANDROID__)
  // On Android, kernel modules are stored in /system/lib/modules, /vendor/lib/modules,
  // /odm/lib/modules.
  // See https://source.android.com/docs/core/architecture/partitions/gki-partitions and
  // https://source.android.com/docs/core/architecture/partitions/vendor-odm-dlkm-partition.
  // They can also be stored in vendor_kernel_ramdisk.img, which isn't accessible from userspace.
  // See https://source.android.com/docs/core/architecture/kernel/kernel-module-support.
  for (const auto& path : {"/system/lib/modules", "/vendor/lib/modules", "/odm/lib/modules"}) {
    GetAllModuleFiles(path, &module_file_map);
  }
#else
  utsname uname_buf;
  if (TEMP_FAILURE_RETRY(uname(&uname_buf)) != 0) {
    PLOG(ERROR) << "uname() failed";
    return std::vector<KernelMmap>();
  }
  std::string linux_version = uname_buf.release;
  std::string module_dirpath = "/lib/modules/" + linux_version + "/kernel";
  GetAllModuleFiles(module_dirpath, &module_file_map);
#endif
  for (auto& module : module_mmaps) {
    auto it = module_file_map.find(module.name);
    if (it != module_file_map.end()) {
      module.filepath = it->second;
    }
  }
  return module_mmaps;
}

void GetKernelAndModuleMmaps(KernelMmap* kernel_mmap, std::vector<KernelMmap>* module_mmaps) {
  kernel_mmap->name = DEFAULT_KERNEL_MMAP_NAME;
  kernel_mmap->start_addr = 0;
  kernel_mmap->len = std::numeric_limits<uint64_t>::max();
  if (uint64_t kstart_addr = GetKernelStartAddress(); kstart_addr != 0) {
    kernel_mmap->name = std::string(DEFAULT_KERNEL_MMAP_NAME) + "_stext";
    kernel_mmap->start_addr = kstart_addr;
    kernel_mmap->len = std::numeric_limits<uint64_t>::max() - kstart_addr;
  }
  kernel_mmap->filepath = kernel_mmap->name;
  *module_mmaps = GetModulesInUse();
  for (auto& map : *module_mmaps) {
    if (map.filepath.empty()) {
      map.filepath = "[" + map.name + "]";
    }
  }
}

bool ReadThreadNameAndPid(pid_t tid, std::string* comm, pid_t* pid) {
  android::procinfo::ProcessInfo procinfo;
  if (!android::procinfo::GetProcessInfo(tid, &procinfo)) {
    return false;
  }
  if (comm != nullptr) {
    *comm = procinfo.name;
  }
  if (pid != nullptr) {
    *pid = procinfo.pid;
  }
  return true;
}

std::vector<pid_t> GetThreadsInProcess(pid_t pid) {
  std::vector<pid_t> result;
  android::procinfo::GetProcessTids(pid, &result);
  return result;
}

bool IsThreadAlive(pid_t tid) {
  return IsDir(android::base::StringPrintf("/proc/%d", tid));
}

bool GetProcessForThread(pid_t tid, pid_t* pid) {
  return ReadThreadNameAndPid(tid, nullptr, pid);
}

bool GetThreadName(pid_t tid, std::string* name) {
  return ReadThreadNameAndPid(tid, name, nullptr);
}

std::vector<pid_t> GetAllProcesses() {
  std::vector<pid_t> result;
  std::vector<std::string> entries = GetEntriesInDir("/proc");
  for (const auto& entry : entries) {
    pid_t pid;
    if (!android::base::ParseInt(entry.c_str(), &pid, 0)) {
      continue;
    }
    result.push_back(pid);
  }
  return result;
}

bool GetThreadMmapsInProcess(pid_t pid, std::vector<ThreadMmap>* thread_mmaps) {
  thread_mmaps->clear();
  return android::procinfo::ReadProcessMaps(pid, [&](const android::procinfo::MapInfo& mapinfo) {
    thread_mmaps->emplace_back(mapinfo.start, mapinfo.end - mapinfo.start, mapinfo.pgoff,
                               mapinfo.name.c_str(), mapinfo.flags);
  });
}

bool GetKernelBuildId(BuildId* build_id) {
  ElfStatus result = GetBuildIdFromNoteFile("/sys/kernel/notes", build_id);
  if (result != ElfStatus::NO_ERROR) {
    LOG(DEBUG) << "failed to read /sys/kernel/notes: " << result;
  }
  return result == ElfStatus::NO_ERROR;
}

bool GetModuleBuildId(const std::string& module_name, BuildId* build_id,
                      const std::string& sysfs_dir) {
  std::string notefile = sysfs_dir + "/module/" + module_name + "/notes/.note.gnu.build-id";
  return GetBuildIdFromNoteFile(notefile, build_id) == ElfStatus::NO_ERROR;
}

/*
 * perf event allow level:
 *  -1 - everything allowed
 *   0 - disallow raw tracepoint access for unpriv
 *   1 - disallow cpu events for unpriv
 *   2 - disallow kernel profiling for unpriv
 *   3 - disallow user profiling for unpriv
 */
static const char* perf_event_allow_path = "/proc/sys/kernel/perf_event_paranoid";

static std::optional<int> ReadPerfEventAllowStatus() {
  std::string s;
  if (!android::base::ReadFileToString(perf_event_allow_path, &s)) {
    PLOG(DEBUG) << "failed to read " << perf_event_allow_path;
    return std::nullopt;
  }
  s = android::base::Trim(s);
  int value;
  if (!android::base::ParseInt(s.c_str(), &value)) {
    PLOG(ERROR) << "failed to parse " << perf_event_allow_path << ": " << s;
    return std::nullopt;
  }
  return value;
}

bool CanRecordRawData() {
  if (IsRoot()) {
    return true;
  }
#if defined(__ANDROID__)
  // Android R uses selinux to control perf_event_open. Whether raw data can be recorded is hard
  // to check unless we really try it. And probably there is no need to record raw data in non-root
  // users.
  return false;
#else
  return ReadPerfEventAllowStatus() == -1;
#endif
}

uint64_t GetMemorySize() {
  struct sysinfo info;
  sysinfo(&info);
  return info.totalram;
}

static const char* GetLimitLevelDescription(int limit_level) {
  switch (limit_level) {
    case -1:
      return "unlimited";
    case 0:
      return "disallowing raw tracepoint access for unpriv";
    case 1:
      return "disallowing cpu events for unpriv";
    case 2:
      return "disallowing kernel profiling for unpriv";
    case 3:
      return "disallowing user profiling for unpriv";
    default:
      return "unknown level";
  }
}

bool CheckPerfEventLimit() {
  std::optional<int> old_level = ReadPerfEventAllowStatus();

  // Root is not limited by perf_event_allow_path. However, the monitored threads
  // may create child processes not running as root. To make sure the child processes have
  // enough permission to create inherited tracepoint events, write -1 to perf_event_allow_path.
  // See http://b/62230699.
  if (IsRoot()) {
    if (old_level == -1) {
      return true;
    }
    if (android::base::WriteStringToFile("-1", perf_event_allow_path)) {
      return true;
    }
    // On host, we may not be able to write to perf_event_allow_path (like when running in docker).
#if defined(__ANDROID__)
    PLOG(ERROR) << "failed to write -1 to " << perf_event_allow_path;
    return false;
#endif
  }
  if (old_level.has_value() && old_level <= 1) {
    return true;
  }
#if defined(__ANDROID__)
  const std::string prop_name = "security.perf_harden";
  std::string prop_value = android::base::GetProperty(prop_name, "");
  if (prop_value.empty()) {
    // can't do anything if there is no such property.
    return true;
  }
  if (prop_value == "0") {
    return true;
  }
  // Try to enable perf events by setprop security.perf_harden=0.
  if (android::base::SetProperty(prop_name, "0")) {
    sleep(1);
    // Check the result of setprop, by reading allow status or the property value.
    if (auto level = ReadPerfEventAllowStatus(); level.has_value() && level <= 1) {
      return true;
    }
    if (android::base::GetProperty(prop_name, "") == "0") {
      return true;
    }
  }
  if (old_level.has_value()) {
    LOG(ERROR) << perf_event_allow_path << " is " << old_level.value() << ", "
               << GetLimitLevelDescription(old_level.value()) << ".";
  }
  LOG(ERROR) << "Try using `adb shell setprop security.perf_harden 0` to allow profiling.";
  return false;
#else
  if (old_level.has_value()) {
    LOG(ERROR) << perf_event_allow_path << " is " << old_level.value() << ", "
               << GetLimitLevelDescription(old_level.value()) << ". Try using `echo -1 >"
               << perf_event_allow_path << "` to enable profiling.";
    return false;
  }
#endif
  return true;
}

#if defined(__ANDROID__)
static bool SetProperty(const char* prop_name, uint64_t value) {
  if (!android::base::SetProperty(prop_name, std::to_string(value))) {
    LOG(ERROR) << "Failed to SetProperty " << prop_name << " to " << value;
    return false;
  }
  return true;
}

bool SetPerfEventLimits(uint64_t sample_freq, size_t cpu_percent, uint64_t mlock_kb) {
  if (!SetProperty("debug.perf_event_max_sample_rate", sample_freq) ||
      !SetProperty("debug.perf_cpu_time_max_percent", cpu_percent) ||
      !SetProperty("debug.perf_event_mlock_kb", mlock_kb) ||
      !SetProperty("security.perf_harden", 0)) {
    return false;
  }
  // Wait for init process to change perf event limits based on properties.
  const size_t max_wait_us = 3 * 1000000;
  const size_t interval_us = 10000;
  int finish_mask = 0;
  for (size_t i = 0; i < max_wait_us && finish_mask != 7; i += interval_us) {
    usleep(interval_us);  // Wait 10ms to avoid busy loop.
    if ((finish_mask & 1) == 0) {
      uint64_t freq;
      if (!GetMaxSampleFrequency(&freq) || freq == sample_freq) {
        finish_mask |= 1;
      }
    }
    if ((finish_mask & 2) == 0) {
      size_t percent;
      if (!GetCpuTimeMaxPercent(&percent) || percent == cpu_percent) {
        finish_mask |= 2;
      }
    }
    if ((finish_mask & 4) == 0) {
      uint64_t kb;
      if (!GetPerfEventMlockKb(&kb) || kb == mlock_kb) {
        finish_mask |= 4;
      }
    }
  }
  if (finish_mask != 7) {
    LOG(WARNING) << "Wait setting perf event limits timeout";
  }
  return true;
}
#else  // !defined(__ANDROID__)
bool SetPerfEventLimits(uint64_t, size_t, uint64_t) {
  return true;
}
#endif

template <typename T>
static bool ReadUintFromProcFile(const std::string& path, T* value) {
  std::string s;
  if (!android::base::ReadFileToString(path, &s)) {
    PLOG(DEBUG) << "failed to read " << path;
    return false;
  }
  s = android::base::Trim(s);
  if (!android::base::ParseUint(s.c_str(), value)) {
    LOG(ERROR) << "failed to parse " << path << ": " << s;
    return false;
  }
  return true;
}

template <typename T>
static bool WriteUintToProcFile(const std::string& path, T value) {
  if (IsRoot()) {
    return android::base::WriteStringToFile(std::to_string(value), path);
  }
  return false;
}

bool GetMaxSampleFrequency(uint64_t* max_sample_freq) {
  return ReadUintFromProcFile("/proc/sys/kernel/perf_event_max_sample_rate", max_sample_freq);
}

bool SetMaxSampleFrequency(uint64_t max_sample_freq) {
  return WriteUintToProcFile("/proc/sys/kernel/perf_event_max_sample_rate", max_sample_freq);
}

bool GetCpuTimeMaxPercent(size_t* percent) {
  return ReadUintFromProcFile("/proc/sys/kernel/perf_cpu_time_max_percent", percent);
}

bool SetCpuTimeMaxPercent(size_t percent) {
  return WriteUintToProcFile("/proc/sys/kernel/perf_cpu_time_max_percent", percent);
}

bool GetPerfEventMlockKb(uint64_t* mlock_kb) {
  return ReadUintFromProcFile("/proc/sys/kernel/perf_event_mlock_kb", mlock_kb);
}

bool SetPerfEventMlockKb(uint64_t mlock_kb) {
  return WriteUintToProcFile("/proc/sys/kernel/perf_event_mlock_kb", mlock_kb);
}

ArchType GetMachineArch() {
#if defined(__i386__)
  // For 32 bit x86 build, we can't get machine arch by uname().
  ArchType arch = ARCH_UNSUPPORTED;
  std::unique_ptr<FILE, decltype(&pclose)> fp(popen("uname -m", "re"), pclose);
  if (fp) {
    char machine[40];
    if (fgets(machine, sizeof(machine), fp.get()) == machine) {
      arch = GetArchType(android::base::Trim(machine));
    }
  }
#else
  utsname uname_buf;
  if (TEMP_FAILURE_RETRY(uname(&uname_buf)) != 0) {
    PLOG(WARNING) << "uname() failed";
    return GetTargetArch();
  }
  ArchType arch = GetArchType(uname_buf.machine);
#endif
  if (arch != ARCH_UNSUPPORTED) {
    return arch;
  }
  return GetTargetArch();
}

void PrepareVdsoFile() {
  // vdso is an elf file in memory loaded in each process's user space by the kernel. To read
  // symbols from it and unwind through it, we need to dump it into a file in storage.
  // It doesn't affect much when failed to prepare vdso file, so there is no need to return values.
  std::vector<ThreadMmap> thread_mmaps;
  if (!GetThreadMmapsInProcess(getpid(), &thread_mmaps)) {
    return;
  }
  const ThreadMmap* vdso_map = nullptr;
  for (const auto& map : thread_mmaps) {
    if (map.name == "[vdso]") {
      vdso_map = &map;
      break;
    }
  }
  if (vdso_map == nullptr) {
    return;
  }
  std::string s(vdso_map->len, '\0');
  memcpy(&s[0], reinterpret_cast<void*>(static_cast<uintptr_t>(vdso_map->start_addr)),
         vdso_map->len);
  std::unique_ptr<TemporaryFile> tmpfile = ScopedTempFiles::CreateTempFile();
  if (!android::base::WriteStringToFd(s, tmpfile->fd)) {
    return;
  }
  Dso::SetVdsoFile(tmpfile->path, sizeof(size_t) == sizeof(uint64_t));
}

static bool HasOpenedAppApkFile(int pid) {
  std::string fd_path = "/proc/" + std::to_string(pid) + "/fd/";
  std::vector<std::string> files = GetEntriesInDir(fd_path);
  for (const auto& file : files) {
    std::string real_path;
    if (!android::base::Readlink(fd_path + file, &real_path)) {
      continue;
    }
    if (real_path.find("app") != std::string::npos && real_path.find(".apk") != std::string::npos) {
      return true;
    }
  }
  return false;
}

std::set<pid_t> WaitForAppProcesses(const std::string& package_name) {
  std::set<pid_t> result;
  size_t loop_count = 0;
  while (true) {
    std::vector<pid_t> pids = GetAllProcesses();
    for (pid_t pid : pids) {
      std::string process_name = GetCompleteProcessName(pid);
      if (process_name.empty()) {
        continue;
      }
      // The app may have multiple processes, with process name like
      // com.google.android.googlequicksearchbox:search.
      size_t split_pos = process_name.find(':');
      if (split_pos != std::string::npos) {
        process_name = process_name.substr(0, split_pos);
      }
      if (process_name != package_name) {
        continue;
      }
      // If a debuggable app with wrap.sh runs on Android O, the app will be started with
      // logwrapper as below:
      // 1. Zygote forks a child process, rename it to package_name.
      // 2. The child process execute sh, which starts a child process running
      //    /system/bin/logwrapper.
      // 3. logwrapper starts a child process running sh, which interprets wrap.sh.
      // 4. wrap.sh starts a child process running the app.
      // The problem here is we want to profile the process started in step 4, but sometimes we
      // run into the process started in step 1. To solve it, we can check if the process has
      // opened an apk file in some app dirs.
      if (!HasOpenedAppApkFile(pid)) {
        continue;
      }
      if (loop_count > 0u) {
        LOG(INFO) << "Got process " << pid << " for package " << package_name;
      }
      result.insert(pid);
    }
    if (!result.empty()) {
      return result;
    }
    if (++loop_count == 1u) {
      LOG(INFO) << "Waiting for process of app " << package_name;
    }
    usleep(1000);
  }
}

namespace {

bool IsAppDebuggable(int user_id, const std::string& package_name) {
  return Workload::RunCmd({"run-as", package_name, "--user", std::to_string(user_id), "echo",
                           ">/dev/null", "2>/dev/null"},
                          false);
}

class InAppRunner {
 public:
  InAppRunner(int user_id, const std::string& package_name)
      : user_id_(std::to_string(user_id)), package_name_(package_name) {}
  virtual ~InAppRunner() {
    if (!tracepoint_file_.empty()) {
      unlink(tracepoint_file_.c_str());
    }
  }
  virtual bool Prepare() = 0;
  bool RunCmdInApp(const std::string& cmd, const std::vector<std::string>& args,
                   size_t workload_args_size, const std::string& output_filepath,
                   bool need_tracepoint_events);

 protected:
  virtual std::vector<std::string> GetPrefixArgs(const std::string& cmd) = 0;

  const std::string user_id_;
  const std::string package_name_;
  std::string tracepoint_file_;
};

bool InAppRunner::RunCmdInApp(const std::string& cmd, const std::vector<std::string>& cmd_args,
                              size_t workload_args_size, const std::string& output_filepath,
                              bool need_tracepoint_events) {
  // 1. Build cmd args running in app's context.
  std::vector<std::string> args = GetPrefixArgs(cmd);
  args.insert(args.end(), {"--in-app", "--log", GetLogSeverityName()});
  if (log_to_android_buffer) {
    args.emplace_back("--log-to-android-buffer");
  }
  if (need_tracepoint_events) {
    // Since we can't read tracepoint events from tracefs in app's context, we need to prepare
    // them in tracepoint_file in shell's context, and pass the path of tracepoint_file to the
    // child process using --tracepoint-events option.
    const std::string tracepoint_file = "/data/local/tmp/tracepoint_events";
    if (!EventTypeManager::Instance().WriteTracepointsToFile(tracepoint_file)) {
      PLOG(ERROR) << "Failed to store tracepoint events";
      return false;
    }
    tracepoint_file_ = tracepoint_file;
    args.insert(args.end(), {"--tracepoint-events", tracepoint_file_});
  }

  android::base::unique_fd out_fd;
  if (!output_filepath.empty()) {
    // A process running in app's context can't open a file outside it's data directory to write.
    // So pass it a file descriptor to write.
    out_fd = FileHelper::OpenWriteOnly(output_filepath);
    if (out_fd == -1) {
      PLOG(ERROR) << "Failed to open " << output_filepath;
      return false;
    }
    args.insert(args.end(), {"--out-fd", std::to_string(int(out_fd))});
  }

  // We can't send signal to a process running in app's context. So use a pipe file to send stop
  // signal.
  android::base::unique_fd stop_signal_rfd;
  android::base::unique_fd stop_signal_wfd;
  if (!android::base::Pipe(&stop_signal_rfd, &stop_signal_wfd, 0)) {
    PLOG(ERROR) << "pipe";
    return false;
  }
  args.insert(args.end(), {"--stop-signal-fd", std::to_string(int(stop_signal_rfd))});

  for (size_t i = 0; i < cmd_args.size(); ++i) {
    if (i < cmd_args.size() - workload_args_size) {
      // Omit "-o output_file". It is replaced by "--out-fd fd".
      if (cmd_args[i] == "-o" || cmd_args[i] == "--app") {
        i++;
        continue;
      }
    }
    args.push_back(cmd_args[i]);
  }
  char* argv[args.size() + 1];
  for (size_t i = 0; i < args.size(); ++i) {
    argv[i] = &args[i][0];
  }
  argv[args.size()] = nullptr;

  // 2. Run child process in app's context.
  auto ChildProcFn = [&]() {
    stop_signal_wfd.reset();
    execvp(argv[0], argv);
    exit(1);
  };
  std::unique_ptr<Workload> workload = Workload::CreateWorkload(ChildProcFn);
  if (!workload) {
    return false;
  }
  stop_signal_rfd.reset();

  // Wait on signals.
  IOEventLoop loop;
  bool need_to_stop_child = false;
  std::vector<int> stop_signals = {SIGINT, SIGTERM};
  if (!SignalIsIgnored(SIGHUP)) {
    stop_signals.push_back(SIGHUP);
  }
  if (!loop.AddSignalEvents(stop_signals, [&]() {
        need_to_stop_child = true;
        return loop.ExitLoop();
      })) {
    return false;
  }
  if (!loop.AddSignalEvent(SIGCHLD, [&]() { return loop.ExitLoop(); })) {
    return false;
  }

  if (!workload->Start()) {
    return false;
  }
  if (!loop.RunLoop()) {
    return false;
  }
  if (need_to_stop_child) {
    stop_signal_wfd.reset();
  }
  int exit_code;
  if (!workload->WaitChildProcess(true, &exit_code) || exit_code != 0) {
    return false;
  }
  return true;
}

class RunAs : public InAppRunner {
 public:
  RunAs(int user_id, const std::string& package_name) : InAppRunner(user_id, package_name) {}
  virtual ~RunAs() {
    if (simpleperf_copied_in_app_) {
      Workload::RunCmd({"run-as", package_name_, "--user", user_id_, "rm", "-rf", "simpleperf"});
    }
  }
  bool Prepare() override;

 protected:
  std::vector<std::string> GetPrefixArgs(const std::string& cmd) {
    std::vector<std::string> args = {"run-as",
                                     package_name_,
                                     "--user",
                                     user_id_,
                                     simpleperf_copied_in_app_ ? "./simpleperf" : simpleperf_path_,
                                     cmd,
                                     "--app",
                                     package_name_};
    if (cmd == "record") {
      if (simpleperf_copied_in_app_ || GetAndroidVersion() >= kAndroidVersionS) {
        args.emplace_back("--add-meta-info");
        args.emplace_back("app_type=debuggable");
      }
    }
    return args;
  }

  bool simpleperf_copied_in_app_ = false;
  std::string simpleperf_path_;
};

bool RunAs::Prepare() {
  // run-as can't run /data/local/tmp/simpleperf directly. So copy simpleperf binary if needed.
  if (!android::base::Readlink("/proc/self/exe", &simpleperf_path_)) {
    PLOG(ERROR) << "ReadLink failed";
    return false;
  }
  if (simpleperf_path_.find("CtsSimpleperfTest") != std::string::npos) {
    simpleperf_path_ = "/system/bin/simpleperf";
    return true;
  }
  if (android::base::StartsWith(simpleperf_path_, "/system")) {
    return true;
  }
  if (!Workload::RunCmd(
          {"run-as", package_name_, "--user", user_id_, "cp", simpleperf_path_, "simpleperf"})) {
    return false;
  }
  simpleperf_copied_in_app_ = true;
  return true;
}

class SimpleperfAppRunner : public InAppRunner {
 public:
  SimpleperfAppRunner(int user_id, const std::string& package_name, const std::string& app_type)
      : InAppRunner(user_id, package_name) {
    // On Android < S, the app type is unknown before running simpleperf_app_runner. Assume it's
    // profileable.
    app_type_ = app_type == "unknown" ? "profileable" : app_type;
  }
  bool Prepare() override { return GetAndroidVersion() >= kAndroidVersionQ; }

 protected:
  std::vector<std::string> GetPrefixArgs(const std::string& cmd) {
    std::vector<std::string> args = {"simpleperf_app_runner", package_name_};
    if (user_id_ != "0") {
      args.emplace_back("--user");
      args.emplace_back(user_id_);
    }
    args.emplace_back(cmd);
    if (cmd == "record" && GetAndroidVersion() >= kAndroidVersionS) {
      args.emplace_back("--add-meta-info");
      args.emplace_back("app_type=" + app_type_);
    }
    return args;
  }

  std::string app_type_;
};

}  // namespace

static bool allow_run_as = true;
static bool allow_simpleperf_app_runner = true;

void SetRunInAppToolForTesting(bool run_as, bool simpleperf_app_runner) {
  allow_run_as = run_as;
  allow_simpleperf_app_runner = simpleperf_app_runner;
}

static int GetCurrentUserId() {
  std::unique_ptr<FILE, decltype(&pclose)> fd(popen("am get-current-user", "r"), pclose);
  if (fd) {
    char buf[128];
    if (fgets(buf, sizeof(buf), fd.get()) != nullptr) {
      int user_id;
      if (android::base::ParseInt(android::base::Trim(buf), &user_id, 0)) {
        return user_id;
      }
    }
  }
  return 0;
}

std::string GetAppType(const std::string& app_package_name) {
  if (GetAndroidVersion() < kAndroidVersionS) {
    return "unknown";
  }
  std::string cmd = "simpleperf_app_runner " + app_package_name + " --show-app-type";
  std::unique_ptr<FILE, decltype(&pclose)> fp(popen(cmd.c_str(), "re"), pclose);
  if (fp) {
    char buf[128];
    if (fgets(buf, sizeof(buf), fp.get()) != nullptr) {
      return android::base::Trim(buf);
    }
  }
  // Can't get app_type. It means the app doesn't exist.
  return "not_exist";
}

bool RunInAppContext(const std::string& app_package_name, const std::string& cmd,
                     const std::vector<std::string>& args, size_t workload_args_size,
                     const std::string& output_filepath, bool need_tracepoint_events) {
  int user_id = GetCurrentUserId();
  std::unique_ptr<InAppRunner> in_app_runner;

  std::string app_type = GetAppType(app_package_name);
  if (app_type == "unknown" && IsAppDebuggable(user_id, app_package_name)) {
    app_type = "debuggable";
  }

  if (allow_run_as && app_type == "debuggable") {
    in_app_runner.reset(new RunAs(user_id, app_package_name));
    if (!in_app_runner->Prepare()) {
      in_app_runner = nullptr;
    }
  }
  if (!in_app_runner && allow_simpleperf_app_runner) {
    if (app_type == "debuggable" || app_type == "profileable" || app_type == "unknown") {
      in_app_runner.reset(new SimpleperfAppRunner(user_id, app_package_name, app_type));
      if (!in_app_runner->Prepare()) {
        in_app_runner = nullptr;
      }
    }
  }
  if (!in_app_runner) {
    LOG(ERROR) << "Package " << app_package_name
               << " doesn't exist or isn't debuggable/profileable.";
    return false;
  }
  return in_app_runner->RunCmdInApp(cmd, args, workload_args_size, output_filepath,
                                    need_tracepoint_events);
}

void AllowMoreOpenedFiles() {
  // On Android <= O, the hard limit is 4096, and the soft limit is 1024.
  // On Android >= P, both the hard and soft limit are 32768.
  rlimit limit;
  if (getrlimit(RLIMIT_NOFILE, &limit) != 0) {
    return;
  }
  rlim_t new_limit = limit.rlim_max;
  if (IsRoot()) {
    rlim_t sysctl_nr_open = 0;
    if (ReadUintFromProcFile("/proc/sys/fs/nr_open", &sysctl_nr_open) &&
        sysctl_nr_open > new_limit) {
      new_limit = sysctl_nr_open;
    }
  }
  if (limit.rlim_cur < new_limit) {
    limit.rlim_cur = limit.rlim_max = new_limit;
    if (setrlimit(RLIMIT_NOFILE, &limit) == 0) {
      LOG(DEBUG) << "increased open file limit to " << new_limit;
    }
  }
}

std::string ScopedTempFiles::tmp_dir_;
std::vector<std::string> ScopedTempFiles::files_to_delete_;

std::unique_ptr<ScopedTempFiles> ScopedTempFiles::Create(const std::string& tmp_dir) {
  if (access(tmp_dir.c_str(), W_OK | X_OK) != 0) {
    return nullptr;
  }
  return std::unique_ptr<ScopedTempFiles>(new ScopedTempFiles(tmp_dir));
}

ScopedTempFiles::ScopedTempFiles(const std::string& tmp_dir) {
  CHECK(tmp_dir_.empty());  // No other ScopedTempFiles.
  tmp_dir_ = tmp_dir;
}

ScopedTempFiles::~ScopedTempFiles() {
  tmp_dir_.clear();
  for (auto& file : files_to_delete_) {
    unlink(file.c_str());
  }
  files_to_delete_.clear();
}

std::unique_ptr<TemporaryFile> ScopedTempFiles::CreateTempFile(bool delete_in_destructor) {
  CHECK(!tmp_dir_.empty());
  std::unique_ptr<TemporaryFile> tmp_file(new TemporaryFile(tmp_dir_));
  CHECK_NE(tmp_file->fd, -1) << "failed to create tmpfile under " << tmp_dir_;
  if (delete_in_destructor) {
    tmp_file->DoNotRemove();
    files_to_delete_.push_back(tmp_file->path);
  }
  return tmp_file;
}

void ScopedTempFiles::RegisterTempFile(const std::string& path) {
  files_to_delete_.emplace_back(path);
}

bool SignalIsIgnored(int signo) {
  struct sigaction act;
  if (sigaction(signo, nullptr, &act) != 0) {
    PLOG(FATAL) << "failed to query signal handler for signal " << signo;
  }

  if ((act.sa_flags & SA_SIGINFO)) {
    return false;
  }

  return act.sa_handler == SIG_IGN;
}

int GetAndroidVersion() {
#if defined(__ANDROID__)
  static int android_version = -1;
  if (android_version == -1) {
    android_version = 0;
    std::string s = android::base::GetProperty("ro.build.version.codename", "REL");
    if (s == "REL") {
      s = android::base::GetProperty("ro.build.version.release", "");
    }
    // The release string can be a list of numbers (like 8.1.0), a character (like Q)
    // or many characters (like OMR1).
    if (!s.empty()) {
      // Each Android version has a version number: L is 5, M is 6, N is 7, O is 8, etc.
      if (s[0] >= 'A' && s[0] <= 'Z') {
        android_version = s[0] - 'P' + kAndroidVersionP;
      } else if (isdigit(s[0])) {
        sscanf(s.c_str(), "%d", &android_version);
      }
    }
  }
  return android_version;
#else  // defined(__ANDROID__)
  return 0;
#endif
}

std::string GetHardwareFromCpuInfo(const std::string& cpu_info) {
  for (auto& line : android::base::Split(cpu_info, "\n")) {
    size_t pos = line.find(':');
    if (pos != std::string::npos) {
      std::string key = android::base::Trim(line.substr(0, pos));
      if (key == "Hardware") {
        return android::base::Trim(line.substr(pos + 1));
      }
    }
  }
  return "";
}

bool MappedFileOnlyExistInMemory(const char* filename) {
  // Mapped files only existing in memory:
  //   empty name
  //   [anon:???]
  //   [stack]
  //   /dev/*
  //   //anon: generated by kernel/events/core.c.
  //   /memfd: created by memfd_create.
  return filename[0] == '\0' || (filename[0] == '[' && strcmp(filename, "[vdso]") != 0) ||
         strncmp(filename, "//", 2) == 0 || strncmp(filename, "/dev/", 5) == 0 ||
         strncmp(filename, "/memfd:", 7) == 0;
}

std::string GetCompleteProcessName(pid_t pid) {
  std::string argv0;
  if (!android::base::ReadFileToString("/proc/" + std::to_string(pid) + "/cmdline", &argv0)) {
    // Maybe we don't have permission to read it.
    return std::string();
  }
  size_t pos = argv0.find('\0');
  if (pos != std::string::npos) {
    argv0.resize(pos);
  }
  // argv0 can be empty if the process is in zombie state. In that case, we don't want to pass argv0
  // to Basename(), which returns ".".
  return argv0.empty() ? std::string() : android::base::Basename(argv0);
}

const char* GetTraceFsDir() {
  static const char* tracefs_dir = nullptr;
  if (tracefs_dir == nullptr) {
    for (const char* path : {"/sys/kernel/debug/tracing", "/sys/kernel/tracing"}) {
      if (IsDir(path)) {
        tracefs_dir = path;
        break;
      }
    }
  }
  return tracefs_dir;
}

std::optional<std::pair<int, int>> GetKernelVersion() {
  static std::optional<std::pair<int, int>> kernel_version;
  if (!kernel_version.has_value()) {
    utsname uname_buf;
    int major;
    int minor;
    if (TEMP_FAILURE_RETRY(uname(&uname_buf)) != 0 ||
        sscanf(uname_buf.release, "%d.%d", &major, &minor) != 2) {
      return std::nullopt;
    }
    kernel_version = std::make_pair(major, minor);
  }
  return kernel_version;
}

#if defined(__ANDROID__)
bool IsInAppUid() {
  return getuid() % AID_USER_OFFSET >= AID_APP_START;
}
#endif

std::optional<uid_t> GetProcessUid(pid_t pid) {
  std::string status_file = "/proc/" + std::to_string(pid) + "/status";
  LineReader reader(status_file);
  if (!reader.Ok()) {
    return std::nullopt;
  }

  std::string* line;
  while ((line = reader.ReadLine()) != nullptr) {
    if (android::base::StartsWith(*line, "Uid:")) {
      uid_t uid;
      if (sscanf(line->data() + strlen("Uid:"), "%u", &uid) == 1) {
        return uid;
      }
    }
  }
  return std::nullopt;
}

std::vector<ARMCpuModel> GetARMCpuModels() {
  std::vector<ARMCpuModel> cpu_models;
  LineReader reader("/proc/cpuinfo");
  if (!reader.Ok()) {
    return cpu_models;
  }
  auto add_cpu = [&](uint32_t processor, uint32_t implementer, uint32_t partnum) {
    for (auto& model : cpu_models) {
      if (model.implementer == implementer && model.partnum == partnum) {
        model.cpus.push_back(processor);
        return;
      }
    }
    cpu_models.resize(cpu_models.size() + 1);
    ARMCpuModel& model = cpu_models.back();
    model.implementer = implementer;
    model.partnum = partnum;
    model.cpus.push_back(processor);
  };

  uint32_t processor = 0;
  uint32_t implementer = 0;
  uint32_t partnum = 0;
  int parsed = 0;
  std::string* line;
  while ((line = reader.ReadLine()) != nullptr) {
    std::vector<std::string> strs = android::base::Split(*line, ":");
    if (strs.size() != 2) {
      continue;
    }
    std::string name = android::base::Trim(strs[0]);
    std::string value = android::base::Trim(strs[1]);
    if (name == "processor") {
      if (android::base::ParseUint(value, &processor)) {
        parsed |= 1;
      }
    } else if (name == "CPU implementer") {
      if (android::base::ParseUint(value, &implementer)) {
        parsed |= 2;
      }
    } else if (name == "CPU part") {
      if (android::base::ParseUint(value, &partnum) && parsed == 0x3) {
        add_cpu(processor, implementer, partnum);
      }
      parsed = 0;
    }
  }
  return cpu_models;
}

}  // namespace simpleperf
