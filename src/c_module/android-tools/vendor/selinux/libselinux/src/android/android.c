#include <errno.h>
#include <fnmatch.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <log/log.h>
#include <selinux/android.h>
#include <selinux/label.h>

#include "android_internal.h"
#include "callbacks.h"

#ifdef __ANDROID_VNDK__
#ifndef LOG_EVENT_STRING
#define LOG_EVENT_STRING(...)
#endif  // LOG_EVENT_STRING
#endif  // __ANDROID_VNDK__

static const path_alts_t service_context_paths = { .paths = {
	{
		"/system/etc/selinux/plat_service_contexts",
		"/plat_service_contexts"
	},
	{
		"/system_ext/etc/selinux/system_ext_service_contexts",
		"/system_ext_service_contexts"
	},
	{
		"/product/etc/selinux/product_service_contexts",
		"/product_service_contexts"
	},
	{
		"/vendor/etc/selinux/vendor_service_contexts",
		"/vendor_service_contexts"
	},
	{
		"/odm/etc/selinux/odm_service_contexts",
	}
}};

static const path_alts_t hwservice_context_paths = { .paths = {
	{
		"/system/etc/selinux/plat_hwservice_contexts",
		"/plat_hwservice_contexts"
	},
	{
		"/system_ext/etc/selinux/system_ext_hwservice_contexts",
		"/system_ext_hwservice_contexts"
	},
	{
		"/product/etc/selinux/product_hwservice_contexts",
		"/product_hwservice_contexts"
	},
	{
		"/vendor/etc/selinux/vendor_hwservice_contexts",
		"/vendor_hwservice_contexts"
	},
	{
		"/odm/etc/selinux/odm_hwservice_contexts",
		"/odm_hwservice_contexts"
	},
}};

static const path_alts_t vndservice_context_paths = { .paths = {
	{
		"/vendor/etc/selinux/vndservice_contexts",
		"/vndservice_contexts"
	}
}};

static const path_alts_t keystore2_context_paths = { .paths = {
	{
		"/system/etc/selinux/plat_keystore2_key_contexts",
		"/plat_keystore2_key_contexts"
	},
	{
		"/system_ext/etc/selinux/system_ext_keystore2_key_contexts",
		"/system_ext_keystore2_key_contexts"
	},
	{
		"/product/etc/selinux/product_keystore2_key_contexts",
		"/product_keystore2_key_contexts"
	},
	{
		"/vendor/etc/selinux/vendor_keystore2_key_contexts",
		"/vendor_keystore2_key_contexts"
	}
}};

size_t find_existing_files(
		const path_alts_t *path_sets,
		const char* paths[MAX_CONTEXT_PATHS])
{
	return find_existing_files_with_partitions(
		path_sets,
		paths,
		NULL
	);
}

size_t find_existing_files_with_partitions(
		const path_alts_t *path_sets,
		const char* paths[MAX_CONTEXT_PATHS],
		const char* partitions[MAX_CONTEXT_PATHS])
{
	size_t i, j, len = 0;
	for (i = 0; i < MAX_CONTEXT_PATHS; i++) {
		for (j = 0; j < MAX_ALT_CONTEXT_PATHS; j++) {
			const char* file = path_sets->paths[i][j];
			if (file && access(file, R_OK) != -1) {
				if (partitions) {
					partitions[len] = path_sets->partitions[i];
				}
				paths[len++] = file;
				/* Within each set, only the first valid entry is used */
				break;
			}
		}
	}
	return len;
}

void paths_to_opts(const char* paths[MAX_CONTEXT_PATHS],
		size_t npaths,
		struct selinux_opt* const opts)
{
	for (size_t i = 0; i < npaths; i++) {
		opts[i].type = SELABEL_OPT_PATH;
		opts[i].value = paths[i];
	}
}

struct selabel_handle* initialize_backend(
		unsigned int backend,
		const char* name,
		const struct selinux_opt* opts,
		size_t nopts)
{
		struct selabel_handle* sehandle;

		sehandle = selabel_open(backend, opts, nopts);

		if (!sehandle) {
				selinux_log(SELINUX_ERROR, "%s: Error getting %s handle (%s)\n",
								__FUNCTION__, name, strerror(errno));
				return NULL;
		}
		selinux_log(SELINUX_INFO, "SELinux: Loaded %s context from:\n", name);
		for (unsigned i = 0; i < nopts; i++) {
			if (opts[i].type == SELABEL_OPT_PATH)
				selinux_log(SELINUX_INFO, "		%s\n", opts[i].value);
		}
		return sehandle;
}

struct selabel_handle* context_handle(
		unsigned int backend,
		const path_alts_t *context_paths,
		const char *name)
{
	const char* existing_paths[MAX_CONTEXT_PATHS];
	struct selinux_opt opts[MAX_CONTEXT_PATHS];
	int size = 0;

	size = find_existing_files(context_paths, existing_paths);
	paths_to_opts(existing_paths, size, opts);

	return initialize_backend(backend, name, opts, size);
}

struct selabel_handle* selinux_android_service_context_handle(void)
{
	return context_handle(SELABEL_CTX_ANDROID_SERVICE, &service_context_paths, "service");
}

struct selabel_handle* selinux_android_hw_service_context_handle(void)
{
	return context_handle(SELABEL_CTX_ANDROID_SERVICE, &hwservice_context_paths, "hwservice");
}

struct selabel_handle* selinux_android_vendor_service_context_handle(void)
{
	return context_handle(SELABEL_CTX_ANDROID_SERVICE, &vndservice_context_paths, "vndservice");
}

struct selabel_handle* selinux_android_keystore2_key_context_handle(void)
{
	return context_handle(SELABEL_CTX_ANDROID_KEYSTORE2_KEY, &keystore2_context_paths, "keystore2");
}

/* The contents of these paths are encrypted on FBE devices until user
 * credentials are presented (filenames inside are mangled), so we need
 * to delay restorecon of those until vold explicitly requests it. */
// NOTE: these paths need to be kept in sync with vold
#define DATA_SYSTEM_CE_PATH "/data/system_ce"
#define DATA_VENDOR_CE_PATH "/data/vendor_ce"
#define DATA_MISC_CE_PATH "/data/misc_ce"

/* The path prefixes of package data directories. */
#define DATA_DATA_PATH "/data/data"
#define DATA_USER_PATH "/data/user"
#define DATA_USER_DE_PATH "/data/user_de"
#define DATA_MISC_DE_PATH "/data/misc_de"
#define DATA_STORAGE_AREA_PATH "/data/storage_area"
#define SDK_SANDBOX_DATA_CE_PATH "/data/misc_ce/*/sdksandbox"
#define SDK_SANDBOX_DATA_DE_PATH "/data/misc_de/*/sdksandbox"

#define EXPAND_MNT_PATH "/mnt/expand/\?\?\?\?\?\?\?\?-\?\?\?\?-\?\?\?\?-\?\?\?\?-\?\?\?\?\?\?\?\?\?\?\?\?"
#define EXPAND_USER_PATH EXPAND_MNT_PATH "/user"
#define EXPAND_USER_DE_PATH EXPAND_MNT_PATH "/user_de"
#define EXPAND_SDK_CE_PATH EXPAND_MNT_PATH "/misc_ce/*/sdksandbox"
#define EXPAND_SDK_DE_PATH EXPAND_MNT_PATH "/misc_de/*/sdksandbox"

#define DATA_DATA_PREFIX DATA_DATA_PATH "/"
#define DATA_USER_PREFIX DATA_USER_PATH "/"
#define DATA_USER_DE_PREFIX DATA_USER_DE_PATH "/"
#define DATA_STORAGE_AREA_PREFIX DATA_STORAGE_AREA_PATH "/"
#define DATA_MISC_CE_PREFIX DATA_MISC_CE_PATH "/"
#define DATA_MISC_DE_PREFIX DATA_MISC_DE_PATH "/"
#define EXPAND_MNT_PATH_PREFIX EXPAND_MNT_PATH "/"

bool is_app_data_path(const char *pathname) {
	int flags = FNM_LEADING_DIR|FNM_PATHNAME;
#ifdef SELINUX_FLAGS_DATA_DATA_IGNORE
	if (!strcmp(pathname, DATA_DATA_PATH)) {
		return true;
	}
#endif
	return (!strncmp(pathname, DATA_DATA_PREFIX, sizeof(DATA_DATA_PREFIX)-1) ||
		!strncmp(pathname, DATA_USER_PREFIX, sizeof(DATA_USER_PREFIX)-1) ||
		!strncmp(pathname, DATA_USER_DE_PREFIX, sizeof(DATA_USER_DE_PREFIX)-1) ||
		!strncmp(pathname, DATA_STORAGE_AREA_PREFIX, sizeof(DATA_STORAGE_AREA_PREFIX)-1) ||
		!fnmatch(EXPAND_USER_PATH, pathname, flags) ||
		!fnmatch(EXPAND_USER_DE_PATH, pathname, flags) ||
		!fnmatch(SDK_SANDBOX_DATA_CE_PATH, pathname, flags) ||
		!fnmatch(SDK_SANDBOX_DATA_DE_PATH, pathname, flags) ||
		!fnmatch(EXPAND_SDK_CE_PATH, pathname, flags) ||
		!fnmatch(EXPAND_SDK_DE_PATH, pathname, flags));
}

bool is_credential_encrypted_path(const char *pathname) {
	return !strncmp(pathname, DATA_SYSTEM_CE_PATH, sizeof(DATA_SYSTEM_CE_PATH)-1) ||
	       !strncmp(pathname, DATA_MISC_CE_PATH, sizeof(DATA_MISC_CE_PATH)-1) ||
	       !strncmp(pathname, DATA_VENDOR_CE_PATH, sizeof(DATA_VENDOR_CE_PATH)-1);
}

/*
 * Extract the userid from a path.
 * On success, pathname is updated past the userid.
 * Returns 0 on success, -1 on error
 */
static int extract_userid(const char **pathname, unsigned int *userid)
{
	char *end = NULL;

	errno = 0;
	*userid = strtoul(*pathname, &end, 10);
	if (errno) {
		selinux_log(SELINUX_ERROR, "SELinux: Could not parse userid %s: %s.\n",
			*pathname, strerror(errno));
		return -1;
	}
	if (*pathname == end) {
		return -1;
	}
	if (*userid > 1000) {
		return -1;
	}
	*pathname = end;
	return 0;
}

int extract_pkgname_and_userid(const char *pathname, char **pkgname, unsigned int *userid)
{
	char *end = NULL;

	if (pkgname == NULL || *pkgname != NULL || userid == NULL) {
		errno = EINVAL;
		return -2;
	}

	/* Skip directory prefix before package name. */
	if (!strncmp(pathname, DATA_DATA_PREFIX, sizeof(DATA_DATA_PREFIX)-1)) {
		pathname += sizeof(DATA_DATA_PREFIX) - 1;
	} else if (!strncmp(pathname, DATA_USER_PREFIX, sizeof(DATA_USER_PREFIX)-1)) {
		pathname += sizeof(DATA_USER_PREFIX) - 1;
		int rc = extract_userid(&pathname, userid);
		if (rc)
			return -1;
		if (*pathname == '/')
			pathname++;
		else
			return -1;
	} else if (!strncmp(pathname, DATA_USER_DE_PREFIX, sizeof(DATA_USER_DE_PREFIX)-1)) {
		pathname += sizeof(DATA_USER_DE_PREFIX) - 1;
		int rc = extract_userid(&pathname, userid);
		if (rc)
			return -1;
		if (*pathname == '/')
			pathname++;
		else
			return -1;
	} else if (!strncmp(pathname, DATA_STORAGE_AREA_PREFIX, sizeof(DATA_STORAGE_AREA_PREFIX)-1)) {
		pathname += sizeof(DATA_STORAGE_AREA_PREFIX) - 1;
		int rc = extract_userid(&pathname, userid);
		if (rc)
			return -1;
		if (*pathname == '/')
			pathname++;
		else
			return -1;
	} else if (!fnmatch(EXPAND_USER_PATH, pathname, FNM_LEADING_DIR|FNM_PATHNAME)) {
		pathname += sizeof(EXPAND_USER_PATH);
		int rc = extract_userid(&pathname, userid);
		if (rc)
			return -1;
		if (*pathname == '/')
			pathname++;
		else
			return -1;
	} else if (!fnmatch(EXPAND_USER_DE_PATH, pathname, FNM_LEADING_DIR|FNM_PATHNAME)) {
		pathname += sizeof(EXPAND_USER_DE_PATH);
		int rc = extract_userid(&pathname, userid);
		if (rc)
			return -1;
		if (*pathname == '/')
			pathname++;
		else
			return -1;
	} else if (!strncmp(pathname, DATA_MISC_CE_PREFIX, sizeof(DATA_MISC_CE_PREFIX)-1)) {
		pathname += sizeof(DATA_MISC_CE_PREFIX) - 1;
		int rc = extract_userid(&pathname, userid);
		if (rc)
			return -1;
		if (!strncmp(pathname, "/sdksandbox/", sizeof("/sdksandbox/")-1))
			pathname += sizeof("/sdksandbox/") - 1;
		else
			return -1;
	} else if (!strncmp(pathname, DATA_MISC_DE_PREFIX, sizeof(DATA_MISC_DE_PREFIX)-1)) {
		pathname += sizeof(DATA_MISC_DE_PREFIX) - 1;
		int rc = extract_userid(&pathname, userid);
		if (rc)
			return -1;
		if (!strncmp(pathname, "/sdksandbox/", sizeof("/sdksandbox/")-1))
			pathname += sizeof("/sdksandbox/") - 1;
		else
			return -1;
	} else if (!fnmatch(EXPAND_SDK_CE_PATH, pathname, FNM_LEADING_DIR|FNM_PATHNAME)) {
		pathname += sizeof(EXPAND_MNT_PATH_PREFIX) - 1;
		pathname += sizeof("misc_ce/") - 1;
		int rc = extract_userid(&pathname, userid);
		if (rc)
			return -1;
		if (!strncmp(pathname, "/sdksandbox/", sizeof("/sdksandbox/")-1))
			pathname += sizeof("/sdksandbox/") - 1;
		else
			return -1;
	} else if (!fnmatch(EXPAND_SDK_DE_PATH, pathname, FNM_LEADING_DIR|FNM_PATHNAME)) {
		pathname += sizeof(EXPAND_MNT_PATH_PREFIX) - 1;
		pathname += sizeof("misc_de/") - 1;
		int rc = extract_userid(&pathname, userid);
		if (rc)
			return -1;
		if (!strncmp(pathname, "/sdksandbox/", sizeof("/sdksandbox/")-1))
			pathname += sizeof("/sdksandbox/") - 1;
		else
			return -1;
	} else
		return -1;

	if (!(*pathname))
		return -1;

	*pkgname = strdup(pathname);
	if (!(*pkgname))
		return -2;

	// Trim pkgname.
	for (end = *pkgname; *end && *end != '/'; end++);
	*end = '\0';

	return 0;
}

static void __selinux_log_callback(bool add_to_event_log, int type, const char *fmt, va_list ap) {
	int priority;
	char *strp;

	switch(type) {
	case SELINUX_WARNING:
		priority = ANDROID_LOG_WARN;
		break;
	case SELINUX_INFO:
		priority = ANDROID_LOG_INFO;
		break;
	default:
		priority = ANDROID_LOG_ERROR;
		break;
	}

	int len = vasprintf(&strp, fmt, ap);
	if (len < 0) {
		return;
	}

	/* libselinux log messages usually contain a new line character, while
	 * Android LOG() does not expect it. Remove it to avoid empty lines in
	 * the log buffers.
	 */
	if (len > 0 && strp[len - 1] == '\n') {
		strp[len - 1] = '\0';
	}
	LOG_PRI(priority, "SELinux", "%s", strp);
	if (add_to_event_log) {
		LOG_EVENT_STRING(AUDITD_LOG_TAG, strp);
	}
	free(strp);
}

int selinux_log_callback(int type, const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	__selinux_log_callback(true, type, fmt, ap);
	va_end(ap);
	return 0;
}

int selinux_vendor_log_callback(int type, const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	__selinux_log_callback(false, type, fmt, ap);
	va_end(ap);
	return 0;
}
