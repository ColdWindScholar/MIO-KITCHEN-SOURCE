"""AI Document For MIO-KITCHEN"""
# Copyright (C) 2024 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
library = {
    "error: ext4_allocate_best_fit_partial: failed to allocate xxx blocks, out of space?": {
        "en": "You should increase the size for the img you are packing, if u use <auto>, You should switch to the <original size> , and modify <PARTNAME>_size.txt(under <config> folder) to increase the size of the image, and try again",
        "cn": "您应该增加镜像打包的大小，如果您使用＜自动读取＞，您应该切换到＜原大小＞，并修改＜分区名＞_size.txt(位于<config>文件夹)增加图像的大小，然后重试打包"
    },
    'error: build_directory_structure: cannot lookup security context for xxx': {
        "en": "You should make sure there is no whitespace characters in directory or file names and try again.",
        "cn": "您应该检查此文件夹是否存在名称带空格的文件夹/文件，发现后请重命名或删除，然后重新打包"
    },
    "Partition table must have at least one entry": {
        "en": "Please select at least one partition for Super",
        "cn": "请为Super至少选择一个分区打包"
    },
}
