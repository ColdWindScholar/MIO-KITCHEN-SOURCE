/*
 * Copyright (C) 2015 The Android Open Source Project
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

#include <pthread.h>

#include "Thread.h"

Thread::Thread() {
  pthread_cond_init(&cond_, nullptr);
}

Thread::~Thread() {
  pthread_cond_destroy(&cond_);
}

void Thread::WaitForReady() {
  pthread_mutex_lock(&mutex_);
  while (pending_) {
    pthread_cond_wait(&cond_, &mutex_);
  }
  pthread_mutex_unlock(&mutex_);
}

void Thread::WaitForPending() {
  pthread_mutex_lock(&mutex_);
  while (!pending_) {
    pthread_cond_wait(&cond_, &mutex_);
  }
  pthread_mutex_unlock(&mutex_);
}

void Thread::SetPending() {
  pthread_mutex_lock(&mutex_);
  pending_ = true;
  pthread_mutex_unlock(&mutex_);
  pthread_cond_signal(&cond_);
}

void Thread::ClearPending() {
  pthread_mutex_lock(&mutex_);
  pending_ = false;
  pthread_mutex_unlock(&mutex_);
  pthread_cond_signal(&cond_);
}
