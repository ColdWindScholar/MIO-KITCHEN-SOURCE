# JIT symbols

[TOC]

## Java JIT symbols

On Android >= P, simpleperf supports profiling Java code, no matter whether it is executed by
the interpreter, or JITed, or compiled into native instructions. So you don't need to do anything.

For details on Android O and N, see
[android_application_profiling.md](./android_application_profiling.md#prepare-an-android-application).

## Generic JIT symbols

Simpleperf supports picking up symbols from per-pid symbol map files, somewhat similar to what
Linux kernel perftool does. Application should create those files at specific locations.

### Symbol map file location for application

Application should create symbol map files in its data directory.

For example, process `123` of application `foo.bar.baz` should create
`/data/data/foo.bar.baz/perf-123.map`.

### Symbol map file location for standalone program

Standalone programs should create symbol map files in `/data/local/tmp`.

For example, standalone program process `123` should create `/data/local/tmp/perf-123.map`.

### Symbol map file format

Symbol map file is a text file.

Every line describes a new symbol. Line format is:
```
<symbol-absolute-address> <symbol-size> <symbol-name>
```

For example:
```
0x10000000 0x16 jit_symbol_one
0x20000000 0x332 jit_symbol_two
0x20002004 0x8 jit_symbol_three
```

All characters after the symbol size and until the end of the line are parsed as the symbol name,
with leading and trailing spaces removed. This means spaces are allowed in symbol names themselves.

### Known issues

Current implementation gets confused if memory pages where JIT symbols reside are reused by mapping
a file either before or after.

For example, if memory pages were first used by `dlopen("libfoo.so")`, then freed by `dlclose`,
then allocated for JIT symbols - simpleperf will report symbols from `libfoo.so` instead.
