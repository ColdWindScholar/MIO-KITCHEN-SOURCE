#!/usr/bin/env python3
# pylint: disable=line-too-long, broad-except
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
import sys
from pathlib import Path

# --- Шаг 1: Установка зависимостей ---
try:
    import pip
    if hasattr(pip, '_internal') and hasattr(pip._internal, 'cli') and hasattr(pip._internal.cli, 'main'):
        from pip._internal.cli.main import main as _pip_main
    else:
        import subprocess
        print("Using subprocess for pip commands.")
        def _pip_main_subprocess(args):
            try:
                result = subprocess.run([sys.executable, "-m", "pip"] + args, check=True, capture_output=True, text=True)
                # print(result.stdout) # Можно раскомментировать для отладки pip
                return 0
            except subprocess.CalledProcessError as e:
                print(f"Error running pip command: {' '.join(args)}\nStderr: {e.stderr}")
                return e.returncode
            except FileNotFoundError:
                print(f"Error: '{sys.executable} -m pip' not found.")
                return -1
        _pip_main = _pip_main_subprocess

    print("Checking and installing requirements...")
    requirements_file = Path('requirements.txt')
    if requirements_file.is_file():
        with open(requirements_file, 'r', encoding='utf-8') as req_file:
            for requirement in req_file:
                requirement = requirement.strip()
                if requirement and not requirement.startswith('#'):
                    print(f"Processing requirement: {requirement}")
                    ret_code = _pip_main(['install', '--upgrade', '--no-cache-dir', '--disable-pip-version-check', '--no-input', requirement])
                    if ret_code == 0:
                        print(f"Successfully processed {requirement}")
                    elif ret_code != 0 :
                        print(f"Warning: pip install for {requirement} returned code {ret_code}.")
    else:
        print(f"Warning: '{requirements_file}' not found. Skipping dependency installation.")
except ImportError:
    print("Warning: pip module could not be imported. Skipping dependency installation.")
except Exception as e:
    print(f"Error during dependency installation phase: {e}")

# --- Шаг 2: Импорт PyInstaller ---
try:
    import PyInstaller.__main__
except ImportError:
    print("FATAL ERROR: PyInstaller is not installed. Please install it: pip install pyinstaller")
    sys.exit(1)

# --- Шаг 3: Определение переменных ---
ostype = platform.system()
current_dir_path = Path.cwd()
spec_file_path = current_dir_path / 'tool.spec'
splash_file_path = current_dir_path / 'splash.png' # Сплэш-экран в корне

final_zip_archive_name = ""
if ostype == 'Linux':
    final_zip_archive_name = 'MIO-KITCHEN-linux.zip'
elif ostype == 'Darwin':
    final_zip_archive_name = 'MIO-KITCHEN-macos-intel.zip' if platform.machine() == 'x86_64' else 'MIO-KITCHEN-macos.zip'
else: # Windows
    final_zip_archive_name = 'MIO-KITCHEN-win.zip'

# Имя папки, куда PyInstaller временно соберет приложение (из COLLECT(name=...) в .spec)
pyinstaller_temp_output_folder_name = 'MIO-Kitchen-AppBase'
# Имя финальной папки, куда будет помещена вся сборка (tool.exe, bin/, LICENSE)
final_release_folder_name = f"MIO-KITCHEN-Release-{ostype}-{platform.machine()}" # Делаем имя уникальным

# --- Шаг 4: Функция для архивации ---
def zip_folder_contents(folder_to_zip_path_str, output_zip_file_path_str):
    source_path = Path(folder_to_zip_path_str).resolve()
    output_path = Path(output_zip_file_path_str).resolve()
    if not source_path.is_dir():
        print(f"Error: Source for zipping '{source_path}' is not a directory.")
        return
    print(f"Archiving contents of '{source_path}' into '{output_path}'...")
    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for item_path in source_path.rglob('*'):
                archive_item_path = item_path.relative_to(source_path)
                if item_path.is_file():
                    archive.write(item_path, archive_item_path)
                elif item_path.is_dir() and not any(item_path.iterdir()):
                    dir_info = zipfile.ZipInfo(str(archive_item_path) + '/')
                    archive.writestr(dir_info, '')
        print(f"Archive '{output_path}' created successfully!")
    except Exception as e_zip:
        print(f"Error during archiving '{output_path}': {e_zip}")


# --- Шаг 5: Сборка с помощью PyInstaller ---
print(f"Starting PyInstaller build for {ostype} ({platform.machine()})...")
if not spec_file_path.is_file():
    print(f"FATAL ERROR: PyInstaller .spec file not found at '{spec_file_path}'.")
    sys.exit(1)

pyinstaller_args = [
    str(spec_file_path),
    '--noconfirm',
    '--clean',
]

# УДАЛЕНО: Логика добавления --splash из командной строки,
# так как это конфликтует с использованием .spec файла.
# Сплэш-экран теперь должен быть настроен ВНУТРИ tool.spec, если он нужен.
# splash_arg = []
# if (ostype == 'Windows' or ostype == 'Linux') and splash_file_path.is_file():
#    pyinstaller_args.extend(['--splash', str(splash_file_path)])
# elif (ostype == 'Windows' or ostype == 'Linux'):
#    print(f"Warning: Splash file '{splash_file_path}' not found. Splash screen will not be used (if not defined in .spec).")
# final_pyinstaller_args = pyinstaller_base_args + splash_arg # pyinstaller_base_args переименован в pyinstaller_args

try:
    PyInstaller.__main__.run(pyinstaller_args)
    print("PyInstaller build completed.")
except Exception as e_pyinst:
    # Формируем безопасную для вывода строку ошибки
    error_message = str(e_pyinst)
    try:
        # Попытка декодировать, если это bytes (маловероятно для объекта исключения)
        if isinstance(error_message, bytes):
            error_message = error_message.decode(sys.stdout.encoding or 'utf-8', 'replace')
    except Exception:
        pass # Если декодирование не удалось, используем str(e_pyinst)

    # Вывод с обработкой ошибок кодировки
    try:
        print(f"FATAL ERROR: PyInstaller failed: {error_message}")
    except UnicodeEncodeError:
        safe_error_message = error_message.encode(sys.stdout.encoding or 'utf-8', 'replace').decode(sys.stdout.encoding or 'utf-8', 'replace')
        print(f"FATAL ERROR: PyInstaller failed (error message has unprintable characters): {safe_error_message}")
    sys.exit(1)

# --- Шаг 6: Пост-обработка и создание финальной структуры ---
print("Starting post-build processing...")

# Путь к временной папке, созданной PyInstaller (например, dist/MIO-Kitchen-AppBase)
pyinstaller_temp_dist_app_folder = current_dir_path / 'dist' / pyinstaller_temp_output_folder_name
if not pyinstaller_temp_dist_app_folder.is_dir():
    print(f"Error: PyInstaller output directory '{pyinstaller_temp_dist_app_folder}' not found.")
    sys.exit(1)

# Путь к финальной папке релиза (например, dist/MIO-KITCHEN-Release-Windows-AMD64)
final_release_target_path = current_dir_path / 'dist' / final_release_folder_name
if final_release_target_path.exists():
    print(f"Removing existing final release directory: {final_release_target_path}")
    shutil.rmtree(final_release_target_path)
# Перемещаем/переименовываем результат PyInstaller в финальную папку
print(f"Moving PyInstaller output from '{pyinstaller_temp_dist_app_folder}' to '{final_release_target_path}'")
shutil.move(str(pyinstaller_temp_dist_app_folder), str(final_release_target_path))


# 1. Копируем ВСЮ папку `bin` из исходников в `final_release_target_path/bin`
release_bin_path = final_release_target_path / 'bin'
project_source_bin_path = current_dir_path / 'bin'
if project_source_bin_path.is_dir():
    print(f"Copying project 'bin' directory '{project_source_bin_path}' to '{release_bin_path}'...")
    shutil.copytree(project_source_bin_path, release_bin_path, dirs_exist_ok=True)
else:
    print(f"CRITICAL WARNING: Source 'bin' directory not found at '{project_source_bin_path}'. It will be MISSING in the release!")

# 2. Копируем `LICENSE` в `final_release_target_path/LICENSE`
project_source_license_file = current_dir_path / 'LICENSE'
release_license_path = final_release_target_path / 'LICENSE'
if project_source_license_file.is_file():
    print(f"Copying '{project_source_license_file}' to '{release_license_path}'...")
    shutil.copy2(project_source_license_file, release_license_path)
else:
    print(f"Warning: LICENSE file not found at '{project_source_license_file}'.")

# 3. Фильтрация `tkdnd` в `final_release_target_path/bin/tkdnd`
tkdnd_in_release_bin = release_bin_path / 'tkdnd'
if tkdnd_in_release_bin.is_dir():
    dndplat_filter_key = None
    # ... (логика определения dndplat_filter_key как в предыдущем ответе) ...
    if ostype == 'Darwin':
        dndplat_filter_key = 'osx-x64' if platform.machine() == 'x86_64' else 'osx-arm64'
    elif ostype == 'Linux':
        dndplat_filter_key = 'linux-x64' if platform.machine() == 'x86_64' else 'linux-arm64'
    elif ostype == 'Windows':
        mach = platform.machine()
        arch_32 = platform.architecture()[0] == '32bit'
        if arch_32 and mach == 'AMD64': dndplat_filter_key = 'win-x86'
        elif mach == 'x86': dndplat_filter_key = 'win-x86'
        elif mach == 'AMD64': dndplat_filter_key = 'win-x64'
        elif mach == 'ARM64': dndplat_filter_key = 'win-arm64'

    if dndplat_filter_key:
        print(f"Filtering tkdnd versions in '{tkdnd_in_release_bin}' for platform: {dndplat_filter_key}")
        target_tkdnd_platform_path = tkdnd_in_release_bin / dndplat_filter_key
        if not target_tkdnd_platform_path.exists():
             print(f"  Warning: Target tkdnd platform folder '{dndplat_filter_key}' not found. TkDND might not work.")
        for item in tkdnd_in_release_bin.iterdir():
            if item.name == dndplat_filter_key:
                print(f"  Keeping tkdnd version: {item.name}")
                continue
            print(f"  Removing tkdnd version: {item.name}")
            if item.is_dir(): shutil.rmtree(item, ignore_errors=True)
            else: item.unlink(missing_ok=True)
    else:
        print(f"Warning: Could not determine tkdnd platform for filtering in '{tkdnd_in_release_bin}'. All versions kept.")
else:
    if project_source_bin_path.is_dir(): # Только если папка bin вообще была
         print(f"Warning: tkdnd directory not found at '{tkdnd_in_release_bin}'. Skipping tkdnd filtering.")

# 4. Выдача прав на исполняемый файл (tool.exe или tool)
executable_name_from_spec = 'tool' # Имя из EXE(name=...) в .spec
executable_path_in_release = final_release_target_path / executable_name_from_spec
if ostype == 'Windows':
    executable_path_in_release = final_release_target_path / (executable_name_from_spec + '.exe')

if (ostype == 'Linux' or ostype == 'Darwin'):
    if executable_path_in_release.is_file():
        print(f"Setting execute permissions for: {executable_path_in_release}")
        try: os.chmod(executable_path_in_release, 0o755)
        except Exception as e_chmod: print(f"  Warning: Failed to set execute permissions: {e_chmod}")
    else:
        print(f"Warning: Executable '{executable_path_in_release}' not found for setting permissions.")

# --- Шаг 7: Архивация финальной папки релиза ---
if final_release_target_path.is_dir():
    zip_output_file_path = current_dir_path / 'dist' / final_zip_archive_name
    zip_folder_contents(str(final_release_target_path), str(zip_output_file_path))
else:
    print(f"Error: Final release directory '{final_release_target_path}' not found. Archiving failed.")

print("Build script finished.")
