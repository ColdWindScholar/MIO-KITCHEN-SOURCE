import json
import os
import os.path as op

from src.core.utils import tool_bin, prog_path

# configs for porttool
support_chipset_portstep = {
    'mt6572/mt6582/mt6592 kernel-3.4.67': {
        'partitions': {  # This is use for auto generage updater-script
            'system': '/dev/block/mmcblk0p4',
            'boot': '/dev/block/bootimg',
        },
        'flags': {  # flag control in item
            'generate_script': True,  # Auto generate updater-script
            # ========== split line ============ 
            'replace_kernel': True,  # startwith replace will replace file
            'replace_fstab': False,
            'selinux_permissive': True,
            'enable_adb': True,
            # ========== split line ============ ↑ is boot.img ↓ is system
            'replace_firmware': True,
            'replace_mddb': True,
            'replace_malidriver': True,
            'replace_audiodriver': False,
            'replace_libshowlogo': False,
            'replace_mtk-kpd': True,
            'replace_gralloc': True,
            'replace_hwcomposer': True,
            'replace_ril': False,
            'single_simcard': False,
            'dual_simcard': False,
            'fit_density': True,
            'change_model': True,
            'change_timezone': True,
            'change_locale': True,
            'use_custom_update-binary': True,
        },
        'replace': {  # if you flags startswith replace_ you must define which files need to be replace
            'kernel': [  # boot from base -> port
                "kernel",
                # commonly not compressed by gz at mt6572 etc
                # "kernel.gz",
            ],
            'fstab': [  # boot from base -> port
                "initrd/fstab",
                "initrd/fstab.mt6572",
                "initrd/fstab.mt6582",
                "initrd/fstab.mt6592",
            ],
            'firmware': [  # below is system
                "etc/firmware"  # if is a directory, will remove first
            ],
            'mddb': [
                "etc/mddb"
            ],
            'malidriver': [
                "lib/libMali.so"
            ],
            'audiodriver': [
                "lib/libaudio.primary.default.so",
                "etc/audio_effects.conf",
                "etc/audio_policy.conf"
            ],
            'libshowlogo': [
                "lib/libshowlogo.so"
            ],
            'mtk-kpd': [
                "usr/keylayout/mtk-kpd.kl"
            ],
            'ril': [
                "bin/ccci_fsd",
                "bin/ccci_mdinit",
                "bin/gsm0710muxd",
                "bin/gsm0710muxdmd2 ",
                "bin/rild",
                "bin/rildmd2",
                "lib/librilmtk.so",
                "lib/librilmtkmd2.so",
                "lib/librilutils.so ",
                "lib/mtk-ril.so",
                "lib/mtk-rilmd2.so",
            ],
            'gralloc': [
                "lib/hw/gralloc.mt6572.so",
                "lib/hw/gralloc.mt6582.so",
                "lib/hw/gralloc.mt6592.so",
            ],
            'hwcomposer': [
                "lib/hw/hwcomposer.mt6572.so",
                "lib/hw/hwcomposer.mt6582.so",
                "lib/hw/hwcomposer.mt6592.so",
            ]
        },
    },
    'kernel only (only replace kernel)': {
        'partitions': {
            # of couse we have no idea to know system and boot partition at which position
            # keep empty and set generate_script: False
        },
        'flags': {
            'generate_script': False,  # do not generate updater-script on kernel only mode
            'replace_kernel': True,
            'selinux_permissive': True,
            'enable_adb': True,
            'replace_firmware': True,
            'replace_mddb': True,
        },
        'replace': {
            'kernel': [  # boot from base -> port
                "kernel",
                "kernel.gz"  # may be gz compressed
            ],
            'firmware': [  # below is system
                "etc/firmware"  # if is a directory, will remove first
            ],
            'mddb': [
                "etc/mddb"
            ],
        },
    },
    'G79 (mt6735/mt6735m/mt6737) kernel-3.18.19': {
        'partitions': {},
        'flags': {  # flag control in item
            'generate_script': False,  # Auto generate updater-script
            # ========== split line ============ 
            'replace_kernel': True,  # startwith replace will replace file
            'replace_fstab': False,
            'selinux_permissive': True,
            'enable_adb': True,
            # ========== split line ============ ↑ is boot.img ↓ is system
            'replace_firmware': True,
            'replace_mddb': True,
            'replace_malidriver': False,
            'replace_audiodriver': False,
            'replace_libshowlogo': False,
            'replace_mtk-kpd': False,
            'replace_wifi': False,
            'replace_camera': False,
            'single_simcard': False,
            'dual_simcard': False,
            'fit_density': True,
            'change_model': True,
            'change_timezone': True,
            'change_locale': True,
            'use_custom_update-binary': True,
        },
        'replace': {  # if you flags startswith replace_ you must define which files need to be replace
            'kernel': [  # boot from base -> port
                "kernel",
                # commonly not compressed by gz at mt6572 etc
                # "kernel.gz",
            ],
            'fstab': [  # boot from base -> port
                "initrd/fstab",
                "initrd/fstab.mt6735",
                "initrd/fstab.mt6737",
            ],
            'firmware': [  # below is system
                "etc/firmware"  # if is a directory, will remove first
            ],
            'mddb': [
                "etc/mddb"
            ],
            'malidriver': [
                "lib/libMali.so"
            ],
            'audiodriver': [
                "lib/hw/audio.primary.mt6735.so",
                "lib/hw/audio.primary.mt6735m.so",
                "lib/hw/audio.primary.mt6737.so",
                "lib/hw/audio.primary.mt6737m.so",
            ],
            'libshowlogo': [
                "lib/libshowlogo.so"
            ],
            'mtk-kpd': [
                "usr/keylayout/mtk-kpd.kl"
            ],
            'wifi': [
                "bin/netcfg",
                "bin/dhcpcd",
                "bin/ifconfig",
                "bin/hostap",
                "bin/hostapd",
                "bin/hostapd_bin",
                "bin/pcscd",
                "bin/wlan*",
                "bin/wpa*",
                "bin/netd",
                "lib/libhardware_legacy.so",
                "etc/wifi",
            ],
            'camera': [
                "lib/lib3a.so",
                "lib/libcamalgo.so",
                "lib/libcamdrv.so",
                "lib/libcameracustom.so",
                "lib/libfeatureio.so",
                "lib/libimageio.so",
                "lib/libimageio_plat_drv.so",
                "lib/libJpgDecPipe.so",
                "lib/libJpgEncPipe.so",
                "lib/libmhalImageCodec.so",
                "lib/libmtkcamera_client.so",
                "lib/libmtkjpeg.so",
                "lib/libcam.paramsmgr.so",
            ]
        },
    },
}
configs = os.path.join(prog_path, 'bin', 'configs.json')
if op.isfile(configs):
    with open(configs, 'r') as c:
        support_chipset_portstep = json.load(c)
else:
    with open(configs, 'w') as c:
        json.dump(support_chipset_portstep, c, indent=4)

support_chipset = list(support_chipset_portstep.keys())
support_packtype = ['zip', 'img']
ext_ext = '.exe' if os.name == 'nt' else ''

# binarys
make_ext4fs_bin = op.join(tool_bin, f"make_ext4fs{ext_ext}")
magiskboot_bin = op.join(tool_bin, f"magiskboot{ext_ext}")
simg2img_bin = op.join(tool_bin, f"simg2img{ext_ext}]")
img2simg_bin = op.join(tool_bin, f"img2simg{ext_ext}")
