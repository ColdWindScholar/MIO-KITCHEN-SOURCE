/*
 * Copyright (C) 2024 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at:
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

#include <record_file.h>
#include "fuzzer/FuzzedDataProvider.h"

using namespace simpleperf;
using namespace std;
using namespace android;
static uint32_t kMaxLen = 100;
static uint32_t kMinCount = 1;
static uint32_t kMaxCount = 1000;
static uint32_t kMinASCII = 0;
static uint32_t kMaxASCII = 255;

class SimplePerfWriterFuzzer {
 public:
  SimplePerfWriterFuzzer(const uint8_t* data, size_t size) : mFdp(data, size) {
    /**
     * Use maximum of 80% of buffer to write in FD and save at least 20% for fuzzing other APIs
     */
    const int32_t dataSize = mFdp.ConsumeIntegralInRange<int32_t>(0, (size * 80) / 100);
    std::vector<uint8_t> dataPointer = mFdp.ConsumeBytes<uint8_t>(dataSize);
    android::base::WriteFully(mTempfile.fd, dataPointer.data(), dataPointer.size());
  }
  void process();

 private:
  FuzzedDataProvider mFdp;
  TemporaryFile mTempfile;
  EventAttrIds mAttributeIDs;
  bool AddEvents();
  void CreateRecord();
};

bool SimplePerfWriterFuzzer::AddEvents() {
  size_t eventNo = mFdp.ConsumeIntegralInRange<size_t>(kMinCount, kMaxCount);
  for (size_t idx = 0; idx < eventNo; ++idx) {
    string event = mFdp.ConsumeRandomLengthString(kMaxLen);
    if (event.size() == 0) {
      event = "cpu-cycles";
    }
    uint64_t fakeID = mAttributeIDs.size();
    mAttributeIDs.resize(mAttributeIDs.size() + 1);
    EventAttrWithId& attrID = mAttributeIDs.back();
    std::unique_ptr<EventTypeAndModifier> eventTypeModifier = ParseEventType(event);
    if (!eventTypeModifier) {
      return false;
    }
    attrID.attr = CreateDefaultPerfEventAttr(eventTypeModifier->event_type);
    attrID.ids.push_back(fakeID);
  }
  return true;
}

void SimplePerfWriterFuzzer::process() {
  std::unique_ptr<RecordFileWriter> writer = RecordFileWriter::CreateInstance(mTempfile.path);
  if (!writer.get()) {
    return;
  }
  writer->WriteAttrSection(mAttributeIDs);
  int32_t features = mFdp.ConsumeIntegralInRange<int32_t>(kMinCount, kMaxCount);

  if (!AddEvents()) {
    return;
  }

  string event = mFdp.ConsumeRandomLengthString(kMaxLen);
  size_t index = mFdp.ConsumeIntegralInRange<size_t>(0, mAttributeIDs.size() - 1);
  perf_event_attr attr = mAttributeIDs[index].attr;
  MmapRecord mmprcd(
      attr, mFdp.ConsumeBool() /* in_kernel */, getpid() /* pid */, gettid() /* tid */,
      mFdp.ConsumeIntegral<uint64_t>() /* addr */, mFdp.ConsumeIntegral<uint64_t>() /* len */,
      mFdp.ConsumeIntegral<uint64_t>() /* pgoff */, event,
      mFdp.ConsumeIntegral<uint64_t>() /* event_id */, mFdp.ConsumeIntegral<uint64_t>() /* time */);

  writer->WriteRecord(mmprcd);
  writer->BeginWriteFeatures(features);
  std::vector<Dso*> dsos;
  while (features-- > 0) {
    auto invokeWriter = mFdp.PickValueInArray<const std::function<void()>>({
        [&]() {
          BuildId build_id(mFdp.ConsumeRandomLengthString(kMaxLen));
          std::vector<BuildIdRecord> buildIdRecords;
          buildIdRecords.push_back(
              BuildIdRecord(mFdp.ConsumeBool() /* in_kernel */, getpid() /* pid */, build_id,
                            mFdp.ConsumeRandomLengthString(kMaxLen) /* filename */));
          writer->WriteBuildIdFeature(buildIdRecords);
        },
        [&]() {
          writer->WriteFeatureString(
              mFdp.ConsumeBool() ? PerfFileFormat::FEAT_OSRELEASE : PerfFileFormat::FEAT_ARCH,
              mFdp.ConsumeRandomLengthString(kMaxLen) /* string */);
        },
        [&]() {
          std::vector<std::string> cmdline;
          cmdline.push_back("simpleperf");
          int32_t iter = mFdp.ConsumeIntegralInRange<int32_t>(kMinCount, kMaxCount);
          for (int32_t idx = 0; idx < iter; ++idx) {
            cmdline.push_back(mFdp.ConsumeRandomLengthString(kMaxLen));
          }
          writer->WriteCmdlineFeature(cmdline);
        },
        [&]() {
          int32_t iter = mFdp.ConsumeIntegralInRange<int32_t>(kMinCount, kMaxCount);
          for (int32_t idx = 0; idx < iter; ++idx) {
            DsoType dso_type =
                (DsoType)mFdp.ConsumeIntegralInRange<size_t>(DSO_KERNEL, DSO_UNKNOWN_FILE);
            std::unique_ptr<Dso> dso =
                Dso::CreateDso(dso_type, mFdp.ConsumeRandomLengthString(kMaxLen) /* path */,
                               mFdp.ConsumeBool() /*  force_64bit */);
            if (dso) {
              dsos.push_back(dso.release());
            }
          }
          writer->WriteFileFeatures(dsos);
        },
        [&]() {
          std::unordered_map<std::string, std::string> info_map;
          int32_t iter = mFdp.ConsumeIntegralInRange<int32_t>(kMinCount, kMaxCount);
          for (int32_t idx = 0; idx < iter; ++idx) {
            std::string key = mFdp.ConsumeRandomLengthString(kMaxLen);
            std::string value = mFdp.ConsumeRandomLengthString(kMaxLen);
            info_map[key] = value;
          }
          writer->WriteMetaInfoFeature(info_map);
        },
        [&]() { writer->WriteBranchStackFeature(); },
        [&]() {
          std::vector<uint64_t> auxtrace;
          int32_t iter = mFdp.ConsumeIntegralInRange<int32_t>(kMinCount, kMaxCount);
          for (int32_t idx = 0; idx < iter; ++idx) {
            auxtrace.push_back(mFdp.ConsumeIntegral<uint64_t>());
          }
          writer->WriteAuxTraceFeature(auxtrace);
        },
        [&]() {
          DebugUnwindFeature debugVector;
          int32_t iter = mFdp.ConsumeIntegralInRange<int32_t>(kMinCount, kMaxCount);
          for (int32_t idx = 0; idx < iter; ++idx) {
            DebugUnwindFile testFile;
            testFile.path = mFdp.ConsumeRandomLengthString(kMaxLen);
            testFile.size = kMaxLen;
            debugVector.push_back(testFile);
          }
          writer->WriteDebugUnwindFeature(debugVector);
        },
    });
    invokeWriter();
  }
  writer->EndWriteFeatures();
  writer->Close();
  for (Dso* dso : dsos) {
    delete dso;
    dso = nullptr;
  }
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  SimplePerfWriterFuzzer simplePerfWriterFuzzer(data, size);
  simplePerfWriterFuzzer.process();
  return 0;
}
