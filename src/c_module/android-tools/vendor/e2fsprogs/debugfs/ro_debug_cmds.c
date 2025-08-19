/* debugfs/ro_debug_cmds.c - automatically generated from debugfs/ro_debug_cmds.ct */
#include <ss/ss.h>

static char const * const ssu00001[] = {
"show_debugfs_params",
    "params",
    (char const *)0
};
extern void do_show_debugfs_params __SS_PROTO;
static char const * const ssu00002[] = {
"open_filesys",
    "open",
    (char const *)0
};
extern void do_open_filesys __SS_PROTO;
static char const * const ssu00003[] = {
"close_filesys",
    "close",
    (char const *)0
};
extern void do_close_filesys __SS_PROTO;
static char const * const ssu00004[] = {
"freefrag",
    "e2freefrag",
    (char const *)0
};
extern void do_freefrag __SS_PROTO;
static char const * const ssu00005[] = {
"show_super_stats",
    "stats",
    (char const *)0
};
extern void do_show_super_stats __SS_PROTO;
static char const * const ssu00006[] = {
"ncheck",
    (char const *)0
};
extern void do_ncheck __SS_PROTO;
static char const * const ssu00007[] = {
"icheck",
    (char const *)0
};
extern void do_icheck __SS_PROTO;
static char const * const ssu00008[] = {
"change_root_directory",
    "chroot",
    (char const *)0
};
extern void do_chroot __SS_PROTO;
static char const * const ssu00009[] = {
"change_working_directory",
    "cd",
    (char const *)0
};
extern void do_change_working_dir __SS_PROTO;
static char const * const ssu00010[] = {
"list_directory",
    "ls",
    (char const *)0
};
extern void do_list_dir __SS_PROTO;
static char const * const ssu00011[] = {
"show_inode_info",
    "stat",
    (char const *)0
};
extern void do_stat __SS_PROTO;
static char const * const ssu00012[] = {
"dump_extents",
    "extents",
    "ex",
    (char const *)0
};
extern void do_dump_extents __SS_PROTO;
static char const * const ssu00013[] = {
"blocks",
    (char const *)0
};
extern void do_blocks __SS_PROTO;
static char const * const ssu00014[] = {
"filefrag",
    (char const *)0
};
extern void do_filefrag __SS_PROTO;
static char const * const ssu00015[] = {
"testi",
    (char const *)0
};
extern void do_testi __SS_PROTO;
static char const * const ssu00016[] = {
"find_free_block",
    "ffb",
    (char const *)0
};
extern void do_find_free_block __SS_PROTO;
static char const * const ssu00017[] = {
"find_free_inode",
    "ffi",
    (char const *)0
};
extern void do_find_free_inode __SS_PROTO;
static char const * const ssu00018[] = {
"print_working_directory",
    "pwd",
    (char const *)0
};
extern void do_print_working_directory __SS_PROTO;
static char const * const ssu00019[] = {
"list_deleted_inodes",
    "lsdel",
    (char const *)0
};
extern void do_lsdel __SS_PROTO;
static char const * const ssu00020[] = {
"logdump",
    (char const *)0
};
extern void do_logdump __SS_PROTO;
static char const * const ssu00021[] = {
"htree_dump",
    "htree",
    (char const *)0
};
extern void do_htree_dump __SS_PROTO;
static char const * const ssu00022[] = {
"dx_hash",
    "hash",
    (char const *)0
};
extern void do_dx_hash __SS_PROTO;
static char const * const ssu00023[] = {
"dirsearch",
    (char const *)0
};
extern void do_dirsearch __SS_PROTO;
static char const * const ssu00024[] = {
"bmap",
    (char const *)0
};
extern void do_bmap __SS_PROTO;
static char const * const ssu00025[] = {
"imap",
    (char const *)0
};
extern void do_imap __SS_PROTO;
static char const * const ssu00026[] = {
"supported_features",
    (char const *)0
};
extern void do_supported_features __SS_PROTO;
static char const * const ssu00027[] = {
"dump_mmp",
    (char const *)0
};
extern void do_dump_mmp __SS_PROTO;
static char const * const ssu00028[] = {
"extent_open",
    "eo",
    (char const *)0
};
extern void do_extent_open __SS_PROTO;
static char const * const ssu00029[] = {
"lost_quota",
    "lq",
    (char const *)0
};
extern void do_list_quota __SS_PROTO;
static char const * const ssu00030[] = {
"get_quota",
    "gq",
    (char const *)0
};
extern void do_get_quota __SS_PROTO;
static ss_request_entry ssu00031[] = {
    { ssu00001,
      do_show_debugfs_params,
      "Show debugfs parameters",
      0 },
    { ssu00002,
      do_open_filesys,
      "Open a filesystem",
      0 },
    { ssu00003,
      do_close_filesys,
      "Close the filesystem",
      0 },
    { ssu00004,
      do_freefrag,
      "Report free space fragmentation",
      0 },
    { ssu00005,
      do_show_super_stats,
      "Show superblock statistics",
      0 },
    { ssu00006,
      do_ncheck,
      "Do inode->name translation",
      0 },
    { ssu00007,
      do_icheck,
      "Do block->inode translation",
      0 },
    { ssu00008,
      do_chroot,
      "Change root directory",
      0 },
    { ssu00009,
      do_change_working_dir,
      "Change working directory",
      0 },
    { ssu00010,
      do_list_dir,
      "List directory",
      0 },
    { ssu00011,
      do_stat,
      "Show inode information ",
      0 },
    { ssu00012,
      do_dump_extents,
      "Dump extents information ",
      0 },
    { ssu00013,
      do_blocks,
      "Dump blocks used by an inode ",
      0 },
    { ssu00014,
      do_filefrag,
      "Report fragmentation information for an inode",
      0 },
    { ssu00015,
      do_testi,
      "Test an inode's in-use flag",
      0 },
    { ssu00016,
      do_find_free_block,
      "Find free block(s)",
      0 },
    { ssu00017,
      do_find_free_inode,
      "Find free inode(s)",
      0 },
    { ssu00018,
      do_print_working_directory,
      "Print current working directory",
      0 },
    { ssu00019,
      do_lsdel,
      "List deleted inodes",
      0 },
    { ssu00020,
      do_logdump,
      "Dump the contents of the journal",
      0 },
    { ssu00021,
      do_htree_dump,
      "Dump a hash-indexed directory",
      0 },
    { ssu00022,
      do_dx_hash,
      "Calculate the directory hash of a filename",
      0 },
    { ssu00023,
      do_dirsearch,
      "Search a directory for a particular filename",
      0 },
    { ssu00024,
      do_bmap,
      "Calculate the logical->physical block mapping for an inode",
      0 },
    { ssu00025,
      do_imap,
      "Calculate the location of an inode",
      0 },
    { ssu00026,
      do_supported_features,
      "Print features supported by this version of e2fsprogs",
      0 },
    { ssu00027,
      do_dump_mmp,
      "Dump MMP information",
      0 },
    { ssu00028,
      do_extent_open,
      "Open inode for extent manipulation",
      0 },
    { ssu00029,
      do_list_quota,
      "List quota",
      0 },
    { ssu00030,
      do_get_quota,
      "Get quota",
      0 },
    { 0, 0, 0, 0 }
};

ss_request_table debug_cmds = { 2, ssu00031 };
