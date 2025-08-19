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
package com.android.car.test.stressfs;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Bundle;
import android.os.IBinder;

/**
 * Used to instantiate the WritingService service at a high priority.
 */
public class WritingActivity extends Activity {

    private static final String TAG = "StressFS";

    /**
     * Activity-wide connection to keep the service going.
     * Not used for any specific interaction.
     */
    private ServiceConnection mConnection = new ServiceConnection() {
        /** No-op */
        public void onServiceConnected(ComponentName className, IBinder service) {
            // Nothing to do.
        }

        /** No-op */
        public void onServiceDisconnected(ComponentName className) {
            // Nothing to do.
        }
    };

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        bindService(
            new Intent(
                getIntent().getAction(),
                getIntent().getData(),
                this,
                WritingService.class),
            mConnection,
            Context.BIND_AUTO_CREATE);
    }
}
