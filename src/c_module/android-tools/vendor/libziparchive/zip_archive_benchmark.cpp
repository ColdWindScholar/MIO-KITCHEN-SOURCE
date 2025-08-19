/*
 * Copyright (C) 2017 The Android Open Source Project
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

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include <android-base/test_utils.h>
#include <benchmark/benchmark.h>
#include <ziparchive/zip_archive.h>
#include <ziparchive/zip_archive_stream_entry.h>
#include <ziparchive/zip_writer.h>

static std::unique_ptr<TemporaryFile> CreateZip(int size = 4, int count = 1000,
                                                bool compress = true) {
  auto result = std::make_unique<TemporaryFile>();
  FILE* fp = fdopen(result->fd, "w");

  ZipWriter writer(fp);
  std::string baseName = "file";
  for (size_t i = 0; i < count; i++) {
    // Make file names longer and longer.
    if (i && (i % 100 == 0)) {
      baseName += "more";
    }
    std::string name = baseName + std::to_string(i);
    writer.StartEntry(name.c_str(), compress ? ZipWriter::kCompress : 0);
    while (size > 0) {
      writer.WriteBytes("helo", 4);
      size -= 4;
    }
    writer.FinishEntry();
  }
  writer.Finish();
  fclose(fp);

  return result;
}

static void OpenClose(benchmark::State& state) {
  std::unique_ptr<TemporaryFile> temp_file(CreateZip(4, int(state.range(0))));
  ZipArchiveHandle handle;
  for (auto _ : state) {
    OpenArchive(temp_file->path, &handle);
    CloseArchive(handle);
  }
}
BENCHMARK(OpenClose)->Arg(1)->Arg(10)->Arg(1000)->Arg(10000);

static void FindEntry_no_match(benchmark::State& state) {
  // Create a temporary zip archive.
  std::unique_ptr<TemporaryFile> temp_file(CreateZip(4, int(state.range(0))));
  ZipArchiveHandle handle;
  ZipEntry data;

  // In order to walk through all file names in the archive, look for a name
  // that does not exist in the archive.
  std::string_view name("thisFileNameDoesNotExist");

  // Start the benchmark.
  OpenArchive(temp_file->path, &handle);
  for (auto _ : state) {
    FindEntry(handle, name, &data);
  }
  CloseArchive(handle);
}
BENCHMARK(FindEntry_no_match)->Arg(1)->Arg(10)->Arg(1000)->Arg(10000);

static void Iterate_all_files(benchmark::State& state) {
  std::unique_ptr<TemporaryFile> temp_file(CreateZip(4, int(state.range(0))));
  ZipArchiveHandle handle;
  void* iteration_cookie;
  ZipEntry data;
  std::string_view name;

  OpenArchive(temp_file->path, &handle);
  for (auto _ : state) {
    StartIteration(handle, &iteration_cookie);
    while (Next(iteration_cookie, &data, &name) == 0) {
    }
    EndIteration(iteration_cookie);
  }
  CloseArchive(handle);
}
BENCHMARK(Iterate_all_files)->Arg(1)->Arg(10)->Arg(1000)->Arg(10000);

static void StartAlignedEntry(benchmark::State& state) {
  TemporaryFile file;
  FILE* fp = fdopen(file.fd, "w");

  ZipWriter writer(fp);

  auto alignment = uint32_t(state.range(0));
  std::string name = "name";
  int counter = 0;
  for (auto _ : state) {
    writer.StartAlignedEntry(name + std::to_string(counter++), 0, alignment);
    state.PauseTiming();
    writer.FinishEntry();
    state.ResumeTiming();
  }

  writer.Finish();
  fclose(fp);
}
BENCHMARK(StartAlignedEntry)->Arg(2)->Arg(16)->Arg(1024)->Arg(4096);

static void ExtractEntry(benchmark::State& state) {
  const auto size = int(state.range(0));
  std::unique_ptr<TemporaryFile> temp_file(CreateZip(size * 1024, 1));

  ZipArchiveHandle handle;
  ZipEntry data;
  if (OpenArchive(temp_file->path, &handle)) {
    state.SkipWithError("Failed to open archive");
  }
  if (FindEntry(handle, "file0", &data)) {
    state.SkipWithError("Failed to find archive entry");
  }

  std::vector<uint8_t> buffer(size * 1024);
  for (auto _ : state) {
    if (ExtractToMemory(handle, &data, buffer.data(), uint32_t(buffer.size()))) {
      state.SkipWithError("Failed to extract archive entry");
      break;
    }
  }
  CloseArchive(handle);
}

BENCHMARK(ExtractEntry)->Arg(2)->Arg(16)->Arg(64)->Arg(1024)->Arg(4096);

static void ExtractStored(benchmark::State& state) {
  const auto size = int(state.range(0));
  std::unique_ptr<TemporaryFile> temp_file(CreateZip(size * 1024, 1, false));

  ZipArchiveHandle handle;
  ZipEntry data;
  if (OpenArchive(temp_file->path, &handle)) {
    state.SkipWithError("Failed to open archive");
  }
  if (FindEntry(handle, "file0", &data)) {
    state.SkipWithError("Failed to find archive entry");
  }

  std::vector<uint8_t> buffer(size * 1024);
  for (auto _ : state) {
    if (ExtractToMemory(handle, &data, buffer.data(), uint32_t(buffer.size()))) {
      state.SkipWithError("Failed to extract archive entry");
      break;
    }
  }
  CloseArchive(handle);
}

BENCHMARK(ExtractStored)->Arg(2)->Arg(16)->Arg(64)->Arg(1024)->Arg(4096);

BENCHMARK_MAIN();
