/* Copyright (C) 2008 The Android Open Source Project
 */

#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <linux/ioctl.h>

#define AUDIO_IOCTL_MAGIC 'a'

#define AUDIO_START        _IOW(AUDIO_IOCTL_MAGIC, 0, unsigned)
#define AUDIO_STOP         _IOW(AUDIO_IOCTL_MAGIC, 1, unsigned)
#define AUDIO_FLUSH        _IOW(AUDIO_IOCTL_MAGIC, 2, unsigned)
#define AUDIO_GET_CONFIG   _IOR(AUDIO_IOCTL_MAGIC, 3, unsigned)
#define AUDIO_SET_CONFIG   _IOW(AUDIO_IOCTL_MAGIC, 4, unsigned)
#define AUDIO_GET_STATS    _IOR(AUDIO_IOCTL_MAGIC, 5, unsigned)

struct msm_audio_config {
    uint32_t buffer_size;
    uint32_t buffer_count;
    uint32_t channel_count;
    uint32_t sample_rate;
    uint32_t codec_type;
    uint32_t unused[3];
};

struct msm_audio_stats {
    uint32_t out_bytes;
    uint32_t unused[3];
};
    
int pcm_play(unsigned rate, unsigned channels,
             int (*fill)(void *buf, unsigned sz, void *cookie),
             void *cookie)
{
    struct msm_audio_config config;
#if 0
    struct msm_audio_stats stats;
#endif
    unsigned sz, n;
    char buf[8192];
    int afd;
    
    afd = open("/dev/msm_pcm_out", O_RDWR);
    if (afd < 0) {
        perror("pcm_play: cannot open audio device");
        return -1;
    }

    if(ioctl(afd, AUDIO_GET_CONFIG, &config)) {
        perror("could not get config");
        return -1;
    }

    config.channel_count = channels;
    config.sample_rate = rate;
    if (ioctl(afd, AUDIO_SET_CONFIG, &config)) {
        perror("could not set config");
        return -1;
    }
    sz = config.buffer_size;
    if (sz > sizeof(buf)) {
        fprintf(stderr,"too big\n");
        return -1;
    }

    fprintf(stderr,"prefill\n");
    for (n = 0; n < config.buffer_count; n++) {
        if (fill(buf, sz, cookie))
            break;
        if (write(afd, buf, sz) != (ssize_t) sz)
            break;
    }

    fprintf(stderr,"start\n");
    ioctl(afd, AUDIO_START, 0);

    for (;;) {
#if 0
        if (ioctl(afd, AUDIO_GET_STATS, &stats) == 0)
            fprintf(stderr,"%10d\n", stats.out_bytes);
#endif
        if (fill(buf, sz, cookie))
            break;
        if (write(afd, buf, sz) != (ssize_t) sz)
            break;
    }

    close(afd);
    return 0;
}

/* http://ccrma.stanford.edu/courses/422/projects/WaveFormat/ */

#define ID_RIFF 0x46464952
#define ID_WAVE 0x45564157
#define ID_FMT  0x20746d66
#define ID_DATA 0x61746164

#define FORMAT_PCM 1

struct wav_header {
	uint32_t riff_id;
	uint32_t riff_sz;
	uint32_t riff_fmt;
	uint32_t fmt_id;
	uint32_t fmt_sz;
	uint16_t audio_format;
	uint16_t num_channels;
	uint32_t sample_rate;
	uint32_t byte_rate;       /* sample_rate * num_channels * bps / 8 */
	uint16_t block_align;     /* num_channels * bps / 8 */
	uint16_t bits_per_sample;
	uint32_t data_id;
	uint32_t data_sz;
};


static char *next;
static unsigned avail;

int fill_buffer(void *buf, unsigned sz, void *cookie)
{
    if (sz > avail)
        return -1;
    memcpy(buf, next, sz);
    next += sz;
    avail -= sz;
    return 0;
}

void play_file(unsigned rate, unsigned channels,
               int fd, unsigned count)
{
    next = malloc(count);
    if (!next) {
        fprintf(stderr,"could not allocate %d bytes\n", count);
        return;
    }
    if (read(fd, next, count) != (ssize_t) count) {
        fprintf(stderr,"could not read %d bytes\n", count);
        return;
    }
    avail = count;
    pcm_play(rate, channels, fill_buffer, 0);
}

int wav_play(const char *fn)
{
	struct wav_header hdr;
	int fd;
	fd = open(fn, O_RDONLY);
	if (fd < 0) {
        fprintf(stderr, "playwav: cannot open '%s'\n", fn);
		return -1;
	}
	if (read(fd, &hdr, sizeof(hdr)) != sizeof(hdr)) {
        fprintf(stderr, "playwav: cannot read header\n");
		return -1;
	}
    fprintf(stderr,"playwav: %d ch, %d hz, %d bit, %s\n",
            hdr.num_channels, hdr.sample_rate, hdr.bits_per_sample,
            hdr.audio_format == FORMAT_PCM ? "PCM" : "unknown");
    
    if ((hdr.riff_id != ID_RIFF) ||
        (hdr.riff_fmt != ID_WAVE) ||
        (hdr.fmt_id != ID_FMT)) {
        fprintf(stderr, "playwav: '%s' is not a riff/wave file\n", fn);
        return -1;
    }
    if ((hdr.audio_format != FORMAT_PCM) ||
        (hdr.fmt_sz != 16)) {
        fprintf(stderr, "playwav: '%s' is not pcm format\n", fn);
        return -1;
    }
    if (hdr.bits_per_sample != 16) {
        fprintf(stderr, "playwav: '%s' is not 16bit per sample\n", fn);
        return -1;
    }

    play_file(hdr.sample_rate, hdr.num_channels,
              fd, hdr.data_sz);
    
    return 0;
}

int wav_rec(const char *fn, unsigned channels, unsigned rate)
{
    struct wav_header hdr;
    unsigned char buf[8192];
    struct msm_audio_config cfg;
    unsigned sz;
    int fd, afd;
    unsigned total = 0;
    unsigned char tmp;
    
    hdr.riff_id = ID_RIFF;
    hdr.riff_sz = 0;
    hdr.riff_fmt = ID_WAVE;
    hdr.fmt_id = ID_FMT;
    hdr.fmt_sz = 16;
    hdr.audio_format = FORMAT_PCM;
    hdr.num_channels = channels;
    hdr.sample_rate = rate;
    hdr.byte_rate = hdr.sample_rate * hdr.num_channels * 2;
    hdr.block_align = hdr.num_channels * 2;
    hdr.bits_per_sample = 16;
    hdr.data_id = ID_DATA;
    hdr.data_sz = 0;

    fd = open(fn, O_CREAT | O_RDWR, 0666);
    if (fd < 0) {
        perror("cannot open output file");
        return -1;
    }
    write(fd, &hdr, sizeof(hdr));

    afd = open("/dev/msm_pcm_in", O_RDWR);
    if (afd < 0) {
        perror("cannot open msm_pcm_in");
        close(fd);
        return -1;
    }

        /* config change should be a read-modify-write operation */
    if (ioctl(afd, AUDIO_GET_CONFIG, &cfg)) {
        perror("cannot read audio config");
        goto fail;
    }

    cfg.channel_count = hdr.num_channels;
    cfg.sample_rate = hdr.sample_rate;
    if (ioctl(afd, AUDIO_SET_CONFIG, &cfg)) {
        perror("cannot write audio config");
        goto fail;
    }

    if (ioctl(afd, AUDIO_GET_CONFIG, &cfg)) {
        perror("cannot read audio config");
        goto fail;
    }

    sz = cfg.buffer_size;
    fprintf(stderr,"buffer size %d x %d\n", sz, cfg.buffer_count);
    if (sz > sizeof(buf)) {
        fprintf(stderr,"buffer size %d too large\n", sz);
        goto fail;
    }

    if (ioctl(afd, AUDIO_START, 0)) {
        perror("cannot start audio");
        goto fail;
    }

    fcntl(0, F_SETFL, O_NONBLOCK);
    fprintf(stderr,"\n*** RECORDING * HIT ENTER TO STOP ***\n");

    for (;;) {
        while (read(0, &tmp, 1) == 1) {
            if ((tmp == 13) || (tmp == 10)) goto done;
        }
        if (read(afd, buf, sz) != (ssize_t) sz) {
            perror("cannot read buffer");
            goto fail;
        }
        if (write(fd, buf, sz) != (ssize_t) sz) {
            perror("cannot write buffer");
            goto fail;
        }
        total += sz;

    }
done:
    close(afd);

        /* update lengths in header */
    hdr.data_sz = total;
    hdr.riff_sz = total + 8 + 16 + 8;
    lseek(fd, 0, SEEK_SET);
    write(fd, &hdr, sizeof(hdr));
    close(fd);
    return 0;

fail:
    close(afd);
    close(fd);
    unlink(fn);
    return -1;
}

int mp3_play(const char *fn)
{
    char buf[64*1024];
    int r;
    int fd, afd;

    fd = open(fn, O_RDONLY);
    if (fd < 0) {
        perror("cannot open mp3 file");
        return -1;
    }

    afd = open("/dev/msm_mp3", O_RDWR);
    if (afd < 0) {
        close(fd);
        perror("cannot open mp3 output device");
        return -1;
    }

    fprintf(stderr,"MP3 PLAY\n");
    ioctl(afd, AUDIO_START, 0);

    for (;;) {
        r = read(fd, buf, 64*1024);
        if (r <= 0) break;
        r = write(afd, buf, r);
        if (r < 0) break;
    }

    close(fd);
    close(afd);
    return 0;
}

int main(int argc, char **argv)
{
    const char *fn = 0;
    int play = 1;
    unsigned channels = 1;
    unsigned rate = 44100;

    argc--;
    argv++;
    while (argc > 0) {
        if (!strcmp(argv[0],"-rec")) {
            play = 0;
        } else if (!strcmp(argv[0],"-play")) {
            play = 1;
        } else if (!strcmp(argv[0],"-stereo")) {
            channels = 2;
        } else if (!strcmp(argv[0],"-mono")) {
            channels = 1;
        } else if (!strcmp(argv[0],"-rate")) {
            argc--;
            argv++;
            if (argc == 0) {
                fprintf(stderr,"playwav: -rate requires a parameter\n");
                return -1;
            }
            rate = atoi(argv[0]);
        } else {
            fn = argv[0];
        }
        argc--;
        argv++;
    }

    if (fn == 0) {
        fn = play ? "/data/out.wav" : "/data/rec.wav";
    }

    if (play) {
        const char *dot = strrchr(fn, '.');
        if (dot && !strcmp(dot,".mp3")) {
            return mp3_play(fn);
        } else {
            return wav_play(fn);
        }
    } else {
        return wav_rec(fn, channels, rate);
    }
	return 0;
}
