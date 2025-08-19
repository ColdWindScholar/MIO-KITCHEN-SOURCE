/*
 * Property Service contexts backend for labeling Android
 * property keys
 */

#include <stdarg.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <sys/types.h>
#include <sys/stat.h>
#include "callbacks.h"
#include "label_internal.h"

/* A property security context specification. */
typedef struct spec {
	struct selabel_lookup_rec lr;	/* holds contexts for lookup result */
	char *property_key;		/* property key string */
} spec_t;

/* Our stored configuration */
struct saved_data {
	/*
	 * The array of specifications is sorted for longest
	 * prefix match
	 */
	spec_t *spec_arr;
	unsigned int nspec;	/* total number of specifications */
};

static int cmp(const void *A, const void *B)
{
	const struct spec *sp1 = A, *sp2 = B;

	if (strncmp(sp1->property_key, "*", 1) == 0)
		return 1;
	if (strncmp(sp2->property_key, "*", 1) == 0)
		return -1;

	size_t L1 = strlen(sp1->property_key);
	size_t L2 = strlen(sp2->property_key);

	return (L1 < L2) - (L1 > L2);
}

/*
 * Warn about duplicate specifications. Return error on different specifications.
 * TODO: Remove duplicate specifications. Move duplicate check to after sort
 * to improve performance.
 */
static int nodups_specs(struct saved_data *data)
{
	int rc = 0;
	unsigned int ii, jj;
	struct spec *curr_spec, *spec_arr = data->spec_arr;

	for (ii = 0; ii < data->nspec; ii++) {
		curr_spec = &spec_arr[ii];
		for (jj = ii + 1; jj < data->nspec; jj++) {
			if (!strcmp(spec_arr[jj].property_key,
					    curr_spec->property_key)) {
				if (strcmp(spec_arr[jj].lr.ctx_raw,
						    curr_spec->lr.ctx_raw)) {
					rc = -1;
					errno = EINVAL;
					selinux_log
						(SELINUX_ERROR,
						 "Multiple different specifications for %s  (%s and %s).\n",
						 curr_spec->property_key,
						 spec_arr[jj].lr.ctx_raw,
						 curr_spec->lr.ctx_raw);
				} else {
					selinux_log
						(SELINUX_WARNING,
						 "Multiple same specifications for %s.\n",
						 curr_spec->property_key);
				}
			}
		}
	}
	return rc;
}

static int process_line(struct selabel_handle *rec,
			const char *path, char *line_buf,
			int pass, unsigned lineno)
{
	int items;
	char *prop = NULL, *context = NULL;
	struct saved_data *data = (struct saved_data *)rec->data;
	spec_t *spec_arr = data->spec_arr;
	unsigned int nspec = data->nspec;
	const char *errbuf = NULL;

	items = read_spec_entries(line_buf, &errbuf, 2, &prop, &context);
	if (items < 0) {
		if (errbuf) {
			selinux_log(SELINUX_ERROR,
				    "%s:  line %u error due to: %s\n", path,
				    lineno, errbuf);
		} else {
			selinux_log(SELINUX_ERROR,
				    "%s:  line %u error due to: %m\n", path,
				    lineno);
		}
		return -1;
	}

	if (items == 0)
		return items;

	if (items != 2) {
		selinux_log(SELINUX_ERROR,
			    "%s:  line %u is missing fields\n", path,
			    lineno);
		free(prop);
		errno = EINVAL;
		return -1;
	}

	if (pass == 0) {
		free(prop);
		free(context);
	} else if (pass == 1) {
		/* On the second pass, process and store the specification in spec. */
		spec_arr[nspec].property_key = prop;
		spec_arr[nspec].lr.ctx_raw = context;

		if (rec->validating) {
			if (selabel_validate(rec, &spec_arr[nspec].lr) < 0) {
				selinux_log(SELINUX_ERROR,
					    "%s:  line %u has invalid context %s\n",
					    path, lineno, spec_arr[nspec].lr.ctx_raw);
				errno = EINVAL;
				return -1;
			}
		}

		data->nspec = ++nspec;
	}

	return 0;
}

static int process_file(struct selabel_handle *rec, const char *path)
{
	struct saved_data *data = (struct saved_data *)rec->data;
	char line_buf[BUFSIZ];
	unsigned int lineno, maxnspec, pass;
	struct stat sb;
	FILE *fp;
	int status = -1;
	unsigned int nspec;
	spec_t *spec_arr;

	/* Open the specification file. */
	if ((fp = fopen(path, "re")) == NULL)
		return -1;

	if (fstat(fileno(fp), &sb) < 0)
		goto finish;

	errno = EINVAL;

	if (!S_ISREG(sb.st_mode))
		goto finish;

	/*
	 * Two passes per specification file. First is to get the size.
	 * After the first pass, the spec array is malloced / realloced to
	 * the appropriate size. Second pass is to populate the spec array.
	 */
	maxnspec = UINT_MAX / sizeof(spec_t);
	for (pass = 0; pass < 2; pass++) {
		nspec = 0;
		lineno = 0;

		while (fgets(line_buf, sizeof(line_buf) - 1, fp) &&
			nspec < maxnspec) {
			if (process_line(rec, path, line_buf, pass, ++lineno))
				goto finish;
			nspec++;
		}

		if (pass == 0) {
			if (nspec == 0) {
				status = 0;
				goto finish;
			}

			/* grow spec array if required */
			spec_arr = realloc(data->spec_arr,
					(data->nspec + nspec) * sizeof(spec_t));
			if (spec_arr == NULL)
				goto finish;

			memset(&spec_arr[data->nspec], 0, nspec * sizeof(spec_t));
			data->spec_arr = spec_arr;
			maxnspec = nspec;
			rewind(fp);
		}
	}

	status = digest_add_specfile(rec->digest, fp, NULL, sb.st_size, path);

finish:
	fclose(fp);
	return status;
}

static void closef(struct selabel_handle *rec);

static int init(struct selabel_handle *rec, const struct selinux_opt *opts,
		unsigned n)
{
	struct saved_data *data = (struct saved_data *)rec->data;
	char **paths = NULL;
	size_t num_paths = 0;
	int status = -1;
	size_t i;

	/* Process arguments */
	i = n;
	while (i--) {
		switch (opts[i].type) {
		case SELABEL_OPT_PATH:
			num_paths++;
			break;
		}
	}

	if (!num_paths)
		return -1;

	paths = calloc(num_paths, sizeof(*paths));
	if (!paths)
		return -1;

	rec->spec_files = paths;
	rec->spec_files_len = num_paths;

	i = n;
	while (i--) {
		switch(opts[i].type) {
		case SELABEL_OPT_PATH:
			*paths = strdup(opts[i].value);
			if (*paths == NULL)
				goto finish;
			paths++;
		}
	}

	for (i = 0; i < num_paths; i++) {
		status = process_file(rec, rec->spec_files[i]);
		if (status)
			goto finish;
	}

	/* warn about duplicates after all files have been processed. */
	status = nodups_specs(data);
	if (status)
		goto finish;

	qsort(data->spec_arr, data->nspec, sizeof(struct spec), cmp);

	digest_gen_hash(rec->digest);

finish:
	if (status)
		closef(rec);

	return status;
}

/*
 * Backend interface routines
 */
static void closef(struct selabel_handle *rec)
{
	struct saved_data *data = (struct saved_data *)rec->data;
	struct spec *spec;
	unsigned int i;

	if (!data)
		return;

	/* make sure successive ->func_close() calls are harmless */
	rec->data = NULL;

	if (data->spec_arr) {
		for (i = 0; i < data->nspec; i++) {
			spec = &data->spec_arr[i];
			free(spec->property_key);
			free(spec->lr.ctx_raw);
			free(spec->lr.ctx_trans);
		}

		free(data->spec_arr);
	}

	free(data);
}

static struct selabel_lookup_rec *property_lookup(struct selabel_handle *rec,
					 const char *key,
					 int __attribute__((unused)) type)
{
	struct saved_data *data = (struct saved_data *)rec->data;
	spec_t *spec_arr = data->spec_arr;
	unsigned int i;
	struct selabel_lookup_rec *ret = NULL;

	if (!data->nspec) {
		errno = ENOENT;
		goto finish;
	}

	for (i = 0; i < data->nspec; i++) {
		if (strncmp(spec_arr[i].property_key, key,
			    strlen(spec_arr[i].property_key)) == 0) {
			break;
		}
		if (strncmp(spec_arr[i].property_key, "*", 1) == 0)
			break;
	}

	if (i >= data->nspec) {
		/* No matching specification. */
		errno = ENOENT;
		goto finish;
	}

	ret = &spec_arr[i].lr;

finish:
	return ret;
}

static struct selabel_lookup_rec *lookup_exact_match(struct selabel_handle *rec,
		const char *key, int __attribute__((unused)) type)
{
	struct saved_data *data = (struct saved_data *)rec->data;
	spec_t *spec_arr = data->spec_arr;
	unsigned int i;
	struct selabel_lookup_rec *ret = NULL;

	if (!data->nspec) {
		errno = ENOENT;
		goto finish;
	}

	for (i = 0; i < data->nspec; i++) {
		if (strcmp(spec_arr[i].property_key, key) == 0)
			break;
		if (strcmp(spec_arr[i].property_key, "*") == 0)
			break;
	}

	if (i >= data->nspec) {
		/* No matching specification. */
		errno = ENOENT;
		goto finish;
	}

	ret = &spec_arr[i].lr;

finish:
	return ret;
}

static void stats(struct selabel_handle __attribute__((unused)) *rec)
{
	selinux_log(SELINUX_WARNING, "'stats' functionality not implemented.\n");
}

int selabel_property_init(struct selabel_handle *rec,
			  const struct selinux_opt *opts,
			  unsigned nopts)
{
	struct saved_data *data;

	data = (struct saved_data *)calloc(1, sizeof(*data));
	if (!data)
		return -1;

	rec->data = data;
	rec->func_close = &closef;
	rec->func_stats = &stats;
	rec->func_lookup = &property_lookup;

	return init(rec, opts, nopts);
}

int selabel_exact_match_init(struct selabel_handle *rec,
		const struct selinux_opt *opts, unsigned nopts)
{
	struct saved_data *data;

	data = (struct saved_data *)calloc(1, sizeof(*data));
	if (!data)
		return -1;

	rec->data = data;
	rec->func_close = &closef;
	rec->func_stats = &stats;
	rec->func_lookup = &lookup_exact_match;

	return init(rec, opts, nopts);
}
