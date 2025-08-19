#include <stdio.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdlib.h>
#include <getopt.h>
#include <string.h>
#include <errno.h>

const char* smaps_file = "smaps";
bool verbose = false;
int iterations = 1;
int bufsz = -1;

int64_t
get_pss(int pid)
{
  char filename[64];
  snprintf(filename, sizeof(filename), "/proc/%" PRId32 "/%s", pid,
           smaps_file);
  if (verbose)
    fprintf(stderr, "smaps:[%s]\n", filename);

  FILE * file = fopen(filename, "r");
  if (!file) {
    return (int64_t) -1;
  }

  if (bufsz >= 0) {
    if (setvbuf(file, NULL, _IOFBF, bufsz)) {
      fprintf(stderr, "setvbuf failed: %s\n", strerror(errno));
      exit(1);
    }
  }

  // Tally up all of the Pss from the various maps
  char line[256];
  int64_t pss = 0;
  while (fgets(line, sizeof(line), file)) {
    int64_t v;
    if (sscanf(line, "Pss: %" SCNd64 " kB", &v) == 1) {
      if (verbose)
        fprintf(stderr, "pss line: %llu\n", (unsigned long long) v);
      pss += v;
    }
  }

  fclose(file);

  // Return the Pss value in bytes, not kilobytes
  return pss * 1024;
}

int
main(int argc, char** argv)
{
  int c;
  while ((c = getopt(argc, argv, "n:rvb:")) != -1) {
    switch (c) {
      case 'r':
        smaps_file = "smaps_rollup";
        break;
      case 'v':
        verbose = true;
        break;
      case 'n':
        iterations = atoi(optarg);
        break;
      case 'b':
        bufsz = atoi(optarg);
        break;
      default:
        return 1;
    }
  }

  if (argv[optind] == NULL) {
    fprintf(stderr, "pssbench: no PID given\n");
    return 1;
  }
  int pid = atoi(argv[optind]);
  int64_t pss = 0;
  for (int i = 0; i < iterations; ++i)
    pss = get_pss(pid);
  fflush(NULL);

  printf("iterations:%d pid:%d pss:%lld\n", iterations, pid, (long long)pss);
  return 0;
}
