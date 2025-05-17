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
                    # Use a subprocess call for pip install for better isolation and error handling
                    # result = subprocess.run([sys.executable, "-m", "pip", "install", requirement], capture_output=True, text=True)
                    # if result.returncode != 0:
                    #     print(f"ERROR installing {requirement}: {result.stderr}")
                    # else:
                    #     print(f"Successfully installed {requirement}.")
                    # For simplicity, keeping _pip_main if it works for you, but subprocess is more robust.
                    return_code = _pip_main(['install', requirement])
                    if return_code != 0:
                        print(f"WARNING: pip install for '{requirement}' returned code {return_code}.")
    except FileNotFoundError:
        print("WARNING: requirements.txt not found. Skipping dependency installation.")
    except Exception as e_pip:
        print(f"ERROR during pip dependency installation: {e_pip}. Please ensure pip and setuptools are up-to-date.")
else:
    print("INFO: pip command interface not available. Skipping dependency installation from requirements.txt.")


current_os_type = plat.system() # 'Windows', 'Linux', 'Darwin'
current_machine_arch = plat.machine() # e.g., 'AMD64', 'x86_64', 'arm64', 'aarch64'

archive_name_prefix = 'MIO-KITCHEN' # Base name for executable and zip
archive_version = "4.1.0" # Example version, manage this as needed

if current_os_type == 'Linux':
    zip_archive_name = f'{archive_name_prefix}-{archive_version}-linux.zip'
elif current_os_type == 'Darwin': # macOS
    if current_machine_arch == 'x86_64':
        zip_archive_name = f'{archive_name_prefix}-{archive_version}-macos-intel.zip'
    else: # Assuming arm64 (Apple Silicon) or other
        zip_archive_name = f'{archive_name_prefix}-{archive_version}-macos-arm.zip'
    try:
        import tkinter # Early check for Tkinter on macOS
    except ImportError:
        print("CRITICAL ERROR: Tkinter is not installed or not found! The macOS build will likely fail.")
        # sys.exit(1) # Consider exiting if Tkinter is essential
else: # Default to Windows
    zip_archive_name = f'{archive_name_prefix}-{archive_version}-win.zip'

# --- Test Suite (Optional) ---
try:
    from src.tool_tester import test_main, Test as TestFlag
    if TestFlag and callable(test_main): # Check if TestFlag is True and test_main is callable
        print("Running pre-build tests...")
        test_main(exit=False)
except ImportError:
    print("INFO: Test module (src.tool_tester) not found or 'Test' flag not defined. Skipping tests.")
    TestFlag = False


def create_zip_archive(source_folder_to_zip, output_zip_full_path):
    """
    Zips the contents of the source_folder_to_zip into output_zip_full_path.
    The paths inside the zip will be relative to source_folder_to_zip.
    """
    abs_source_folder = os.path.abspath(source_folder_to_zip)
    print(f"Creating ZIP archive: {output_zip_full_path} from folder: {abs_source_folder}")
    try:
        with zipfile.ZipFile(output_zip_full_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for root, dirs, files in os.walk(abs_source_folder):
                # Exclude .git from being added to the zip
                if '.git' in dirs:
                    dirs.remove('.git')
                
                for file_item in files:
                    full_file_path = os.path.join(root, file_item)
                    # Path inside the ZIP, relative to the source_folder_to_zip
                    path_in_archive = os.path.relpath(full_file_path, abs_source_folder)
                    print(f"Adding to ZIP: {path_in_archive}")
                    archive.write(full_file_path, path_in_archive)
        print(f"Successfully created ZIP: {output_zip_full_path}")
    except Exception as e_zip_creation:
        print(f"ERROR creating ZIP archive '{output_zip_full_path}': {e_zip_creation}")

# --- PyInstaller Build Configuration ---
project_root_dir = os.getcwd() # Assuming build.py is at the project root
dist_output_dir = os.path.join(project_root_dir, 'dist') # Standard PyInstaller output
final_app_dir_in_dist = os.path.join(dist_output_dir, archive_name_prefix) # e.g., dist/MIO-KITCHEN (for one-dir)

# Clean previous build (optional, but recommended)
if os.path.isdir(dist_output_dir):
    print(f"Cleaning previous build directory: {dist_output_dir}")
    shutil.rmtree(dist_output_dir, ignore_errors=True)
build_temp_dir = os.path.join(project_root_dir, 'build')
if os.path.isdir(build_temp_dir):
    print(f"Cleaning previous PyInstaller build temp directory: {build_temp_dir}")
    shutil.rmtree(build_temp_dir, ignore_errors=True)


print("Starting PyInstaller build process...")
try:
    import PyInstaller.__main__
except ImportError:
    print("CRITICAL ERROR: PyInstaller is not installed. Please install it with 'pip install pyinstaller'.")
    sys.exit(1)

# Common PyInstaller arguments
# We will build as one-folder ('-D' or default) first for easier debugging of tkdnd,
# then you can switch to one-file ('-F') if tkdnd works correctly.
# One-file can sometimes make path resolution for external Tcl libraries harder.
pyinstaller_base_args = [
    'tool.py',
    '--noconfirm',         # Overwrite output without asking
    '--name', archive_name_prefix,
    '--icon', 'icon.ico',
    '--distpath', dist_output_dir, # Output to 'dist/'
    '--workpath', build_temp_dir,  # Temporary build files to 'build/'
    # '--onedir',  # Build as a directory (one-dir) - RECOMMENDED FOR DEBUGGING TKDND
                      # If you must use one-file, change to '--onefile' later
    '--collect-data', 'sv_ttk',
    '--collect-data', 'chlorophyll',
    # Hidden imports crucial for Pillow and Tkinter integration
    '--hidden-import', 'tkinter',
    '--hidden-import', 'PIL',
    '--hidden-import', 'PIL.Image',       # Explicitly include PIL.Image
    '--hidden-import', 'PIL.ImageTk',
    '--hidden-import', 'PIL._tkinter_finder',
    '--hidden-import', 'PIL._imaging',    # Core C extension
    '--hidden-import', 'PIL._imagingtk',  # Tkinter display support
    '--exclude-module', 'numpy',
    '--exclude-module', 'matplotlib', # Example of another large library you might not need
    '--exclude-module', 'scipy',
    '--exclude-module', 'pandas',
    # Consider adding '--clean' to clear PyInstaller cache before build
    '--clean',
]

# Platform-specific arguments for PyInstaller
dndplat_tkdnd_subdir_name = None  # This will be like 'win-x64', 'linux-x64', etc.

if current_os_type == 'Darwin': # macOS
    pyinstaller_base_args.append('--windowed') # Creates a .app bundle
    if current_machine_arch == 'x86_64':
        dndplat_tkdnd_subdir_name = 'osx-x64'
    elif current_machine_arch == 'arm64':
        dndplat_tkdnd_subdir_name = 'osx-arm64'
    # Add macOS specific options if needed, e.g., bundle identifier
    # pyinstaller_base_args.extend(['--osx-bundle-identifier', 'com.yourdomain.miokitchen'])

elif current_os_type == 'Linux':
    pyinstaller_base_args.append('--windowed') # Typically for windowed apps
    pyinstaller_base_args.extend(['--splash', 'splash.png'])
    if current_machine_arch == 'x86_64':
        dndplat_tkdnd_subdir_name = 'linux-x64'
    elif current_machine_arch == 'aarch64': # Common for ARM Linux (e.g. Raspberry Pi 64-bit)
        dndplat_tkdnd_subdir_name = 'linux-arm64'
    # For 32-bit Linux (less common now)
    elif current_machine_arch in ['i386', 'i686']:
        dndplat_tkdnd_subdir_name = 'linux-x86' # Assuming your tkdnd has this structure

elif current_os_type == 'Windows':
    pyinstaller_base_args.append('--windowed') # No console window
    pyinstaller_base_args.extend(['--splash', 'splash.png'])
    
    if current_machine_arch == 'AMD64': # Standard 64-bit Windows
        dndplat_tkdnd_subdir_name = 'win-x64'
    elif current_machine_arch == 'ARM64':
        dndplat_tkdnd_subdir_name = 'win-arm64'
    # For 32-bit Windows, platform.machine() might be 'x86' or 'IA32' or 'i386' etc.
    # platform.architecture()[0] is more reliable for '32bit' vs '64bit'
    elif '32bit' in plat.architecture()[0] or current_machine_arch.lower() in ['x86', 'i386', 'i686']:
        dndplat_tkdnd_subdir_name = 'win-x86'
    else:
        print(f"WARNING: Unhandled Windows architecture '{current_machine_arch}'. Trying a default for tkdnd.")
        dndplat_tkdnd_subdir_name = 'win-x64' if sys.maxsize > 2**32 else 'win-x86' # Default based on Python's bitness
        print(f"Defaulted tkdnd sub-directory to: {dndplat_tkdnd_subdir_name}")
else:
    print(f"ERROR: Unsupported OS type '{current_os_type}' for PyInstaller build.")
    sys.exit(1)

if not dndplat_tkdnd_subdir_name:
    print("CRITICAL ERROR: Could not determine the platform-specific sub-directory for tkdnd. Build aborted.")
    sys.exit(1)

# Add one-file or one-dir option LAST
# For debugging TkDnD, one-dir is often easier. Switch to --onefile for final release.
# pyinstaller_base_args.append('--onefile') # For one-file executable
pyinstaller_base_args.append('--onedir')  # For one-folder bundle

print(f"Running PyInstaller with arguments: {pyinstaller_base_args}")
try:
    PyInstaller.__main__.run(pyinstaller_base_args)
    print("PyInstaller build process completed.")
except Exception as e_pyinstaller_run:
    print(f"CRITICAL ERROR: PyInstaller execution failed: {e_pyinstaller_run}")
    sys.exit(1)

# --- Post-build: Copying additional data and filtering tkdnd ---

# Path to the directory created by PyInstaller (e.g., dist/MIO-KITCHEN if one-dir)
# If one-file, the actual executable is dist/MIO-KITCHEN.exe (or similar)
# and data files need to be placed relative to where the user runs it from,
# or handled via sys._MEIPASS at runtime if collected by PyInstaller.
# Since we're now assuming one-dir for easier tkdnd, this is dist/MIO-KITCHEN/
app_bundle_root_dir = os.path.join(dist_output_dir, archive_name_prefix) 

# Target for our 'bin' folder *inside* the app bundle
final_custom_bin_dir = os.path.join(app_bundle_root_dir, 'bin')
if not os.path.exists(final_custom_bin_dir):
    os.makedirs(final_custom_bin_dir, exist_ok=True)

# Files and folders to copy from 'project_root_dir/bin' to 'app_bundle_root_dir/bin'
items_to_copy_to_bundle_bin = [
    "images", "languages", "licenses", "module", 
    "extra_flash", "setting.ini", "kemiaojiang.png", 
    "License_kemiaojiang.txt", "tkdnd", "help_document.json", "exec.sh"
]
# Also copy platform-specific binaries from 'project_root_dir/bin/<ostype>'
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
                print(f"Copying directory: '{source_item_path}' to '{dest_item_path}'")
                shutil.copytree(source_item_path, dest_item_path, dirs_exist_ok=True)
            else: # It's a file
                print(f"Copying file: '{source_item_path}' to '{dest_item_path}'")
                shutil.copy2(source_item_path, dest_item_path)
        except Exception as e_file_copy:
            print(f"ERROR copying '{source_item_path}' to '{dest_item_path}': {e_file_copy}")
    else:
        print(f"Warning: Source item '{source_item_path}' not found for copying.")

# Create 'temp' directory structure if needed (usually runtime generated, but if structure is important)
temp_dir_in_bundle_bin = os.path.join(final_custom_bin_dir, 'temp')
if not os.path.exists(temp_dir_in_bundle_bin):
    os.makedirs(temp_dir_in_bundle_bin, exist_ok=True)
    print(f"Ensured 'temp' directory exists at: {temp_dir_in_bundle_bin}")

# Copy main LICENSE file to the root of the app bundle
main_license_source = os.path.join(project_root_dir, 'LICENSE')
main_license_dest = os.path.join(app_bundle_root_dir, 'LICENSE')
if os.path.exists(main_license_source):
    try:
        print(f"Copying '{main_license_source}' to '{main_license_dest}'")
        shutil.copy2(main_license_source, main_license_dest)
    except Exception as e_main_license_copy:
        print(f"ERROR copying main LICENSE file: {e_main_license_copy}")
else:
    print(f"Warning: Main LICENSE file '{main_license_source}' not found.")


# Filter tkdnd libraries within 'app_bundle_root_dir/bin/tkdnd'
tkdnd_path_in_bundle_bin = os.path.join(final_custom_bin_dir, 'tkdnd')
if os.path.isdir(tkdnd_path_in_bundle_bin):
    print(f"Filtering tkdnd libraries in '{tkdnd_path_in_bundle_bin}' for platform: {dndplat_tkdnd_subdir_name}")
    found_correct_tkdnd = False
    for item_in_tkdnd_dir in os.listdir(tkdnd_path_in_bundle_bin):
        item_full_path = os.path.join(tkdnd_path_in_bundle_bin, item_in_tkdnd_dir)
        if os.path.isdir(item_full_path): # We are interested in platform subdirectories
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


# POSIX: Set execute permissions
if current_os_type == 'Linux' or current_os_type == 'Darwin':
    print("Setting execute permissions for specific files in bundle (POSIX)...")
    # Main executable (its name is archive_name_prefix)
    main_exe_path = os.path.join(app_bundle_root_dir, archive_name_prefix)
    if os.path.exists(main_exe_path):
        try:
            os.chmod(main_exe_path, 0o755) # rwxr-xr-x
            print(f"Set +x on '{main_exe_path}'")
        except Exception as e_chmod_main_exe:
            print(f"Warning: Could not chmod main executable '{main_exe_path}': {e_chmod_main_exe}")
    
    # Scripts like exec.sh in 'app_bundle_root_dir/bin/'
    scripts_to_make_executable = ["exec.sh"] # Add others if needed
    for script_filename in scripts_to_make_executable:
        script_full_path = os.path.join(final_custom_bin_dir, script_filename)
        if os.path.isfile(script_full_path):
            try:
                os.chmod(script_full_path, 0o755)
                print(f"Set +x on '{script_full_path}'")
            except Exception as e_chmod_script:
                print(f"Warning: Could not chmod script '{script_full_path}': {e_chmod_script}")

# --- Create final ZIP archive ---
# The ZIP will contain the 'app_bundle_root_dir' (e.g., 'dist/MIO-KITCHEN')
final_zip_output_path = os.path.join(project_root_dir, zip_archive_name)

# We want to zip the 'MIO-KITCHEN' folder itself, not its contents directly into the root of the zip.
# So, the source_folder_to_zip should be 'dist', and inside the zip, we'll have 'MIO-KITCHEN/...'
# Or, more simply, zip the 'app_bundle_root_dir' directly.
# Let's zip the 'app_bundle_root_dir' such that its name is the root inside the zip.
# To do this, we can temporarily chdir into 'dist' and zip 'MIO-KITCHEN' folder.

if os.path.isdir(app_bundle_root_dir): # e.g. dist/MIO-KITCHEN
    print(f"Zipping the application bundle: {app_bundle_root_dir}")
    try:
        # To get 'MIO-KITCHEN/...' inside the zip, we chdir to 'dist'
        # and then zip the 'MIO-KITCHEN' folder.
        os.chdir(dist_output_dir) # Go into 'dist'
        # Now zip 'archive_name_prefix' (which is 'MIO-KITCHEN')
        create_zip_archive(archive_name_prefix, final_zip_output_path)
    except FileNotFoundError:
        print(f"ERROR: Could not change directory to '{dist_output_dir}' for zipping the bundle.")
    except Exception as e_chdir_zip_bundle:
        print(f"ERROR during zipping of the application bundle: {e_chdir_zip_bundle}")
    finally:
        os.chdir(project_root_dir) # Always change back to the original project root directory
else:
    print(f"ERROR: Application bundle directory '{app_bundle_root_dir}' not found. Cannot create ZIP.")

print(f"Build process finished. Output archive should be at: {final_zip_output_path}")
