#ifndef _SELINUX_ANDROID_H_
#define _SELINUX_ANDROID_H_

#include <stdbool.h>
#include <sys/types.h>
#include <unistd.h>

#include <selinux/label.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Returns the file context handle */
extern struct selabel_handle* selinux_android_file_context_handle(void);

/* Returns the service context handle */
extern struct selabel_handle* selinux_android_service_context_handle(void);

/* Returns the hardware service context handle */
extern struct selabel_handle* selinux_android_hw_service_context_handle(void);

/* Returns the vendor service context handle */
extern struct selabel_handle* selinux_android_vendor_service_context_handle(void);

/* Returns the keystore2 context handle */
extern struct selabel_handle* selinux_android_keystore2_key_context_handle(void);

/* Sets the file context handle. Must be called using the output of
 * selinux_android_file_context_handle. This function can be used to preload
 * the file_contexts files and speed up later calls to
 * selinux_android_restorecon and selinux_android_restorecon_pkgdir */
extern void selinux_android_set_sehandle(const struct selabel_handle *hndl);

/* Sets the context of the current process. This should be used in preference
 * to setcon() on Android. */
extern int selinux_android_setcon(const char *con);

/* Sets the context of the current app process based on the information
 * provided. Returns -1 if no matching context is found or the transition
 * failed */
extern int selinux_android_setcontext(uid_t uid,
				      bool isSystemServer,
				      const char *seinfo,
				      const char *name);

/* Builds a new context based on context, adding the categories from userid and
 * appid. If userid or appid are -1, the corresponding categories are not
 * modified. */
extern int selinux_android_context_with_level(const char * context,
					      char ** newContext,
					      uid_t userid,
					      uid_t appid);

/* Provides a log callback that uses the Android logging facility. See selinux_set_callback. */
extern int selinux_log_callback(int type, const char *fmt, ...)
    __attribute__ ((format(printf, 2, 3)));

/* Provides a log callback that uses the Android logging facility for vendors.
 * See selinux_set_callback. */
extern int selinux_vendor_log_callback(int type, const char *fmt, ...)
    __attribute__ ((format(printf, 2, 3)));

#define SELINUX_ANDROID_RESTORECON_NOCHANGE 1
#define SELINUX_ANDROID_RESTORECON_VERBOSE  2
#define SELINUX_ANDROID_RESTORECON_RECURSE  4
#define SELINUX_ANDROID_RESTORECON_FORCE    8
#define SELINUX_ANDROID_RESTORECON_DATADATA 16
#define SELINUX_ANDROID_RESTORECON_SKIPCE   32
#define SELINUX_ANDROID_RESTORECON_CROSS_FILESYSTEMS   64
#define SELINUX_ANDROID_RESTORECON_SKIP_SEHASH         128
/* Restores the security context of a file. */
extern int selinux_android_restorecon(const char *file, unsigned int flags);

/* Restores the security context of a package's private directory. */
extern int selinux_android_restorecon_pkgdir(const char *pkgdir,
                                             const char *seinfo,
                                             uid_t uid,
                                             unsigned int flags);

/* Initialize the seapp contexts for future lookups. Loads all the
 * seapp_contexts files. To force a reload of the files, use
 * selinux_android_seapp_context_reload. While not required, this function can
 * be used to speed up the inital calls to selinux_android_setcontext,
 * selinux_android_restorecon and selinux_android_restorecon_pkgdir. */
extern void selinux_android_seapp_context_init(void);

/* Forces a reload of the seapp_contexts files. */
extern int selinux_android_seapp_context_reload(void);

#ifdef __cplusplus
}
#endif
#endif
