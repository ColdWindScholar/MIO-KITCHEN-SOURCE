# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under theGNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
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


def extract_field(error, keyword):
    match = re.search(f"{keyword}=([^\\s]+)", error)
    if match:
        return match.group(1).replace('u:r:', '').replace('u:object_r:', '').replace(':s0', '')
    return None


def find_permissions(rule_list, all_config):
    perms = re.search(f"{re.escape(all_config)} (.+)", rule_list)
    if perms:
        return perms.group(1)
    return ""


def remove_empty_lines(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line for line in f.readlines() if line.strip()]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("".join(lines))


def merge_permissions(existing_perms, new_perms):
    existing_perm_set = set(existing_perms.split())
    new_perm_set = set(new_perms.split())
    return ' '.join(sorted(existing_perm_set.union(new_perm_set)))


def handle_target_file(target):
    if os.path.isfile(target) and os.path.getsize(target) > 0:
        action = 'y'
        if action.lower() in ["y", "yes"]:
            print(f"- 继续写入 {target}")
            with open(target, 'r', encoding='utf-8') as f:
                return re.sub(r"[{}()]", "", f.read()).replace('allow ', '')
        elif action.lower() in ["n", "no"]:
            print(f"- 清空 {target}")
            open(target, 'w').close()
            return ""
    else:
        open(target, 'w').close()
        return ""


def main(input_log, output_dir):
    sepolicy_rule = os.path.join(output_dir, 'sepolicy.rule')
    sepolicy_cil = os.path.join(output_dir, 'sepolicy.cil')
    rules = 0

    print("========SELinux audit allow tool========")

    if os.path.isfile(os.path.join(output_dir, input_log)):
        file = os.path.join(output_dir, input_log)
    elif os.path.isfile(input_log):
        file = input_log
    else:
        print(f"! 未找到日志文件: {input_log}\n")
        return

    rule_list = ""
    for target in [sepolicy_rule, sepolicy_cil]:
        rule_list += handle_target_file(target)

    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
        log = [line for line in f if "avc:  denied" in line and "untrusted_app" not in line]

    rules_text_rule = ""
    rules_text_cil = ""

    rules_dict = {}

    for error in log:
        scontext = extract_field(error, "scontext")
        tcontext = extract_field(error, "tcontext")
        tclass = extract_field(error, "tclass")
        perms_match = re.search(r"{([^}]+)}", error)
        perms = perms_match.group(1).strip() if perms_match else ""
        all_config = f"{scontext} {tcontext} {tclass}"

        rules += 1

        if not scontext or not tcontext or not tclass or not perms:
            continue

        if all_config in rules_dict:
            existing_perms = rules_dict[all_config]
            merged_perms = merge_permissions(existing_perms, perms)
            rules_dict[all_config] = merged_perms
        else:
            rules_dict[all_config] = perms

    for all_config, perms in rules_dict.items():
        scontext, tcontext, tclass = all_config.split(' ', 2)
        rules_text_rule += f"allow {scontext} {tcontext} {tclass} {{ {perms} }}\n"
        rules_text_cil += f"(allow {scontext} {tcontext} ({tclass} ({perms})))\n"

    with open(sepolicy_rule, 'a', encoding='utf-8') as f:
        f.write(rules_text_rule)

    with open(sepolicy_cil, 'a', encoding='utf-8') as f:
        f.write(rules_text_cil)

    remove_empty_lines(sepolicy_rule)
    remove_empty_lines(sepolicy_cil)

    print("- Done!")
