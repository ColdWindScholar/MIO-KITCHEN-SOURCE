#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <ctype.h>
#include <limits.h>

#define STRINGIFY_ARG(a)        #a
#define STRINGIFY(a)            STRINGIFY_ARG(a)

#define DEF_SORT_FUNC		sort_nr_objs
#define SLABINFO_LINE_LEN	512	/* size of longest line */
#define SLABINFO_NAME_LEN	32	/* cache name size (will truncate) */
#define SLABINFO_FILE		"/proc/slabinfo"
#define DEF_NR_ROWS		15	/* default nr of caches to show */

/* object representing a slab cache (each line of slabinfo) */
struct slab_info {
	char name[SLABINFO_NAME_LEN];	/* name of this cache */
	struct slab_info *next;
	unsigned long nr_pages;		/* size of cache in pages */
	unsigned long nr_objs;		/* number of objects in this cache */
	unsigned long nr_active_objs;	/* number of active objects */
	unsigned long obj_size;		/* size of each object */
	unsigned long objs_per_slab;	/* number of objects per slab */
	unsigned long nr_slabs;		/* number of slabs in this cache */
	unsigned long use;		/* percent full: total / active */
};

/* object representing system-wide statistics */
struct slab_stat {
	unsigned long total_size;	/* size of all objects */
	unsigned long active_size;	/* size of all active objects */
	unsigned long nr_objs;		/* total number of objects */
	unsigned long nr_active_objs;	/* total number of active objects */
	unsigned long nr_slabs;		/* total number of slabs */
	unsigned long nr_active_slabs;	/* total number of active slabs*/
	unsigned long nr_caches;	/* number of caches */
	unsigned long nr_active_caches;	/* number of active caches */
	unsigned long avg_obj_size;	/* average object size */
	unsigned long min_obj_size;	/* size of smallest object */
	unsigned long max_obj_size;	/* size of largest object */
};

typedef int (*sort_t)(const struct slab_info *, const struct slab_info *);
static sort_t sort_func;

/*
 * get_slabinfo - open, read, and parse a slabinfo 2.x file, which has the
 * following format:
 *
 * slabinfo - version: 2.1
 * <name>  <active_objs> <num_objs> <objsize> <objperslab> <pagesperslab>
 * : tunables <limit> <batchcount> <sharedfactor>
 * : slabdata <active_slabs> <num_slabs> <sharedavail>
 *
 * Returns the head of the new list of slab_info structures, or NULL on error.
 */
static struct slab_info * get_slabinfo(struct slab_stat *stats)
{
	struct slab_info *head = NULL, *p = NULL, *prev = NULL;
	FILE *slabfile;
	char line[SLABINFO_LINE_LEN];
	unsigned int major, minor;

	slabfile = fopen(SLABINFO_FILE, "r");
	if (!slabfile) {
		perror("fopen");
		return NULL;
	}

	if (!fgets(line, SLABINFO_LINE_LEN, slabfile)) {
		fprintf(stderr, "cannot read from " SLABINFO_FILE "\n");
		return NULL;
	}

	if (sscanf(line, "slabinfo - version: %u.%u", &major, &minor) != 2) {
		fprintf(stderr, "unable to parse slabinfo version!\n");
		return NULL;
	}

	if (major != 2 || minor > 1) {
		fprintf(stderr, "we only support slabinfo 2.0 and 2.1!\n");
		return NULL;
	}

	stats->min_obj_size = INT_MAX;

	while (fgets(line, SLABINFO_LINE_LEN, slabfile)) {
		unsigned long nr_active_slabs, pages_per_slab;
		int ret;

		if (line[0] == '#')
			continue;

		p = malloc(sizeof (struct slab_info));
		if (!p) {
			perror("malloc");
			head = NULL;
			break;
		}
		if (stats->nr_caches++ == 0)
			head = prev = p;

		ret = sscanf(line, "%" STRINGIFY(SLABINFO_NAME_LEN) "s"
			     " %lu %lu %lu %lu %lu : tunables %*d %*d %*d : \
			     slabdata %lu %lu %*d", p->name, 
			     &p->nr_active_objs, &p->nr_objs, 
			     &p->obj_size, &p->objs_per_slab,
			     &pages_per_slab,
			     &nr_active_slabs,
			     &p->nr_slabs);

		if (ret != 8) {
			fprintf(stderr, "unrecognizable data in slabinfo!\n");
			head = NULL;
			break;
		}

		if (p->obj_size < stats->min_obj_size)
			stats->min_obj_size = p->obj_size;
		if (p->obj_size > stats->max_obj_size)
			stats->max_obj_size = p->obj_size;

		p->nr_pages = p->nr_slabs * pages_per_slab;

		if (p->nr_objs) {
			p->use = 100 * p->nr_active_objs / p->nr_objs;
			stats->nr_active_caches++;
		} else
			p->use = 0;

		stats->nr_objs += p->nr_objs;
		stats->nr_active_objs += p->nr_active_objs;
		stats->total_size += p->nr_objs * p->obj_size;
		stats->active_size += p->nr_active_objs * p->obj_size;
		stats->nr_slabs += p->nr_slabs;
		stats->nr_active_slabs += nr_active_slabs;

		prev->next = p;
		prev = p;
	}

	if (fclose(slabfile))
		perror("fclose");

	if (p)
		p->next = NULL;
	if (stats->nr_objs)
		stats->avg_obj_size = stats->total_size / stats->nr_objs;

	return head;
}

/*
 * free_slablist - deallocate the memory associated with each node in the
 * provided slab_info linked list
 */
static void free_slablist(struct slab_info *list)
{
	while (list) {
		struct slab_info *temp = list->next;
		free(list);
		list = temp;
	}
}

static struct slab_info *merge_objs(struct slab_info *a, struct slab_info *b)
{
	struct slab_info list;
	struct slab_info *p = &list;

	while (a && b) {
		if (sort_func(a, b)) {
			p->next = a;
			p = a;
			a = a->next;
		} else {
			p->next = b;
			p = b;
			b = b->next;
		}
	}

	p->next = (a == NULL) ? b : a;
	return list.next;
}

/* 
 * slabsort - merge sort the slab_info linked list based on sort_func
 */
static struct slab_info *slabsort(struct slab_info *list)
{
	struct slab_info *a, *b;

	if (!list || !list->next)
		return list;

	a = list;
	b = list->next;

	while (b && b->next) {
		list = list->next;
		b = b->next->next;
	}

	b = list->next;
	list->next = NULL;

	return merge_objs(slabsort(a), slabsort(b));
}

/*
 * Sort Routines.  Each of these should be associated with a command-line
 * search option.  The functions should fit the prototype:
 *
 *	int sort_foo(const struct slab_info *a, const struct slab_info *b)
 *
 * They return zero if the first parameter is smaller than the second.
 * Otherwise, they return nonzero.
 */

static int sort_name(const struct slab_info *a, const struct slab_info *b)
{
	return (strcmp(a->name, b->name) < 0 ) ? 1: 0;
}

#define BUILD_SORT_FUNC(VAL) \
	static int sort_ ## VAL \
		(const struct slab_info *a, const struct slab_info *b) { \
			return (a-> VAL > b-> VAL); }

BUILD_SORT_FUNC(nr_objs)
BUILD_SORT_FUNC(nr_active_objs)
BUILD_SORT_FUNC(obj_size)
BUILD_SORT_FUNC(objs_per_slab)
BUILD_SORT_FUNC(nr_slabs)
BUILD_SORT_FUNC(use)
BUILD_SORT_FUNC(nr_pages)

/*
 * set_sort_func - return the slab_sort_func that matches the given key.
 * On unrecognizable key, the call returns NULL.
 */
static sort_t set_sort_func(char key)
{
	switch (tolower(key)) {
	case 'a':
		return sort_nr_active_objs;
	case 'c':
		return sort_nr_pages;
	case 'l':
		return sort_nr_slabs;	
	case 'n':
		return sort_name;
	case 'o':
		return sort_nr_objs;
	case 'p':
		return sort_objs_per_slab;	
	case 's':
		return sort_obj_size;
	case 'u':
		return sort_use;
	default:
		return NULL;
	}
}

int main(int argc, char *argv[])
{
	struct slab_info *list, *p;
	struct slab_stat stats = { .nr_objs = 0 };
	unsigned int page_size = getpagesize() / 1024, nr_rows = DEF_NR_ROWS, i;

	sort_func = DEF_SORT_FUNC;

	if (argc > 1) {
		/* FIXME: Ugh. */
		if (argc == 3 && !strcmp(argv[1], "-n")) {
			errno = 0;
			nr_rows = (unsigned int) strtoul(argv[2], NULL, 0);
			if (errno) {
				perror("strtoul");
				exit(EXIT_FAILURE);
			}
		}
		else if (argc == 3 && !strcmp(argv[1], "-s"))
			sort_func = set_sort_func(argv[2][0]) ? : DEF_SORT_FUNC;
		else {
			fprintf(stderr, "usage: %s [options]\n\n", argv[0]);
			fprintf(stderr, "options:\n");
			fprintf(stderr, "  -s S   specify sort criteria S\n");
			fprintf(stderr, "  -h     display this help\n\n");
			fprintf(stderr, "Valid sort criteria:\n");
			fprintf(stderr, "  a: number of Active objects\n");
			fprintf(stderr, "  c: Cache size\n");
			fprintf(stderr, "  l: number of sLabs\n");
			fprintf(stderr, "  n: Name\n");
			fprintf(stderr, "  o: number of Objects\n");
			fprintf(stderr, "  p: objects Per slab\n");
			fprintf(stderr, "  s: object Size\n");
			fprintf(stderr, "  u: cache Utilization\n");
			exit(EXIT_FAILURE);
		}
	}

	list = get_slabinfo (&stats);
	if (!list)
		exit(EXIT_FAILURE);

	printf(" Active / Total Objects (%% used) : %lu / %lu (%.1f%%)\n"
	       " Active / Total Slabs (%% used)   : %lu / %lu (%.1f%%)\n"
	       " Active / Total Caches (%% used)  : %lu / %lu (%.1f%%)\n"
	       " Active / Total Size (%% used)    : %.2fK / %.2fK (%.1f%%)\n"
	       " Min / Avg / Max Object Size     : %.2fK / %.2fK / %.2fK\n\n",
	       stats.nr_active_objs,
	       stats.nr_objs,
	       100.0 * stats.nr_active_objs / stats.nr_objs,
	       stats.nr_active_slabs,
	       stats.nr_slabs,
	       100.0 * stats.nr_active_slabs / stats.nr_slabs,
	       stats.nr_active_caches,
	       stats.nr_caches,
	       100.0 * stats.nr_active_caches / stats.nr_caches,
	       stats.active_size / 1024.0,
	       stats.total_size / 1024.0,
	       100.0 * stats.active_size / stats.total_size,
	       stats.min_obj_size / 1024.0,
	       stats.avg_obj_size / 1024.0,
	       stats.max_obj_size / 1024.0);

	printf("%6s %6s %4s %8s %6s %8s %10s %-23s\n",
	       "OBJS", "ACTIVE", "USE", "OBJ SIZE", "SLABS",
	       "OBJ/SLAB", "CACHE SIZE", "NAME");

	p = list = slabsort(list);
	for (i = 0; i < nr_rows && p; i++) {
		printf("%6lu %6lu %3lu%% %7.2fK %6lu %8lu %9luK %-23s\n",
		       p->nr_objs, p->nr_active_objs, p->use,
		       p->obj_size / 1024.0, p->nr_slabs,
		       p->objs_per_slab,
		       p->nr_pages * page_size,
		       p->name);
		p = p->next;
	}

	free_slablist(list);

	return 0;
}
