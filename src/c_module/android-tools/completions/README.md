The AOSP android tools codebase provides generic completion files which
can be used by both bash and zsh but require a `check_type` function to
be provided. We install these generic files to a common directory
(`COMPLETION_COMMON_DIR`) and source them from specific files created
for bash/zsh which provide the `check_type` function.

For more information see [#22](https://github.com/nmeum/android-tools/issues/22).
