/*
 * Copyright (C) 2014 The Android Open Source Project
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

#pragma once

#include <signal.h>
#include <gtest/gtest.h>

#include <array>
#include <memory>

#if !defined(__BIONIC__)
#define sigaction64 sigaction
#endif

// INTRODUCTION
//
// It can be useful to disable debuggerd stack traces/tombstones in death tests.
// Reasons include:
//
//   1. speeding up death tests
//   2. reducing the noise in logcat (for humans)
//   3. avoiding bots from thinking that expected deaths should be reported in
//      stability metrics/have bugs auto-filed
//
// When writing new death tests, inherit the test suite from SilentDeathTest
// defined below.
//
// Only use ScopedSilentDeath in a test case/suite if changing the test base
// class from testing::Test to SilentDeathTest adds additional complextity when
// test suite code is shared between death and non-death tests.
//
// EXAMPLES
//
// For example, use SilentDeathTest for this simple case where there's no shared
// setup or teardown:
//
//   using FooDeathTest = SilentDeathTest;
//
//   TEST(FooTest, DoesThis) {
//     // normal test
//   }
//
//   TEST_F(FooDeathTest, DoesThat) {
//     // death test
//   }
//
// Alternatively, use ScopedSilentDeath if you already have a Test subclass for
// shared setup or teardown:
//
//   class FooTest : public testing::Test { ... /* shared setup/teardown */ };
//
//   using FooDeathTest = FooTest;
//
//   TEST_F(FooTest, DoesThis) {
//     // normal test
//   }
//
//   TEST_F(FooDeathTest, DoesThat) {
//     ScopedSilentDeath _silentDeath;
//     // death test
//   }
//
// NOTES
//
// When writing death tests, consider using ASSERT_EXIT() and EXPECT_EXIT()
// rather than the more obvious ASSERT_DEATH()/EXPECT_DEATH() macros... The
// advantage is that you can specify a regular expression that you expect
// the abort message to match, and can be explicit about what signal you expect
// to die with, and you can also test for *successful* exits too. Examples:
//
//   ASSERT_DEATH(foo(), "some text\\. some more\\.");
//
//   ASSERT_EXIT(bar(), testing::ExitedWithCode(0), "Success");
//
//   ASSERT_EXIT(baz(), testing::KilledBySignal(SIGABRT),
//               "expected detail message \\(blah\\)");
//
// As you can see the regular expression functionality is there for
// ASSERT_DEATH() too, but it's important to realize that it's a regular
// expression, so (as in the first and third examples), you'll need to quote
// any metacharacters (and because it's a string literal, you'll either need
// extra quoting or want to use a raw string).

class ScopedSilentDeath {
 public:
  ScopedSilentDeath() {
    for (int signo : SUPPRESSED_SIGNALS) {
      struct sigaction64 action = {.sa_handler = SIG_DFL};
      sigaction64(signo, &action, &previous_);
    }
  }

  ~ScopedSilentDeath() {
    for (int signo : SUPPRESSED_SIGNALS) {
      sigaction64(signo, &previous_, nullptr);
    }
  }

 private:
  static constexpr std::array<int, 4> SUPPRESSED_SIGNALS = {SIGABRT, SIGBUS, SIGSEGV, SIGSYS};

  struct sigaction64 previous_;
};

class SilentDeathTest : public testing::Test {
 protected:
  void SetUp() override {
    silent_death_ = std::unique_ptr<ScopedSilentDeath>(new ScopedSilentDeath);
  }

  void TearDown() override { silent_death_.reset(); }

 private:
  std::unique_ptr<ScopedSilentDeath> silent_death_;
};
