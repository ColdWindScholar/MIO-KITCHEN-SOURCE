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

#ifndef ANDROID_UTILS_SINGLETON_TEST_H
#define ANDROID_UTILS_SINGLETON_TEST_H


#include "Singleton_test.h"

namespace android {

struct SingletonTestData : Singleton<SingletonTestData> {
    unsigned int contents;
};

#ifdef __cplusplus
extern "C" {
#endif

unsigned int singletonGetInstanceContents();
void singletonSetInstanceContents(unsigned int);
bool singletonHasInstance();

#ifdef __cplusplus
}
#endif

}

#endif // ANDROID_UTILS_SINGLETON_TEST_H

