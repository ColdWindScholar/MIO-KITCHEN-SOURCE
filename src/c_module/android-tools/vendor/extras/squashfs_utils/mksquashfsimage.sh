#!/bin/bash
#
# To call this script, make sure mksquashfs is somewhere in PATH

function usage() {
cat<<EOT
Usage:
${0##*/} SRC_DIR OUTPUT_FILE [-s] [-m MOUNT_POINT] [-d PRODUCT_OUT] [-C FS_CONFIG ] [-c FILE_CONTEXTS] [-B BLOCK_MAP_FILE] [-b BLOCK_SIZE] [-z COMPRESSOR] [-zo COMPRESSOR_OPT] [-t COMPRESS_THRESHOLD] [-w WHITELIST_FILE] [-a]
EOT
}

echo "in mksquashfsimage.sh PATH=$PATH"

if [ $# -lt 2 ]; then
    usage
    exit 1
fi

SRC_DIR=$1
if [ ! -d $SRC_DIR ]; then
  echo "Can not find directory $SRC_DIR!"
  exit 2
fi
OUTPUT_FILE=$2
shift; shift

SPARSE=false
if [[ "$1" == "-s" ]]; then
    SPARSE=true
    shift;
fi

MOUNT_POINT=
if [[ "$1" == "-m" ]]; then
    MOUNT_POINT=$2
    shift; shift
fi

PRODUCT_OUT=
if [[ "$1" == "-d" ]]; then
    PRODUCT_OUT=$2
    shift; shift
fi

FS_CONFIG=
if [[ "$1" == "-C" ]]; then
    FS_CONFIG=$2
    shift; shift
fi

FILE_CONTEXTS=
if [[ "$1" == "-c" ]]; then
    FILE_CONTEXTS=$2
    shift; shift
fi

BLOCK_MAP_FILE=
if [[ "$1" == "-B" ]]; then
    BLOCK_MAP_FILE=$2
    shift; shift
fi

BLOCK_SIZE=131072
if [[ "$1" == "-b" ]]; then
    BLOCK_SIZE=$2
    shift; shift
fi

COMPRESSOR="lz4"
COMPRESSOR_OPT="-Xhc"
if [[ "$1" == "-z" ]]; then
    COMPRESSOR=$2
    COMPRESSOR_OPT=
    shift; shift
fi

if [[ "$1" == "-zo" ]]; then
    COMPRESSOR_OPT=$2
    shift; shift
fi

COMPRESS_THRESHOLD=0
if [[ "$1" == "-t" ]]; then
    COMPRESS_THRESHOLD=$2
    shift; shift
fi

WHITELIST_FILE=
if [[ "$1" == "-w" ]]; then
    WHITELIST_FILE=$2
    shift; shift
fi

DISABLE_4K_ALIGN=false
if [[ "$1" == "-a" ]]; then
    DISABLE_4K_ALIGN=true
    shift;
fi

OPT=""
if [ -n "$MOUNT_POINT" ]; then
  OPT="$OPT -mount-point $MOUNT_POINT"
fi
if [ -n "$PRODUCT_OUT" ]; then
  OPT="$OPT -product-out $PRODUCT_OUT"
fi
if [ -n "$FS_CONFIG" ]; then
  OPT="$OPT -fs-config-file $FS_CONFIG"
fi
if [ -n "$FILE_CONTEXTS" ]; then
  OPT="$OPT -context-file $FILE_CONTEXTS"
fi
if [ -n "$BLOCK_MAP_FILE" ]; then
  OPT="$OPT -block-map $BLOCK_MAP_FILE"
fi
if [ -n "$BLOCK_SIZE" ]; then
  OPT="$OPT -b $BLOCK_SIZE"
fi
if [ -n "$COMPRESS_THRESHOLD" ]; then
  OPT="$OPT -t $COMPRESS_THRESHOLD"
fi
if [ "$DISABLE_4K_ALIGN" = true ]; then
  OPT="$OPT -disable-4k-align"
fi
if [ -n "$WHITELIST_FILE" ]; then
    OPT="$OPT -whitelist $WHITELIST_FILE"
fi

MAKE_SQUASHFS_CMD="mksquashfs $SRC_DIR/ $OUTPUT_FILE -no-progress -comp $COMPRESSOR $COMPRESSOR_OPT -no-exports -noappend -no-recovery -no-fragments -no-duplicates -android-fs-config $OPT"
echo $MAKE_SQUASHFS_CMD
$MAKE_SQUASHFS_CMD

if [ $? -ne 0 ]; then
    exit 4
fi

SPARSE_SUFFIX=".sparse"
if [ "$SPARSE" = true ]; then
    img2simg $OUTPUT_FILE $OUTPUT_FILE$SPARSE_SUFFIX
    if [ $? -ne 0 ]; then
        exit 4
    fi
    mv $OUTPUT_FILE$SPARSE_SUFFIX $OUTPUT_FILE
fi

