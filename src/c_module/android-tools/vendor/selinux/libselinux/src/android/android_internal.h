#pragma once

#include <stdbool.h>
#include <sys/types.h>

#include <selinux/context.h>
#include <selinux/selinux.h>

#ifdef __cplusplus
extern "C" {
#endif

// Context files (file_contexts, service_contexts, etc) may be spread over
// multiple partitions: system, system_ext, product, vendor and/or odm.
#define MAX_CONTEXT_PATHS 5
// The maximum number of alternatives for a file on one partition.
#define MAX_ALT_CONTEXT_PATHS 2
typedef struct path_alts {
	const char *paths[MAX_CONTEXT_PATHS][MAX_ALT_CONTEXT_PATHS];
	const char *partitions[MAX_CONTEXT_PATHS];
} path_alts_t;

/* Within each set of files, adds the first file that is accessible to `paths`.
 * Returns the number of accessible files. */
size_t find_existing_files(
	const path_alts_t *path_sets,
	const char *paths[MAX_CONTEXT_PATHS]);

/* Within each set of files, adds the first file that is accessible to `paths`.
 * Returns the number of accessible files. Also returns the partitions where
 * the files exist. */
size_t find_existing_files_with_partitions(
	const path_alts_t *path_sets,
	const char *paths[MAX_CONTEXT_PATHS],
	const char *partitions[MAX_CONTEXT_PATHS]);

/* Converts an array of file paths into an array of options for selabel_open.
 * opts must be at least as large as paths. */
void paths_to_opts(
	const char* paths[MAX_CONTEXT_PATHS],
	size_t npaths,
	struct selinux_opt* const opts);

/* Initialize a backend using the specified options. Ensure that any error is
 * reported to the android logging facility */
struct selabel_handle* initialize_backend(
	unsigned int backend,
	const char* name,
	const struct selinux_opt* opts,
	size_t nopts);

/* Initialize a backend using a set of context paths */
struct selabel_handle* context_handle(
		unsigned int backend,
		const path_alts_t *context_paths,
		const char* name);

/*
 * This method helps in identifying paths that refer to users' app data.
 * Labeling for app data is based on seapp_contexts and seinfo assignments
 * rather than file_contexts and is managed by installd rather than by init.
 */
bool is_app_data_path(const char *pathname);

/*
 * Determines if a path is Credential Encrypted (CE).
 * Some paths are not available when the device first boots (these are protected
 * by a credential). They should not be processed by restorecon until decrypted.
 * See also the --skip-ce option for restorecon.
 */
bool is_credential_encrypted_path(const char *pathname);

/* Extract the pkgname and userid from a path.
 * On success, the caller is responsible for free'ing pkgname.
 * Returns 0 on success, -1 on invalid path, -2 on error.
 */
int extract_pkgname_and_userid(const char *pathname, char **pkgname, unsigned int *userid);

/* The kind of request when looking up an seapp_context. */
enum seapp_kind {
	/* Returns the SELinux type for the app data directory */
	SEAPP_TYPE,
	/* Returns the SELinux type for the app process */
	SEAPP_DOMAIN
};

/* Search an app (or its data) based on its name and information within the list
 * of known seapp_contexts. If found, sets the type and categories of ctx and
 * returns 0. Returns -1 in case of error; -2 for out of memory */
int seapp_context_lookup(enum seapp_kind kind,
				uid_t uid,
				bool isSystemServer,
				const char *seinfo,
				const char *pkgname,
				context_t ctx);

/* Similar to seapp_context_lookup, but does not implicitly load and use the
 * default context files. It should only be used for unit tests. */
int seapp_context_lookup_internal(enum seapp_kind kind,
				uid_t uid,
				bool isSystemServer,
				const char *seinfo,
				const char *pkgname,
				context_t ctx);

/* Which categories should be associated to the process */
enum levelFrom {
	/* None */
	LEVELFROM_NONE,
	/* The categories of the application */
	LEVELFROM_APP,
	/* The categories of the end-user */
	LEVELFROM_USER,
	/* Application and end-user */
	LEVELFROM_ALL
};

/* Sets the categories of ctx based on the level request */
int set_range_from_level(context_t ctx, enum levelFrom levelFrom, uid_t userid, uid_t appid);

/* Similar to seapp_context_reload, but does not implicitly load the default
 * context files. It should only be used for unit tests. */
int seapp_context_reload_internal(const path_alts_t *context_paths);

#define SEINFO_BUFSIZ 256
/* A parsed seinfo */
struct parsed_seinfo {
	char base[SEINFO_BUFSIZ];
#define IS_PRIV_APP             (1 << 0)
#define IS_FROM_RUN_AS          (1 << 1)
#define IS_EPHEMERAL_APP        (1 << 2)
#define IS_ISOLATED_COMPUTE_APP (1 << 3)
#define IS_SDK_SANDBOX_AUDIT    (1 << 4)
#define IS_SDK_SANDBOX_NEXT     (1 << 5)
	int32_t is;
	bool isPreinstalledApp;
	char partition[SEINFO_BUFSIZ];
	int32_t targetSdkVersion;
};

/* Parses an seinfo string. Returns -1 if an error occurred. */
int parse_seinfo(const char* seinfo, struct parsed_seinfo* info);
#ifdef __cplusplus
}
#endif
