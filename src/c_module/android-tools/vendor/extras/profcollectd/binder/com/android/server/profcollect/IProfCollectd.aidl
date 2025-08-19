/*
 * Copyright (C) 2020 The Android Open Source Project
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

package com.android.server.profcollect;

import com.android.server.profcollect.IProviderStatusCallback;

/** {@hide} */
interface IProfCollectd {
    void schedule();
    void terminate();
    void trace_system(@utf8InCpp String tag);
    void trace_process(@utf8InCpp String tag, @utf8InCpp String processes, float duration);
    void process();
    /** -1 if there is no usageSetting */
    @utf8InCpp String report(int usageSetting);
    @utf8InCpp String get_supported_provider();
    void registerProviderStatusCallback(IProviderStatusCallback cb);
}
