"""AI Document For MIO-KITCHEN"""
library = {
    "error: ext4_allocate_best_fit_partial: failed to allocate xxx blocks, out of space?": {
        "en": "You should increase the size of the img packaging, if u use <auto>, You should switch to the <original size> , and modify <PARTNAME>_size.txt(in <config> folder) increase the size of the image, and try pack again",
        "cn": "您应该增加镜像打包的大小，如果您使用＜自动读取＞，您应该切换到＜原大小＞，并修改＜分区名＞_size.txt(位于<config>文件夹)增加图像的大小，然后重试打包"
    },
    'error: build_directory_structure: cannot lookup security context for xxx': {
        "en": "You should check if there are any folders/files with spaces in their names in this folder. If you find any, please rename or delete them and repackage them",
        "cn": "您应该检查此文件夹是否存在名称带空格的文件夹/文件，发现后请重命名或删除，然后重新打包"
    }
}
