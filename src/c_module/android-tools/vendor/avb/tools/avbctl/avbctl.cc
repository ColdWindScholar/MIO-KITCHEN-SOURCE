/*
 * Copyright (C) 2017 The Android Open Source Project
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy,
 * modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <stdio.h>
#include <string.h>
#include <sysexits.h>

#include <android-base/properties.h>

#include <libavb_user/libavb_user.h>

namespace {

static bool g_opt_force = false;

/* Prints program usage to |where|. */
void usage(FILE* where, int /* argc */, char* argv[]) {
  fprintf(where,
          "%s - command-line tool for AVB.\n"
          "\n"
          "Usage:\n"
          "  %s [--force] COMMAND\n"
          "\n"
          "Commands:\n"
          "  %s get-verity           - Prints whether verity is enabled in "
          "current slot.\n"
          "  %s disable-verity       - Disable verity in current slot.\n"
          "  %s enable-verity        - Enable verity in current slot.\n"
          "  %s get-verification     - Prints whether verification is enabled "
          "in current slot.\n"
          "  %s disable-verification - Disable verification in current slot.\n"
          "  %s enable-verification  - Enable verification in current slot.\n",
          argv[0],
          argv[0],
          argv[0],
          argv[0],
          argv[0],
          argv[0],
          argv[0],
          argv[0]);
}

/* Returns true if device is in LOCKED mode and --force wasn't
 * passed. In this case also prints diagnostic message to stderr as a
 * side-effect.
 */
bool is_locked_and_not_forced() {
  std::string device_state;

  device_state = android::base::GetProperty("ro.boot.vbmeta.device_state", "");
  if (device_state == "locked" && !g_opt_force) {
    fprintf(stderr,
            "Manipulating vbmeta on a LOCKED device will likely cause the\n"
            "device to fail booting with little chance of recovery.\n"
            "\n"
            "If you really want to do this, use the --force option.\n"
            "\n"
            "ONLY DO THIS IF YOU KNOW WHAT YOU ARE DOING.\n"
            "\n");
    return false;
  }

  return true;
}

/* Function to enable and disable verification. The |ops| parameter
 * should be an |AvbOps| from libavb_user.
 */
int do_set_verification(AvbOps* ops,
                        const std::string& ab_suffix,
                        bool enable_verification) {
  bool verification_enabled;

  if (!avb_user_verification_get(
          ops, ab_suffix.c_str(), &verification_enabled)) {
    fprintf(stderr, "Error getting whether verification is enabled.\n");
    return EX_SOFTWARE;
  }

  if ((verification_enabled && enable_verification) ||
      (!verification_enabled && !enable_verification)) {
    fprintf(stdout,
            "verification is already %s",
            verification_enabled ? "enabled" : "disabled");
    if (ab_suffix != "") {
      fprintf(stdout, " on slot with suffix %s", ab_suffix.c_str());
    }
    fprintf(stdout, ".\n");
    return EX_OK;
  }

  if (!is_locked_and_not_forced()) {
    return EX_NOPERM;
  }

  if (!avb_user_verification_set(ops, ab_suffix.c_str(), enable_verification)) {
    fprintf(stderr, "Error setting verification.\n");
    return EX_SOFTWARE;
  }

  fprintf(stdout,
          "Successfully %s verification",
          enable_verification ? "enabled" : "disabled");
  if (ab_suffix != "") {
    fprintf(stdout, " on slot with suffix %s", ab_suffix.c_str());
  }
  fprintf(stdout, ". Reboot the device for changes to take effect.\n");

  return EX_OK;
}

/* Function to query if verification. The |ops| parameter should be an
 * |AvbOps| from libavb_user.
 */
int do_get_verification(AvbOps* ops, const std::string& ab_suffix) {
  bool verification_enabled;

  if (!avb_user_verification_get(
          ops, ab_suffix.c_str(), &verification_enabled)) {
    fprintf(stderr, "Error getting whether verification is enabled.\n");
    return EX_SOFTWARE;
  }

  fprintf(stdout,
          "verification is %s",
          verification_enabled ? "enabled" : "disabled");
  if (ab_suffix != "") {
    fprintf(stdout, " on slot with suffix %s", ab_suffix.c_str());
  }
  fprintf(stdout, ".\n");

  return EX_OK;
}

/* Function to enable and disable dm-verity. The |ops| parameter
 * should be an |AvbOps| from libavb_user.
 */
int do_set_verity(AvbOps* ops,
                  const std::string& ab_suffix,
                  bool enable_verity) {
  bool verity_enabled;

  if (!avb_user_verity_get(ops, ab_suffix.c_str(), &verity_enabled)) {
    fprintf(stderr, "Error getting whether verity is enabled.\n");
    return EX_SOFTWARE;
  }

  if ((verity_enabled && enable_verity) ||
      (!verity_enabled && !enable_verity)) {
    fprintf(stdout,
            "verity is already %s",
            verity_enabled ? "enabled" : "disabled");
    if (ab_suffix != "") {
      fprintf(stdout, " on slot with suffix %s", ab_suffix.c_str());
    }
    fprintf(stdout, ".\n");
    return EX_OK;
  }

  if (!is_locked_and_not_forced()) {
    return EX_NOPERM;
  }

  if (!avb_user_verity_set(ops, ab_suffix.c_str(), enable_verity)) {
    fprintf(stderr, "Error setting verity.\n");
    return EX_SOFTWARE;
  }

  fprintf(
      stdout, "Successfully %s verity", enable_verity ? "enabled" : "disabled");
  if (ab_suffix != "") {
    fprintf(stdout, " on slot with suffix %s", ab_suffix.c_str());
  }
  fprintf(stdout, ". Reboot the device for changes to take effect.\n");

  return EX_OK;
}

/* Function to query if dm-verity is enabled. The |ops| parameter
 * should be an |AvbOps| from libavb_user.
 */
int do_get_verity(AvbOps* ops, const std::string& ab_suffix) {
  bool verity_enabled;

  if (!avb_user_verity_get(ops, ab_suffix.c_str(), &verity_enabled)) {
    fprintf(stderr, "Error getting whether verity is enabled.\n");
    return EX_SOFTWARE;
  }

  fprintf(stdout, "verity is %s", verity_enabled ? "enabled" : "disabled");
  if (ab_suffix != "") {
    fprintf(stdout, " on slot with suffix %s", ab_suffix.c_str());
  }
  fprintf(stdout, ".\n");

  return EX_OK;
}

/* Helper function to get A/B suffix, if any. If the device isn't
 * using A/B the empty string is returned. Otherwise either "_a",
 * "_b", ... is returned.
 */
std::string get_ab_suffix() {
  return android::base::GetProperty("ro.boot.slot_suffix", "");
}

}  // namespace

enum class Command {
  kNone,
  kDisableVerity,
  kEnableVerity,
  kGetVerity,
  kDisableVerification,
  kEnableVerification,
  kGetVerification,
};

int main(int argc, char* argv[]) {
  int ret;
  AvbOps* ops = nullptr;
  std::string ab_suffix = get_ab_suffix();
  Command cmd = Command::kNone;

  if (argc < 2) {
    usage(stderr, argc, argv);
    ret = EX_USAGE;
    goto out;
  }

  ops = avb_ops_user_new();
  if (ops == nullptr) {
    fprintf(stderr, "Error getting AVB ops.\n");
    ret = EX_SOFTWARE;
    goto out;
  }

  for (int n = 1; n < argc; n++) {
    if (strcmp(argv[n], "--force") == 0) {
      g_opt_force = true;
    } else if (strcmp(argv[n], "disable-verity") == 0) {
      cmd = Command::kDisableVerity;
    } else if (strcmp(argv[n], "enable-verity") == 0) {
      cmd = Command::kEnableVerity;
    } else if (strcmp(argv[n], "get-verity") == 0) {
      cmd = Command::kGetVerity;
    } else if (strcmp(argv[n], "disable-verification") == 0) {
      cmd = Command::kDisableVerification;
    } else if (strcmp(argv[n], "enable-verification") == 0) {
      cmd = Command::kEnableVerification;
    } else if (strcmp(argv[n], "get-verification") == 0) {
      cmd = Command::kGetVerification;
    }
  }

  switch (cmd) {
    case Command::kNone:
      usage(stderr, argc, argv);
      ret = EX_USAGE;
      break;
    case Command::kDisableVerity:
      ret = do_set_verity(ops, ab_suffix, false);
      break;
    case Command::kEnableVerity:
      ret = do_set_verity(ops, ab_suffix, true);
      break;
    case Command::kGetVerity:
      ret = do_get_verity(ops, ab_suffix);
      break;
    case Command::kDisableVerification:
      ret = do_set_verification(ops, ab_suffix, false);
      break;
    case Command::kEnableVerification:
      ret = do_set_verification(ops, ab_suffix, true);
      break;
    case Command::kGetVerification:
      ret = do_get_verification(ops, ab_suffix);
      break;
  }

out:
  if (ops != nullptr) {
    avb_ops_user_free(ops);
  }
  return ret;
}
