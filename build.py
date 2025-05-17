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
import platform
import shutil
import zipfile
from platform import system # 'machine' is not directly imported, use platform.machine()

from pip._internal.cli.main import main as _main # For installing requirements

# Install requirements
try:
    with open('requirements.txt', 'r', encoding='utf-8') as l:
        for i in l.read().split("\n"):
            if i and not i.startswith('#'): # Skip empty lines and comments
                print(f"Installing {i}...")
                _main(['install', i])
except FileNotFoundError:
    print("WARNING: requirements.txt not found. Skipping dependency installation.")
except Exception as e_pip:
    print(f"ERROR during pip install: {e_pip}. Please ensure pip and setuptools are up-to-date.")

ostype = system()
archive_name_prefix = 'MIO-KITCHEN'
if ostype == 'Linux':
    name = f'{archive_name_prefix}-linux.zip'
elif ostype == 'Darwin':
    if platform.machine() == 'x86_64':
        name = f'{archive_name_prefix}-macos-intel.zip'
    else: # Assuming arm64 or other non-intel
        name = f'{archive_name_prefix}-macos.zip'
    # Check for Tkinter early if building for macOS, as it's a common issue
    try:
        import tkinter
    except ImportError:
        print("CRITICAL ERROR: Tkinter is not installed or not found! The build will likely fail for macOS.")
        # Consider exiting here if Tkinter is absolutely essential for macOS build steps
        # sys.exit(1) 
else: # Default to Windows
    name = f'{archive_name_prefix}-win.zip'

# Attempt to import test components carefully
try:
    from src.tool_tester import test_main, Test
    # Run tests if Test flag is True
    if Test and callable(test_main):
        print("Running pre-build tests...")
        test_main(exit=False) # Assuming test_main handles its own output
except ImportError:
    print("INFO: Test module (src.tool_tester) not found. Skipping tests.")
    Test = False # Ensure Test is False if module not found

def zip_folder(folder_path, output_zip_name):
    abs_folder_path = os.path.abspath(folder_path)
    # Ensure the output directory for the zip exists (local current dir in this case)
    # output_zip_path = os.path.join(os.getcwd(), output_zip_name) # If zip in current dir
    output_zip_path = output_zip_name # Assuming output_zip_name can be a full path or relative

    print(f"Creating ZIP archive: {output_zip_path}")
    try:
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for root, dirs, files in os.walk(abs_folder_path):
                # Exclude .git directory from being walked or added
                if '.git' in dirs:
                    dirs.remove('.git') 
                
                for file in files:
                    if file == os.path.basename(output_zip_path): # Avoid zipping itself if in the same dir
                        continue
                    
                    file_path = os.path.join(root, file)
                    # Path inside the ZIP, relative to the folder_path being zipped
                    archive_name = os.path.relpath(file_path, abs_folder_path)
                    print(f"Adding to ZIP: {archive_name}")
                    archive.write(file_path, archive_name)
        print(f"Successfully created ZIP: {output_zip_path}")
    except Exception as e_zip:
        print(f"ERROR creating ZIP archive: {e_zip}")


local_base_path = os.getcwd() # Store the original current working directory
print("Starting PyInstaller build process...")

try:
    import PyInstaller.__main__
except ImportError:
    print("CRITICAL ERROR: PyInstaller is not installed. Please install it with 'pip install pyinstaller'.")
    sys.exit(1) # Exit if PyInstaller is not found

# Common PyInstaller arguments
common_args = [
    'tool.py',         # Entry point script
    '--noconfirm',     # Overwrite output without asking
    '-F',              # Create a one-file bundled executable
    # '-w',            # Windowed (no console) - Handled per platform below
    '--name', archive_name_prefix, # Name of the executable
    '--icon', 'icon.ico', # Application icon
    '--exclude-module', 'numpy',
    '--collect-data', 'sv_ttk',
    '--collect-data', 'chlorophyll',
    # --- Hidden imports for Tkinter and Pillow ---
    '--hidden-import', 'tkinter',
    '--hidden-import', 'PIL',             # Ensures PIL (Pillow) itself is found
    '--hidden-import', 'PIL._tkinter_finder', # For Tkinter PhotoImage compatibility
    '--hidden-import', 'PIL._imaging',    # Core C extension for Pillow <--- ADDED
    '--hidden-import', 'PIL.ImageTk',     # Often needed explicitly for PhotoImage <--- ADDED
    '--hidden-import', 'PIL._imagingtk',  # For Tkinter integration <--- ADDED
    # Add other specific Pillow modules if still issues, e.g., PIL.PngImagePlugin
    # '--copy-metadata', 'Pillow', # May help PyInstaller find Pillow's own data
]

# Platform-specific PyInstaller arguments and dndplat determination
dndplat = None # For tkdnd library path selection

if ostype == 'Darwin': # macOS
    common_args.append('-w') # Windowed application
    if platform.machine() == 'x86_64':
        dndplat = 'osx-x64'
    elif platform.machine() == 'arm64':
        dndplat = 'osx-arm64'
    # macOS specific PyInstaller args if any can be added here
    # For example, to handle .app bundles, entitlements, etc.
    # common_args.extend(['--osx-bundle-identifier', 'com.yourcompany.miokitchen'])

elif ostype == 'Linux':
    common_args.append('-w') # Typically creates a windowed app, console might still appear briefly
    common_args.extend(['--splash', 'splash.png']) # Splash screen for Linux
    if platform.machine() == 'x86_64':
        dndplat = 'linux-x64'
    elif platform.machine() == 'aarch64':
        dndplat = 'linux-arm64'
    # Add any Linux specific libraries if needed, e.g., via --add-binary

elif ostype == 'Windows': # For Windows (os.name == 'nt')
    common_args.append('--windowed') # Correct flag for no console on Windows
    common_args.extend(['--splash', 'splash.png']) # Splash screen for Windows

    # Handle platform.machine() for Windows architecture correctly
    # The original lambda override for platform.machine() is a bit unusual.
    # It's generally better to rely on standard platform.machine() or sys.getwindowsversion()
    # if absolutely necessary, but PyInstaller usually handles architecture well.
    # For simplicity, let's use platform.machine() directly.
    current_machine = platform.machine()
    if current_machine == 'x86': # Though 'x86' is uncommon for platform.machine()
        dndplat = 'win-x86'
    elif current_machine == 'AMD64': # Standard for 64-bit Windows
        dndplat = 'win-x64'
    elif current_machine == 'ARM64':
        dndplat = 'win-arm64'
    else: # Fallback or if platform.machine() returns something like 'i386' for 32-bit
        if '32bit' in platform.architecture()[0]:
            dndplat = 'win-x86'
        else: # Default to x64 if unsure
            dndplat = 'win-x64'
            print(f"Warning: Unhandled Windows architecture '{current_machine}'. Defaulting tkdnd to win-x64.")
else:
    print(f"Unsupported OS type: {ostype}. Build might fail or be incomplete.")


# Run PyInstaller
print(f"Running PyInstaller with arguments: {common_args}")
try:
    PyInstaller.__main__.run(common_args)
    print("PyInstaller build completed successfully.")
except Exception as e_pyi:
    print(f"CRITICAL ERROR: PyInstaller build failed: {e_pyi}")
    sys.exit(1)

# --- Post-build steps: Copying data files ---
dist_path = os.path.join(local_base_path, 'dist', archive_name_prefix) # Path to the one-file output or dir
output_dir_for_files = os.path.join(local_base_path, 'dist') # Where bin, licenses etc. will be relative to the exe's final location

# If one-dir build, files go into 'dist/MIO-KITCHEN/'.
# If one-file build, PyInstaller puts collected data into a temp dir at runtime.
# For non-collected files (like your 'bin' folder), they need to be alongside the .exe.
# The script currently assumes one-file ('-F'), so 'dist/MIO-KITCHEN' will be the .exe.
# We'll create 'dist/bin' etc. next to 'dist/MIO-KITCHEN.exe'

final_bin_path = os.path.join(output_dir_for_files, 'bin') # e.g. dist/bin
if not os.path.exists(final_bin_path):
    os.makedirs(final_bin_path, exist_ok=True)

# List of files and folders to copy into 'dist/bin' or 'dist/'
# Paths are relative to 'local_base_path' (where build.py is)
files_to_copy_into_dist_bin = {
    "images": "images",
    "languages": "languages",
    "licenses_folder": "licenses", # Renamed to avoid conflict with LICENSE file
    "module": "module",
    "temp_folder_structure_only": "temp", # Usually temp is runtime, but if you need its structure
    "extra_flash": "extra_flash",
    "setting.ini": "setting.ini",
    # ostype folder: e.g., copy content of 'bin/Windows' to 'dist/bin/Windows'
    # This needs careful handling if 'ostype' variable contains the OS name.
    # shutil.copytree(os.path.join(local_base_path, "bin", ostype), os.path.join(final_bin_path, ostype), dirs_exist_ok=True)
    "kemiaojiang.png": "kemiaojiang.png",
    "License_kemiaojiang.txt": "License_kemiaojiang.txt",
    "tkdnd": "tkdnd", # This will be filtered later
    "help_document.json": "help_document.json",
    "exec.sh": "exec.sh"
}

# Copy platform-specific binaries based on 'ostype' from 'bin/<ostype>'
platform_bin_source = os.path.join(local_base_path, "bin", ostype)
platform_bin_dest = os.path.join(final_bin_path, ostype)
if os.path.isdir(platform_bin_source):
    print(f"Copying platform binaries from '{platform_bin_source}' to '{platform_bin_dest}'...")
    shutil.copytree(platform_bin_source, platform_bin_dest, dirs_exist_ok=True)
else:
    print(f"Warning: Platform-specific binary folder '{platform_bin_source}' not found.")


for item_name_in_script, item_disk_name in files_to_copy_into_dist_bin.items():
    source_path = os.path.join(local_base_path, "bin", item_disk_name)
    dest_path = os.path.join(final_bin_path, item_disk_name)
    
    if item_name_in_script == "temp_folder_structure_only": # Special case for temp
        if not os.path.exists(dest_path): os.makedirs(dest_path, exist_ok=True)
        print(f"Ensured 'temp' directory structure exists at: {dest_path}")
        continue

    if os.path.exists(source_path):
        try:
            if os.path.isdir(source_path):
                print(f"Copying directory: '{source_path}' to '{dest_path}'")
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
            else: # It's a file
                print(f"Copying file: '{source_path}' to '{dest_path}'")
                shutil.copy2(source_path, dest_path) # copy2 preserves metadata
        except Exception as e_copy:
            print(f"ERROR copying '{source_path}': {e_copy}")
    else:
        print(f"Warning: Source item '{source_path}' for copying not found.")

# Copy main LICENSE file to 'dist/'
license_file_source = os.path.join(local_base_path, 'LICENSE')
license_file_dest = os.path.join(output_dir_for_files, 'LICENSE')
if os.path.exists(license_file_source):
    try:
        print(f"Copying '{license_file_source}' to '{license_file_dest}'")
        shutil.copy2(license_file_source, license_file_dest)
    except Exception as e_copy_license:
        print(f"ERROR copying main LICENSE file: {e_copy_license}")
else:
    print(f"Warning: Main LICENSE file '{license_file_source}' not found.")


# Filter tkdnd versions
tkdnd_base_path_in_dist = os.path.join(final_bin_path, 'tkdnd')
if dndplat and os.path.isdir(tkdnd_base_path_in_dist):
    print(f"Filtering tkdnd libraries for platform: {dndplat}")
    for item in os.listdir(tkdnd_base_path_in_dist):
        item_path = os.path.join(tkdnd_base_path_in_dist, item)
        # Keep only the directory that matches dndplat
        if item != dndplat and os.path.isdir(item_path):
            print(f"Removing unused tkdnd folder: {item_path}")
            shutil.rmtree(item_path, ignore_errors=True)
elif not dndplat:
    print("CRITICAL WARNING: 'dndplat' not determined. TkinterDnD2 might not work correctly.")
    # Consider exiting if tkdnd is critical and platform couldn't be matched.
    # sys.exit(1)
else: # tkdnd_base_path_in_dist does not exist
    print(f"Warning: tkdnd base directory '{tkdnd_base_path_in_dist}' not found after copying. Drag and drop may not work.")


# POSIX-specific post-build steps (chmod)
if ostype == 'Linux' or ostype == 'Darwin': # More general POSIX check
    print("Setting execute permissions for files in dist (POSIX)...")
    # Target the actual executable and potentially scripts in bin
    executable_in_dist = os.path.join(output_dir_for_files, archive_name_prefix) # e.g., dist/MIO-KITCHEN
    if os.path.exists(executable_in_dist):
        try:
            os.chmod(executable_in_dist, 0o755) # rwxr-xr-x
            print(f"Set +x on {executable_in_dist}")
        except Exception as e_chmod_exe:
            print(f"Warning: Could not chmod main executable: {e_chmod_exe}")

    # If there are specific scripts in dist/bin that need +x
    scripts_in_bin_to_chmod = ["exec.sh"] # Add other scripts if needed
    for script_name in scripts_in_bin_to_chmod:
        script_path = os.path.join(final_bin_path, script_name)
        if os.path.exists(script_path):
            try:
                os.chmod(script_path, 0o755)
                print(f"Set +x on {script_path}")
            except Exception as e_chmod_script:
                print(f"Warning: Could not chmod script '{script_path}': {e_chmod_script}")
    # The original code chmod'd all files recursively, which is usually not necessary or desired.

# Create ZIP archive
# The zip file should be created in 'local_base_path', containing the 'dist' folder's content
# or containing the 'MIO-KITCHEN' executable and its accompanying 'bin', 'LICENSE' folders.
# Current zip_folder zips the content of 'dist' relative to 'dist'.

# If you want the zip to be MIO-KITCHEN-os.zip containing [MIO-KITCHEN.exe, bin/, LICENSE]:
# Change directory to 'dist' and zip its contents.
zip_output_path = os.path.join(local_base_path, name) # e.g. C:\path\to\project\MIO-KITCHEN-win.zip
content_to_zip_path = output_dir_for_files # This is 'dist'

# Change CWD for zipping if zip_folder expects to be run from the parent of what it zips
try:
    os.chdir(content_to_zip_path) # Go into 'dist'
    zip_folder(".", zip_output_path) # Zip contents of current dir (which is 'dist') into the target zip
except FileNotFoundError:
    print(f"ERROR: Could not change directory to '{content_to_zip_path}' for zipping.")
except Exception as e_chdir_zip:
    print(f"ERROR during zipping phase: {e_chdir_zip}")
finally:
    os.chdir(local_base_path) # Always change back to original directory

print(f"Build process finished. Archive created: {name}")
