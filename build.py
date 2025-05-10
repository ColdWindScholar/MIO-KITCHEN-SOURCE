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
#!/usr/bin/env python3
# pylint: disable=line-too-long
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
# ... (лицензия) ...

import os
import platform # Import the whole module
import shutil
import zipfile
import sys # For sys.exit

# Determine the root directory of the project (where build.py is located)
project_root_dir = os.path.abspath(os.path.dirname(__file__))

# Install requirements
try:
    from pip._internal.cli.main import main as _pip_main
    print("Checking and installing requirements...")
    requirements_file_path = os.path.join(project_root_dir, 'requirements.txt')
    if os.path.exists(requirements_file_path):
        with open(requirements_file_path, 'r', encoding='utf-8') as req_file:
            for requirement_line in req_file:
                requirement = requirement_line.strip()
                if requirement and not requirement.startswith('#'):
                    print(f"Installing {requirement}...")
                    try:
                        _pip_main(['install', requirement])
                    except Exception as e_pip_install:
                        print(f"Warning: Failed to install {requirement}: {e_pip_install}")
    else:
        print(f"Warning: requirements.txt not found at {requirements_file_path}")
except ImportError:
    print("Warning: pip is not available. Please ensure all dependencies from requirements.txt are installed manually.")

current_os_type = platform.system()
app_name_base = "MIO-KITCHEN" # Base name for output files
output_zip_name = f"{app_name_base.lower()}.zip" # Default zip name
pyinstaller_app_name = "tool" # Name for the executable and output folder by PyInstaller

if current_os_type == 'Linux':
    output_zip_name = f'{app_name_base}-linux.zip'
elif current_os_type == 'Darwin':
    if platform.machine() == 'x86_64':
        output_zip_name = f'{app_name_base}-macos-intel.zip'
    else:
        output_zip_name = f'{app_name_base}-macos.zip'
    try:
        from tkinter import END # Simple check for tkinter availability
    except ImportError:
        print("CRITICAL: Tkinter is not available on this macOS system! The build may not work correctly.")
elif current_os_type == 'Windows':
    output_zip_name = f'{app_name_base}-win.zip'
else:
    print(f"Warning: Unsupported OS type: {current_os_type}. Using generic zip name.")
    output_zip_name = f'{app_name_base}-{current_os_type.lower()}.zip'


# --- PyInstaller Configuration ---
print(f"Starting PyInstaller build for {current_os_type}...")
import PyInstaller.__main__

pyinstaller_args = [
    os.path.join(project_root_dir, 'tool.py'), # Entry point script (PROJECT_ROOT/tool.py)
    '--name', pyinstaller_app_name,          # Output name for exe and one-dir folder
    '-D',                                    # Create a one-dir bundle
    '--console',                             # Keep console for debugging; use '-w' or '--noconsole' for release
    # '-w',                                  # For windowed (no console) release build
    '--icon', os.path.join(project_root_dir, 'icon.ico'),
    '--exclude-module', 'numpy',
    '--collect-data', 'sv_ttk',
    '--collect-data', 'chlorophyll',
    '--paths', os.path.join(project_root_dir, 'src'), # Add 'src' to module search path
]

# Data files and folders to include (from PROJECT_ROOT/bin and PROJECT_ROOT)
# Format: 'source_path_on_disk:destination_path_in_bundle'
# os.pathsep is ';' on Windows, ':' on POSIX
data_to_bundle = [
    (os.path.join(project_root_dir, 'bin'), 'bin'),                 # Entire 'bin' directory
    (os.path.join(project_root_dir, 'LICENSE'), '.'),               # LICENSE file to bundle root
    (os.path.join(project_root_dir, 'config'), '.'),                # 'config' file to bundle root
    # Add other root-level files if needed, e.g., READMEs, splash images not handled by --splash
    # (os.path.join(project_root_dir, 'README.md'), '.'),
]
for src_path, dest_in_bundle in data_to_bundle:
    if os.path.exists(src_path): # Check if source exists before adding
        pyinstaller_args.append(f'--add-data={src_path}{os.pathsep}{dest_in_bundle}')
    else:
        print(f"Warning: Data source path not found, skipping: {src_path}")


# Hidden imports that PyInstaller might miss
hidden_imports_list = [
    'tkinter', 'PIL', 'PIL._tkinter_finder', 
    'requests', 'idna', # Common ones for network
    # Add any other modules PyInstaller struggles to find
]
for hi in hidden_imports_list:
    pyinstaller_args.extend(['--hidden-import', hi])

# Splash screen
splash_file_path = os.path.join(project_root_dir, 'splash.png')
if os.path.exists(splash_file_path) and current_os_type != 'Darwin': # Splash for Darwin typically via Info.plist
    pyinstaller_args.extend(['--splash', splash_file_path])

# Run PyInstaller
print(f"Executing PyInstaller with arguments: {' '.join(pyinstaller_args)}")
try:
    PyInstaller.__main__.run(pyinstaller_args)
    print("PyInstaller build process finished.")
except Exception as e_pyinstaller_run:
    print(f"CRITICAL: PyInstaller execution failed: {e_pyinstaller_run}")
    sys.exit(1)

# --- Post-build Processing ---
dist_path = os.path.join(project_root_dir, 'dist')
app_bundle_path = os.path.join(dist_path, pyinstaller_app_name) # e.g., dist/tool

if not os.path.isdir(app_bundle_path):
    print(f"CRITICAL: PyInstaller output directory not found: {app_bundle_path}")
    sys.exit(1)

# Clean up unnecessary tkdnd library versions
tkdnd_path_in_bundle = os.path.join(app_bundle_path, 'bin', 'tkdnd')
dndplat_to_keep = None
current_machine_arch_for_dnd = platform.machine()

if current_os_type == 'Darwin':
    dndplat_to_keep = 'osx-arm64' if current_machine_arch_for_dnd == 'arm64' else 'osx-x64'
elif current_os_type == 'Linux':
    dndplat_to_keep = 'linux-arm64' if current_machine_arch_for_dnd == 'aarch64' else 'linux-x64'
elif current_os_type == 'Windows':
    win_py_arch, _ = platform.architecture()
    if win_py_arch == '32bit' and current_machine_arch_for_dnd == 'AMD64': # 32-bit Python on 64-bit OS
        dndplat_to_keep = 'win-x86'
    elif current_machine_arch_for_dnd == 'x86':
        dndplat_to_keep = 'win-x86'
    elif current_machine_arch_for_dnd == 'AMD64':
        dndplat_to_keep = 'win-x64'
    elif current_machine_arch_for_dnd == 'ARM64':
        dndplat_to_keep = 'win-arm64'

if dndplat_to_keep and os.path.isdir(tkdnd_path_in_bundle):
    print(f"Cleaning tkdnd libraries in bundle, keeping: {dndplat_to_keep}")
    for item_name in os.listdir(tkdnd_path_in_bundle):
        item_full_path = os.path.join(tkdnd_path_in_bundle, item_name)
        if os.path.isdir(item_full_path) and item_name != dndplat_to_keep:
            print(f"Removing: {item_full_path}")
            shutil.rmtree(item_full_path, ignore_errors=True)
elif not dndplat_to_keep:
    print(f"Warning: Could not determine specific tkdnd platform for {current_os_type}/{current_machine_arch_for_dnd}. All versions kept.")
else:
    print(f"Warning: TkDnD path not found in bundle: {tkdnd_path_in_bundle}. Skipping tkdnd cleanup.")

# Set executable permissions for POSIX systems (Linux/macOS)
if os.name == 'posix':
    print(f"Setting executable permissions for POSIX in: {app_bundle_path}")
    # Binaries that typically need execute permission
    executables_to_chmod = [pyinstaller_app_name] # The main app
    # Add other binaries from your 'bin' folder if they are directly executed
    # Example: os.path.join('bin', platform.system(), platform.machine(), 'my_tool')
    # For now, just the main app and .sh scripts.
    for root, _, files in os.walk(app_bundle_path):
        for file_item in files:
            if file_item in executables_to_chmod or file_item.endswith(".sh"):
                file_path_to_chmod = os.path.join(root, file_item)
                try:
                    print(f"  chmod +x {file_path_to_chmod}")
                    # Add execute permission for owner, group, and others (u+x, g+x, o+x)
                    current_mode = os.stat(file_path_to_chmod).st_mode
                    os.chmod(file_path_to_chmod, current_mode | 0o111) # stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                except Exception as e_chmod_err:
                    print(f"  Warning: Failed to chmod {file_path_to_chmod}: {e_chmod_err}")

# Create final ZIP archive
final_zip_file_path = os.path.join(project_root_dir, output_zip_name)
print(f"Creating final ZIP archive: {final_zip_file_path}")
os.chdir(dist_path) # Change to 'dist' directory to have 'app_name/' as root in ZIP
try:
    with zipfile.ZipFile(final_zip_file_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for root, dirnames, files in os.walk(pyinstaller_app_name): # Walk the 'app_name' folder (e.g., 'tool')
            # Exclude .git if it somehow ends up here
            if ".git" in dirnames:
                dirnames.remove(".git")
            for file_item in files:
                file_path_in_dist = os.path.join(root, file_item)
                # arcname will be like 'tool/tool.exe', 'tool/bin/setting.ini', etc.
                print(f"  Adding to ZIP: {file_path_in_dist}")
                archive.write(file_path_in_dist, file_path_in_dist)
    print(f"Successfully created {final_zip_file_path}")
except Exception as e_final_zip:
    print(f"Error creating final ZIP archive: {e_final_zip}")
finally:
    os.chdir(project_root_dir) # Important: change back to the original directory

print("Build script finished.")
