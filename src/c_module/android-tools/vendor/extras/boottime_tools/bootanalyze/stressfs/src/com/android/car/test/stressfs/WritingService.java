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

import android.app.Service;
import android.app.Notification;
import android.app.NotificationChannel;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.Environment;
import android.os.IBinder;
import android.util.Log;
import android.R.drawable;

import java.io.*;
import java.util.*;

/**
 * Used to stress the file writing before and during shutdown to help ensure
 * that the filesystem shuts down at the right time, in a consistent manner,
 * and does not get corrupted.
 *
 * Writes to two files - one on the data partition, one on the external storage
 * partition - simultaneous in two separate threads; starting over after a
 * certain amount of data is written.
 *
 * This class is intended to be invoked from the shell.  For a 64KB file
 * written in 1KB chunks, invoke from the host workstation:
 *   adb install -g StressFS.apk
 *   adb shell am start \
 *     -n com.android.car.test.stressfs/.WritingActivity \
 *     -a com.android.car.test.stressfs.START
 *     -d "stressfs://start?block=1024\&file=65536"
 *
 * After reboot:
 *   adb uninstall com.android.car.test.stressfs
 *   adb shell "rm -rf /storage/emulated/0/stressfs_data*"
 *
 * On boot after running this while shutting down, fsck should flag any
 * corruption that it sees resulting from this running.  The goal is to set the
 * shutdown sequence in a manner that does not corrupt so that this check can
 * be avoided.
 */
public class WritingService extends Service {

    private static final String TAG = "StressFS";

    private static final String ACTION_START = "com.android.car.test.stressfs.START";

    private static final int DEFAULT_BLOCK_SIZE = 4096;
    private static final int DEFAULT_FILE_SIZE = 16 * 1024 * 1024;

    private static final String FILENAME_PREFIX = "stressfs_data_";

    private static final int NOTIFICATION_ID = 100;

    /** Continuously writes test data to a specified file. */
    private static class WriteToDisk extends Thread {
        private final String mLogTag;
        private final File mFile;
        private final int mFileSize;
        private final byte[] mTestData;

        public WriteToDisk(
                String logTag,
                File file,
                int fileSize,
                byte[] testData) {
            mLogTag = logTag;
            mFile = file;
            mFileSize = fileSize;
            mTestData = testData;
        }

        /** Writes data to a file, restarting once the maximum amount of data is reached.*/
        @Override
        public void run() {
            Log.d(TAG, mLogTag + " thread started");
            while (true) {
                try {
                    FileOutputStream fos = new FileOutputStream(mFile);
                    // Write in chunks until the amount of data requested
                    // is written.
                    for (int j = 0; j < mFileSize; j += mTestData.length) {
                        fos.write(mTestData);
                    }
                    fos.close();
                } catch (FileNotFoundException e) {
                    Log.e(TAG, "File not found: ", e);
                } catch (IOException e) {
                    Log.e(TAG, "IO error: ", e);
                }
            }
        }
    }

    /** Raises service priority and starts the writing threads. */
    @Override
    public IBinder onBind(Intent intent) {
        Notification notification =
                new Notification.Builder(this, NotificationChannel.DEFAULT_CHANNEL_ID)
                        .setContentTitle("Stress Filesystem service running.")
                        .setSmallIcon(drawable.ic_menu_save)
                        .build();

        // Raise priority of this service.
        startForeground(NOTIFICATION_ID, notification);

        File dataPartitionFile = getFileStreamPath(FILENAME_PREFIX + UUID.randomUUID());
        File externalPartitionFile = new File(
                Environment.getExternalStorageDirectory(), FILENAME_PREFIX + UUID.randomUUID());

        Log.i(TAG, "External storage state: " +
                Environment.getExternalStorageState(externalPartitionFile));

        Uri data = intent.getData();
        if (data != null) {
            Log.i(TAG, "Data: " + data.toString());
        }
        int blockSize = getQueryParam(data, "block", DEFAULT_BLOCK_SIZE);
        int fileSize = getQueryParam(data, "file", DEFAULT_FILE_SIZE);
        Log.i(TAG, "Block Size: " + blockSize);
        Log.i(TAG, "File Size: " + fileSize);

        if (fileSize % blockSize != 0) {
            Log.w(TAG, "File size should be a multiple of block size.");
        }

        // Populate some test data.
        StringBuilder builder = new StringBuilder(blockSize);
        for (int i = 0; i < builder.capacity(); i++) {
            builder.append((char)(i % 26 + 'A'));
        }
        byte[] testData = new String(builder).getBytes();

        // Spawn two threads - one to write to the /data partition, one to
        // write to the SD card.
        new WriteToDisk("data", dataPartitionFile, fileSize, testData).start();
        new WriteToDisk("external", externalPartitionFile, fileSize, testData).start();

        // No need to return a binder interface, since there is no more
        // interaction needed from the activity starting the service.
        return null;
    }

    /** Keeps service alive once started. */
    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    /** Parses an integer query parameter from the input Uri. */
    private int getQueryParam(Uri data, String key, int defaultValue) {
        if (data == null) {
            return defaultValue;
        }
        String inValString = data.getQueryParameter(key);
        if (inValString != null) {
            try {
                int inVal = Integer.parseInt(inValString);
                if (inVal != 0) {
                    return inVal;
                }
            } catch (NumberFormatException e) {
                return defaultValue;
            }
        }
        return defaultValue;
    }
}
