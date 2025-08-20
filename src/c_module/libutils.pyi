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
