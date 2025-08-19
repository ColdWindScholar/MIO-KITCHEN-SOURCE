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

#include <unistd.h>
#include <stdlib.h>
#include <limits.h>
#include <time.h>
#include <linux/input.h>

#include <functional>

#include <cutils/klog.h>
#include <minui/minui.h>
#include <utils/SystemClock.h>

#define NEXT_TIMEOUT_MS 5000
#define LAST_TIMEOUT_MS 30000

#define LOGE(x...) do { KLOG_ERROR("slideshow", x); } while (0)

static int input_cb(int fd, unsigned int epevents, int *key_code)
{
    struct input_event ev;

    *key_code = -1;

    if (ev_get_input(fd, epevents, &ev)) {
        return -1;
    }

    if (ev.type == EV_KEY && ev.value == 1) {
        *key_code = ev.code;
    }

    return 0;
}

static void clear()
{
    gr_color(0, 0, 0, 0);
    gr_clear();
    gr_flip();
}

static void draw(const char *resname)
{
    GRSurface* surface;
    int w, h, x, y;

    if (res_create_display_surface(resname, &surface) < 0) {
        LOGE("failed to create surface for %s\n", resname);
        return;
    }

    w = gr_get_width(surface);
    h = gr_get_height(surface);
    x = (gr_fb_width() - w) / 2;
    y = (gr_fb_height() - h) / 2;

    gr_blit(surface, 0, 0, w, h, x, y);
    gr_flip();

    res_free_surface(surface);
}

int usage()
{
    LOGE("usage: slideshow [-t timeout] image.png [image2.png ...] last.png\n");
    return EXIT_FAILURE;
}

int main(int argc, char **argv)
{
    int key_code = -1;
    int input = false;
    int opt;
    long int timeout = NEXT_TIMEOUT_MS;
    int64_t start;

    while ((opt = getopt(argc, argv, "t:")) != -1) {
        switch (opt) {
        case 't':
            timeout = strtol(optarg, NULL, 0);

            if (timeout < 0 || timeout >= LONG_MAX) {
                timeout = NEXT_TIMEOUT_MS;
                LOGE("invalid timeout %s, defaulting to %ld\n", optarg,
                    timeout);
            }
            break;
        default:
            return usage();
        }
    }

    if (optind >= argc) {
        return usage();
    }

    if (gr_init() == -1 || ev_init(std::bind(&input_cb, std::placeholders::_1,
                                             std::placeholders::_2, &key_code)) == -1) {
        LOGE("failed to initialize minui\n");
        return EXIT_FAILURE;
    }

    /* display all images except the last one, switch to next image after
     * timeout or user input */

    while (optind < argc - 1) {
        draw(argv[optind++]);

        start = android::uptimeMillis();
        long int timeout_remaining = timeout;
        do {
            if (ev_wait(timeout_remaining) == 0) {
                ev_dispatch();

                if (key_code != -1) {
                    input = true;
                    break;
                }
            }
            timeout_remaining -= android::uptimeMillis() - start;
        } while (timeout_remaining > 0);
    };

    /* if there was user input while showing the images, display the last
     * image and wait until the power button is pressed or LAST_TIMEOUT_MS
     * has elapsed */

    if (input) {
        start = android::uptimeMillis();

        draw(argv[optind]);

        do {
            if (ev_wait(timeout) == 0) {
                ev_dispatch();
            }

            if (android::uptimeMillis() - start >= LAST_TIMEOUT_MS) {
                break;
            }
        } while (key_code != KEY_POWER);
    }

    clear();
    gr_exit();
    ev_exit();

    return EXIT_SUCCESS;
}
