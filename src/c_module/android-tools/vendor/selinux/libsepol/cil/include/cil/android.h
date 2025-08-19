#ifndef _SEPOL_ANDROID_H_
#define _SEPOL_ANDROID_H_
#include <cil/cil.h>

#define PLAT_VERS "curr"
#define PLAT_ID "p"
#define NON_PLAT_ID "n"

/*
 * cil_android_attrib_mapping - extract attributizable elements of the policy in
 * srcdb and create the mapping file necessary to link the platform and
 * non-platform policy files after non-platform policy attributization.
 *   mdb - uninitialized cil_db reference to the resulting policy. Caller
 *         responsibility to destroy.
 *   srcdb - initialized and parsed cil_db reference to source public policy.
 *   num - the version string to append types when converted to attributes.
 * returns SEPOL_OK if successful, otherwise passes on the encountered error.
 */
int cil_android_attrib_mapping(struct cil_db **mdb, struct cil_db *srcdb, const char *num);

/*
 * cil_android_attributize - extract attributizable elements of the policy in
 * srcdb and convert all usage of those elements in tgtdb to versioned attributes.
 * Keep the attributes and type definitions so that tgtdb policy is more robust
 * against future changes to the public policy.
 *   tgtdb - initialized and parsed cil_db reference to modify.
 *   srcdb - initialized and parsed cil_db reference to source public policy
 *           from which to extract attributizable elements.
 *   num - the version string to append types when converted to attributes.
 * returns SEPOL_OK if successful, otherwise passes on the encountered error.
 */
int cil_android_attributize(struct cil_db *tgtdb, struct cil_db *srcdb, const char *num);

/*
 * cil_amend_policydb - amend the policy db with the content of the provided cil_db.
 *   db - initialized and parsed cil_db.
 *   policydb - initialized policy db to modify.
 */
int cil_amend_policydb(struct cil_db *db, sepol_policydb_t *policydb);

#endif /* _SEPOL_ANDROID_H_ */
