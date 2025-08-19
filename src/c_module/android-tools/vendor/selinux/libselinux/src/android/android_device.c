#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <fnmatch.h>
#include <fts.h>
#include <libgen.h>
#include <limits.h>
#include <linux/magic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/vfs.h>
#include <sys/xattr.h>
#include <unistd.h>

#include <log/log.h>
#include <packagelistparser/packagelistparser.h>
#include <private/android_filesystem_config.h>
#include <selinux/android.h>
#include <selinux/context.h>
#include <selinux/selinux.h>

#define _REALLY_INCLUDE_SYS__SYSTEM_PROPERTIES_H_
#include <sys/_system_properties.h>

#include "android_internal.h"
#include "callbacks.h"
#include "label_internal.h"
#include "selinux_internal.h"

int selinux_android_context_with_level(const char * context,
				       char ** newContext,
				       uid_t userid,
				       uid_t appid)
{
	int rc = -2;

	enum levelFrom levelFrom;
	if (userid == (uid_t) -1) {
		levelFrom = (appid == (uid_t) -1) ? LEVELFROM_NONE : LEVELFROM_APP;
	} else {
		levelFrom = (appid == (uid_t) -1) ? LEVELFROM_USER : LEVELFROM_ALL;
	}

	context_t ctx = context_new(context);
	if (!ctx) {
		goto out;
	}

	int res = set_range_from_level(ctx, levelFrom, userid, appid);
	if (res != 0) {
		rc = res;
		goto out;
	}

	const char * newString = context_str(ctx);
	if (!newString) {
		goto out;
	}

	char * newCopied = strdup(newString);
	if (!newCopied) {
		goto out;
	}

	*newContext = newCopied;
	rc = 0;

out:
	context_free(ctx);
	return rc;
}

int selinux_android_setcon(const char *con)
{
	int ret = setcon(con);
	if (ret)
		return ret;
	/*
	  System properties must be reinitialized after setcon() otherwise the
	  previous property files will be leaked since mmap()'ed regions are not
	  closed as a result of setcon().
	*/
	return __system_properties_init();
}

int selinux_android_setcontext(uid_t uid,
			       bool isSystemServer,
			       const char *seinfo,
			       const char *pkgname)
{
	char *orig_ctx_str = NULL;
	const char *ctx_str = NULL;
	context_t ctx = NULL;
	int rc = -1;

	if (is_selinux_enabled() <= 0)
		return 0;

	rc = getcon(&orig_ctx_str);
	if (rc)
		goto err;

	ctx = context_new(orig_ctx_str);
	if (!ctx)
		goto oom;

	rc = seapp_context_lookup(SEAPP_DOMAIN, uid, isSystemServer, seinfo, pkgname, ctx);
	if (rc == -1)
		goto err;
	else if (rc == -2)
		goto oom;

	ctx_str = context_str(ctx);
	if (!ctx_str)
		goto oom;

	rc = security_check_context(ctx_str);
	if (rc < 0)
		goto err;

	if (strcmp(ctx_str, orig_ctx_str)) {
		rc = selinux_android_setcon(ctx_str);
		if (rc < 0)
			goto err;
	}

	rc = 0;
out:
	freecon(orig_ctx_str);
	context_free(ctx);
	return rc;
err:
	if (isSystemServer)
		selinux_log(SELINUX_ERROR,
				"%s:  Error setting context for system server: %s\n",
				__FUNCTION__, strerror(errno));
	else
		selinux_log(SELINUX_ERROR,
				"%s:  Error setting context for app with uid %d, seinfo %s: %s\n",
				__FUNCTION__, uid, seinfo, strerror(errno));

	rc = -1;
	goto out;
oom:
	selinux_log(SELINUX_ERROR, "%s:  Out of memory\n", __FUNCTION__);
	rc = -1;
	goto out;
}

static struct selabel_handle *fc_sehandle = NULL;

static void file_context_init(void)
{
	if (!fc_sehandle)
		fc_sehandle = selinux_android_file_context_handle();
}

static pthread_once_t fc_once = PTHREAD_ONCE_INIT;

#define PKGTAB_SIZE 256
/* Hash table for pkg_info. It uses the package name as key. In case of
 * collision, the next entry is the private_data attribute */
static struct pkg_info *pkgTab[PKGTAB_SIZE];

/* Returns a hash based on the package name */
static unsigned int pkghash(const char *pkgname)
{
	unsigned int h = 7;
	for (; *pkgname; pkgname++) {
		h = h * 31 + *pkgname;
	}
	return h & (PKGTAB_SIZE - 1);
}

/* Adds the pkg_info entry to the hash table */
static bool pkg_parse_callback(pkg_info *info, void *userdata) {

	(void) userdata;

	unsigned int hash = pkghash(info->name);
	if (pkgTab[hash])
		/* Collision. Prepend the entry. */
		info->private_data = pkgTab[hash];
	pkgTab[hash] = info;
	return true;
}

/* Initialize the pkg_info hash table */
static void package_info_init(void)
{

	bool rc = packagelist_parse(pkg_parse_callback, NULL);
	if (!rc) {
		selinux_log(SELINUX_ERROR, "SELinux: Could NOT parse package list\n");
		return;
	}

#if DEBUG
	{
		unsigned int hash, buckets, entries, chainlen, longestchain;
		struct pkg_info *info = NULL;

		buckets = entries = longestchain = 0;
		for (hash = 0; hash < PKGTAB_SIZE; hash++) {
			if (pkgTab[hash]) {
				buckets++;
				chainlen = 0;
				for (info = pkgTab[hash]; info; info = (pkg_info *)info->private_data) {
					chainlen++;
					selinux_log(SELINUX_INFO, "%s:	name=%s uid=%u debuggable=%s dataDir=%s seinfo=%s\n",
								__FUNCTION__,
								info->name, info->uid, info->debuggable ? "true" : "false", info->data_dir, info->seinfo);
				}
				entries += chainlen;
				if (longestchain < chainlen)
					longestchain = chainlen;
			}
		}
		selinux_log(SELINUX_INFO, "SELinux:  %d pkg entries and %d/%d buckets used, longest chain %d\n", entries, buckets, PKGTAB_SIZE, longestchain);
	}
#endif

}

static pthread_once_t pkg_once = PTHREAD_ONCE_INIT;

/* Returns the pkg_info for a package with a specific name */
struct pkg_info *package_info_lookup(const char *name)
{
	struct pkg_info *info;
	unsigned int hash;

	__selinux_once(pkg_once, package_info_init);

	hash = pkghash(name);
	for (info = pkgTab[hash]; info; info = (pkg_info *)info->private_data) {
		if (!strcmp(name, info->name))
			return info;
	}
	return NULL;
}

#define USER_PROFILE_PATH "/data/misc/profiles/cur/*"

static int pkgdir_selabel_lookup(const char *pathname,
				 const char *seinfo,
				 uid_t uid,
				 char **secontextp)
{
	char *pkgname = NULL;
	struct pkg_info *info = NULL;
	const char *orig_ctx_str = *secontextp;
	const char *ctx_str = NULL;
	context_t ctx = NULL;
	int rc = 0;
	unsigned int userid_from_path = 0;

	rc = extract_pkgname_and_userid(pathname, &pkgname, &userid_from_path);
	if (rc) {
		/* Invalid path, we skip it */
		if (rc == -1) {
			return 0;
		}
		return rc;
	}

	if (!seinfo) {
		info = package_info_lookup(pkgname);
		if (!info) {
			selinux_log(SELINUX_WARNING, "SELinux:	Could not look up information for package %s, cannot restorecon %s.\n",
						pkgname, pathname);
			free(pkgname);
			return -1;
		}
		// info->uid only contains the appid and not the userid.
		info->uid += userid_from_path * AID_USER_OFFSET;
	}

	ctx = context_new(orig_ctx_str);
	if (!ctx)
		goto err;

	rc = seapp_context_lookup(SEAPP_TYPE, info ? info->uid : uid, 0,
				  info ? info->seinfo : seinfo, info ? info->name : pkgname, ctx);
	if (rc < 0)
		goto err;

	ctx_str = context_str(ctx);
	if (!ctx_str)
		goto err;

	if (!strcmp(ctx_str, orig_ctx_str))
		goto out;

	rc = security_check_context(ctx_str);
	if (rc < 0)
		goto err;

	freecon(*secontextp);
	*secontextp = strdup(ctx_str);
	if (!(*secontextp))
		goto err;

	rc = 0;

out:
	free(pkgname);
	context_free(ctx);
	return rc;
err:
	selinux_log(SELINUX_ERROR, "%s:  Error looking up context for path %s, pkgname %s, seinfo %s, uid %u: %s\n",
				__FUNCTION__, pathname, pkgname, info ? info->seinfo : seinfo,
				info ? info->uid : uid, strerror(errno));
	rc = -1;
	goto out;
}

#define RESTORECON_PARTIAL_MATCH_DIGEST  "security.sehash"

static int restorecon_sb(const char *pathname,
			 const struct stat *sb,
			 bool nochange,
			 bool verbose,
			 const char *seinfo,
			 uid_t uid)
{
	char *secontext = NULL;
	char *oldsecontext = NULL;
	int rc = 0;

	if (selabel_lookup(fc_sehandle, &secontext, pathname, sb->st_mode) < 0)
		return 0;  /* no match, but not an error */

	if (lgetfilecon(pathname, &oldsecontext) < 0)
		goto err;

	/*
	 * For subdirectories of /data/data or /data/user, we ignore selabel_lookup()
	 * and use pkgdir_selabel_lookup() instead. Files within those directories
	 * have different labeling rules, based off of /seapp_contexts, and
	 * installd is responsible for managing these labels instead of init.
	 */
	if (is_app_data_path(pathname)) {
		if (pkgdir_selabel_lookup(pathname, seinfo, uid, &secontext) < 0)
			goto err;
	}

	if (strcmp(oldsecontext, secontext) != 0) {
		if (verbose)
			selinux_log(SELINUX_INFO,
						"SELinux:  Relabeling %s from %s to %s.\n", pathname, oldsecontext, secontext);
		if (!nochange) {
			if (lsetfilecon(pathname, secontext) < 0)
				goto err;
		}
	}

	rc = 0;

out:
	freecon(oldsecontext);
	freecon(secontext);
	return rc;

err:
	selinux_log(SELINUX_ERROR,
				"SELinux: Could not set context for %s:  %s\n",
				pathname, strerror(errno));
	rc = -1;
	goto out;
}

#define SYS_PATH "/sys"
#define SYS_PREFIX SYS_PATH "/"

struct dir_hash_node {
	char* path;
	uint8_t digest[SHA1_HASH_SIZE];
	struct dir_hash_node *next;
};

// Returns true if the digest of all partial matched contexts is the same as the one
// saved by setxattr. Otherwise returns false and constructs a dir_hash_node with the
// newly calculated digest.
static bool check_context_match_for_dir(const char *pathname,
					struct dir_hash_node **new_node,
					bool force, int error)
{
	uint8_t read_digest[SHA1_HASH_SIZE];
	ssize_t read_size = getxattr(pathname, RESTORECON_PARTIAL_MATCH_DIGEST,
					 read_digest, SHA1_HASH_SIZE);
	uint8_t calculated_digest[SHA1_HASH_SIZE];
	bool status = selabel_hash_all_partial_matches(fc_sehandle, pathname,
						       calculated_digest);

	if (!new_node) {
		return false;
	}
	*new_node = NULL;
	if (!force && status && read_size == SHA1_HASH_SIZE &&
		memcmp(read_digest, calculated_digest, SHA1_HASH_SIZE) == 0) {
		return true;
	}

	// Save the digest of all matched contexts for the current directory.
	if (!error && status) {
		*new_node = calloc(1, sizeof(struct dir_hash_node));
		if (*new_node == NULL) {
			selinux_log(SELINUX_ERROR,
						"SELinux: %s: Out of memory\n", __func__);
			return false;
		}

		(*new_node)->path = strdup(pathname);
		if ((*new_node)->path == NULL) {
			selinux_log(SELINUX_ERROR,
						"SELinux: %s: Out of memory\n", __func__);
			free(*new_node);
			*new_node = NULL;
			return false;
		}
		memcpy((*new_node)->digest, calculated_digest, SHA1_HASH_SIZE);
		(*new_node)->next = NULL;
	}

	return false;
}

static int selinux_android_restorecon_common(const char* pathname_orig,
					     const char *seinfo,
					     uid_t uid,
					     unsigned int flags)
{
	bool nochange = (flags & SELINUX_ANDROID_RESTORECON_NOCHANGE) ? true : false;
	bool verbose = (flags & SELINUX_ANDROID_RESTORECON_VERBOSE) ? true : false;
	bool recurse = (flags & SELINUX_ANDROID_RESTORECON_RECURSE) ? true : false;
	bool force = (flags & SELINUX_ANDROID_RESTORECON_FORCE) ? true : false;
	bool datadata = (flags & SELINUX_ANDROID_RESTORECON_DATADATA) ? true : false;
	bool skipce = (flags & SELINUX_ANDROID_RESTORECON_SKIPCE) ? true : false;
	bool cross_filesystems = (flags & SELINUX_ANDROID_RESTORECON_CROSS_FILESYSTEMS) ? true : false;
	bool setrestoreconlast = (flags & SELINUX_ANDROID_RESTORECON_SKIP_SEHASH) ? false : true;
	bool issys;
	struct stat sb;
	struct statfs sfsb;
	FTS *fts;
	FTSENT *ftsent;
	char *pathname = NULL, *pathdnamer = NULL, *pathdname, *pathbname;
	char * paths[2] = { NULL , NULL };
	int ftsflags = FTS_NOCHDIR | FTS_PHYSICAL;
	int error, sverrno;
	struct dir_hash_node *current = NULL;
	struct dir_hash_node *head = NULL;

	if (!cross_filesystems) {
		ftsflags |= FTS_XDEV;
	}

	if (is_selinux_enabled() <= 0) {
		selinux_log(SELINUX_WARNING, "SELinux: SELinux is disabled, skipping restorecon");
		return 0;
	}

	__selinux_once(fc_once, file_context_init);

	if (!fc_sehandle)
		return 0;

	/*
	 * Convert passed-in pathname to canonical pathname by resolving realpath of
	 * containing dir, then appending last component name.
	 */
	pathbname = basename(pathname_orig);
	if (!strcmp(pathbname, "/") || !strcmp(pathbname, ".") || !strcmp(pathbname, "..")) {
		pathname = realpath(pathname_orig, NULL);
		if (!pathname)
			goto realpatherr;
	} else {
		pathdname = dirname(pathname_orig);
		pathdnamer = realpath(pathdname, NULL);
		if (!pathdnamer)
			goto realpatherr;
		if (!strcmp(pathdnamer, "/"))
			error = asprintf(&pathname, "/%s", pathbname);
		else
			error = asprintf(&pathname, "%s/%s", pathdnamer, pathbname);
		if (error < 0)
			goto oom;
	}

	paths[0] = pathname;
	issys = (!strcmp(pathname, SYS_PATH)
			|| !strncmp(pathname, SYS_PREFIX, sizeof(SYS_PREFIX)-1)) ? true : false;

	if (!recurse) {
		if (lstat(pathname, &sb) < 0) {
			error = -1;
			goto cleanup;
		}

		error = restorecon_sb(pathname, &sb, nochange, verbose, seinfo, uid);
		goto cleanup;
	}

	/*
	 * Ignore saved partial match digest on /data/data or /data/user
	 * since their labeling is based on seapp_contexts and seinfo
	 * assignments rather than file_contexts and is managed by
	 * installd rather than init.
	 */
	if (is_app_data_path(pathname))
		setrestoreconlast = false;

	/* Also ignore on /sys since it is regenerated on each boot regardless. */
	if (issys)
		setrestoreconlast = false;

	/* Ignore files on in-memory filesystems */
	if (statfs(pathname, &sfsb) == 0) {
		if (sfsb.f_type == RAMFS_MAGIC || sfsb.f_type == TMPFS_MAGIC)
			setrestoreconlast = false;
	}

	fts = fts_open(paths, ftsflags, NULL);
	if (!fts) {
		error = -1;
		goto cleanup;
	}

	error = 0;
	while ((ftsent = fts_read(fts)) != NULL) {
		switch (ftsent->fts_info) {
		case FTS_DC:
			selinux_log(SELINUX_ERROR,
						"SELinux:  Directory cycle on %s.\n", ftsent->fts_path);
			errno = ELOOP;
			error = -1;
			goto out;
		case FTS_DP:
			continue;
		case FTS_DNR:
			selinux_log(SELINUX_ERROR,
						"SELinux:  Could not read %s: %s.\n", ftsent->fts_path, strerror(errno));
			fts_set(fts, ftsent, FTS_SKIP);
			continue;
		case FTS_NS:
			selinux_log(SELINUX_ERROR,
						"SELinux:  Could not stat %s: %s.\n", ftsent->fts_path, strerror(errno));
			fts_set(fts, ftsent, FTS_SKIP);
			continue;
		case FTS_ERR:
			selinux_log(SELINUX_ERROR,
						"SELinux:  Error on %s: %s.\n", ftsent->fts_path, strerror(errno));
			fts_set(fts, ftsent, FTS_SKIP);
			continue;
		case FTS_D:
			if (issys && !selabel_partial_match(fc_sehandle, ftsent->fts_path)) {
				fts_set(fts, ftsent, FTS_SKIP);
				continue;
			}

			if (!datadata && !fnmatch(USER_PROFILE_PATH, ftsent->fts_path, FNM_PATHNAME)) {
				// Don't label this directory, vold takes care of that, but continue below it.
				continue;
			}

			if (setrestoreconlast) {
				struct dir_hash_node* new_node = NULL;
				if (check_context_match_for_dir(ftsent->fts_path, &new_node, force, error)) {
					selinux_log(SELINUX_INFO,
								"SELinux: Skipping restorecon on directory(%s)\n",
								ftsent->fts_path);
					fts_set(fts, ftsent, FTS_SKIP);
					continue;
				}
				if (new_node) {
					if (!current) {
						current = new_node;
						head = current;
					} else {
						current->next = new_node;
						current = current->next;
					}
				}
			}

			if (skipce && is_credential_encrypted_path(ftsent->fts_path)) {
				// Don't label anything below this directory.
				fts_set(fts, ftsent, FTS_SKIP);
				// but fall through and make sure we label the directory itself
			}

			if (!datadata && is_app_data_path(ftsent->fts_path)) {
				// Don't label anything below this directory.
				fts_set(fts, ftsent, FTS_SKIP);
				// but fall through and make sure we label the directory itself
			}
			/* fall through */
		default:
			error |= restorecon_sb(ftsent->fts_path, ftsent->fts_statp, nochange, verbose, seinfo, uid);
			break;
		}
	}

	// Labeling successful. Write the partial match digests for subdirectories.
	// TODO: Write the digest upon FTS_DP if no error occurs in its descents.
	if (setrestoreconlast && !nochange && !error) {
		current = head;
		while (current != NULL) {
			if (setxattr(current->path, RESTORECON_PARTIAL_MATCH_DIGEST, current->digest,
					SHA1_HASH_SIZE, 0) < 0) {
				selinux_log(SELINUX_ERROR,
							"SELinux:  setxattr failed: %s:  %s\n",
							current->path,
							strerror(errno));
			}
			current = current->next;
		}
	}

out:
	sverrno = errno;
	(void) fts_close(fts);
	errno = sverrno;
cleanup:
	free(pathdnamer);
	free(pathname);
	current = head;
	while (current != NULL) {
		struct dir_hash_node *next = current->next;
		free(current->path);
		free(current);
		current = next;
	}
	return error;
oom:
	sverrno = errno;
	selinux_log(SELINUX_ERROR, "%s:  Out of memory\n", __FUNCTION__);
	errno = sverrno;
	error = -1;
	goto cleanup;
realpatherr:
	sverrno = errno;
	selinux_log(SELINUX_ERROR, "SELinux: Could not get canonical path for %s restorecon: %s.\n",
			pathname_orig, strerror(errno));
	errno = sverrno;
	error = -1;
	goto cleanup;
}

int selinux_android_restorecon(const char *file, unsigned int flags)
{
	return selinux_android_restorecon_common(file, NULL, -1, flags);
}

int selinux_android_restorecon_pkgdir(const char *pkgdir,
				      const char *seinfo,
				      uid_t uid,
				      unsigned int flags)
{
	return selinux_android_restorecon_common(pkgdir, seinfo, uid, flags | SELINUX_ANDROID_RESTORECON_DATADATA);
}


void selinux_android_set_sehandle(const struct selabel_handle *hndl)
{
	fc_sehandle = (struct selabel_handle *) hndl;
}

int selinux_android_load_policy()
{
	selinux_log(SELINUX_ERROR, "selinux_android_load_policy is not implemented\n");
	return -1;
}

int selinux_android_load_policy_from_fd(int fd __attribute__((unused)), const char *description __attribute__((unused)))
{
	selinux_log(SELINUX_ERROR, "selinux_android_load_policy_from_fd is not implemented\n");
	return -1;
}
