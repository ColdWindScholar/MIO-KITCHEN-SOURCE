#include <cil/android.h>
#include <sepol/policydb/hashtab.h>
#include <stdlib.h>
#include <string.h>

#include "cil_binary.h"
#include "cil_build_ast.h"
#include "cil_internal.h"
#include "cil_strpool.h"
#include "cil_symtab.h"
#include "cil_tree.h"

#define VER_MAP_SZ (1 << 12)

/* added to hashmap - currently unused as hashmap is used as a set */
struct version_datum {
	struct cil_db *db;
	struct cil_tree_node *ast_node;
	char *orig_name;
};

struct version_args {
	struct cil_db *db;
	hashtab_t vers_map;
	const char *num;
};

struct policydb_amend_args {
	const struct cil_db *db;
	policydb_t *pdb;
	void **type_value_to_cil;
};

enum plat_flavor {
	PLAT_NONE = 0,
	PLAT_TYPE,
	PLAT_ATTRIB
};

static unsigned int ver_map_hash_val(hashtab_t h, const_hashtab_key_t key)
{
	/* from cil_stpool.c */
	char *p, *keyp;
	size_t size;
	unsigned int val;

	val = 0;
	keyp = (char*)key;
	size = strlen(keyp);
	for (p = keyp; ((size_t) (p - keyp)) < size; p++)
		val =
			(val << 4 | (val >> (8 * sizeof(unsigned int) - 4))) ^ (*p);
	return val & (h->size - 1);
}


static int ver_map_key_cmp(hashtab_t h __attribute__ ((unused)),
			   const_hashtab_key_t key1, const_hashtab_key_t key2)
{
	/* hashtab_key_t is just a const char* underneath */
	return strcmp(key1, key2);
}

/*
 * version_datum  pointers all refer to memory owned elsewhere, so just free the
 * datum itself.
 */
static int ver_map_entry_destroy(__attribute__ ((unused))hashtab_key_t k,
				 hashtab_datum_t d, __attribute__ ((unused))void *args)
{
	free(d);
	return 0;
}

static void ver_map_destroy(hashtab_t h)
{
	hashtab_map(h, ver_map_entry_destroy, NULL);
	hashtab_destroy(h);
}

static int __extract_attributees_helper(struct cil_tree_node *node, uint32_t *finished, void *extra_args)
{
	int rc = SEPOL_ERR;
	struct version_args *args = (struct version_args *) extra_args;
	char *key;
	struct version_datum *datum;

	if (node == NULL || finished == NULL || extra_args == NULL) {
		goto exit;
	}

	switch (node->flavor) {
	case CIL_ROLE:
		cil_log(CIL_ERR, "%s unsupported statement in attributee policy (line %d)\n",
			CIL_KEY_ROLE, node->line);
		rc = SEPOL_ERR;
		break;
	case CIL_TYPE:
	case CIL_TYPEATTRIBUTE:
		datum = cil_malloc(sizeof(*datum));
		datum->db = args->db;
		datum->ast_node = node;
		datum->orig_name = DATUM(node->data)->name;
		key = datum->orig_name;
		if (!strncmp(key, "base_typeattr_", 14)) {
			/* checkpolicy creates base attributes which are just typeattributesets,
			   of the existing types and attributes.  These may be differnt in
			   every checkpolicy output, ignore them here, they'll be dealt with
			   as a special case when attributizing. */
			free(datum);
		} else {
			rc = hashtab_insert(args->vers_map, (hashtab_key_t) key, (hashtab_datum_t) datum);
			if (rc != SEPOL_OK) {
				goto exit;
			}
		}
		break;
	case CIL_TYPEALIAS:
		cil_log(CIL_ERR, "%s unsupported statement in attributee policy (line %d)\n",
			CIL_KEY_TYPEALIAS, node->line);
		goto exit;
		break;
	case CIL_TYPEPERMISSIVE:
		cil_log(CIL_ERR, "%s unsupported statement in attributee policy (line %d)\n",
			CIL_KEY_TYPEPERMISSIVE, node->line);
		goto exit;
		break;
	case CIL_NAMETYPETRANSITION:
	case CIL_TYPE_RULE:
		cil_log(CIL_ERR, "%s unsupported statement in attributee policy (line %d)\n",
			CIL_KEY_TYPETRANSITION, node->line);
		goto exit;
		break;
	default:
		break;
	}
	return SEPOL_OK;
exit:
	return rc;
}

/*
 * For the given db, with an already-built AST, fill the vers_map hash table
 * with every encountered type and attribute.  This could eventually be expanded
 * to include other language constructs, such as users and roles, in which case
 * multiple hash tables would be needed.  These tables can then be used by
 * attributize() to change all references to these types.
 */
int cil_extract_attributees(struct cil_db *db, hashtab_t vers_map)
{
	/* walk ast. */
	int rc = SEPOL_ERR;
	struct version_args extra_args;
	extra_args.db = db;
	extra_args.vers_map = vers_map;
	extra_args.num = NULL;
	rc = cil_tree_walk(db->ast->root, __extract_attributees_helper, NULL, NULL, &extra_args);
	if (rc != SEPOL_OK) {
		goto exit;
	}

	return SEPOL_OK;
exit:
	return rc;
}

static enum plat_flavor __cil_get_plat_flavor(hashtab_t vers_map, hashtab_key_t key)
{
	enum plat_flavor rc;
	struct version_datum *vers_datum;

	vers_datum = (struct version_datum *)hashtab_search(vers_map, key);
	if (vers_datum == NULL) {
		return PLAT_NONE;
	}
	switch (vers_datum->ast_node->flavor) {
	case CIL_TYPE:
		rc = PLAT_TYPE;
		break;
	case CIL_TYPEATTRIBUTE:
		rc = PLAT_ATTRIB;
		break;
	default:
		rc = PLAT_NONE;
		break;
	}
	return rc;
}

/*
 * Takes the old name and version string and creates a new strpool entry by
 * combining them.
 */
static char *__cil_attrib_get_versname(char *old, const char *vers)
{
	size_t len = 0;
	char *tmp_new = NULL;
	char *final;

	len += strlen(old) + strlen(vers) + 2;
	tmp_new = cil_malloc(len);
	snprintf(tmp_new, len, "%s_%s", old, vers);
	final = cil_strpool_add(tmp_new);
	free(tmp_new);
	return final;
}

/*
 * Change type to attribute - create new versioned name based on old, create
 * typeattribute node add to the existing type node.
 */
static int __cil_attrib_convert_type(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	struct cil_type *type = (struct cil_type *)node->data;
	struct cil_typeattribute *typeattr = NULL;
	struct cil_tree_node *new_ast_node = NULL;
	char *new_key;

	cil_typeattribute_init(&typeattr);

	new_key = __cil_attrib_get_versname(type->datum.name, args->num);

	/* create new tree node to contain typeattribute and add to tree */
	cil_tree_node_init(&new_ast_node);
	new_ast_node->parent = node->parent;
	new_ast_node->next = node->next;
	node->next = new_ast_node;

	rc = cil_gen_node(args->db, new_ast_node, (struct cil_symtab_datum *) typeattr,
			  new_key, CIL_SYM_TYPES, CIL_TYPEATTRIBUTE);
	if (rc != SEPOL_OK) {
		goto exit;
	}

	return SEPOL_OK;
exit:
	return rc;
}

/*
 * Update datum - create new key, remove entry under old key,
 * update entry, and insert under new key
 */
static int __cil_attrib_swap_symtab_key(struct cil_tree_node *node, char *old_key,
					const char *num)
{
	int rc = SEPOL_ERR;
	char *new_key;
	symtab_t *symtab;
	struct cil_symtab_datum *datum = (struct cil_symtab_datum *) node->data;

	new_key = __cil_attrib_get_versname(old_key, num);

	symtab = datum->symtab;

	/* TODO: remove, but what happens to other nodes on this datum ?*/
	cil_list_remove(datum->nodes, CIL_NODE, node, 0);
	cil_symtab_remove_datum(datum);

	rc = cil_symtab_insert(symtab, new_key, datum, node);

	if (rc != SEPOL_OK) {
		goto exit;
	}

	return SEPOL_OK;
exit:
	return rc;
}

/*
 * expressions may contains strings which are not in the type-attribute
 * namespace, so this is not a general cil_expr attributizer.
 * TODO: add support for other types of expressions which may contain types.
 */
static int cil_attrib_type_expr(struct cil_list *expr_str, struct version_args *args)
{
	int rc = SEPOL_ERR;
	struct cil_list_item *curr = NULL;
	char *new;
	hashtab_key_t key;

	/* iterate through cil_list, replacing types */
	cil_list_for_each(curr, expr_str) {
		switch(curr->flavor) {
		case CIL_LIST:
			rc = cil_attrib_type_expr((struct cil_list *)curr->data, args);
			if (rc != SEPOL_OK)
				goto exit;
			break;
		case CIL_STRING:
			key = (hashtab_key_t) curr->data;
			enum plat_flavor pf = __cil_get_plat_flavor(args->vers_map, key);
			if (!strncmp(curr->data, "base_typeattr_", 14) || pf == PLAT_TYPE) {
				new = __cil_attrib_get_versname((char *) curr->data, args->num);
				curr->data = (void *) new;
			}
			break;
		case CIL_DATUM:
			cil_log(CIL_ERR, "AST already resolved. Not yet supported.\n");
			rc = SEPOL_ERR;
			goto exit;
			break;
		default:
			break;
		}
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_check_context(struct cil_context *ctxt, struct version_args *args)
{
	int rc = SEPOL_ERR;
	hashtab_key_t key;

	if (ctxt->type != NULL) {
		cil_log(CIL_ERR, "AST already resolved. Not yet supported.\n");
		goto exit;
	}

	key = (hashtab_key_t) ctxt->type_str;
	if (__cil_get_plat_flavor(args->vers_map, key) != PLAT_NONE) {
        /* TODO: reinstate check, but leave out for now
		cil_log(CIL_ERR, "AST contains context with platform public type: %s\n",
			ctxt->type_str);
		rc = SEPOL_ERR;
		goto exit; */
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_sidcontext(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	struct cil_sidcontext *sidcon = (struct cil_sidcontext *)node->data;

	if (sidcon->context_str == NULL) {
		/* sidcon contains an anon context, which needs to have type checked */
		rc = cil_attrib_check_context(sidcon->context, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_context(struct cil_tree_node *node, struct version_args *args)
{
	struct cil_context *ctxt = (struct cil_context *)node->data;

	return cil_attrib_check_context(ctxt, args);
}

static int cil_attrib_roletype(struct cil_tree_node *node,
			       __attribute__((unused)) struct version_args *args)
{
	int rc = SEPOL_ERR;
	char *key;
	struct cil_roletype *roletype = (struct cil_roletype *)node->data;

	if (roletype->role) {
		cil_log(CIL_ERR, "AST already resolved.  !!! Not yet supported.\n");
		goto exit;
	}
	key = roletype->type_str;
	if (__cil_get_plat_flavor(args->vers_map, (hashtab_key_t) key) == PLAT_TYPE) {
		roletype->type_str = __cil_attrib_get_versname(key, args->num);
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_type(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	struct cil_type *type = (struct cil_type *)node->data;
	char *key = type->datum.name;

	if (type->value) {
		cil_log(CIL_ERR, "AST already resolved.  !!! Not yet supported.\n");
		goto exit;
	}
	if (__cil_get_plat_flavor(args->vers_map, (hashtab_key_t) key) == PLAT_TYPE) {
		rc = __cil_attrib_convert_type(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_typepermissive(struct cil_tree_node *node,
				     struct version_args *args __attribute__ ((unused)))
{
	struct cil_typepermissive *typeperm = (struct cil_typepermissive *)node->data;

	if (typeperm->type != NULL) {
		cil_log(CIL_ERR, "AST already resolved.  ### Not yet supported.\n");
		return SEPOL_ERR;
	}

	return SEPOL_OK;
}

static int cil_attrib_typeattribute(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	struct cil_typeattribute *typeattr = (struct cil_typeattribute *)node->data;
	char *key = typeattr->datum.name;

	if (typeattr->types) {
		cil_log(CIL_ERR, "AST already resolved. Not yet supported (line %d).\n",
			node->line);
		goto exit;
	}
	if (!strncmp(key, "base_typeattr_", 14)) {
		rc = __cil_attrib_swap_symtab_key(node, key, args->num);
		if (rc != SEPOL_OK) {
			goto exit;
		}
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_typeattributeset(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	char *key;
	struct cil_typeattributeset *typeattrset = (struct cil_typeattributeset *) node->data;

	if (typeattrset->datum_expr != NULL) {
		cil_log(CIL_ERR, "AST already resolved. Not yet supported (line %d).\n",
			node->line);
		goto exit;
	}

	key = typeattrset->attr_str;
	/* first check to see if the attribute to which this set belongs is versioned */
	if (!strncmp(key, "base_typeattr_", 14)) {
		typeattrset->attr_str = __cil_attrib_get_versname(key, args->num);
	}

	rc = cil_attrib_type_expr(typeattrset->str_expr, args);
	if (rc != SEPOL_OK) {
		goto exit;
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_typealiasactual(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	char *key;
	struct cil_aliasactual *aliasact = (struct cil_aliasactual *)node->data;

	key = aliasact->actual_str;
	if (__cil_get_plat_flavor(args->vers_map, (hashtab_key_t) key) != PLAT_NONE) {
		cil_log(CIL_ERR, "%s with platform public type not allowed (line %d)\n",
		    CIL_KEY_TYPEALIASACTUAL, node->line);
		goto exit;
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_nametypetransition(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	char *key;
	struct cil_nametypetransition *namettrans = (struct cil_nametypetransition *)node->data;

	if (namettrans->src != NULL) {
		cil_log(CIL_ERR, "AST already resolved. Not yet supported (line %d).\n",
			node->line);
		goto exit;
	}
	key = namettrans->src_str;
	if (__cil_get_plat_flavor(args->vers_map, (hashtab_key_t) key) == PLAT_TYPE) {
		namettrans->src_str = __cil_attrib_get_versname(key, args->num);
	}

	key = namettrans->tgt_str;
	if (__cil_get_plat_flavor(args->vers_map, (hashtab_key_t) key) == PLAT_TYPE) {
		namettrans->tgt_str = __cil_attrib_get_versname(key, args->num);
	}

	return SEPOL_OK;
exit:
	return rc;
}

/*
 * This is exactly the same as cil_attrib_nametypetransition, but the struct
 * layouts differ, so we can't reuse it.
 */
static int cil_attrib_type_rule(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	char *key;
	struct cil_type_rule *type_rule = (struct cil_type_rule *)node->data;

	if (type_rule->src != NULL) {
		cil_log(CIL_ERR, "AST already resolved. Not yet supported (line %d).\n",
			node->line);
		goto exit;
	}
	key = type_rule->src_str;
	if (__cil_get_plat_flavor(args->vers_map, (hashtab_key_t) key) == PLAT_TYPE) {
		type_rule->src_str = __cil_attrib_get_versname(key, args->num);
	}

	key = type_rule->tgt_str;
	if (__cil_get_plat_flavor(args->vers_map, (hashtab_key_t) key) == PLAT_TYPE) {
		type_rule->tgt_str = __cil_attrib_get_versname(key, args->num);
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_avrule(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	char *key;
	struct cil_avrule *avrule = (struct cil_avrule *)node->data;

	if (avrule->src != NULL) {
		cil_log(CIL_ERR, "AST already resolved. Not yet supported (line %d).\n",
			node->line);
		goto exit;
	}

	key = avrule->src_str;
	if (!strncmp(key, "base_typeattr_", 14) ||
	    __cil_get_plat_flavor(args->vers_map, (hashtab_key_t) key) == PLAT_TYPE) {
		avrule->src_str = __cil_attrib_get_versname(key, args->num);
	}

	key = avrule->tgt_str;
	if (!strncmp(key, "base_typeattr_", 14) ||
	    __cil_get_plat_flavor(args->vers_map, (hashtab_key_t) key) == PLAT_TYPE) {
		avrule->tgt_str = __cil_attrib_get_versname(key, args->num);
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_genfscon(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;

	struct cil_genfscon *genfscon = (struct cil_genfscon *)node->data;

	if (genfscon->context_str == NULL) {
		/* genfscon contains an anon context, which needs to have type checked */
		rc = cil_attrib_check_context(genfscon->context, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int cil_attrib_fsuse(struct cil_tree_node *node, struct version_args *args)
{
	int rc = SEPOL_ERR;
	struct cil_fsuse *fsuse = (struct cil_fsuse *)node->data;

	if (fsuse->context_str == NULL) {
		/* fsuse contains an anon context, which needs to have type checked */
		rc = cil_attrib_check_context(fsuse->context, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
	}

	return SEPOL_OK;
exit:
	return rc;
}

static int __attributize_helper(struct cil_tree_node *node, uint32_t *finished, void *extra_args)
{
	int rc = SEPOL_ERR;
	struct version_args *args = (struct version_args *) extra_args;

	if (node == NULL || finished == NULL || extra_args == NULL) {
		goto exit;
	}

	switch (node->flavor) {
	case CIL_SIDCONTEXT:
		/* contains type, but shouldn't involve an attributized type, maybe add
		   a check on type and error if it conflicts */
		rc = cil_attrib_sidcontext(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_ROLE:
		cil_log(CIL_ERR, "%s declaration illegal non-platform policy (line %d)\n",
			CIL_KEY_ROLE, node->line);
		rc = SEPOL_ERR;
		break;
	case CIL_ROLETYPE:
		/* Yes, this is needed if we support roletype in non-platform policy.
		   type_id can be type, typealias or typeattr */
		rc = cil_attrib_roletype(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_ROLEATTRIBUTE:
		/* don't think this is needed, only used for cil_gen_req, and we aren't
		   yet supporting roles in non-platform policy. */
		break;
	case CIL_TYPE:
		/* conver to attribute if in policy */
		rc = cil_attrib_type(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_TYPEPERMISSIVE:
		rc = cil_attrib_typepermissive(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_TYPEATTRIBUTE:
		rc = cil_attrib_typeattribute(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_TYPEATTRIBUTESET:
		rc = cil_attrib_typeattributeset(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_TYPEALIASACTUAL:
		/* this will break on an attributized type - identify it and throw error */
		rc = cil_attrib_typealiasactual(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_NAMETYPETRANSITION:
		/* not allowed in plat-policy. Types present, throw error if attributee */
		rc = cil_attrib_nametypetransition(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_TYPE_RULE:
		/* not allowed in plat-policy. Types present, throw error if attributee */
		rc = cil_attrib_type_rule(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_AVRULE:
	case CIL_AVRULEX:
		rc = cil_attrib_avrule(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_CONTEXT:
		/* not currently found in AOSP policy, but if found would need to be
		   checked to not be attributee */
		rc = cil_attrib_context(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_GENFSCON:
		/* not allowed in plat-policy, but types present, throw error if attributee */
		rc = cil_attrib_genfscon(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_FILECON:
	case CIL_NODECON:
	case CIL_PORTCON:
	case CIL_PIRQCON:
	case CIL_IOMEMCON:
	case CIL_IOPORTCON:
	case CIL_PCIDEVICECON:
	case CIL_DEVICETREECON:
	case CIL_VALIDATETRANS:
	case CIL_MLSVALIDATETRANS:
	case CIL_CALL:
	case CIL_MACRO:
	case CIL_OPTIONAL:
		/* Not currently found in AOSP and not yet properly handled.  Return err until support added. */
		cil_log(CIL_ERR, "unsupported policy statement (line %d)\n", node->line);
		rc = SEPOL_ERR;
		goto exit;
	case CIL_FSUSE:
		/* not allowed in plat-policy, but types present, throw error if attributee */
		cil_attrib_fsuse(node, args);
		if (rc != SEPOL_OK) {
			goto exit;
		}
		break;
	case CIL_CONSTRAIN:
	case CIL_MLSCONSTRAIN:
		/* there is type info here, but not sure if we'll allow non-platform code
		   to have this, or whether or not it's in platform policy.  Currently
		   assuming that mlsconstrain is private-platform only, and that normal
		   constrain is verboten. */
		cil_log(CIL_ERR, "unsupported policy statement (line %d)\n", node->line);
		rc = SEPOL_ERR;
		goto exit;
	default:
		break;
	}

	return SEPOL_OK;
exit:
	return rc;
}

/*
 * walk ast, replacing previously identified types and attributes with the
 * attributized version. Also replace previous references to the attributees
 * with the versioned type.
 */
static int cil_attributize(struct cil_db *db, hashtab_t vers_map, const char *num)
{
	int rc = SEPOL_ERR;
	struct version_args extra_args;
	extra_args.db = db;
	extra_args.vers_map = vers_map;
	extra_args.num = num;

	rc = cil_tree_walk(db->ast->root, __attributize_helper, NULL, NULL, &extra_args);
	if (rc != SEPOL_OK) {
		goto exit;
	}

	return SEPOL_OK;
exit:
	return rc;
}

/*
 * Create typeattributeset mappings from the attributes generated from the
 * original types/attributes to the original values.  This mapping will provide
 * the basis for the platform policy's mapping to this public version.
 *
 * Add these new typeattributeset nodes to the given cil_db.
 */
static int cil_build_mappings_tree(hashtab_key_t k, hashtab_datum_t d, void *args)
{
	struct cil_typeattributeset *attrset = NULL;
	struct cil_typeattribute *typeattr = NULL;
	struct cil_expandtypeattribute *expandattr = NULL;
	struct cil_tree_node *ast_node = NULL;
	struct version_args *verargs = (struct version_args *)args;
	struct cil_tree_node *ast_parent = verargs->db->ast->root;
	char *orig_type = (char *) k;
	struct version_datum *vers_datum = (struct version_datum *) d;
	char *new_key = __cil_attrib_get_versname(orig_type, verargs->num);

	if (vers_datum->ast_node->flavor == CIL_TYPEATTRIBUTE) {
		// platform attributes are not versioned
		return SEPOL_OK;
	}
	/* create typeattributeset datum */
	cil_typeattributeset_init(&attrset);
	cil_list_init(&attrset->str_expr, CIL_TYPE);
	attrset->attr_str = new_key;
	cil_list_append(attrset->str_expr, CIL_STRING, orig_type);

	/* create containing tree node */
	cil_tree_node_init(&ast_node);
	ast_node->data = attrset;
	ast_node->flavor = CIL_TYPEATTRIBUTESET;

	/* add to tree */
	ast_node->parent = ast_parent;
	if (ast_parent->cl_head == NULL)
		ast_parent->cl_head = ast_node;
	else
		ast_parent->cl_tail->next = ast_node;
	ast_parent->cl_tail = ast_node;

	/* create expandtypeattribute datum */
	cil_expandtypeattribute_init(&expandattr);
	cil_list_init(&expandattr->attr_strs, CIL_TYPE);
	cil_list_append(expandattr->attr_strs, CIL_STRING, new_key);
	expandattr->expand = CIL_TRUE;

	/* create containing tree node */
	cil_tree_node_init(&ast_node);
	ast_node->data = expandattr;
	ast_node->flavor = CIL_EXPANDTYPEATTRIBUTE;
	/* add to tree */
	ast_node->parent = ast_parent;
	ast_parent->cl_tail->next = ast_node;
	ast_parent->cl_tail = ast_node;

	/* re)declare typeattribute. */
	cil_typeattribute_init(&typeattr);
	typeattr->datum.name = new_key;
	typeattr->datum.fqn = new_key;
	cil_tree_node_init(&ast_node);
	ast_node->data = typeattr;
	ast_node->flavor = CIL_TYPEATTRIBUTE;
	ast_node->parent = ast_parent;
	ast_parent->cl_tail->next = ast_node;
	ast_parent->cl_tail = ast_node;

	return SEPOL_OK;
}

/*
 * Initializes the given db and uses the version mapping generated by
 * cil_extract_attributees() to fill it with the glue policy required to
 * connect the attributized policy created by cil_attributize() to the policy
 * declaring the concrete types.
 */
static int cil_attrib_mapping(struct cil_db **db, hashtab_t vers_map, const char *num)
{
	int rc = SEPOL_ERR;
	struct version_args extra_args;

	cil_db_init(db);

	/* foreach entry in vers_map, create typeattributeset node and attach to tree */
	extra_args.db = *db;
	extra_args.vers_map = NULL;
	extra_args.num = num;
	rc = hashtab_map(vers_map, cil_build_mappings_tree, &extra_args);
	if (rc != SEPOL_OK) {
		goto exit;
	}

	return SEPOL_OK;
exit:
	return rc;
}

int cil_android_attrib_mapping(struct cil_db **mdb, struct cil_db *srcdb, const char *num)
{
	int rc = SEPOL_ERR;
	hashtab_t ver_map_tab = NULL;

	ver_map_tab = hashtab_create(ver_map_hash_val, ver_map_key_cmp, VER_MAP_SZ);
	if (!ver_map_tab) {
		cil_log(CIL_ERR, "Unable to create version mapping table.\n");
		goto exit;
	}
	rc = cil_build_ast(srcdb, srcdb->parse->root, srcdb->ast->root);
	if (rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Unable to build source db AST.\n");
		goto exit;
	}
	rc = cil_extract_attributees(srcdb, ver_map_tab);
	if (rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Unable to extract attributizable elements from source db.\n");
		goto exit;
	}
	rc = cil_attrib_mapping(mdb, ver_map_tab, num);
	if (rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Unable to create mapping db from source db.\n");
		goto exit;
	}
exit:
	ver_map_destroy(ver_map_tab);
	return rc;
}

int cil_android_attributize(struct cil_db *tgtdb, struct cil_db *srcdb, const char *num)
{
	int rc = SEPOL_ERR;
	hashtab_t ver_map_tab = NULL;

	ver_map_tab = hashtab_create(ver_map_hash_val, ver_map_key_cmp, VER_MAP_SZ);
	if (!ver_map_tab) {
		cil_log(CIL_ERR, "Unable to create version mapping table.\n");
		goto exit;
	}
	rc = cil_build_ast(srcdb, srcdb->parse->root, srcdb->ast->root);
	if (rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Unable to build source db AST.\n");
		goto exit;
	}
	rc = cil_extract_attributees(srcdb, ver_map_tab);
	if (rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Unable to extract attributizable elements from source db.\n");
		goto exit;
	}
	rc = cil_build_ast(tgtdb, tgtdb->parse->root, tgtdb->ast->root);
	if (rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Unable to build target db AST.\n");
		goto exit;
	}
	rc = cil_attributize(tgtdb, ver_map_tab, num);
	if (rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Unable to attributize target db.\n");
		goto exit;
	}
exit:
	ver_map_destroy(ver_map_tab);
	return rc;
}

static int define_symbols(struct cil_tree_node *node, uint32_t *finished __attribute__((unused)), void *extra_args)
{
	int rc = SEPOL_OK;
	struct cil_type *type = NULL;
	struct cil_typeattribute *typeattribute = NULL;
	struct policydb_amend_args *args = extra_args;
	policydb_t *pdb = args->pdb;
	void **type_value_to_cil = args->type_value_to_cil;

	switch (node->flavor) {
	case CIL_TYPE:
		rc = cil_type_to_policydb(pdb, node->data, type_value_to_cil);
		// symtab_insert returns 1 when the symbol already exists
		if (rc == 1) {
			type = node->data;
			cil_log(CIL_WARN, "Type with symbol \"%s\" already exists.\n", type->datum.fqn);
			rc = SEPOL_OK;
		}
		break;
	case CIL_TYPEATTRIBUTE:
		rc = cil_typeattribute_to_policydb(pdb, node->data, type_value_to_cil);
		// symtab_insert returns 1 when the symbol already exists
		if (rc == 1) {
			typeattribute = node->data;
			cil_log(CIL_WARN, "Typeattribute with symbol \"%s\" already exists.\n", typeattribute->datum.fqn);
			rc = SEPOL_OK;
		}
		break;
	case CIL_ROLE:
	case CIL_POLICYCAP:
	case CIL_USER:
	case CIL_BOOL:
	case CIL_CATALIAS:
	case CIL_SENS: // Unsupported symbol statements.
	default:
		break;
	}

	return rc;
}

static int expand_symbols(struct cil_tree_node *node, uint32_t *finished __attribute__((unused)), void *extra_args)
{
	int rc = SEPOL_OK;
	struct policydb_amend_args *args = extra_args;
	const struct cil_db *db = args->db;
	policydb_t *pdb = args->pdb;

	switch (node->flavor) {
	case CIL_TYPEATTRIBUTE:
		rc = cil_typeattribute_to_bitmap(pdb, db, node->data);
		break;
	case CIL_ROLE:
	case CIL_AVRULE:
	case CIL_AVRULEX:
	case CIL_TYPE:
	case CIL_TYPEALIAS:
	case CIL_TYPEPERMISSIVE:
	case CIL_SENSALIAS:
	case CIL_USER:
	case CIL_TYPE_RULE:
	case CIL_ROLETRANSITION:
	case CIL_ROLEATTRIBUTESET:
	case CIL_NAMETYPETRANSITION:
	case CIL_CONSTRAIN:
	case CIL_MLSCONSTRAIN:
	case CIL_VALIDATETRANS:
	case CIL_MLSVALIDATETRANS:
	case CIL_RANGETRANSITION:
	case CIL_DEFAULTUSER:
	case CIL_DEFAULTROLE:
	case CIL_DEFAULTTYPE:
	case CIL_DEFAULTRANGE: // Unsupported symbol statements.
	default:
		break;
	}

	return rc;
}

static int apply_rules(struct cil_tree_node *node, uint32_t *finished __attribute__((unused)), void *extra_args)
{
	int rc = SEPOL_OK;
	struct cil_avrule *rule = NULL;
	struct policydb_amend_args *args = extra_args;
	const struct cil_db *db = args->db;
	policydb_t *pdb = args->pdb;

	switch (node->flavor) {
	case CIL_AVRULE:
		rule = node->data;
		if (rule->rule_kind != CIL_AVRULE_NEVERALLOW) {
			rc = cil_avrule_to_policydb(pdb, db, node->data);
		}
		else {
			cil_log(CIL_WARN, "Found a neverallow rule.\n");
		}
		break;
	case CIL_BOOLEANIF:
	case CIL_AVRULEX:
	case CIL_ROLEALLOW: // Unsupported rule statement.
	default:
		break;
	}

	return rc;
}

int cil_amend_policydb(struct cil_db *db, sepol_policydb_t *policydb)
{
	int rc = SEPOL_ERR;
	policydb_t *pdb = &policydb->p;

	if (db == NULL || policydb == NULL) {
		if (db == NULL) {
			cil_log(CIL_ERR, "db == NULL\n");
		}
		else if (policydb == NULL) {
			cil_log(CIL_ERR, "policydb == NULL\n");
		}
		return rc;
	}

	// type_value_to_cil should be able to map the new types in the cil_db, the
	// existing types in the pdb, and the redefinitions from the cil_db.
	// Since libsepol values start at 1, we allocate extra memory instead of shifting every value.
	void **type_value_to_cil = calloc(db->num_types_and_attrs + pdb->p_types.nprim + 1,
									  sizeof(*type_value_to_cil));
	if (!type_value_to_cil)
		goto exit;

	struct policydb_amend_args extra_args;
	extra_args.db = db;
	extra_args.pdb = pdb;
	extra_args.type_value_to_cil = type_value_to_cil;

	// 1) Add types and attributes symbols to policy_db.
	unsigned int types_size = pdb->p_types.nprim;
	rc = cil_tree_walk(db->ast->root, define_symbols, NULL, NULL, &extra_args);
	if(rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Error adding symbols to policydb.\n");
		goto exit;
	}
	if (pdb->p_types.nprim > types_size) {
		// We introduced new types, we need to expand the type<->attr maps.
		pdb->type_attr_map = cil_realloc(pdb->type_attr_map, pdb->p_types.nprim * sizeof(ebitmap_t));
		pdb->attr_type_map = cil_realloc(pdb->attr_type_map, pdb->p_types.nprim * sizeof(ebitmap_t));
		for (unsigned int i = types_size; i < pdb->p_types.nprim; i++) {
			ebitmap_init(&pdb->type_attr_map[i]);
			ebitmap_init(&pdb->attr_type_map[i]);
		}
	}

	// 2) Expand typeattribute symbols.
	rc = cil_tree_walk(db->ast->root, expand_symbols, NULL, NULL, &extra_args);
	if(rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Error expanding symbols.\n");
		goto exit;
	}

	// 3) Apply rule statements.
	rc = cil_tree_walk(db->ast->root, apply_rules, NULL, NULL, &extra_args);
	if(rc != SEPOL_OK) {
		cil_log(CIL_ERR, "Error applying rules.\n");
		goto exit;
	}

exit:
	free(type_value_to_cil);
	return rc;
}
