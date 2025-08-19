/*
 * Copyright (C) 2019 The Android Open Source Project
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

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android/lpdump/ILpdump.h>
#include <binder/IServiceManager.h>
#include <iostream>
#include <string>
#include <vector>

using namespace android;
using namespace std::chrono_literals;
using ::android::lpdump::ILpdump;

int Run(ILpdump* service, const std::vector<std::string>& args) {
    std::string output;
    binder::Status status = service->run(args, &output);
    if (status.isOk()) {
        std::cout << output;
        return 0;
    }
    std::cerr << status.exceptionMessage();
    if (status.serviceSpecificErrorCode() != 0) {
        return status.serviceSpecificErrorCode();
    }
    return -status.exceptionCode();
}

std::vector<std::string> GetArgVector(int argc, char* argv[]) {
    std::vector<std::string> args;
    args.reserve(argc);
    for (int i = 0; i < argc; ++i) {
        args.push_back(argv[i]);
    }
    return args;
}

class LpdumpService {
public:
    LpdumpService() {
        base::SetProperty("sys.lpdumpd", "start");
        status_t status = getService(String16("lpdump_service"), &service_);
        int wait_counter = 0;
        while (status != OK && wait_counter++ < 3) {
            sleep(1);
            status = getService(String16("lpdump"), &service_);
        }
        if (status != OK || service_ == nullptr) {
            std::cerr << "Cannot get lpdump service: " << strerror(-status) << std::endl;
            LOG(ERROR) << "Cannot get lpdump service: " << strerror(-status);
        }
    }
    ~LpdumpService() {
        base::SetProperty("sys.lpdumpd", "stop");
    }
    sp<ILpdump> get() { return service_; }
private:
    sp<ILpdump> service_;
};

int main(int argc, char* argv[]) {
    LpdumpService wrapper;
    sp<ILpdump> service = wrapper.get();
    if (service == nullptr) {
        return 1;
    }
    int ret = Run(service.get(), GetArgVector(argc, argv));
    base::SetProperty("sys.lpdumpd", "stop");
    return ret;
}
