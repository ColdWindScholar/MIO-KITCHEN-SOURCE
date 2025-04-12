# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
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
import os
import re
from .posix import symlink
from . import contextpatch
from . import fspatch
def parse_update_script(fd):
    if not fd:
        raise IOError('fd isn\'t valid!')
    fd.seek(0, 0)
    commands = re.findall(r'(\w+)\((.*?)\)', fd.read().replace('\n', ''))
    parsed_commands = [
        [command, *(arg[0] or arg[1] or arg[2] for arg in re.findall(r'"([^"]+)"|(\b\d+\b)|(\b\S+\b)', args))]
        for command, args in commands]
    return parsed_commands


# This Function copy from affggh mtk-porttool(https://gitee.com/affggh/mtk-garbage-porttool)
def script2fs_context(input_f, outdir, project):
    fs_label = [["/", '0', '0', '0755'], ["/lost\\+found", '0', '0', '0700']]
    fc_label = [['/', 'u:object_r:system_file:s0'], ['/system(/.*)?', 'u:object_r:system_file:s0']]
    print("Parsing flash script...")
    with open(input_f, 'r', encoding='utf-8') as updater:
        contents = parse_update_script(updater)
    last_fpath = ''
    for content in contents:
        command, *args = content

        if command == 'symlink':
            src, *targets = args
            for target in targets:
                symlink(src, str(os.path.join(project, target.lstrip('/'))))
        elif command in ['set_metadata', 'set_metadata_recursive']:
            dirmode = False if command == 'set_metadata' else True
            fpath, *fargs = args
            fpath = fpath.replace("+", "\\+").replace("[", "\\[").replace('//', '/')
            if fpath == last_fpath:
                continue  # skip same path
            # initial
            uid, gid, mode, extra = '0', '0', '644', ''
            selable = 'u:object_r:system_file:s0'  # common system selable
            for index, farg in enumerate(fargs):
                if farg == 'uid':
                    uid = fargs[index + 1]
                elif farg == 'gid':
                    gid = fargs[index + 1]
                elif farg in ['mode', 'fmode', 'dmode']:
                    if dirmode and farg == 'dmode':
                        mode = fargs[index + 1]
                    else:
                        mode = fargs[index + 1]
                elif farg == 'capabilities':
                    # continue
                    if fargs[index + 1] == '0x0':
                        extra = ''
                    else:
                        extra = 'capabilities=' + fargs[index + 1]
                elif farg == 'selabel':
                    selable = fargs[index + 1]
            fs_label.append(
                [fpath.lstrip('/'), uid, gid, mode, extra])
            fc_label.append(
                [fpath, selable])
            last_fpath = fpath

    # generate config
    print("生成fs_config 和 file_contexts")
    fs_label.sort()
    fc_label.sort()
    with open(os.path.join(outdir, "system_fs_config"), 'w', newline='\n', encoding='utf-8') as fs_config, open(
            os.path.join(outdir, "system_file_contexts"), 'w', newline='\n', encoding='utf-8') as file_contexts:
        for fs in fs_label:
            fs_config.write(" ".join(fs) + '\n')
        for fc in fc_label:
            file_contexts.write(" ".join(fc) + '\n')
    fspatch.main(os.path.join(project, 'system'), os.path.join(outdir, "system_fs_config"))
    contextpatch.main(os.path.join(project, 'system'), os.path.join(outdir, "system_file_contexts"), None)
