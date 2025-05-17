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
import platform as plat 
import shutil
import sys 
import zipfile
import re # For reading version from ini

# --- Configuration ---
APP_NAME_PREFIX = 'MIO-KITCHEN'
PROJECT_ROOT_DIR = os.getcwd() # Assumes build.py is in the project root
DIST_OUTPUT_DIR = os.path.join(PROJECT_ROOT_DIR, 'dist')
BUILD_TEMP_DIR = os.path.join(PROJECT_ROOT_DIR, 'build')
SETTINGS_INI_PATH = os.path.join(PROJECT_ROOT_DIR, "bin", "setting.ini")
ICON_PATH = os.path.join(PROJECT_ROOT_DIR, "icon.ico")
SPLASH_PATH = os.path.join(PROJECT_ROOT_DIR, "splash.png")
REQUIREMENTS_PATH = os.path.join(PROJECT_ROOT_DIR, "requirements.txt")
MAIN_SCRIPT_NAME = "tool.py" # Entry point script at project root

# --- Helper Functions ---
def get_version_from_settings_ini(settings_file_path=SETTINGS_INI_PATH):
    """Reads the version from the settings.ini file."""
    try:
        with open(settings_file_path, 'r', encoding='utf-8') as f_settings:
            for line in f_settings:
                if line.strip().lower().startswith("version"): # Case-insensitive check for "version"
                    match = re.search(r"version\s*=\s*([\w.-]+)", line.strip(), re.IGNORECASE)
                    if match:
                        return match.group(1)
        print(f"WARNING: 'version' key not found or malformed in '{settings_file_path}'.")
    except FileNotFoundError:
        print(f"WARNING: Settings file '{settings_file_path}' not found for version reading.")
    except Exception as e:
        print(f"WARNING: Error reading version from '{settings_file_path}': {e}")
    return "0.0.0-unknown" # Fallback version

def install_requirements(requirements_file_path=REQUIREMENTS_PATH):
    """Installs dependencies from requirements.txt using pip internal API."""
    try:
        from pip._internal.cli.main import main as _pip_main
    except ImportError:
        print("WARNING: pip._internal.cli.main could not be imported. Cannot install dependencies.")
        return

    if not os.path.isfile(requirements_file_path):
        print(f"WARNING: '{requirements_file_path}' not found. Skipping dependency installation.")
        return

    print(f"Installing dependencies from '{requirements_file_path}'...")
    try:
        with open(requirements_file_path, 'r', encoding='utf-8') as req_file:
            for requirement_line in req_file:
                requirement = requirement_line.strip()
                if requirement and not requirement.startswith('#'):
                    print(f"  Installing: {requirement}")
                    return_code = _pip_main(['install', requirement])
                    if return_code != 0:
                        print(f"  WARNING: pip install for '{requirement}' failed with code {return_code}.")
        print("Dependency installation complete.")
    except Exception as e_pip:
        print(f"ERROR during pip dependency installation: {e_pip}.")

def create_zip_archive(source_folder_to_zip, output_zip_full_path):
    """Zips the contents of source_folder_to_zip into output_zip_full_path."""
    abs_source_folder = os.path.abspath(source_folder_to_zip)
    print(f"Creating ZIP archive: '{output_zip_full_path}' from folder: '{abs_source_folder}'")
    try:
        with zipfile.ZipFile(output_zip_full_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for root, dirs, files in os.walk(abs_source_folder):
                if '.git' in dirs: dirs.remove('.git') # Don't zip .git
                
                for file_item in files:
                    full_file_path = os.path.join(root, file_item)
                    path_in_archive = os.path.relpath(full_file_path, abs_source_folder)
                    archive.write(full_file_path, path_in_archive)
        print(f"Successfully created ZIP: '{output_zip_full_path}'")
    except Exception as e_zip_creation:
        print(f"ERROR creating ZIP archive '{output_zip_full_path}': {e_zip_creation}")

# --- Main Build Logic ---
if __name__ == "__main__":
    # 1. Install Dependencies
    install_requirements()

    # 2. Determine Version and OS/Arch specifics
    app_version = get_version_from_settings_ini()
    if app_version == "0.0.0-unknown":
        print("CRITICAL WARNING: Application version could not be determined. Build might be incorrectly named.")
        # sys.exit(1) # Optionally exit

    current_os_type = plat.system()
    current_machine_arch = plat.machine()
    
    os_suffix_map = {'Windows': 'win', 'Linux': 'linux', 'Darwin': 'macos'}
    os_zip_suffix = os_suffix_map.get(current_os_type, 'unknownOS')

    if current_os_type == 'Darwin': # macOS needs arch differentiation
        os_zip_suffix = f"macos-{current_machine_arch == 'x86_64' and 'intel' or 'arm'}"
    
    final_zip_name = f"{APP_NAME_PREFIX}-{app_version}-{os_zip_suffix}.zip"
    final_zip_full_path = os.path.join(PROJECT_ROOT_DIR, final_zip_name)

    # 3. Clean previous builds
    if os.path.isdir(DIST_OUTPUT_DIR):
        print(f"Cleaning previous dist directory: {DIST_OUTPUT_DIR}")
        shutil.rmtree(DIST_OUTPUT_DIR, ignore_errors=True)
    if os.path.isdir(BUILD_TEMP_DIR):
        print(f"Cleaning previous build temp directory: {BUILD_TEMP_DIR}")
        shutil.rmtree(BUILD_TEMP_DIR, ignore_errors=True)
    os.makedirs(DIST_OUTPUT_DIR, exist_ok=True)


    # 4. PyInstaller Configuration
    print("Starting PyInstaller build process...")
    try:
        import PyInstaller.__main__
    except ImportError:
        print("CRITICAL ERROR: PyInstaller is not installed. Please install it (e.g., 'pip install pyinstaller').")
        sys.exit(1)

    pyinstaller_args = [
        os.path.join(PROJECT_ROOT_DIR, MAIN_SCRIPT_NAME),
        '--noconfirm',
        '--name', APP_NAME_PREFIX,
        '--icon', ICON_PATH,
        '--distpath', DIST_OUTPUT_DIR,
        '--workpath', BUILD_TEMP_DIR,
        '--clean',
        '--paths', os.path.join(PROJECT_ROOT_DIR, 'src'),
        '--collect-data', 'sv_ttk',
        '--collect-data', 'chlorophyll',
        # Essential hidden imports
        '--hidden-import', 'tkinter',
        '--hidden-import', 'PIL',
        '--hidden-import', 'PIL.Image',
        '--hidden-import', 'PIL.ImageTk',
        '--hidden-import', 'PIL._tkinter_finder',
        '--hidden-import', 'PIL._imaging',
        '--hidden-import', 'PIL._imagingtk',
        # Your project's modules from 'src'
        '--hidden-import', 'src.tkui.tool',
        '--hidden-import', 'src.tkui.TkinterDnD',
        '--hidden-import', 'src.tkui.tkinterdnd2_build_in',
        '--hidden-import', 'src.core.utils',
        '--hidden-import', 'src.core.config_parser',
        # Add ALL other modules from src.core and src.tkui that are directly or indirectly imported
        # Example:
        '--hidden-import', 'src.tkui.editor',
        '--hidden-import', 'src.tkui.AI_engine',
        '--hidden-import', 'src.tkui.controls',
        '--hidden-import', 'src.tkui.sv_ttk_fixes',
        '--hidden-import', 'src.core.dumper',
        '--hidden-import', 'src.core.Magisk',
        '--hidden-import', 'src.core.addon_register',
        # ... list all of them to be safe ...
        '--exclude-module', 'numpy',
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'scipy',
        '--exclude-module', 'pandas',
    ]

    dndplat_tkdnd_subdir_name = None
    if current_os_type == 'Darwin':
        pyinstaller_args.append('--windowed')
        if current_machine_arch == 'x86_64': dndplat_tkdnd_subdir_name = 'osx-x64'
        elif current_machine_arch == 'arm64': dndplat_tkdnd_subdir_name = 'osx-arm64'
    elif current_os_type == 'Linux':
        pyinstaller_args.append('--windowed')
        if os.path.exists(SPLASH_PATH): pyinstaller_args.extend(['--splash', SPLASH_PATH])
        if current_machine_arch == 'x86_64': dndplat_tkdnd_subdir_name = 'linux-x64'
        elif current_machine_arch == 'aarch64': dndplat_tkdnd_subdir_name = 'linux-arm64'
        elif current_machine_arch in ['i386', 'i686']: dndplat_tkdnd_subdir_name = 'linux-x86'
    elif current_os_type == 'Windows':
        pyinstaller_args.append('--windowed')
        if os.path.exists(SPLASH_PATH): pyinstaller_args.extend(['--splash', SPLASH_PATH])
        if current_machine_arch == 'AMD64': dndplat_tkdnd_subdir_name = 'win-x64'
        elif current_machine_arch == 'ARM64': dndplat_tkdnd_subdir_name = 'win-arm64'
        elif '32bit' in plat.architecture()[0] or current_machine_arch.lower() in ['x86', 'i386', 'i686']:
            dndplat_tkdnd_subdir_name = 'win-x86'
        else:
            print(f"WARNING: Unhandled Windows architecture '{current_machine_arch}'.")
            dndplat_tkdnd_subdir_name = 'win-x64' if sys.maxsize > 2**32 else 'win-x86'
            print(f"Defaulted tkdnd sub-directory to: {dndplat_tkdnd_subdir_name}")
    
    if not dndplat_tkdnd_subdir_name:
        print("CRITICAL ERROR: Could not determine platform-specific sub-directory for tkdnd. Build aborted.")
        sys.exit(1)

    pyinstaller_args.append('--onedir') # Build as a folder (recommended for complex apps and debugging)
    # To build as one file, change to: pyinstaller_args.append('--onefile')

    print(f"Running PyInstaller with arguments: {' '.join(pyinstaller_args)}")
    try:
        PyInstaller.__main__.run(pyinstaller_args)
        print("PyInstaller build process completed.")
    except SystemExit as e_pyi_exit: # PyInstaller often exits with SystemExit
        if e_pyi_exit.code != 0:
            print(f"CRITICAL ERROR: PyInstaller execution failed with exit code {e_pyi_exit.code}.")
            sys.exit(e_pyi_exit.code)
        else:
            print("PyInstaller finished (likely successfully, code 0).")
    except Exception as e_pyinstaller_run:
        print(f"CRITICAL ERROR: PyInstaller execution failed: {e_pyinstaller_run}")
        sys.exit(1)

    # 5. Post-build: Copying additional data
    app_bundle_output_dir = os.path.join(DIST_OUTPUT_DIR, APP_NAME_PREFIX) # e.g., dist/MIO-KITCHEN/
    
    if not os.path.isdir(app_bundle_output_dir):
        print(f"ERROR: PyInstaller output directory not found: {app_bundle_output_dir}")
        sys.exit(1)

    final_custom_bin_dir_in_bundle = os.path.join(app_bundle_output_dir, 'bin')
    if not os.path.exists(final_custom_bin_dir_in_bundle):
        os.makedirs(final_custom_bin_dir_in_bundle, exist_ok=True)

    items_to_copy_to_bundle_bin = [
        "images", "languages", "licenses", "module", "extra_flash", "setting.ini", 
        "kemiaojiang.png", "License_kemiaojiang.txt", "tkdnd", 
        "help_document.json", "exec.sh"
    ]
    # Copy platform-specific binaries from 'PROJECT_ROOT_DIR/bin/<ostype>'
    platform_bin_source = os.path.join(PROJECT_ROOT_DIR, "bin", current_os_type)
    if os.path.isdir(platform_bin_source):
        platform_bin_dest = os.path.join(final_custom_bin_dir_in_bundle, current_os_type)
        print(f"Copying platform binaries: '{platform_bin_source}' -> '{platform_bin_dest}'")
        shutil.copytree(platform_bin_source, platform_bin_dest, dirs_exist_ok=True)
    else:
        print(f"Warning: Platform binary source dir '{platform_bin_source}' not found.")

    for item_name in items_to_copy_to_bundle_bin:
        source_path = os.path.join(PROJECT_ROOT_DIR, "bin", item_name)
        dest_path = os.path.join(final_custom_bin_dir_in_bundle, item_name)
        if os.path.exists(source_path):
            try:
                if os.path.isdir(source_path):
                    shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(source_path, dest_path)
            except Exception as e_copy:
                print(f"ERROR copying '{source_path}' to '{dest_path}': {e_copy}")
        # else: print(f"Info: Source item '{source_path}' not found for copying (optional?).")

    temp_dir_in_bundle = os.path.join(final_custom_bin_dir_in_bundle, 'temp')
    if not os.path.exists(temp_dir_in_bundle):
        os.makedirs(temp_dir_in_bundle, exist_ok=True)

    main_license_src = os.path.join(PROJECT_ROOT_DIR, 'LICENSE')
    main_license_dst = os.path.join(app_bundle_output_dir, 'LICENSE')
    if os.path.isfile(main_license_src):
        shutil.copy2(main_license_src, main_license_dst)
    else:
        print(f"Warning: Main LICENSE file '{main_license_src}' not found.")

    # Filter tkdnd libraries
    tkdnd_final_path = os.path.join(final_custom_bin_dir_in_bundle, 'tkdnd')
    if os.path.isdir(tkdnd_final_path):
        print(f"Filtering tkdnd libraries in '{tkdnd_final_path}' for platform: {dndplat_tkdnd_subdir_name}")
        for item in os.listdir(tkdnd_final_path):
            item_full_path = os.path.join(tkdnd_final_path, item)
            if os.path.isdir(item_full_path) and item != dndplat_tkdnd_subdir_name:
                print(f"Removing unused tkdnd platform folder: {item_full_path}")
                shutil.rmtree(item_full_path, ignore_errors=True)
    else:
        print(f"WARNING: tkdnd directory '{tkdnd_final_path}' not found after copying. Drag & Drop will fail.")

    # POSIX: Set execute permissions
    if current_os_type in ['Linux', 'Darwin']:
        print("Setting execute permissions for specific files in bundle (POSIX)...")
        main_executable_path = os.path.join(app_bundle_output_dir, APP_NAME_PREFIX)
        if os.path.isfile(main_executable_path): # Check if it's a file (not a dir like .app)
            try: os.chmod(main_executable_path, 0o755)
            except Exception as e: print(f"Warning: chmod failed for '{main_executable_path}': {e}")
        
        # For macOS .app bundle, the executable is inside
        if current_os_type == 'Darwin' and os.path.isdir(f"{main_executable_path}.app"):
            macos_exe_path = os.path.join(f"{main_executable_path}.app", "Contents", "MacOS", APP_NAME_PREFIX)
            if os.path.isfile(macos_exe_path):
                try: os.chmod(macos_exe_path, 0o755)
                except Exception as e: print(f"Warning: chmod failed for macOS bundle exe '{macos_exe_path}': {e}")
        
        scripts_to_chmod = [os.path.join(final_custom_bin_dir_in_bundle, "exec.sh")]
        for script_p in scripts_to_chmod:
            if os.path.isfile(script_p):
                try: os.chmod(script_p, 0o755)
                except Exception as e: print(f"Warning: chmod failed for script '{script_p}': {e}")
    
    # 6. Create final ZIP archive
    print(f"Preparing to create ZIP archive: {final_zip_full_path}")
    if os.path.isdir(app_bundle_output_dir):
        try:
            os.chdir(DIST_OUTPUT_DIR) # Go into 'dist'
            create_zip_archive(APP_NAME_PREFIX, final_zip_full_path) # Zip 'MIO-KITCHEN' folder
        except FileNotFoundError:
            print(f"ERROR: Could not change directory to '{DIST_OUTPUT_DIR}' for zipping.")
        except Exception as e_zip:
            print(f"ERROR during final zipping stage: {e_zip}")
        finally:
            os.chdir(PROJECT_ROOT_DIR) # Always change back
    else:
        print(f"ERROR: Application bundle directory '{app_bundle_output_dir}' not found. Cannot create ZIP.")

    print(f"Build process finished. Output archive: {final_zip_full_path}")
