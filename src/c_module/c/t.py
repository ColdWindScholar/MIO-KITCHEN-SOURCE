import libutils
libutils.ext4_extractor(".", "/metadata", "./metadata.img", "metadata", 4096, 'e', False, "metadata")
libutils.img2simg('raw.img', 'sparse.img', 4096, False)
libutils.simg2img(['sparse.img'], 'raw.img')
print("fuck")
libutils.e2fsdroid("", "", 1286544607,"./metadata_fs_config", "./metadata_file_contexts", "", "/metadata", ""
                   ,"metadata", False, False, "", "", "./raw.img")