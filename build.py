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
    # Используем pip как модуль, если он доступен
    import pip
    # Проверка версии pip, некоторые старые версии могут не иметь pip._internal.cli.main
    if hasattr(pip, '_internal') and hasattr(pip._internal, 'cli') and hasattr(pip._internal.cli, 'main'):
        from pip._internal.cli.main import main as _pip_main
    else: # Попытка использовать subprocess, если прямой импорт недоступен или pip старый
        import subprocess
        print("Using subprocess for pip commands as direct import is unavailable.")
        def _pip_main_subprocess(args):
            try:
                # sys.executable - это путь к текущему интерпретатору Python
                result = subprocess.run([sys.executable, "-m", "pip"] + args, check=True, capture_output=True, text=True)
                print(result.stdout)
                return 0 # Успех
            except subprocess.CalledProcessError as e:
                print(f"Error running pip command: {' '.join(args)}")
                print(f"Stdout: {e.stdout}")
                print(f"Stderr: {e.stderr}")
                return e.returncode # Код ошибки от pip
            except FileNotFoundError:
                print(f"Error: '{sys.executable} -m pip' command not found. Is pip installed and in PATH for this Python environment?")
                return -1 # Обозначаем ошибку, которую не смог обработать pip
        _pip_main = _pip_main_subprocess

    print("Checking and installing requirements...")
    requirements_file = Path('requirements.txt')
    if requirements_file.is_file():
        with open(requirements_file, 'r', encoding='utf-8') as req_file:
            for requirement in req_file:
                requirement = requirement.strip()
                if requirement and not requirement.startswith('#'):
                    print(f"Processing requirement: {requirement}")
                    # '--disable-pip-version-check' чтобы убрать лишние предупреждения
                    # '--no-input' чтобы не запрашивать ввод
                    ret_code = _pip_main(['install', '--upgrade', '--no-cache-dir', '--disable-pip-version-check', '--no-input', requirement])
                    if ret_code == 0:
                        print(f"Successfully processed {requirement}")
                    # pip._internal.cli.main может возвращать не только 0 в случае успеха (например, если пакет уже последней версии)
                    # Поэтому мы не проверяем строго на 0, а смотрим на ошибки в логе, если ret_code не 0.
                    elif ret_code != 0: # Обрабатываем только явные коды ошибок, отличные от 0
                        print(f"Warning: pip install for {requirement} returned code {ret_code}.")
    else:
        print(f"Warning: '{requirements_file}' not found. Skipping dependency installation.")

except ImportError:
    print("Warning: pip module could not be imported. Skipping automatic dependency installation. Please ensure all dependencies are installed manually.")
except Exception as e:
    print(f"Error during dependency installation phase: {e}")

# --- Шаг 2: Импорт PyInstaller (ПОСЛЕ установки зависимостей) ---
try:
    import PyInstaller.__main__
except ImportError:
    print("FATAL ERROR: PyInstaller is not installed or cannot be imported. Please install it: pip install pyinstaller")
    sys.exit(1)

# --- Шаг 3: Определение переменных для сборки ---
ostype = platform.system()
current_dir_path = Path.cwd()
spec_file_path = current_dir_path / 'tool.spec' # Предполагаем, что tool.spec в корне

# Имя ZIP-архива, который будет создан в конце
final_zip_archive_name = ""
if ostype == 'Linux':
    final_zip_archive_name = 'MIO-KITCHEN-linux.zip'
elif ostype == 'Darwin':
    if platform.machine() == 'x86_64':
        final_zip_archive_name = 'MIO-KITCHEN-macos-intel.zip'
    else:
        final_zip_archive_name = 'MIO-KITCHEN-macos.zip'
else: # Windows
    final_zip_archive_name = 'MIO-KITCHEN-win.zip'

# Имя папки, создаваемой PyInstaller (из COLLECT(name=...) в .spec)
# Должно совпадать с app_collection_name в tool.spec
pyinstaller_output_base_folder_name = 'MIO-Kitchen-AppBase'

# Имя финальной папки релиза, куда все будет скопировано перед архивацией
# Вы можете сделать это имя динамическим, например, с версией
final_release_build_folder_name = "MIO-KITCHEN-Build" # Папка, в которую будет помещена структура для архивации

# --- Шаг 4: Функция для архивации ---
def zip_folder_contents(folder_to_zip_path_str, output_zip_file_path_str):
    source_path = Path(folder_to_zip_path_str).resolve()
    output_path = Path(output_zip_file_path_str).resolve()

    if not source_path.is_dir():
        print(f"Error: Source for zipping '{source_path}' is not a directory or does not exist.")
        return

    print(f"Archiving contents of '{source_path}' into '{output_path}'...")
    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for item_path in source_path.rglob('*'): # rglob для рекурсивного обхода
                if item_path.is_file():
                    archive_item_path = item_path.relative_to(source_path)
                    # print(f"Adding file: {archive_item_path}") # Раскомментировать для отладки
                    archive.write(item_path, archive_item_path)
                elif item_path.is_dir():
                    # Проверяем, действительно ли папка пуста (без скрытых файлов тоже)
                    if not any(item_path.iterdir()):
                        archive_item_path = item_path.relative_to(source_path)
                        # print(f"Adding empty directory: {archive_item_path}/") # Раскомментировать для отладки
                        # Добавляем / в конце для явного указания, что это папка
                        dir_info = zipfile.ZipInfo(str(archive_item_path) + '/')
                        archive.writestr(dir_info, '')
        print(f"Archive '{output_path}' created successfully!")
    except Exception as e_zip:
        print(f"Error during archiving: {e_zip}")

# --- Шаг 5: Сборка с помощью PyInstaller ---
print(f"Starting PyInstaller build for {ostype} ({platform.machine()})...")
if not spec_file_path.is_file():
    print(f"FATAL ERROR: PyInstaller .spec file not found at '{spec_file_path}'. Cannot build.")
    sys.exit(1)

pyinstaller_args = [
    str(spec_file_path),
    '--noconfirm',      # Не запрашивать подтверждения при перезаписи
    '--clean',          # Очищать кэш PyInstaller и временные файлы перед сборкой
    # '--distpath', str(current_dir_path / 'dist_temp'), # Можно указать временную папку для вывода PyInstaller
    # '--workpath', str(current_dir_path / 'build_temp'), # Временная папка для файлов сборки
]

# Добавление сплэш-экрана, если он есть и не указан в .spec
splash_png_path = current_dir_path / 'splash.png'
if (ostype == 'Windows' or ostype == 'Linux') and splash_png_path.is_file():
    # Убедитесь, что splash не дублируется, если он уже есть в .spec
    # Если сплэш определен в .spec, эта опция здесь не нужна.
    pyinstaller_args.extend(['--splash', str(splash_png_path)])
else:
    if ostype == 'Windows' or ostype == 'Linux':
         print("Warning: splash.png not found, splash screen will not be used (if not defined in .spec).")

try:
    PyInstaller.__main__.run(pyinstaller_args)
    print("PyInstaller build completed.")
except Exception as e_pyinst:
    print(f"FATAL ERROR: PyInstaller failed: {e_pyinst}")
    sys.exit(1)

# --- Шаг 6: Пост-обработка и создание финальной структуры ---
print("Starting post-build processing...")

# Путь к папке, созданной PyInstaller (например, dist/MIO-Kitchen-AppBase)
pyinstaller_output_app_folder_path = current_dir_path / 'dist' / pyinstaller_output_base_folder_name

if not pyinstaller_output_app_folder_path.is_dir():
    print(f"Error: PyInstaller output directory '{pyinstaller_output_app_folder_path}' not found. Post-processing cannot continue.")
    sys.exit(1)

# Путь к финальной папке релиза (например, dist/MIO-KITCHEN-Build)
final_release_dir_path = current_dir_path / 'dist' / final_release_build_folder_name

# Очищаем/создаем финальную папку релиза
if final_release_dir_path.exists():
    print(f"Removing existing final release directory: {final_release_dir_path}")
    shutil.rmtree(final_release_dir_path)
print(f"Creating final release directory: {final_release_dir_path}")
final_release_dir_path.mkdir(parents=True, exist_ok=True)

# 1. Копируем содержимое папки, созданной PyInstaller, в финальную папку релиза
# Это создаст структуру, где tool.exe и его зависимости лежат прямо в final_release_dir_path
print(f"Copying application files from '{pyinstaller_output_app_folder_path}' to '{final_release_dir_path}'...")
for item in pyinstaller_output_app_folder_path.iterdir():
    if item.is_dir():
        shutil.copytree(item, final_release_dir_path / item.name, dirs_exist_ok=True)
    else:
        shutil.copy2(item, final_release_dir_path / item.name)

# 2. Копируем папку `bin` из исходников в `final_release_dir_path/bin`
target_bin_path_in_release = final_release_dir_path / 'bin'
source_bin_path = current_dir_path / 'bin'
if source_bin_path.is_dir():
    print(f"Copying source 'bin' directory '{source_bin_path}' to '{target_bin_path_in_release}'...")
    shutil.copytree(source_bin_path, target_bin_path_in_release, dirs_exist_ok=True)
else:
    print(f"Warning: Source 'bin' directory not found at '{source_bin_path}'. It will be missing in the release.")

# 3. Копируем `LICENSE` в `final_release_dir_path/LICENSE`
source_license_file = current_dir_path / 'LICENSE'
target_license_in_release = final_release_dir_path / 'LICENSE'
if source_license_file.is_file():
    print(f"Copying '{source_license_file}' to '{target_license_in_release}'...")
    shutil.copy2(source_license_file, target_license_in_release)
else:
    print(f"Warning: LICENSE file not found at '{source_license_file}'. It will be missing in the release.")

# 4. Фильтрация `tkdnd` в `final_release_dir_path/bin/tkdnd`
tkdnd_path_in_release_bin = target_bin_path_in_release / 'tkdnd'
if tkdnd_path_in_release_bin.is_dir():
    dndplat_filter_key = None
    if ostype == 'Darwin':
        dndplat_filter_key = 'osx-x64' if platform.machine() == 'x86_64' else 'osx-arm64'
    elif ostype == 'Linux':
        dndplat_filter_key = 'linux-x64' if platform.machine() == 'x86_64' else 'linux-arm64'
    elif ostype == 'Windows':
        mach = platform.machine()
        arch_32 = platform.architecture()[0] == '32bit'
        if arch_32 and mach == 'AMD64': dndplat_filter_key = 'win-x86' # WoW64
        elif mach == 'x86': dndplat_filter_key = 'win-x86'
        elif mach == 'AMD64': dndplat_filter_key = 'win-x64'
        elif mach == 'ARM64': dndplat_filter_key = 'win-arm64'

    if dndplat_filter_key:
        print(f"Filtering tkdnd versions in '{tkdnd_path_in_release_bin}' for platform: {dndplat_filter_key}")
        if not (tkdnd_path_in_release_bin / dndplat_filter_key).exists():
            print(f"  Warning: Target tkdnd platform '{dndplat_filter_key}' not found. TkDND might not work correctly.")
        
        for item in tkdnd_path_in_release_bin.iterdir():
            if item.name == dndplat_filter_key:
                print(f"  Keeping tkdnd version: {item.name}")
                continue
            # Ваша оригинальная логика фильтрации была сложнее. Это упрощенный вариант: удалить все, что не dndplat_filter_key.
            # Если у вас была особая логика (например, не удалять x64, если целевая x86), ее нужно восстановить здесь.
            # Пример:
            # if item.name.startswith(dndplat_filter_key[:3]): # e.g., 'win'
            #     if item.name.endswith("x64") and dndplat_filter_key.endswith("x86"):
            #         print(f"  Skipping removal of {item.name} due to x86 target compatibility.")
            #         continue
            print(f"  Removing tkdnd version: {item.name}")
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else: # Файл (маловероятно для tkdnd)
                item.unlink(missing_ok=True)
    else:
        print(f"Warning: Could not determine specific tkdnd platform for filtering in '{tkdnd_path_in_release_bin}'. All versions kept.")
else:
    print(f"Warning: tkdnd directory not found at '{tkdnd_path_in_release_bin}'. Skipping tkdnd filtering.")

# 5. Выдача прав на исполняемый файл для Linux/macOS
# Имя исполняемого файла из .spec -> EXE(name=...)
executable_filename_in_spec = 'tool' # Должно совпадать с EXE(name=...) в .spec
executable_path_in_release = final_release_dir_path / executable_filename_in_spec
if ostype == 'Windows': # Для Windows добавляем .exe
    executable_path_in_release = final_release_dir_path / (executable_filename_in_spec + '.exe')


if (ostype == 'Linux' or ostype == 'Darwin'):
    if executable_path_in_release.is_file():
        print(f"Setting execute permissions for: {executable_path_in_release}")
        try:
            os.chmod(executable_path_in_release, 0o755) # rwxr-xr-x
        except Exception as e_chmod:
            print(f"  Warning: Failed to set execute permissions: {e_chmod}")
    else:
        print(f"Warning: Executable not found at '{executable_path_in_release}' for setting permissions.")

# --- Шаг 7: Архивация финальной папки релиза ---
if final_release_dir_path.is_dir():
    # Архив будет создан в папке 'dist/' (рядом с папкой релиза)
    zip_output_file = current_dir_path / 'dist' / final_zip_archive_name
    zip_folder_contents(str(final_release_dir_path), str(zip_output_file))
else:
    print(f"Error: Final release directory '{final_release_dir_path}' not found. Archiving failed.")

print("Build script finished.")
