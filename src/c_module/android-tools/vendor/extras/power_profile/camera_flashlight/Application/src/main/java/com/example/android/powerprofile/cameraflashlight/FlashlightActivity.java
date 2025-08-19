/*
 * Copyright 2014 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.example.android.powerprofile.cameraflashlight;

import android.app.Activity;
import android.content.Context;
import android.hardware.camera2.CameraAccessException;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.os.Bundle;

public class FlashlightActivity extends Activity {

    private CameraManager mCameraManager;
    private String mCameraId;

    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        try {
            mCameraManager = (CameraManager) getSystemService(Context.CAMERA_SERVICE);

            for (String cameraId: mCameraManager.getCameraIdList()) {
                Boolean flashAvailable = mCameraManager.getCameraCharacteristics(cameraId).
                        get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                if (flashAvailable != null && Boolean.TRUE.equals(flashAvailable)) {
                    mCameraId = cameraId;
                    break;
                }
            }
        } catch (CameraAccessException e) {
            e.printStackTrace();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();

        try {
            if (mCameraId != null) {
                mCameraManager.setTorchMode(mCameraId, true);
            }
        } catch (CameraAccessException e) {
            e.printStackTrace();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();

        try {
            if (mCameraId != null) {
                mCameraManager.setTorchMode(mCameraId, false);
            }
        } catch (CameraAccessException e) {
            e.printStackTrace();
        }
    }

}
