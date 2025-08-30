#!/bin/env python3
from typing import Literal


def ext4_extractor(config_dir: str, mountpoint: str, filename: str, directory: str, blocksize: int,
                   image_type: Literal['e', 's'], android_configure_only: bool, part_name:str) -> int:
    """
    :param part_name: partition_name:e.g:system
    :param config_dir: dir to store config files
    :param mountpoint: e.g: "/system"
    :param filename: image file path
    :param directory: output directory
    :param blocksize: recommended 4096 as default
    :param image_type: if s, sparse. if e, raw.
    :param android_configure_only: extract configure only
    :return: 0 if successful else != 0
    """
    raise NotImplementedError("Sorry!Cannot use the func.")

def simg2img(sparse_file_list:list[str], output_filename:str) -> int:
    """

    :param sparse_file_list:e.g:["sparse1.img", "sparse2.img"]
    :param output_filename:e.g:"raw.img"
    :return:0 if successful else != 0
    """
    raise NotImplementedError("Not Ready!")

def img2simg(raw_image_file:str, sparse_image_file:str, block_size:int, read_hole:bool) -> int:
    """

    :param raw_image_file: Raw image file path
    :param sparse_image_file:Output sparse_image file path
    :param block_size:default is 4096
    :param read_hole: default is False
    :return:0 if successful else 0
    """
    raise NotImplementedError("Not Ready!")

def e2fsdroid(block_list:str, basefs_out:str,timestamp:int, fs_config:str, file_contexts:str, product_out:str, mountpoint:str, basefs_in:str, src_dir:str, is_raw:bool, is_share_dup:bool, uid_mapping:str, gid_mapping:str,image:str) -> str:
    """

    :param block_list:
    :param basefs_out:
    :param timestamp:
    :param fs_config:
    :param file_contexts:
    :param product_out:
    :param mountpoint:
    :param basefs_in:
    :param src_dir:
    :param is_raw:
    :param is_share_dup:
    :param uid_mapping:
    :param gid_mapping:
    :param image:
    :return:
    """
    raise NotImplementedError("Not Ready!")