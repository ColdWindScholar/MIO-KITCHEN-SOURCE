#!/usr/bin/env python3
# pylint: disable=line-too-long
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
import platform as plat # Renamed to avoid conflict with 'platform' variable later
import shutil
import sys # For sys.exit, sys.executable, sys.maxsize, sys.frozen
import zipfile
# from platform import system # 'system' is already available via 'plat.system()'

# It's good practice to handle potential absence of pip or errors during install
try:
    from pip._internal.cli.main import main as _pip_main
except ImportError:
    print("WARNING: pip._internal.cli.main could not be imported. Dependency installation might fail.")
    _pip_main = None

# Install requirements
if _pip_main:
    try:
        with open('requirements.txt', 'r', encoding='utf-8') as req_file:
            for requirement_line in req_file:
                requirement = requirement_line.strip()
                if requirement and not requirement.startswith('#'): # Skip empty lines and comments
                    print(f"Installing {requirement}...")
                    return_code = _pip_main(['install', requirement])
                    if return_code != 0:
                        print(f"WARNING: pip install for '{requirement}' returned code {return_code}.")
    except FileNotFoundError:
        print("WARNING: requirements.txt not found. Skipping dependency installation.")
    except Exception as e_pip:
        print(f"ERROR during pip dependency installation: {e_pip}. Please ensure pip and setuptools are up-to-date.")
else:
    print("INFO: pip command interface not available. Skipping dependency installation from requirements.txt.")

import re # For version reading

def get_version_from_settings_ini(settings_file_path="bin/setting.ini"):
    """Reads the version from the settings.ini file."""
    try:
        with open(settings_file_path, 'r', encoding='utf-8') as f_settings:
            for line in f_settings:
                if line.strip().startswith("version"): # More robust check
                    match = re.search(r"version\s*=\s*([\w.-]+)", line.strip()) # Use re.search
                    if match:
                        return match.group(1)
    except FileNotFoundError:
        print(f"WARNING: Settings file '{settings_file_path}' not found for version reading.")
    except Exception as e:
        print(f"WARNING: Error reading version from '{settings_file_path}': {e}")
    return "unknown" # Fallback version

current_os_type = plat.system() 
current_machine_arch = plat.machine()

archive_name_prefix = 'MIO-KITCHEN' 
archive_version = get_version_from_settings_ini() 

if archive_version == "unknown":
    print("CRITICAL WARNING: Could not determine application version from settings.ini. Using 'unknown'.")
    # sys.exit(1) # Optionally exit if version is critical

if current_os_type == 'Linux':
    zip_archive_name = f'{archive_name_prefix}-{archive_version}-linux.zip'
elif current_os_type == 'Darwin': 
    if current_machine_arch == 'x86_64':
        zip_archive_name = f'{archive_name_prefix}-{archive_version}-macos-intel.zip'
    else: 
        zip_archive_name = f'{archive_name_prefix}-{archive_version}-macos-arm.zip'
    try:
        import tkinter 
    except ImportError:
        print("CRITICAL ERROR: Tkinter is not installed or not found! The macOS build will likely fail.")
else: 
    zip_archive_name = f'{archive_name_prefix}-{archive_version}-win.zip'

try:
    from src.tool_tester import test_main, Test as TestFlag
    if TestFlag and callable(test_main): 
        print("Running pre-build tests...")
        test_main(exit=False)
except ImportError:
    print("INFO: Test module (src.tool_tester) not found or 'Test' flag not defined. Skipping tests.")
    TestFlag = False


def create_zip_archive(source_folder_to_zip, output_zip_full_path):
    abs_source_folder = os.path.abspath(source_folder_to_zip)
    print(f"Creating ZIP archive: {output_zip_full_path} from folder: {abs_source_folder}")
    try:
        with zipfile.ZipFile(output_zip_full_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for root, dirs, files in os.walk(abs_source_folder):
                if '.git' in dirs:
                    dirs.remove('.git')
                
                for file_item in files:
                    full_file_path = os.path.join(root, file_item)
                    path_in_archive = os.path.relpath(full_file_path, abs_source_folder)
                    # print(f"Adding to ZIP: {path_in_archive}") # Can be too verbose
                    archive.write(full_file_path, path_in_archive)
        print(f"Successfully created ZIP: {output_zip_full_path}")
    except Exception as e_zip_creation:
        print(f"ERROR creating ZIP archive '{output_zip_full_path}': {e_zip_creation}")

project_root_dir = os.getcwd() 
dist_output_dir = os.path.join(project_root_dir, 'dist') 
build_temp_dir = os.path.join(project_root_dir, 'build')

if os.path.isdir(dist_output_dir):
    print(f"Cleaning previous build directory: {dist_output_dir}")
    shutil.rmtree(dist_output_dir, ignore_errors=True)
if os.path.isdir(build_temp_dir):
    print(f"Cleaning previous PyInstaller build temp directory: {build_temp_dir}")
    shutil.rmtree(build_temp_dir, ignore_errors=True)

print("Starting PyInstaller build process...")
try:
    import PyInstaller.__main__
except ImportError:
    print("CRITICAL ERROR: PyInstaller is not installed. Please install it with 'pip install pyinstaller'.")
    sys.exit(1)

pyinstaller_base_args = [
    'tool.py',
    '--noconfirm',
    '--name', archive_name_prefix,
    '--icon', 'icon.ico',
    '--distpath', dist_output_dir,
    '--workpath', build_temp_dir,
    '--clean',
    '--paths', os.path.join(project_root_dir, 'src'), # Tell PyInstaller where 'src' package is
    '--collect-data', 'sv_ttk',
    '--collect-data', 'chlorophyll',
    '--hidden-import', 'tkinter',
    '--hidden-import', 'PIL',
    '--hidden-import', 'PIL.Image',
    '--hidden-import', 'PIL.ImageTk',
    '--hidden-import', 'PIL._tkinter_finder',
    '--hidden-import', 'PIL._imaging',
    '--hidden-import', 'PIL._imagingtk',
    '--hidden-import', 'src.tkui.tool',
    '--hidden-import', 'src.tkui.TkinterDnD',
    '--hidden-import', 'src.tkui.tkinterdnd2_build_in',
    '--hidden-import', 'src.core.utils',
    '--hidden-import', 'src.core.config_parser',
    '--hidden-import', 'src.core.dumper',
    '--hidden-import', 'src.core.Magisk',
    '--hidden-import', 'src.core.addon_register',
    '--hidden-import', 'src.core.cpio',
    '--hidden-import', 'src.core.qsb_imger',
    '--hidden-import', 'src.core.romfs_parse',
    '--hidden-import', 'src.core.unkdz',
    '--hidden-import', 'src.core.imgextractor',
    '--hidden-import', 'src.core.lpunpack',
    '--hidden-import', 'src.core.mkdtboimg',
    '--hidden-import', 'src.core.ozipdecrypt',
    '--hidden-import', 'src.core.splituapp',
    '--hidden-import', 'src.core.ofp_qc_decrypt',
    '--hidden-import', 'src.core.ofp_mtk_decrypt',
    '--hidden-import', 'src.core.opscrypto',
    '--hidden-import', 'src.core.images',
    '--hidden-import', 'src.core.extra',
    '--hidden-import', 'src.core.ext4',
    '--hidden-import', 'src.core.unpac',
    '--hidden-import', 'src.core.undz',
    '--hidden-import', 'src.core.selinux_audit_allow',
    '--hidden-import', 'src.core.pycase',
    '--hidden-import', 'src.core.blockimgdiff',
    '--hidden-import', 'src.core.sparse_img',
    '--hidden-import', 'src.core.update_metadata_pb2',
    '--hidden-import', 'src.tkui.editor',
    '--hidden-import', 'src.tkui.AI_engine',
    '--hidden-import', 'src.tkui.controls',
    '--hidden-import', 'src.tkui.sv_ttk_fixes',
    # Add Pro modules if they exist and are in src/pro
    # '--hidden-import', 'src.pro.sn',
    # '--hidden-import', 'src.pro.active_ui',
    '--exclude-module', 'numpy',
    '--exclude-module', 'matplotlib',
    '--exclude-module', 'scipy',
    '--exclude-module', 'pandas',
]

dndplat_tkdnd_subdir_name = None
if current_os_type == 'Darwin':
    pyinstaller_base_args.append('--windowed')
    if current_machine_arch == 'x86_64':
        dndplat_tkdnd_subdir_name = 'osx-x64'
    elif current_machine_arch == 'arm64':
        dndplat_tkdnd_subdir_name = 'osx-arm64'
elif current_os_type == 'Linux':
    pyinstaller_base_args.append('--windowed')
    pyinstaller_base_args.extend(['--splash', 'splash.png'])
    if current_machine_arch == 'x86_64':
        dndplat_tkdnd_subdir_name = 'linux-x64'
    elif current_machine_arch == 'aarch64':
        dndplat_tkdnd_subdir_name = 'linux-arm64'
    elif current_machine_arch in ['i386', 'i686']:
        dndplat_tkdnd_subdir_name = 'linux-x86'
elif current_os_type == 'Windows':
    pyinstaller_base_args.append('--windowed')
    pyinstaller_base_args.extend(['--splash', 'splash.png'])
    if current_machine_arch == 'AMD64':
        dndplat_tkdnd_subdir_name = 'win-x64'
    elif current_machine_arch == 'ARM64':
        dndplat_tkdnd_subdir_name = 'win-arm64'
    elif '32bit' in plat.architecture()[0] or current_machine_arch.lower() in ['x86', 'i386', 'i686']:
        dndplat_tkdnd_subdir_name = 'win-x86'
    else:
        print(f"WARNING: Unhandled Windows architecture '{current_machine_arch}'. Defaulting tkdnd.")
        dndplat_tkdnd_subdir_name = 'win-x64' if sys.maxsize > 2**32 else 'win-x86'
        print(f"Defaulted tkdnd sub-directory to: {dndplat_tkdnd_subdir_name}")
else:
    print(f"ERROR: Unsupported OS type '{current_os_type}' for PyInstaller build.")
    sys.exit(1)

if not dndplat_tkdnd_subdir_name:
    print("CRITICAL ERROR: Could not determine platform-specific sub-directory for tkdnd. Build aborted.")
    sys.exit(1)

pyinstaller_base_args.append('--onedir') # Build as a folder for easier debugging initially

print(f"Running PyInstaller with arguments: {pyinstaller_base_args}")
try:
    PyInstaller.__main__.run(pyinstaller_base_args)
    print("PyInstaller build process completed.")
except Exception as e_pyinstaller_run:
    print(f"CRITICAL ERROR: PyInstaller execution failed: {e_pyinstaller_run}")
    sys.exit(1)

app_bundle_root_dir = os.path.join(dist_output_dir, archive_name_prefix) 
final_custom_bin_dir = os.path.join(app_bundle_root_dir, 'bin')
if not os.path.exists(final_custom_bin_dir):
    os.makedirs(final_custom_bin_dir, exist_ok=True)

items_to_copy_to_bundle_bin = [
    "images", "languages", "licenses", "module", 
    "extra_flash", "setting.ini", "kemiaojiang.png", 
    "License_kemiaojiang.txt", "tkdnd", "help_document.json", "exec.sh"
]
platform_specific_source_dir = os.path.join(project_root_dir, "bin", current_os_type)
if os.path.isdir(platform_specific_source_dir):
    platform_specific_dest_dir = os.path.join(final_custom_bin_dir, current_os_type)
    print(f"Copying platform-specific binaries from '{platform_specific_source_dir}' to '{platform_specific_dest_dir}'...")
    shutil.copytree(platform_specific_source_dir, platform_specific_dest_dir, dirs_exist_ok=True)
else:
    print(f"Warning: Platform-specific binary source dir '{platform_specific_source_dir}' not found.")

for item_name in items_to_copy_to_bundle_bin:
    source_item_path = os.path.join(project_root_dir, "bin", item_name)
    dest_item_path = os.path.join(final_custom_bin_dir, item_name)
    if os.path.exists(source_item_path):
        try:
            if os.path.isdir(source_item_path):
                # print(f"Copying directory: '{source_item_path}' to '{dest_item_path}'") # Verbose
                shutil.copytree(source_item_path, dest_item_path, dirs_exist_ok=True)
            else: 
                # print(f"Copying file: '{source_item_path}' to '{dest_item_path}'") # Verbose
                shutil.copy2(source_item_path, dest_item_path)
        except Exception as e_file_copy:
            print(f"ERROR copying '{source_item_path}' to '{dest_item_path}': {e_file_copy}")
    # else: # Can be too verbose if some optional files are not present
        # print(f"Warning: Source item '{source_item_path}' not found for copying.")

temp_dir_in_bundle_bin = os.path.join(final_custom_bin_dir, 'temp')
if not os.path.exists(temp_dir_in_bundle_bin):
    os.makedirs(temp_dir_in_bundle_bin, exist_ok=True)

main_license_source = os.path.join(project_root_dir, 'LICENSE')
main_license_dest = os.path.join(app_bundle_root_dir, 'LICENSE')
if os.path.exists(main_license_source):
    try:
        shutil.copy2(main_license_source, main_license_dest)
    except Exception as e_main_license_copy:
        print(f"ERROR copying main LICENSE file: {e_main_license_copy}")
else:
    print(f"Warning: Main LICENSE file '{main_license_source}' not found.")

tkdnd_path_in_bundle_bin = os.path.join(final_custom_bin_dir, 'tkdnd')
if os.path.isdir(tkdnd_path_in_bundle_bin):
    print(f"Filtering tkdnd libraries in '{tkdnd_path_in_bundle_bin}' for platform: {dndplat_tkdnd_subdir_name}")
    found_correct_tkdnd = False
    for item_in_tkdnd_dir in os.listdir(tkdnd_path_in_bundle_bin):
        item_full_path = os.path.join(tkdnd_path_in_bundle_bin, item_in_tkdnd_dir)
        if os.path.isdir(item_full_path): 
            if item_in_tkdnd_dir == dndplat_tkdnd_subdir_name:
                print(f"Keeping correct tkdnd platform folder: {item_full_path}")
                found_correct_tkdnd = True
            else:
                print(f"Removing unused tkdnd platform folder: {item_full_path}")
                shutil.rmtree(item_full_path, ignore_errors=True)
    if not found_correct_tkdnd:
        print(f"WARNING: The specific tkdnd folder '{dndplat_tkdnd_subdir_name}' was not found in '{tkdnd_path_in_bundle_bin}'. Drag and Drop might fail.")
else:
    print(f"WARNING: tkdnd directory '{tkdnd_path_in_bundle_bin}' not found. Drag and Drop will likely fail.")

if current_os_type == 'Linux' or current_os_type == 'Darwin':
    print("Setting execute permissions for specific files in bundle (POSIX)...")
    main_exe_path = os.path.join(app_bundle_root_dir, archive_name_prefix)
    if os.path.exists(main_exe_path):
        try:
            os.chmod(main_exe_path, 0o755) 
            print(f"Set +x on '{main_exe_path}'")
        except Exception as e_chmod_main_exe:
            print(f"Warning: Could not chmod main executable '{main_exe_path}': {e_chmod_main_exe}")
    
    scripts_to_make_executable = ["exec.sh"] 
    for script_filename in scripts_to_make_executable:
        script_full_path = os.path.join(final_custom_bin_dir, script_filename)
        if os.path.isfile(script_full_path):
            try:
                os.chmod(script_full_path, 0o755)
                print(f"Set +x on '{script_full_path}'")
            except Exception as e_chmod_script:
                print(f"Warning: Could not chmod script '{script_full_path}': {e_chmod_script}")

final_zip_output_path = os.path.join(project_root_dir, zip_archive_name)
if os.path.isdir(app_bundle_root_dir): 
    print(f"Zipping the application bundle: {app_bundle_root_dir}")
    try:
        os.chdir(dist_output_dir) 
        create_zip_archive(archive_name_prefix, final_zip_output_path)
    except FileNotFoundError:
        print(f"ERROR: Could not change directory to '{dist_output_dir}' for zipping the bundle.")
    except Exception as e_chdir_zip_bundle:
        print(f"ERROR during zipping of the application bundle: {e_chdir_zip_bundle}")
    finally:
        os.chdir(project_root_dir) 
else:
    print(f"ERROR: Application bundle directory '{app_bundle_root_dir}' not found. Cannot create ZIP.")

print(f"Build process finished. Output archive should be at: {final_zip_output_path}")
