/*
 * Copyright (C) 2016 The Android Open Source Project
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

#ifndef COMMANDLINE_H
#define COMMANDLINE_H

#include <android-base/strings.h>

#include <optional>

#include "adb.h"
#include "adb_client.h"
#include "adb_unique_fd.h"
#include "transport.h"

// Callback used to handle the standard streams (stdout and stderr) sent by the
// device's upon receiving a command.

//
class StandardStreamsCallbackInterface {
  public:
    StandardStreamsCallbackInterface() {
    }
    // Handles the stdout output from devices supporting the Shell protocol.
    // Returns true on success and false on failure.
    virtual bool OnStdout(const char* buffer, size_t length) = 0;

    // Handles the stderr output from devices supporting the Shell protocol.
    // Returns true on success and false on failure.
    virtual bool OnStderr(const char* buffer, size_t length) = 0;

    // Indicates the communication is finished and returns the appropriate error
    // code.
    //
    // |status| has the status code returning by the underlying communication
    // channels
    virtual int Done(int status) = 0;

  protected:
    static bool OnStream(std::string* string, FILE* stream, const char* buffer, size_t length,
                         bool returnErrors) {
        if (string != nullptr) {
            string->append(buffer, length);
            return true;
        } else {
            bool okay = (fwrite(buffer, 1, length, stream) == length);
            fflush(stream);
            return returnErrors ? okay : true;
        }
    }

  private:
    DISALLOW_COPY_AND_ASSIGN(StandardStreamsCallbackInterface);
};

// Default implementation that redirects the streams to the equivalent host
// stream or to a string passed to the constructor.
class DefaultStandardStreamsCallback : public StandardStreamsCallbackInterface {
  public:
    // If |stdout_str| is non-null, OnStdout will append to it.
    // If |stderr_str| is non-null, OnStderr will append to it.
    DefaultStandardStreamsCallback(std::string* stdout_str, std::string* stderr_str)
        : stdout_str_(stdout_str), stderr_str_(stderr_str), returnErrors_(false) {
    }
    DefaultStandardStreamsCallback(std::string* stdout_str, std::string* stderr_str,
                                   bool returnErrors)
        : stdout_str_(stdout_str), stderr_str_(stderr_str), returnErrors_(returnErrors) {
    }

    bool OnStdout(const char* buffer, size_t length) {
        return OnStream(stdout_str_, stdout, buffer, length, returnErrors_);
    }

    bool OnStderr(const char* buffer, size_t length) {
        return OnStream(stderr_str_, stderr, buffer, length, returnErrors_);
    }

    int Done(int status) {
        return status;
    }

    void ReturnErrors(bool returnErrors) {
        returnErrors_ = returnErrors;
    }

  private:
    std::string* stdout_str_;
    std::string* stderr_str_;
    bool returnErrors_;

    DISALLOW_COPY_AND_ASSIGN(DefaultStandardStreamsCallback);
};

class SilentStandardStreamsCallbackInterface : public StandardStreamsCallbackInterface {
  public:
    SilentStandardStreamsCallbackInterface() = default;
    bool OnStdout(const char*, size_t) override final { return true; }
    bool OnStderr(const char*, size_t) override final { return true; }
    int Done(int status) override final { return status; }
};

// Singleton.
extern DefaultStandardStreamsCallback DEFAULT_STANDARD_STREAMS_CALLBACK;

int adb_commandline(int argc, const char** argv);

// Helper retrieval function.
const std::optional<FeatureSet>& adb_get_feature_set_or_die();

bool copy_to_file(int inFd, int outFd);

// Connects to the device "shell" service with |command| and prints the
// resulting output.
// if |callback| is non-null, stdout/stderr output will be handled by it.
int send_shell_command(
        const std::string& command, bool disable_shell_protocol = false,
        StandardStreamsCallbackInterface* callback = &DEFAULT_STANDARD_STREAMS_CALLBACK);

// Reads from |fd| and prints received data. If |use_shell_protocol| is true
// this expects that incoming data will use the shell protocol, in which case
// stdout/stderr are routed independently and the remote exit code will be
// returned.
// if |callback| is non-null, stdout/stderr output will be handled by it.
int read_and_dump(borrowed_fd fd, bool use_shell_protocol = false,
                  StandardStreamsCallbackInterface* callback = &DEFAULT_STANDARD_STREAMS_CALLBACK);

// Connects to the device "abb" service with |command| and returns the fd.
template <typename ContainerT>
unique_fd send_abb_exec_command(const ContainerT& command_args, std::string* error) {
    std::string service_string = "abb_exec:" + android::base::Join(command_args, ABB_ARG_DELIMETER);

    unique_fd fd(adb_connect(service_string, error));
    if (fd < 0) {
        fprintf(stderr, "adb: failed to run abb_exec. Error: %s\n", error->c_str());
        return unique_fd{};
    }
    return fd;
}

#endif  // COMMANDLINE_H
